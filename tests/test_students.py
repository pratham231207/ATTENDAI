"""Student enrollment / CRUD tests."""

import numpy as np

from ai.embeddings import serialize_vector


def _fake_embedding():
    return serialize_vector(np.random.rand(640).astype(np.float32))


def test_add_and_get_student(test_db):
    test_db.add_or_update_student(
        "S001", "Rahul Sharma", "10-A", _fake_embedding(), {"method": "test"}
    )
    student = test_db.get_student("S001")
    assert student is not None
    assert student["name"] == "Rahul Sharma"
    assert student["section"] == "10-A"


def test_add_or_update_is_idempotent_on_conflict(test_db):
    test_db.add_or_update_student("S001", "Rahul", "10-A", _fake_embedding(), {})
    test_db.add_or_update_student("S001", "Rahul Sharma Updated", "10-A", _fake_embedding(), {})
    students = test_db.get_all_students()
    assert len(students) == 1
    assert students[0]["name"] == "Rahul Sharma Updated"


def test_get_students_by_section(test_db):
    test_db.add_or_update_student("S001", "Rahul", "10-A", _fake_embedding(), {})
    test_db.add_or_update_student("S002", "Priya", "10-A", _fake_embedding(), {})
    test_db.add_or_update_student("S003", "Aman", "10-B", _fake_embedding(), {})

    section_a = test_db.get_students_by_section("10-A")
    assert {s["student_id"] for s in section_a} == {"S001", "S002"}
    assert test_db.list_sections() == ["10-A", "10-B"]


def test_delete_student(test_db):
    test_db.add_or_update_student("S001", "Rahul", "10-A", _fake_embedding(), {})
    test_db.delete_student("S001")
    assert test_db.get_student("S001") is None
    assert test_db.get_all_students() == []


def test_get_unknown_student_returns_none(test_db):
    """An unenrolled / never-created student ID must never raise — just return None."""
    assert test_db.get_student("NOT_A_REAL_ID") is None
