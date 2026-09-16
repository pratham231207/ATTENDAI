"""Dashboard page - overview of the most recent / selected class session."""

import streamlit as st
import pandas as pd
import plotly.express as px

from database import db
from attendance.engine import get_unknown_face_count
from attendance.export import attendance_rows_to_csv_dicts, to_csv_bytes
import ui


def render():
    st.header("Dashboard")

    sessions = db.get_all_sessions()
    if not sessions:
        st.info(
            "No class sessions yet. Go to **Start Class** to configure a class "
            "and begin a session, or **Student Enrollment** to add students first."
        )
        return

    session_labels = {
        s["session_id"]: f"#{s['session_id']} — {s['class_name']} ({s['section'] or 'no section'}), "
                          f"{s['mode']} mode, {s['status']}"
        for s in sessions
    }
    selected_id = st.selectbox(
        "Session",
        options=list(session_labels.keys()),
        format_func=lambda sid: session_labels[sid],
    )

    session = db.get_session(selected_id)
    attendance_rows = db.get_attendance_for_session(selected_id)

    total = len(attendance_rows)
    present = sum(1 for r in attendance_rows if db.get_effective_status(r) == "PRESENT")
    review = sum(1 for r in attendance_rows if db.get_effective_status(r) == "NEEDS REVIEW")
    unknown = get_unknown_face_count(selected_id)

    ui.stat_strip(
        [
            ("Class", session["class_name"]),
            ("Total students", total),
            ("Present", present),
            ("Needs review", review),
            ("Unknown faces", unknown),
        ]
    )

    st.caption(
        f"Status: **{session['status']}**  ·  Mode: **{session['mode']}**  ·  "
        f"{session['num_snapshots']} snapshots, min {session['min_observations']} required "
        f"to be marked present."
    )

    if not attendance_rows:
        st.warning("This session has no recorded observations yet.")
        return

    chart_col, table_col = st.columns([1, 2])
    with chart_col:
        chart_df = pd.DataFrame(
            {"Status": ["Present", "Needs Review"], "Count": [present, review]}
        )
        chart_df = chart_df[chart_df["Count"] > 0]
        if not chart_df.empty:
            fig = px.pie(
                chart_df, names="Status", values="Count", hole=0.5,
                color="Status",
                color_discrete_map={"Present": ui.PRESENT, "Needs Review": ui.REVIEW},
            )
            fig.update_layout(
                margin=dict(t=10, b=10, l=10, r=10), height=260,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color=ui.INK),
            )
            st.plotly_chart(fig, width='stretch')

    with table_col:
        df = pd.DataFrame(
            [
                {
                    "Student ID": r["student_id"],
                    "Name": r["name"],
                    "Observations": f"{r['observation_count']}/{r['total_snapshots']}",
                    "Coverage": f"{r['coverage_pct']:.0f}%",
                    "Status": db.get_effective_status(r),
                }
                for r in attendance_rows
            ]
        )
        st.dataframe(ui.style_status_column(df), width='stretch', hide_index=True)

    csv_rows = attendance_rows_to_csv_dicts(attendance_rows, class_name=session["class_name"])
    csv_bytes = to_csv_bytes(csv_rows)
    st.download_button(
        "Export CSV",
        data=csv_bytes,
        file_name=f"attendance_session_{selected_id}.csv",
        mime="text/csv",
    )

    review_rows = [r for r in attendance_rows if db.get_effective_status(r) == "NEEDS REVIEW"]
    if review_rows:
        with st.expander(f"Resolve {len(review_rows)} NEEDS REVIEW case(s)"):
            for r in review_rows:
                c1, c2, c3 = st.columns([3, 2, 2])
                c1.write(f"**{r['name']}** ({r['student_id']}) — {r['observation_count']}/{r['total_snapshots']} observed")
                choice = c2.selectbox(
                    "Resolve as",
                    options=["PRESENT", "NEEDS REVIEW"],
                    index=1,
                    key=f"dash_resolve_{selected_id}_{r['student_id']}",
                    label_visibility="collapsed",
                )
                if c3.button("Save", key=f"dash_save_{selected_id}_{r['student_id']}"):
                    db.set_manual_override(selected_id, r["student_id"], choice)
                    st.rerun()
            st.caption(
                "For the full snapshot-by-snapshot breakdown before deciding, use the "
                "Student Timeline page."
            )
