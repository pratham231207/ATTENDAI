"""Tests for attendance/export.py — the CSV export format from spec section 11."""

import csv
import io

from attendance import engine
from attendance.export import attendance_rows_to_csv_dicts, to_csv_bytes


def _enroll(db, student_id, name, section="10-A"):
    db.add_or_update_student(student_id, name, section, b"", {"method": "fake"})


def test_csv_export_matches_spec_columns(test_db):
    _enroll(test_db, "S001", "Rahul Sharma")
    session_id = test_db.create_session("10-A Physics", "10-A", 50, 5, 3, "demo")
    for snap in [1, 2, 3, 4]:
        test_db.record_observation(session_id, snap, "S001", True, 0.9, False)
    rows = engine.finalize_session(session_id)

    csv_dicts = attendance_rows_to_csv_dicts(rows, class_name="10-A Physics")
    assert csv_dicts[0]["Student ID"] == "S001"
    assert csv_dicts[0]["Name"] == "Rahul Sharma"
    assert csv_dicts[0]["Class"] == "10-A Physics"
    assert csv_dicts[0]["Observed"] == 4
    assert csv_dicts[0]["Total Snapshots"] == 5
    assert csv_dicts[0]["Coverage"] == "80%"
    assert csv_dicts[0]["Status"] == "PRESENT"

    csv_bytes = to_csv_bytes(csv_dicts)
    text = csv_bytes.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames
    assert header == ["Student ID", "Name", "Class", "Observed", "Total Snapshots", "Coverage", "Status"]

    parsed_rows = list(reader)
    assert len(parsed_rows) == 1
    assert parsed_rows[0]["Student ID"] == "S001"


def test_csv_export_reflects_manual_override(test_db):
    _enroll(test_db, "S001", "Rahul")
    session_id = test_db.create_session("10-A Physics", "10-A", 50, 5, 3, "demo")
    test_db.record_observation(session_id, 1, "S001", True, 0.9, False)  # only 1/5 -> NEEDS REVIEW
    engine.finalize_session(session_id)
    test_db.set_manual_override(session_id, "S001", "PRESENT")

    rows = test_db.get_attendance_for_session(session_id)
    csv_dicts = attendance_rows_to_csv_dicts(rows)
    assert csv_dicts[0]["Status"] == "PRESENT"


def test_csv_export_empty_rows_returns_empty_bytes(test_db):
    assert to_csv_bytes([]) == b""


def test_csv_export_multiple_students_multiple_rows(test_db):
    _enroll(test_db, "S001", "Rahul")
    _enroll(test_db, "S002", "Priya")
    session_id = test_db.create_session("10-A Physics", "10-A", 50, 5, 3, "demo")
    for snap in [1, 2, 3, 4, 5]:
        test_db.record_observation(session_id, snap, "S001", True, 0.9, False)
    # Priya never observed.
    rows = engine.finalize_session(session_id)
    csv_dicts = attendance_rows_to_csv_dicts(rows)
    csv_bytes = to_csv_bytes(csv_dicts)
    reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8")))
    parsed = {r["Student ID"]: r for r in reader}
    assert parsed["S001"]["Status"] == "PRESENT"
    assert parsed["S002"]["Status"] == "NEEDS REVIEW"
    assert parsed["S002"]["Observed"] == "0"
