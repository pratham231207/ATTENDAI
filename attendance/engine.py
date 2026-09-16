"""
attendance/engine.py — orchestrates one full class session.

This is the glue between the AI pipeline (ai/) and the pure rule logic
(attendance/rules.py): it processes one snapshot frame at a time,
records observations, and — once all snapshots are done — computes the
final PRESENT / NEEDS REVIEW rollup for every enrolled student in the
class's section (including students who were never observed at all,
which is exactly the case the temporal-presence rule exists to catch).
"""

from dataclasses import dataclass, field
from typing import List, Optional

from ai.detector import detect_faces, draw_detections
from ai.embeddings import compute_embedding
from ai.recognizer import match_embedding
from attendance.rules import compute_status, compute_coverage_pct, STATUS_NEEDS_REVIEW
from database import db
from config import DEFAULT_RECOGNITION_THRESHOLD, MIN_FACE_SIZE_PX


@dataclass
class FaceResult:
    box: tuple
    student_id: Optional[str]
    name: Optional[str]
    match_score: float
    is_unknown: bool


@dataclass
class SnapshotResult:
    snapshot_number: int
    faces: List[FaceResult] = field(default_factory=list)
    annotated_frame: Optional[object] = None
    no_face_detected: bool = False


def process_snapshot(
    session_id: int,
    snapshot_number: int,
    frame_bgr,
    enrolled_students: list,
    threshold: float = DEFAULT_RECOGNITION_THRESHOLD,
    min_face_size_px: int = MIN_FACE_SIZE_PX,
) -> SnapshotResult:
    """
    Run detection + recognition on one frame and persist observations.

    Never raises just because a face wasn't recognized or no face was
    found — those are expected, normal outcomes (see spec section 15:
    error handling). Only truly unexpected failures (e.g. a corrupt
    frame) should propagate.

    `min_face_size_px`: smallest face (in pixels, per side) the detector
    will accept. The config default assumes a fairly close/tight webcam
    framing; a wider shot of a full classroom needs this turned down (at
    the cost of more false-positive detections on noise/textures), which
    is why this is exposed as a live, per-session control rather than a
    fixed constant (see views/class_session.py).
    """
    result = SnapshotResult(snapshot_number=snapshot_number)

    faces = detect_faces(frame_bgr, min_size_px=min_face_size_px)
    if not faces:
        result.no_face_detected = True
        result.annotated_frame = frame_bgr
        return result

    annotations = []
    seen_student_ids = set()

    for face in faces:
        embedding = compute_embedding(face.gray_crop)
        match = match_embedding(embedding, enrolled_students, threshold=threshold)

        # Two *different* detected faces in the same frame both best-matching
        # the same enrolled student is a recognizer collision, not a genuine
        # duplicate — it means at least one of them is misidentified. We
        # used to silently drop the second face, which made a possibly-real,
        # possibly-present student vanish from this snapshot with no trace.
        # Instead, treat this face as unresolved/ambiguous: still recorded
        # and still visible in the annotated frame, just not credited to
        # anyone's count, so a teacher reviewing the snapshot can see it
        # happened rather than the system quietly hiding a face.
        is_collision = not match.is_unknown and match.student_id in seen_student_ids
        if is_collision:
            face_result = FaceResult(
                box=face.box, student_id=None, name=None,
                match_score=match.match_score, is_unknown=True,
            )
        else:
            face_result = FaceResult(
                box=face.box,
                student_id=match.student_id,
                name=match.name,
                match_score=match.match_score,
                is_unknown=match.is_unknown,
            )
        result.faces.append(face_result)

        db.record_observation(
            session_id=session_id,
            snapshot_number=snapshot_number,
            student_id=face_result.student_id,     # None for unknown/ambiguous faces
            recognized=not face_result.is_unknown,
            match_score=face_result.match_score,
            is_unknown=face_result.is_unknown,
        )
        if not is_collision and not match.is_unknown:
            seen_student_ids.add(match.student_id)

        if is_collision:
            label = f"AMBIGUOUS - also matched {match.name} ({match.match_score:.2f})"
            color = (0, 0, 255)  # red (BGR) - distinct from unknown's orange
        elif not match.is_unknown:
            label = f"{match.name} ({match.match_score:.2f})"
            color = (0, 200, 0)  # green
        else:
            label = f"UNKNOWN ({match.match_score:.2f})"
            color = (0, 140, 255)  # orange
        annotations.append({"box": face.box, "label": label, "color": color})

    result.annotated_frame = draw_detections(frame_bgr, annotations)
    return result


def finalize_session(session_id: int):
    """
    Compute the final PRESENT / NEEDS REVIEW rollup for every enrolled
    student in this session's section — including students with ZERO
    observations, since "never observed" is precisely the signal the
    temporal rule is designed to flag for review, not to silently drop.
    """
    session = db.get_session(session_id)
    if session is None:
        raise ValueError(f"No such session: {session_id}")

    roster = db.get_students_by_section(session["section"]) if session["section"] else db.get_all_students()
    observations = db.get_observations_for_session(session_id)

    # distinct snapshot numbers a student was recognized in (guards against
    # any accidental duplicate rows for the same snapshot)
    obs_by_student = {}
    for o in observations:
        if o["student_id"] and o["recognized"]:
            obs_by_student.setdefault(o["student_id"], set()).add(o["snapshot_number"])

    total_snapshots = session["num_snapshots"]
    min_required = session["min_observations"]

    for student in roster:
        sid = student["student_id"]
        observation_count = len(obs_by_student.get(sid, set()))
        status = compute_status(observation_count, min_required)
        coverage = compute_coverage_pct(observation_count, total_snapshots)
        db.upsert_attendance(
            session_id=session_id,
            student_id=sid,
            observation_count=observation_count,
            total_snapshots=total_snapshots,
            coverage_pct=coverage,
            status=status,
        )

    db.end_session(session_id)
    return db.get_attendance_for_session(session_id)


def get_unknown_face_count(session_id: int) -> int:
    """Number of distinct snapshot appearances of a face that matched no enrolled student."""
    unknown_obs = db.get_unknown_observations(session_id)
    return len({o["snapshot_number"] for o in unknown_obs})
