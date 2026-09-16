"""
ui.py — AttendAI's shared visual identity.

Design direction: a classroom roll-book / attendance ledger, not another
generic AI dashboard. Warm paper tones and a serif for headings (the
"printed roster" feel) paired with a clean sans for data-heavy tables and
labels; a chalkboard-green sidebar reads as the ledger's cover, the cream
main area as its pages. Status colors (present / needs review / unknown)
are used consistently everywhere a status appears — dashboard, history,
timeline, live capture — so a teacher learns the color language once.

Everything here is pure presentation. No attendance logic lives in this
file, and nothing here is imported by attendance/ or ai/.
"""

import pandas as pd
import streamlit as st

# --- Palette -----------------------------------------------------------
INK = "#20291F"          # primary text
PAPER = "#FAF6EC"        # main background
PAPER_ALT = "#F1EAD9"    # stripes / secondary surfaces
RULE = "#DDD2B5"         # hairline dividers
COVER = "#21362B"        # sidebar "cover" background
COVER_TEXT = "#EFE8D6"   # text on the cover
COVER_MUTED = "#AEC2AF"  # muted text on the cover

PRESENT = "#3F6B4A"
PRESENT_BG = "#E3EEE0"
REVIEW = "#B07A1E"
REVIEW_BG = "#F6E9CE"
UNKNOWN = "#9C4230"
UNKNOWN_BG = "#F4E1D9"

STATUS_COLORS = {
    "PRESENT": (PRESENT, PRESENT_BG),
    "NEEDS REVIEW": (REVIEW, REVIEW_BG),
    "UNKNOWN": (UNKNOWN, UNKNOWN_BG),
    "UNKNOWN / NOT ENROLLED": (UNKNOWN, UNKNOWN_BG),
}

_FONT_HEAD = "'Source Serif 4', Georgia, serif"
_FONT_BODY = "'IBM Plex Sans', -apple-system, sans-serif"


