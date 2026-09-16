"""
Observation recording tests — including the duplicate-observation and
unknown-face edge cases called out in the spec.
"""


def _make_session(test_db):
    return test_db.create_session("10-A Physics", "10-A", 50, 5, 3, "demo")


def test_record_observation_basic(test_db):
    session_id = _make_session(test_db)
    test_db.record_observation(session_id, 1, "S001", recognized=True, match_score=0.9, is_unknown=False)
    obs = test_db.get_observations_for_session(session_id)
    assert len(obs) == 1
    assert obs[0]["student_id"] == "S001"
    assert obs[0]["recognized"] == 1
    assert obs[0]["match_score"] == 0.9


def test_duplicate_observation_same_snapshot_and_student_does_not_duplicate(test_db):
    """
    Recording the same (session, snapshot, student) twice — e.g. because
    Streamlit re-ran the script — must update in place, not create two rows.
    """
    session_id = _make_session(test_db)
    test_db.record_observation(session_id, 1, "S001", recognized=True, match_score=0.7, is_unknown=False)
    test_db.record_observation(session_id, 1, "S001", recognized=True, match_score=0.95, is_unknown=False)

    obs = test_db.get_observations_for_session(session_id)
    matching = [o for o in obs if o["snapshot_number"] == 1 and o["student_id"] == "S001"]
    assert len(matching) == 1, "duplicate observation for the same snapshot+student was not deduplicated"
    assert matching[0]["match_score"] == 0.95, "the later (updated) match_score should win"


def test_unknown_face_observation_has_null_student_id(test_db):
    """An unrecognized face must be recorded (for the unknown-face count) without being
    attributed to any specific student."""
    session_id = _make_session(test_db)
    test_db.record_observation(session_id, 1, None, recognized=False, match_score=0.2, is_unknown=True)

    obs = test_db.get_observations_for_session(session_id)
    assert len(obs) == 1
    assert obs[0]["student_id"] is None
    assert obs[0]["is_unknown"] == 1

    unknown_obs = test_db.get_unknown_observations(session_id)
    assert len(unknown_obs) == 1


def test_multiple_unknown_faces_in_different_snapshots_all_recorded(test_db):
    """Unlike student observations, unknown faces are never deduplicated by
    identity (there is no identity) — each snapshot's unknown appearance is
    tracked independently."""
    session_id = _make_session(test_db)
    for snap in [1, 2, 3]:
        test_db.record_observation(session_id, snap, None, recognized=False, match_score=0.1, is_unknown=True)
    assert len(test_db.get_unknown_observations(session_id)) == 3


def test_observations_across_multiple_snapshots_for_same_student(test_db):
    session_id = _make_session(test_db)
    for snap in [1, 2, 4, 5]:
        test_db.record_observation(session_id, snap, "S001", recognized=True, match_score=0.9, is_unknown=False)
    obs = [o for o in test_db.get_observations_for_session(session_id) if o["student_id"] == "S001"]
    assert len(obs) == 4
    assert {o["snapshot_number"] for o in obs} == {1, 2, 4, 5}
