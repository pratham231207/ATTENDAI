"""
Tests for attendance/engine.py's finalize_session().

These bypass ai/ and camera/ entirely by writing observations directly
via database.db, so the temporal-presence engine itself is verified
independently of face recognition (spec section 16).
"""

from attendance import engine
from attendance.rules import STATUS_PRESENT, STATUS_NEEDS_REVIEW


def _enroll(db, student_id, name, section="10-A"):
    db.add_or_update_student(student_id, name, section, b"", {"method": "fake"})


def test_finalize_session_3_of_5_present(test_db):
    _enroll(test_db, "S001", "Rahul")
    session_id = test_db.create_session("10-A Physics", "10-A", 50, 5, 3, "demo")
    for snap in [1, 2, 3]:
        test_db.record_observation(session_id, snap, "S001", True, 0.9, False)

    rows = engine.finalize_session(session_id)
    row = next(r for r in rows if r["student_id"] == "S001")
    assert row["observation_count"] == 3
    assert row["status"] == STATUS_PRESENT
    assert row["coverage_pct"] == 60.0


def test_finalize_session_never_observed_student_is_needs_review_not_dropped(test_db):
    """
    A student enrolled in the class but never detected in any snapshot
    must still appear in the final rollup with 0 observations and
    NEEDS REVIEW - never silently absent from the report and never
    auto-labeled ABSENT.
    """
    _enroll(test_db, "S001", "Rahul")
    _enroll(test_db, "S002", "Priya")
    session_id = test_db.create_session("10-A Physics", "10-A", 50, 5, 3, "demo")
    for snap in [1, 2, 3, 4]:
        test_db.record_observation(session_id, snap, "S001", True, 0.9, False)

    rows = engine.finalize_session(session_id)
    priya = next(r for r in rows if r["student_id"] == "S002")
    assert priya["observation_count"] == 0
    assert priya["status"] == STATUS_NEEDS_REVIEW
    assert priya["status"] != "ABSENT"


def test_finalize_session_marks_session_completed(test_db):
    _enroll(test_db, "S001", "Rahul")
    session_id = test_db.create_session("10-A Physics", "10-A", 50, 5, 3, "demo")
    test_db.record_observation(session_id, 1, "S001", True, 0.9, False)
    engine.finalize_session(session_id)
    assert test_db.get_session(session_id)["status"] == "completed"


def test_unknown_face_never_counts_toward_any_enrolled_student(test_db):
    """An unmatched/unknown face detection must not inflate any real student's count."""
    _enroll(test_db, "S001", "Rahul")
    session_id = test_db.create_session("10-A Physics", "10-A", 50, 5, 3, "demo")
    test_db.record_observation(session_id, 1, "S001", True, 0.9, False)
    test_db.record_observation(session_id, 2, None, False, 0.2, True)

    rows = engine.finalize_session(session_id)
    rahul = next(r for r in rows if r["student_id"] == "S001")
    assert rahul["observation_count"] == 1
    assert engine.get_unknown_face_count(session_id) == 1


def test_manual_override_takes_precedence_over_computed_status(test_db):
    _enroll(test_db, "S001", "Rahul")
    session_id = test_db.create_session("10-A Physics", "10-A", 50, 5, 3, "demo")
    test_db.record_observation(session_id, 1, "S001", True, 0.9, False)
    engine.finalize_session(session_id)

    test_db.set_manual_override(session_id, "S001", STATUS_PRESENT, resolved_by="teacher_test")

    rows = test_db.get_attendance_for_session(session_id)
    row = next(r for r in rows if r["student_id"] == "S001")
    assert row["status"] == STATUS_NEEDS_REVIEW
    assert test_db.get_effective_status(row) == STATUS_PRESENT


def test_finalize_session_roster_scoped_to_section(test_db):
    """Students from a different section must not appear in this session's rollup."""
    _enroll(test_db, "S001", "Rahul", section="10-A")
    _enroll(test_db, "S999", "Other Section Student", section="10-B")
    session_id = test_db.create_session("10-A Physics", "10-A", 50, 5, 3, "demo")
    test_db.record_observation(session_id, 1, "S001", True, 0.9, False)

    rows = engine.finalize_session(session_id)
    student_ids = {r["student_id"] for r in rows}
    assert student_ids == {"S001"}
