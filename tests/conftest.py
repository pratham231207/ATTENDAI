"""
tests/conftest.py — shared fixtures.

Every test gets its own throwaway SQLite file so tests never touch the
real data/attendai.db and never interfere with each other.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from database import db


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_attendai.db")
    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()
    return db
