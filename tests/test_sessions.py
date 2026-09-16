"""Attendance session (class session) creation/lifecycle tests."""

import pytest


def test_create_session_defaults(test_db):
    session_id = test_db.create_session(
        class_name="10-A Physics", section="10-A",
        lecture_duration_min=50, num_snapshots=5, min_observations=3, mode="demo",
    )
    session = test_db.get_session(session_id)
    assert session["class_name"] == "10-A Physics"
    assert session["num_snapshots"] == 5
    assert session["min_observations"] == 3
    assert session["status"] == "running"
    assert session["mode"] == "demo"


def test_end_session_marks_completed(test_db):
    session_id = test_db.create_session("10-A Physics", "10-A", 50, 5, 3, "demo")
    test_db.end_session(session_id)
    session = test_db.get_session(session_id)
    assert session["status"] == "completed"
    assert session["ended_at"] is not None


def test_get_all_sessions_orders_most_recent_first(test_db):
    id1 = test_db.create_session("Class A", "10-A", 50, 5, 3, "demo")
    id2 = test_db.create_session("Class B", "10-B", 50, 5, 3, "real")
    sessions = test_db.get_all_sessions()
    assert sessions[0]["session_id"] == id2
    assert sessions[1]["session_id"] == id1


def test_get_session_for_missing_id_returns_none(test_db):
    assert test_db.get_session(9999) is None


def test_create_session_rejects_min_observations_below_2(test_db):
    """min_observations=1 would collapse the temporal-presence rule into
    ordinary single-frame recognition, so it's rejected outright."""
    with pytest.raises(ValueError):
        test_db.create_session("10-A Physics", "10-A", 50, 5, 1, "demo")


def test_create_session_rejects_min_observations_above_num_snapshots(test_db):
    with pytest.raises(ValueError):
        test_db.create_session("10-A Physics", "10-A", 50, 3, 5, "demo")
