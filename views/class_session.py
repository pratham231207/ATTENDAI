"""
Start Class / Live Session page.

Configures a class session, then runs the snapshot schedule (REAL or
DEMO mode) against either the laptop webcam or an uploaded pre-recorded
video, using the same attendance engine either way (see
attendance/engine.py and attendance/scheduler.py).
"""

import os
import tempfile
import time

import cv2
import pandas as pd
import streamlit as st

from database import db
from attendance import engine
from attendance.scheduler import compute_snapshot_offsets_sec, compute_snapshot_fractions
from camera.webcam import WebcamSource, CameraError, is_webcam_available
from camera.video import VideoFileSource
import ui
from config import (
    DEFAULT_LECTURE_DURATION_MIN,
    DEFAULT_NUM_SNAPSHOTS,
    DEFAULT_MIN_OBSERVATIONS,
    DEFAULT_RECOGNITION_THRESHOLD,
    MIN_FACE_SIZE_PX,
)


def _reset_session_state():
    for key in ("pending_session", "active_session_id", "video_temp_path"):
        st.session_state.pop(key, None)


def _render_config_form():
    sections = db.list_sections()
    if not sections:
        st.warning("No students enrolled yet. Enroll students first so a class has someone to track.")

    webcam_ok = is_webcam_available()

    with st.form("start_class_form"):
        class_name = st.text_input("Class Name *", placeholder="e.g. 10-A Physics")
        section = st.selectbox("Section", options=sections) if sections else st.text_input("Section")

        col1, col2, col3 = st.columns(3)
        duration = col1.number_input(
            "Lecture duration (min)", min_value=5, max_value=180,
            value=DEFAULT_LECTURE_DURATION_MIN,
        )
        snapshots = col2.number_input(
            "Number of snapshots", min_value=2, max_value=20,
            value=DEFAULT_NUM_SNAPSHOTS,
        )
        min_obs = col3.number_input(
            "Minimum observations required", min_value=2, max_value=20,
            value=DEFAULT_MIN_OBSERVATIONS,
            help=(
                "Kept at 2+ on purpose: requiring only 1 observation would collapse "
                "this back into ordinary single-frame face recognition and defeat the "
                "point of temporal, repeated-evidence attendance."
            ),
        )

        mode = st.radio(
            "Mode",
            options=["demo", "real"],
            format_func=lambda m: (
                "DEMO MODE (compressed ~1-2 min, for judges)" if m == "demo"
                else "REAL MODE (actual lecture timing)"
            ),
            horizontal=True,
        )

        source = st.radio(
            "Camera source",
            options=["webcam", "video"],
            format_func=lambda s: (
                ("Laptop webcam" + ("" if webcam_ok else " (not detected)"))
                if s == "webcam" else "Pre-recorded classroom video"
            ),
            horizontal=True,
            index=0 if webcam_ok else 1,
        )
        video_file = None
        if source == "video":
            video_file = st.file_uploader("Upload classroom video", type=["mp4", "avi", "mov", "mkv"])

        threshold = st.slider(
            "Recognition threshold (match score)", min_value=0.1, max_value=0.9,
            value=DEFAULT_RECOGNITION_THRESHOLD, step=0.05,
            help="Higher = stricter matching (fewer false positives, more UNKNOWNs).",
        )

        min_face_size = st.slider(
            "Minimum face size to detect (px)", min_value=20, max_value=150,
            value=MIN_FACE_SIZE_PX, step=5,
            help=(
                "Faces smaller than this (in pixels) are ignored as likely noise. "
                "The default assumes a fairly close/tight camera framing. If your "
                "camera is capturing a wider shot of the room (more students, "
                "further away, smaller faces on screen), turn this DOWN so back-row "
                "students are still detected — at the cost of more false-positive "
                "detections on textures/shadows. If it's a tight close-up shot, you "
                "can leave it as-is or raise it."
            ),
        )

        started = st.form_submit_button("Start Class", type="primary")

    if not started:
        return

    if not class_name:
        st.error("Class name is required.")
        return
    if min_obs > snapshots:
        st.error("Minimum observations required cannot exceed the number of snapshots.")
        return
    if source == "video" and video_file is None:
        st.error("Please upload a classroom video, or switch source to webcam.")
        return
    if source == "webcam" and not webcam_ok:
        st.error(
            "No webcam was detected on this machine. Switch source to "
            "'Pre-recorded classroom video' instead."
        )
        return

    roster = db.get_students_by_section(section) if section else db.get_all_students()
    if not roster:
        st.error("No enrolled students found for this section. Enroll students first.")
        return

    video_temp_path = None
    if video_file is not None:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(video_file.name)[1])
        tmp.write(video_file.getvalue())
        tmp.close()
        video_temp_path = tmp.name

    session_id = db.create_session(
        class_name=class_name,
        section=section,
        lecture_duration_min=int(duration),
        num_snapshots=int(snapshots),
        min_observations=int(min_obs),
        mode=mode,
    )
    st.session_state["active_session_id"] = session_id
    st.session_state["pending_session"] = {
        "source": source,
        "video_temp_path": video_temp_path,
        "threshold": threshold,
        "min_face_size": min_face_size,
        "roster": roster,
    }
    st.rerun()


