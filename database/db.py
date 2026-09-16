"""
AttendAI - SQLite data access layer.

Tables
------
students     : enrolled students + serialized face embedding/template
sessions     : one row per "class session" (a started lecture)
observations : one row per (student, snapshot_number) recognition event
attendance   : one row per (student, session) final rollup (denormalized
               for fast dashboard reads; can always be recomputed from
               observations, see attendance/engine.py)

Design notes
------------
- We never delete raw enrollment photos after the embedding is computed
  (see ai/embeddings.py) unless the caller asks to keep them for
  debugging; by default we discard raw images once the face template is
  built, per the privacy requirement of not storing unnecessary raw
  biometric imagery.
- All writes go through helper functions here so the rest of the app
  never writes raw SQL. Every function opens+closes its own short-lived
  connection (simple + safe for a Streamlit app which reruns often).
"""

import sqlite3
import json
import time
from contextlib import contextmanager

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    student_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    section         TEXT NOT NULL,
    embedding       BLOB,              -- serialized face template (json/npy bytes)
    embedding_meta  TEXT,              -- json: method used, num samples, etc.
    created_at      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    class_name          TEXT NOT NULL,
    section             TEXT,
    lecture_duration_min INTEGER NOT NULL,
    num_snapshots       INTEGER NOT NULL,
    min_observations    INTEGER NOT NULL,
    mode                TEXT NOT NULL,      -- 'real' or 'demo'
    status              TEXT NOT NULL,      -- 'running' | 'completed'
    started_at          REAL NOT NULL,
    ended_at            REAL
);

CREATE TABLE IF NOT EXISTS observations (
    observation_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       INTEGER NOT NULL,
    snapshot_number  INTEGER NOT NULL,
    student_id       TEXT,               -- NULL if face detected but unmatched
    recognized       INTEGER NOT NULL,   -- 1 if matched to an enrolled student
    match_score      REAL,               -- similarity score, NOT a probability
    is_unknown       INTEGER NOT NULL DEFAULT 0,
    timestamp        REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS attendance (
    session_id         INTEGER NOT NULL,
    student_id         TEXT NOT NULL,
    observation_count  INTEGER NOT NULL,
    total_snapshots    INTEGER NOT NULL,
    coverage_pct       REAL NOT NULL,
    status             TEXT NOT NULL,     -- PRESENT | NEEDS REVIEW | UNKNOWN/NOT ENROLLED
    manual_override    TEXT,              -- teacher-set status, if resolved manually
    resolved_by        TEXT,              -- who resolved it (free text for hackathon)
    resolved_at        REAL,
    PRIMARY KEY (session_id, student_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables if they do not already exist. Safe to call repeatedly."""
    with get_conn() as conn:
        conn.executescript(SCHEMA)


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------

def add_or_update_student(student_id, name, section, embedding_bytes, embedding_meta: dict):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO students (student_id, name, section, embedding, embedding_meta, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                name=excluded.name,
                section=excluded.section,
                embedding=excluded.embedding,
                embedding_meta=excluded.embedding_meta
            """,
            (student_id, name, section, embedding_bytes, json.dumps(embedding_meta), time.time()),
        )


def get_all_students():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM students ORDER BY section, name").fetchall()
        return [dict(r) for r in rows]


def get_students_by_section(section):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM students WHERE section = ? ORDER BY name", (section,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_student(student_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        return dict(row) if row else None


def delete_student(student_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM students WHERE student_id = ?", (student_id,))


def list_sections():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT section FROM students ORDER BY section"
        ).fetchall()
        return [r["section"] for r in rows]


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def create_session(class_name, section, lecture_duration_min, num_snapshots, min_observations, mode):
    if min_observations < 2:
        # A minimum of 1 observation is just single-frame recognition --
        # it defeats the whole "repeated temporal evidence" premise of
        # this system, so it's rejected here as well as in the UI.
        raise ValueError(
            "min_observations must be >= 2 (a minimum of 1 reduces the temporal "
            "presence rule to single-frame recognition)."
        )
    if num_snapshots < min_observations:
        raise ValueError("num_snapshots must be >= min_observations.")
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO sessions (class_name, section, lecture_duration_min, num_snapshots,
                                   min_observations, mode, status, started_at)
            VALUES (?, ?, ?, ?, ?, ?, 'running', ?)
            """,
            (class_name, section, lecture_duration_min, num_snapshots, min_observations, mode, time.time()),
        )
        return cur.lastrowid


def end_session(session_id):
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET status = 'completed', ended_at = ? WHERE session_id = ?",
            (time.time(), session_id),
        )


def get_session(session_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None


def get_all_sessions():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY started_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Observations
# ---------------------------------------------------------------------------

def record_observation(session_id, snapshot_number, student_id, recognized, match_score, is_unknown):
    """
    Idempotent-ish: if an observation already exists for this
    (session, snapshot, student) it is replaced, so re-running a snapshot
    step in the UI (e.g. Streamlit rerun) doesn't create duplicates.
    """
    with get_conn() as conn:
        if student_id is not None:
            existing = conn.execute(
                """SELECT observation_id FROM observations
                   WHERE session_id=? AND snapshot_number=? AND student_id=?""",
                (session_id, snapshot_number, student_id),
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE observations SET recognized=?, match_score=?, is_unknown=?, timestamp=?
                       WHERE observation_id=?""",
                    (int(recognized), match_score, int(is_unknown), time.time(), existing["observation_id"]),
                )
                return existing["observation_id"]
        cur = conn.execute(
            """
            INSERT INTO observations (session_id, snapshot_number, student_id, recognized,
                                       match_score, is_unknown, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, snapshot_number, student_id, int(recognized), match_score, int(is_unknown), time.time()),
        )
        return cur.lastrowid


def get_observations_for_session(session_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM observations WHERE session_id = ? ORDER BY snapshot_number",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_unknown_observations(session_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM observations WHERE session_id = ? AND is_unknown = 1 ORDER BY snapshot_number",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Attendance (final rollup)
# ---------------------------------------------------------------------------

def upsert_attendance(session_id, student_id, observation_count, total_snapshots, coverage_pct, status):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO attendance (session_id, student_id, observation_count, total_snapshots,
                                     coverage_pct, status)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, student_id) DO UPDATE SET
                observation_count=excluded.observation_count,
                total_snapshots=excluded.total_snapshots,
                coverage_pct=excluded.coverage_pct,
                status=excluded.status
            """,
            (session_id, student_id, observation_count, total_snapshots, coverage_pct, status),
        )


def set_manual_override(session_id, student_id, new_status, resolved_by="teacher"):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE attendance
            SET manual_override = ?, resolved_by = ?, resolved_at = ?
            WHERE session_id = ? AND student_id = ?
            """,
            (new_status, resolved_by, time.time(), session_id, student_id),
        )


def get_attendance_for_session(session_id):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT a.*, s.name, s.section
            FROM attendance a
            JOIN students s ON s.student_id = a.student_id
            WHERE a.session_id = ?
            ORDER BY s.name
            """,
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_effective_status(row: dict) -> str:
    """Manual override always wins if the teacher has resolved a review case."""
    return row["manual_override"] if row.get("manual_override") else row["status"]
