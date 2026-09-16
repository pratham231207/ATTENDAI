"""
views/timeline.py — Student Timeline.

Shows exactly which snapshots a student was observed in for a given
session, and lets the teacher manually resolve a NEEDS REVIEW case.
"""

import streamlit as st

from database import db
from attendance.rules import STATUS_PRESENT, STATUS_NEEDS_REVIEW
import ui


def render():
    st.header("Student Timeline")

    sessions = db.get_all_sessions()
    if not sessions:
        st.info("No sessions yet. Start a class first.")
        return

    session_labels = {
        s["session_id"]: f"#{s['session_id']} — {s['class_name']} ({s['section'] or 'no section'}), {s['status']}"
        for s in sessions
    }
    session_id = st.selectbox(
        "Session", options=list(session_labels.keys()), format_func=lambda sid: session_labels[sid]
    )
    session = db.get_session(session_id)

    attendance_rows = db.get_attendance_for_session(session_id)
    if not attendance_rows:
        st.warning("No attendance has been recorded for this session yet.")
        return

    student_labels = {r["student_id"]: f"{r['name']} ({r['student_id']})" for r in attendance_rows}
    student_id = st.selectbox(
        "Student", options=list(student_labels.keys()), format_func=lambda sid: student_labels[sid]
    )

    row = next(r for r in attendance_rows if r["student_id"] == student_id)
    observations = db.get_observations_for_session(session_id)
    observed_snapshots = {
        o["snapshot_number"] for o in observations
        if o["student_id"] == student_id and o["recognized"]
    }
    # also collect the best match_score seen per snapshot, for context
    score_by_snapshot = {
        o["snapshot_number"]: o["match_score"]
        for o in observations
        if o["student_id"] == student_id and o["recognized"]
    }

    st.subheader(f"{row['name']} — {row['student_id']}")

    total = row["total_snapshots"]
    ui.snapshot_chip_row(total, observed_snapshots, score_by_snapshot)

    effective_status = db.get_effective_status(row)

    c1, c2, c3 = st.columns(3)
    c1.metric("Observed", f"{row['observation_count']}/{total}")
    c2.metric("Coverage", f"{row['coverage_pct']:.0f}%")
    with c3:
        st.caption("Status")
        ui.badge(effective_status)

    st.caption(
        "A dash means **not observed** in that snapshot — it does not mean the student "
        "was confirmed absent. They may have been out of camera view, occluded, or "
        "turned away. Coverage reflects how much of the lecture the camera confirmed "
        "presence for, not continuous physical presence."
    )

    if row.get("manual_override"):
        st.info(
            f"Manually resolved to **{row['manual_override']}** by {row.get('resolved_by', 'teacher')}."
        )

    if effective_status == STATUS_NEEDS_REVIEW or row.get("manual_override"):
        st.divider()
        st.subheader("Teacher Review")
        st.caption(
            "Use your own judgement (e.g. checking a seating chart or asking the class) "
            "to resolve this case."
        )
        new_status = st.radio(
            "Resolve as",
            options=[STATUS_PRESENT, STATUS_NEEDS_REVIEW],
            index=0 if effective_status == STATUS_PRESENT else 1,
            horizontal=True,
            key=f"resolve_{session_id}_{student_id}",
        )
        if st.button("Save resolution", key=f"save_{session_id}_{student_id}"):
            db.set_manual_override(session_id, student_id, new_status)
            st.success(f"Marked {row['name']} as {new_status} (manual override).")
            st.rerun()
