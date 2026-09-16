"""
AttendAI — main Streamlit entry point.

Run with:
    streamlit run app.py
"""

import streamlit as st

from config import APP_TITLE
from database import db
import ui

st.set_page_config(page_title="AttendAI", page_icon="🎓", layout="wide")
ui.inject_css()

db.init_db()

PAGES = {
    "Dashboard": "dashboard",
    "Start Class": "class_session",
    "Student Enrollment": "enrollment",
    "Student Timeline": "timeline",
    "Attendance History": "history",
}


def render_privacy_footer():
    with st.sidebar.expander("Privacy & Responsible AI", expanded=False):
        st.markdown(
            """
            - This is a **hackathon prototype**, not a certified attendance system.
            - Facial data requires appropriate **authorization/consent**; only
              consenting participants should be enrolled.
            - Access to biometric templates should be **restricted**.
            - **"Not observed" does not mean "absent."** A student may be out of
              camera view, occluded, or turned away.
            - Uncertain matches are routed to **teacher review**, not auto-decided.
            - Face processing runs **locally** on this machine — no images are
              uploaded to an external service.
            - A production deployment would need formal privacy, retention and
              consent-withdrawal policies. This system makes **no claim of 100%
              accuracy**.
            """
        )


def main():
    st.sidebar.markdown(
        """
        <div style="padding: 0.4rem 0 1rem 0; border-bottom: 1px solid rgba(239,232,214,0.18); margin-bottom: 0.75rem;">
            <div style="font-family:'Source Serif 4',serif; font-size:1.5rem; font-weight:700; line-height:1.1;">AttendAI</div>
            <div style="font-size:0.8rem; opacity:0.75; margin-top:2px;">Attendance through repeated temporal observation</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    choice = st.sidebar.radio("Navigate", options=list(PAGES.keys()), label_visibility="collapsed")
    render_privacy_footer()

    st.sidebar.divider()
    st.sidebar.caption("Hackathon MVP · Phase 1 skeleton")

    page_module = PAGES[choice]
    if page_module == "dashboard":
        from views import dashboard
        dashboard.render()
    elif page_module == "class_session":
        from views import class_session
        class_session.render()
    elif page_module == "enrollment":
        from views import enrollment
        enrollment.render()
    elif page_module == "timeline":
        from views import timeline
        timeline.render()
    elif page_module == "history":
        from views import history
        history.render()


if __name__ == "__main__":
    main()