def inject_css():
    """Call once per page render (from app.py) before any other st.* calls."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

        html, body, [class*="css"] {{
            font-family: {_FONT_BODY};
            color: {INK};
        }}
        .stApp {{
            background-color: {PAPER};
        }}
        h1, h2, h3, [data-testid="stHeader"] {{
            font-family: {_FONT_HEAD} !important;
            font-weight: 600 !important;
            letter-spacing: 0.01em;
        }}
        h1 {{ font-size: 2rem !important; }}
        h2 {{ font-size: 1.45rem !important; }}
        h3 {{ font-size: 1.15rem !important; }}

        /* Hide the default "Made with Streamlit" footer for a cleaner demo */
        footer {{ visibility: hidden; }}

        /* ---------------- Sidebar: the ledger's cover ---------------- */
        [data-testid="stSidebar"] {{
            background-color: {COVER};
        }}
        [data-testid="stSidebar"] * {{
            color: {COVER_TEXT} !important;
        }}
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2 {{
            font-family: {_FONT_HEAD} !important;
        }}
        [data-testid="stSidebar"] hr {{
            border-color: rgba(239,232,214,0.18);
        }}
        /* Nav radio rendered as a plain list of links, not radio buttons */
        [data-testid="stSidebar"] div[role="radiogroup"] > label {{
            display: block;
            padding: 0.5rem 0.6rem;
            margin-bottom: 2px;
            border-radius: 6px;
            border-left: 3px solid transparent;
        }}
        [data-testid="stSidebar"] div[role="radiogroup"] > label:hover {{
            background-color: rgba(239,232,214,0.08);
        }}
        [data-testid="stSidebar"] div[role="radiogroup"] > label[data-checked="true"] {{
            background-color: rgba(239,232,214,0.12);
            border-left: 3px solid {COVER_TEXT};
        }}
        [data-testid="stSidebar"] div[role="radiogroup"] input {{
            /* keep for accessibility/click target, hide the visible circle */
            opacity: 0;
            position: absolute;
        }}
        [data-testid="stSidebar"] [data-testid="stExpander"] {{
            background-color: rgba(250,246,236,0.05);
            border: 1px solid rgba(239,232,214,0.18);
            border-radius: 8px;
        }}

        /* ---------------- Metrics ---------------- */
        [data-testid="stMetric"] {{
            background-color: {PAPER_ALT};
            border: 1px solid {RULE};
            border-radius: 8px;
            padding: 0.75rem 0.9rem;
        }}
        [data-testid="stMetricValue"] {{
            font-family: {_FONT_HEAD};
            color: {INK};
        }}
        [data-testid="stMetricLabel"] {{
            color: #5B6459;
        }}

        /* ---------------- Tables ---------------- */
        [data-testid="stDataFrame"] {{
            border: 1px solid {RULE};
            border-radius: 8px;
        }}

        /* ---------------- Forms & buttons ---------------- */
        [data-testid="stForm"] {{
            background-color: {PAPER_ALT};
            border: 1px solid {RULE};
            border-radius: 10px;
            padding: 1.1rem 1.3rem 0.4rem 1.3rem;
        }}
        .stButton > button, .stFormSubmitButton > button {{
            border-radius: 6px;
            font-weight: 500;
        }}
        .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
            background-color: {PRESENT};
            border-color: {PRESENT};
        }}

        /* ---------------- Custom components (below) ---------------- */
        .attendai-statstrip {{
            display: flex;
            gap: 0;
            border: 1px solid {RULE};
            border-radius: 10px;
            overflow: hidden;
            margin-bottom: 0.75rem;
        }}
        .attendai-stat {{
            flex: 1;
            background-color: {PAPER_ALT};
            padding: 0.85rem 1rem;
            border-right: 1px solid {RULE};
        }}
        .attendai-stat:last-child {{ border-right: none; }}
        .attendai-stat .n {{
            font-family: {_FONT_HEAD};
            font-size: 1.6rem;
            font-weight: 700;
            line-height: 1.1;
        }}
        .attendai-stat .l {{
            font-size: 0.8rem;
            color: #5B6459;
            margin-top: 2px;
        }}

        .attendai-badge {{
            display: inline-block;
            padding: 0.15rem 0.6rem;
            border-radius: 999px;
            font-size: 0.85rem;
            font-weight: 600;
        }}

        .attendai-chip-row {{ display: flex; gap: 6px; flex-wrap: wrap; }}
        .attendai-chip {{
            border-radius: 8px;
            padding: 0.5rem 0.4rem;
            text-align: center;
            min-width: 64px;
            border: 1px solid {RULE};
        }}
        .attendai-chip .mark {{ font-family: {_FONT_HEAD}; font-size: 1.1rem; font-weight: 700; }}
        .attendai-chip .lab {{ font-size: 0.72rem; color: #5B6459; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def stat_strip(stats: list[tuple[str, object]]):
    """Render a row of (label, value) pairs as one bordered strip
    instead of Streamlit's default boxed st.metric-per-column layout."""
    cells = "".join(
        f'<div class="attendai-stat"><div class="n">{value}</div><div class="l">{label}</div></div>'
        for label, value in stats
    )
    st.markdown(f'<div class="attendai-statstrip">{cells}</div>', unsafe_allow_html=True)


def badge_html(status: str) -> str:
    color, bg = STATUS_COLORS.get(status, (INK, PAPER_ALT))
    return f'<span class="attendai-badge" style="color:{color};background-color:{bg};">{status}</span>'


def badge(status: str):
    st.markdown(badge_html(status), unsafe_allow_html=True)


def style_status_column(df: pd.DataFrame, column: str = "Status"):
    """Return a pandas Styler that colors `column`'s cells to match the
    status badge palette, for use with st.dataframe(...)."""

    def _style(val):
        color, bg = STATUS_COLORS.get(val, (None, None))
        if color is None:
            return ""
        return f"color:{color}; background-color:{bg}; font-weight:600;"

    styler = df.style
    # pandas >=2.1 renamed Styler.applymap to Styler.map (applymap is removed
    # in newer pandas / deprecated in others) — support both transparently.
    style_fn = getattr(styler, "map", None) or styler.applymap
    return style_fn(_style, subset=[column])


def snapshot_chip_row(total: int, observed_snapshots: set, score_by_snapshot: dict):
    """Render the per-snapshot ✓/✗ timeline as a row of small chips
    instead of a row of st.metric widgets."""
    chips = []
    for i in range(1, total + 1):
        present = i in observed_snapshots
        color, bg = STATUS_COLORS["PRESENT"] if present else (INK, PAPER_ALT)
        mark = "✓" if present else "–"
        title = (
            f"match score {score_by_snapshot[i]:.2f}"
            if present and i in score_by_snapshot
            else "not observed"
        )
        chips.append(
            f'<div class="attendai-chip" style="background-color:{bg};" title="{title}">'
            f'<div class="mark" style="color:{color};">{mark}</div>'
            f'<div class="lab">Snap {i}</div></div>'
        )
    st.markdown(f'<div class="attendai-chip-row">{"".join(chips)}</div>', unsafe_allow_html=True)
