"""Attendance history page - browse past sessions."""

import streamlit as st
import pandas as pd

from database import db
from attendance import engine
from attendance.export import attendance_rows_to_csv_dicts, to_csv_bytes
import ui


def render():
    st.header("Attendance History")

    sessions = db.get_all_sessions()
    if not sessions:
        st.info("No sessions recorded yet.")
        return

    df = pd.DataFrame(
        [
            {
                "Session": s["session_id"],
                "Class": s["class_name"],
                "Section": s["section"],
                "Mode": s["mode"].upper(),
                "Status": s["status"],
                "Snapshots": s["num_snapshots"],
                "Min Required": s["min_observations"],
            }
            for s in sessions
        ]
    )
    st.dataframe(df, width='stretch', hide_index=True)

    st.divider()
    session_id = st.selectbox(
        "View details for session",
        options=[s["session_id"] for s in sessions],
    )
    session = db.get_session(session_id)
    if session and session["status"] == "running":
        st.warning(
            "This session is still marked **running**. If the page was closed, the "
            "connection dropped, or the browser tab was refreshed while a REAL MODE "
            "lecture was in progress, it can be left stuck like this indefinitely — "
            "the snapshots taken so far are already saved, but no final PRESENT / "
            "NEEDS REVIEW rollup has been computed yet."
        )
        if st.button("Finalize this session now, using snapshots recorded so far"):
            engine.finalize_session(session_id)
            st.success("Session finalized.")
            st.rerun()

    rows = db.get_attendance_for_session(session_id)
    if not rows:
        st.caption("No attendance rows recorded for this session yet.")
        return

    detail_df = pd.DataFrame(
        [
            {
                "Student ID": r["student_id"],
                "Name": r["name"],
                "Observations": f"{r['observation_count']}/{r['total_snapshots']}",
                "Coverage": f"{r['coverage_pct']:.0f}%",
                "Status": db.get_effective_status(r),
            }
            for r in rows
        ]
    )
    st.dataframe(ui.style_status_column(detail_df), width='stretch', hide_index=True)

    csv_rows = attendance_rows_to_csv_dicts(rows, class_name=session["class_name"] if session else "")
    csv_bytes = to_csv_bytes(csv_rows)
    st.download_button(
        "Export CSV",
        data=csv_bytes,
        file_name=f"attendance_session_{session_id}.csv",
        mime="text/csv",
    )