def _live_status_table(session_id, roster):
    observations = db.get_observations_for_session(session_id)
    counts = {}
    for o in observations:
        if o["student_id"] and o["recognized"]:
            counts.setdefault(o["student_id"], set()).add(o["snapshot_number"])

    rows = []
    for s in roster:
        n = len(counts.get(s["student_id"], set()))
        rows.append({"Student ID": s["student_id"], "Name": s["name"], "Observed so far": n})
    return pd.DataFrame(rows)


def _run_capture(session_id, session):
    pending = st.session_state["pending_session"]
    roster = pending["roster"]
    threshold = pending["threshold"]
    min_face_size = pending.get("min_face_size", MIN_FACE_SIZE_PX)
    num_snapshots = session["num_snapshots"]
    mode = session["mode"]
    duration_min = session["lecture_duration_min"]

    # Seed with the session_id so this session's REAL-mode wait timing and
    # its video-fraction mapping agree with each other, but every session
    # gets its own unpredictable schedule (see attendance/scheduler.py).
    offsets = compute_snapshot_offsets_sec(duration_min, num_snapshots, mode, seed=session_id)
    fractions = compute_snapshot_fractions(num_snapshots, seed=session_id)

    st.info(
        f"Running {mode.upper()} mode — {num_snapshots} snapshots over "
        f"{'~' + str(round(offsets[-1])) + 's (compressed)' if mode == 'demo' else str(duration_min) + ' min'}. "
        "Please keep this tab open."
    )

    progress = st.progress(0.0)
    status_placeholder = st.empty()
    frame_placeholder = st.empty()
    table_placeholder = st.empty()

    source_kind = pending["source"]
    cam = None
    video_src = None
    aborted = False

    try:
        if source_kind == "webcam":
            cam = WebcamSource(0).open()
        else:
            video_src = VideoFileSource(pending["video_temp_path"]).open()
    except CameraError as e:
        st.error(f"Could not start capture: {e}")
        aborted = True

    if not aborted:
        prev_offset = 0.0
        for i in range(num_snapshots):
            snap_num = i + 1
            wait_for = max(0.0, offsets[i] - prev_offset)
            status_placeholder.write(
                f"Waiting {wait_for:.1f}s for **Snapshot {snap_num}/{num_snapshots}**..."
            )
            time.sleep(wait_for)
            prev_offset = offsets[i]

            try:
                if source_kind == "webcam":
                    frame = cam.read_frame()
                else:
                    frame = video_src.read_frame_at_fraction(fractions[i])
            except CameraError as e:
                st.error(f"Snapshot {snap_num} failed: {e}. Stopping capture early.")
                aborted = True
                break

            try:
                result = engine.process_snapshot(
                    session_id, snap_num, frame, roster,
                    threshold=threshold, min_face_size_px=min_face_size,
                )
            except Exception as e:  # noqa: BLE001 - never let one bad frame kill the whole session
                st.error(f"Recognition failed on snapshot {snap_num}: {e}. Continuing.")
                result = None

            progress.progress(snap_num / num_snapshots)

            if result is not None:
                shown_frame = cv2.cvtColor(result.annotated_frame, cv2.COLOR_BGR2RGB)
                if result.no_face_detected:
                    status_placeholder.warning(
                        f"Snapshot {snap_num}/{num_snapshots}: no face detected in frame "
                        "(not the same as 'absent' — could be occlusion or camera angle)."
                    )
                else:
                    known = sum(1 for f in result.faces if not f.is_unknown)
                    unknown = sum(1 for f in result.faces if f.is_unknown)
                    status_placeholder.success(
                        f"Snapshot {snap_num}/{num_snapshots}: {known} recognized, {unknown} unknown face(s)."
                    )
                frame_placeholder.image(shown_frame, caption=f"Snapshot {snap_num}", width='stretch')

            table_placeholder.dataframe(
                _live_status_table(session_id, roster), width='stretch', hide_index=True
            )

    if cam is not None:
        cam.release()
    if video_src is not None:
        video_src.release()
    if pending.get("video_temp_path") and os.path.exists(pending["video_temp_path"]):
        try:
            os.remove(pending["video_temp_path"])
        except OSError:
            pass

    st.divider()
    if aborted:
        st.warning("Capture ended early. Finalizing attendance with whatever snapshots were recorded.")
    else:
        st.success("All snapshots processed.")

    attendance_rows = engine.finalize_session(session_id)
    unknown_count = engine.get_unknown_face_count(session_id)

    st.subheader("Final Attendance")
    df = pd.DataFrame(
        [
            {
                "Student ID": r["student_id"],
                "Name": r["name"],
                "Observed": f"{r['observation_count']}/{r['total_snapshots']}",
                "Coverage": f"{r['coverage_pct']:.0f}%",
                "Status": db.get_effective_status(r),
            }
            for r in attendance_rows
        ]
    )
    st.dataframe(ui.style_status_column(df), width='stretch', hide_index=True)
    if unknown_count:
        st.caption(
            f"{unknown_count} snapshot(s) also contained a face that did not match any "
            "enrolled student in this section (shown as UNKNOWN, not linked to any student)."
        )
    st.caption("Full session details are available on the Dashboard and Attendance History pages.")

    _reset_session_state()


def render():
    st.header("Start Class")

    active_id = st.session_state.get("active_session_id")
    if active_id and "pending_session" in st.session_state:
        session = db.get_session(active_id)
        if session and session["status"] == "running":
            st.subheader(f"Session #{active_id} — {session['class_name']} ({session['section'] or 'no section'})")
            _run_capture(active_id, session)
            return

    _render_config_form()
