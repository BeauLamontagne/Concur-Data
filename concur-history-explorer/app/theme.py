"""
Workday-inspired theme system for Concur History Explorer.

Usage in any page:
    from app import theme
    theme.apply_workday_theme()   # call once at the top of render()
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------

PRIMARY        = "#0875E1"   # Workday signature blue
DARK_BLUE      = "#011B3E"   # sidebar, main headers
MEDIUM_BLUE    = "#0E4A8A"   # secondary headers, hover
LIGHT_BLUE     = "#E8F1FD"   # selected rows, info backgrounds
WHITE          = "#FFFFFF"
LIGHT_GRAY     = "#F2F4F7"   # alternate table rows, card backgrounds
MEDIUM_GRAY    = "#6B7280"   # secondary text
DARK_GRAY      = "#1F2937"   # primary text
SUCCESS        = "#0E8A16"   # positive deltas, within-range
WARNING        = "#E67E22"   # >10% over budget
DANGER         = "#DC2626"   # >20% over budget
ACCENT_TEAL    = "#00B5D1"   # chart secondary

# Semantic aliases kept for backward compatibility
INFO           = PRIMARY
TEXT_PRIMARY   = DARK_GRAY
TEXT_SECONDARY = MEDIUM_GRAY
TEXT_MUTED     = "#9AA5B4"
TEXT_ON_DARK   = WHITE
BG_PAGE        = WHITE
BG_CARD        = WHITE
BG_SIDEBAR     = DARK_BLUE
PRIMARY_DARK   = MEDIUM_BLUE
PRIMARY_LIGHT  = LIGHT_BLUE

# ---------------------------------------------------------------------------
# Chart colors
# ---------------------------------------------------------------------------

_CHART_PALETTE = [
    PRIMARY,
    ACCENT_TEAL,
    "#34A853",
    WARNING,
    "#9B59B6",
    "#E74C3C",
    "#1ABC9C",
    MEDIUM_BLUE,
]


def get_chart_colors() -> list[str]:
    """Plotly-compatible ordered color list in Workday palette."""
    return list(_CHART_PALETTE)


def get_plotly_layout(title: str = "", height: int = 400) -> dict:
    """Base Plotly layout dict with Workday styling."""
    return {
        "title": {
            "text": title,
            "font": {"family": _FONT_STACK, "size": 15, "color": DARK_GRAY},
            "x": 0,
            "xanchor": "left",
        },
        "height": height,
        "paper_bgcolor": WHITE,
        "plot_bgcolor": WHITE,
        "font": {"family": _FONT_STACK, "color": DARK_GRAY},
        "colorway": _CHART_PALETTE,
        "legend": {
            "bgcolor": WHITE,
            "bordercolor": LIGHT_GRAY,
            "borderwidth": 1,
            "font": {"size": 12},
        },
        "xaxis": {
            "gridcolor": LIGHT_GRAY,
            "linecolor": "#D1D5DB",
            "tickfont": {"size": 11},
            "title_font": {"size": 12},
        },
        "yaxis": {
            "gridcolor": LIGHT_GRAY,
            "linecolor": "#D1D5DB",
            "tickfont": {"size": 11},
            "title_font": {"size": 12},
        },
        "margin": {"l": 50, "r": 20, "t": 50, "b": 50},
    }


# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

_FONT_STACK = (
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, '
    '"Helvetica Neue", Arial, sans-serif'
)

# ---------------------------------------------------------------------------
# Approval status → badge color
# ---------------------------------------------------------------------------

APPROVAL_COLORS: dict[str, str] = {
    "A_APPR": SUCCESS,
    "A_PAID": SUCCESS,
    "A_EXTV": PRIMARY,
    "A_PEND": WARNING,
    "A_NOTF": MEDIUM_GRAY,
    "A_BACK": DANGER,
    "A_RESU": DANGER,
    "A_CANC": TEXT_MUTED,
}

APPROVAL_LABELS: dict[str, str] = {
    "A_APPR": "Approved",
    "A_PAID": "Paid",
    "A_EXTV": "Sent for Payment",
    "A_PEND": "Pending Approval",
    "A_NOTF": "Not Submitted",
    "A_BACK": "Sent Back",
    "A_RESU": "Recalled",
    "A_CANC": "Cancelled",
}


# ---------------------------------------------------------------------------
# HTML component helpers
# ---------------------------------------------------------------------------

def styled_metric_card(
    label: str,
    value: str,
    delta: str | None = None,
    delta_color: str | None = None,
    border_color: str = PRIMARY,
) -> None:
    """Render a Workday-style metric card via st.markdown."""
    delta_html = ""
    if delta is not None:
        color = delta_color or (SUCCESS if not delta.startswith("-") else DANGER)
        delta_html = (
            f'<div class="wd-metric-delta" style="color:{color};">{delta}</div>'
        )
    st.markdown(
        f"""
        <div class="wd-metric-card" style="border-left-color:{border_color};">
            <div class="wd-metric-value">{value}</div>
            <div class="wd-metric-label">{label}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# Keep the old name as an alias so home.py doesn't break
def metric_card_html(value: str, label: str, border_color: str = PRIMARY) -> str:
    return (
        f'<div class="wd-metric-card" style="border-left-color:{border_color};">'
        f'<div class="wd-metric-value">{value}</div>'
        f'<div class="wd-metric-label">{label}</div>'
        f"</div>"
    )


def styled_header(text: str, level: int = 1, subtitle: str = "") -> None:
    """Render a Workday-style page header."""
    tag = f"h{max(1, min(level, 4))}"
    sub_html = f'<p class="wd-header-sub">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f'<div class="wd-header"><{tag} class="wd-header-title">{text}</{tag}>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def status_badge_html(code: str | None, label: str | None = None) -> str:
    """Return an inline HTML status badge."""
    code_upper = str(code or "").upper()
    color = APPROVAL_COLORS.get(code_upper, MEDIUM_GRAY)
    display = label or APPROVAL_LABELS.get(code_upper, code or "Unknown")
    return (
        f'<span style="background:{color};color:#fff;padding:2px 10px;'
        f'border-radius:12px;font-size:0.78rem;font-weight:600;">{display}</span>'
    )


def styled_dataframe(df: pd.DataFrame) -> None:
    """Render a DataFrame with Workday table styling."""
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------------------------
# Global CSS injection
# ---------------------------------------------------------------------------

_WORKDAY_CSS = f"""
<style>
/* ── Font & base ──────────────────────────────────────────────────────────── */
html, body, [class*="css"] {{
    font-family: {_FONT_STACK};
    font-size: 14px;
    color: {DARK_GRAY};
}}

/* ── Sidebar ──────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background-color: {DARK_BLUE} !important;
}}
[data-testid="stSidebar"] * {{
    color: {WHITE} !important;
}}
[data-testid="stSidebar"] .stRadio label {{
    color: {WHITE} !important;
    padding: 6px 12px;
    border-radius: 6px;
    transition: background 0.15s;
    display: block;
}}
[data-testid="stSidebar"] .stRadio label:hover {{
    background: rgba(255,255,255,0.10) !important;
}}
[data-testid="stSidebar"] .stRadio [aria-checked="true"] + label,
[data-testid="stSidebar"] .stRadio input:checked + label {{
    background: {PRIMARY} !important;
    border-radius: 6px;
}}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{
    color: rgba(255,255,255,0.65) !important;
    font-size: 0.78rem;
}}
[data-testid="stSidebar"] hr {{
    border-color: rgba(255,255,255,0.15) !important;
}}
[data-testid="stSidebar"] .stWarning {{
    background: rgba(230,126,34,0.15) !important;
    border-left-color: {WARNING} !important;
}}
[data-testid="stSidebar"] .stWarning p {{
    color: #F5CBA7 !important;
    font-size: 0.80rem !important;
}}

/* ── Main content area ────────────────────────────────────────────────────── */
.main .block-container {{
    padding-top: 1.5rem;
    padding-bottom: 2rem;
    max-width: 1400px;
}}

/* ── Page / section headers ───────────────────────────────────────────────── */
.wd-header {{
    padding-bottom: 0.75rem;
    margin-bottom: 1.25rem;
    border-bottom: 2px solid {LIGHT_BLUE};
}}
.wd-header-title {{
    color: {DARK_BLUE};
    font-weight: 600;
    margin: 0 0 2px 0;
    letter-spacing: -0.3px;
}}
.wd-header-sub {{
    color: {MEDIUM_GRAY};
    font-size: 0.85rem;
    margin: 0;
}}

/* ── Metric cards ─────────────────────────────────────────────────────────── */
.wd-metric-card {{
    background: {WHITE};
    border-radius: 8px;
    padding: 1.1rem 1.4rem 1.1rem 1.1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.12);
    border-left: 4px solid {PRIMARY};
    margin-bottom: 0.5rem;
    min-height: 80px;
}}
.wd-metric-value {{
    font-size: 1.75rem;
    font-weight: 700;
    color: {DARK_GRAY};
    line-height: 1.1;
}}
.wd-metric-label {{
    font-size: 0.78rem;
    color: {MEDIUM_GRAY};
    margin-top: 3px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.4px;
}}
.wd-metric-delta {{
    font-size: 0.82rem;
    font-weight: 600;
    margin-top: 4px;
}}

/* ── st.metric override → card style ─────────────────────────────────────── */
[data-testid="metric-container"] {{
    background: {WHITE};
    border-radius: 8px;
    padding: 1rem 1.25rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.12);
    border-left: 4px solid {PRIMARY};
}}
[data-testid="stMetricLabel"] {{
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    color: {MEDIUM_GRAY} !important;
}}
[data-testid="stMetricValue"] {{
    font-size: 1.75rem !important;
    font-weight: 700 !important;
    color: {DARK_GRAY} !important;
}}
[data-testid="stMetricDelta"] svg {{
    display: none;
}}

/* ── Buttons ──────────────────────────────────────────────────────────────── */
.stButton > button {{
    background-color: {PRIMARY} !important;
    color: {WHITE} !important;
    border: none !important;
    border-radius: 20px !important;
    padding: 0.4rem 1.4rem !important;
    font-size: 0.875rem !important;
    font-weight: 600 !important;
    transition: background 0.15s, box-shadow 0.15s !important;
    box-shadow: 0 1px 3px rgba(8,117,225,0.3) !important;
}}
.stButton > button:hover {{
    background-color: {MEDIUM_BLUE} !important;
    box-shadow: 0 2px 6px rgba(8,117,225,0.4) !important;
}}
.stButton > button:active {{
    background-color: {DARK_BLUE} !important;
}}

/* ── Download button ──────────────────────────────────────────────────────── */
.stDownloadButton > button {{
    background-color: {WHITE} !important;
    color: {PRIMARY} !important;
    border: 1.5px solid {PRIMARY} !important;
    border-radius: 20px !important;
    padding: 0.4rem 1.4rem !important;
    font-size: 0.875rem !important;
    font-weight: 600 !important;
}}
.stDownloadButton > button:hover {{
    background-color: {LIGHT_BLUE} !important;
}}

/* ── Text inputs & search ─────────────────────────────────────────────────── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {{
    border-radius: 8px !important;
    border: 1.5px solid #D1D5DB !important;
    font-size: 0.875rem !important;
    transition: border-color 0.15s, box-shadow 0.15s !important;
}}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {{
    border-color: {PRIMARY} !important;
    box-shadow: 0 0 0 3px rgba(8,117,225,0.15) !important;
    outline: none !important;
}}

/* ── Select boxes ─────────────────────────────────────────────────────────── */
.stSelectbox > div > div,
.stMultiSelect > div > div {{
    border-radius: 8px !important;
    border: 1.5px solid #D1D5DB !important;
}}
.stSelectbox > div > div:focus-within,
.stMultiSelect > div > div:focus-within {{
    border-color: {PRIMARY} !important;
    box-shadow: 0 0 0 3px rgba(8,117,225,0.15) !important;
}}

/* ── Date inputs ──────────────────────────────────────────────────────────── */
.stDateInput > div > div > input {{
    border-radius: 8px !important;
    border: 1.5px solid #D1D5DB !important;
}}

/* ── Tabs ─────────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
    gap: 0;
    border-bottom: 2px solid {LIGHT_GRAY};
    background: transparent;
}}
.stTabs [data-baseweb="tab"] {{
    background: transparent !important;
    border: none !important;
    border-bottom: 3px solid transparent !important;
    border-radius: 0 !important;
    padding: 0.6rem 1.2rem !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    color: {MEDIUM_GRAY} !important;
    margin-bottom: -2px;
    transition: color 0.15s, border-color 0.15s;
}}
.stTabs [data-baseweb="tab"]:hover {{
    color: {PRIMARY} !important;
    background: {LIGHT_BLUE} !important;
}}
.stTabs [aria-selected="true"] {{
    color: {PRIMARY} !important;
    border-bottom-color: {PRIMARY} !important;
    font-weight: 600 !important;
}}
.stTabs [data-baseweb="tab-panel"] {{
    padding-top: 1rem;
}}

/* ── Expanders ────────────────────────────────────────────────────────────── */
.streamlit-expanderHeader {{
    background: {LIGHT_GRAY} !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    color: {DARK_BLUE} !important;
    border: 1px solid #E5E7EB !important;
}}
.streamlit-expanderHeader:hover {{
    background: {LIGHT_BLUE} !important;
}}
.streamlit-expanderContent {{
    border: 1px solid #E5E7EB !important;
    border-top: none !important;
    border-radius: 0 0 8px 8px !important;
    padding: 1rem !important;
}}

/* ── DataFrames / tables ──────────────────────────────────────────────────── */
.stDataFrame {{
    border-radius: 8px !important;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}}
[data-testid="stDataFrameResizable"] {{
    border-radius: 8px;
}}

/* ── Info / success / warning / error boxes ───────────────────────────────── */
.stAlert {{
    border-radius: 8px !important;
}}
[data-testid="stNotification"] {{
    border-radius: 8px !important;
}}

/* ── Divider ──────────────────────────────────────────────────────────────── */
hr {{
    border-color: {LIGHT_GRAY} !important;
    margin: 1rem 0 !important;
}}

/* ── Cards (generic content container) ────────────────────────────────────── */
.wd-card {{
    background: {WHITE};
    border-radius: 8px;
    padding: 1.25rem 1.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.12);
    margin-bottom: 1rem;
}}
.wd-card-header {{
    font-size: 0.9rem;
    font-weight: 600;
    color: {DARK_BLUE};
    margin-bottom: 0.75rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid {LIGHT_GRAY};
}}

/* ── Filter panel ─────────────────────────────────────────────────────────── */
.wd-filter-panel {{
    background: {LIGHT_GRAY};
    border-radius: 8px;
    padding: 1rem 1.25rem;
    margin-bottom: 1rem;
    border: 1px solid #E5E7EB;
}}

/* ── Section labels ───────────────────────────────────────────────────────── */
.wd-section-label {{
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: {MEDIUM_GRAY};
    margin-bottom: 0.5rem;
}}

/* ── Budget comparison ────────────────────────────────────────────────────── */
.wd-budget-ok   {{ color: {SUCCESS}; font-weight: 600; }}
.wd-budget-warn {{ color: {WARNING}; font-weight: 600; }}
.wd-budget-over {{ color: {DANGER};  font-weight: 600; }}

/* ── Scrollbar ────────────────────────────────────────────────────────────── */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: {LIGHT_GRAY}; }}
::-webkit-scrollbar-thumb {{ background: #C1C9D4; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: {MEDIUM_GRAY}; }}
</style>
"""

_SIDEBAR_BRAND = f"""
<div style="
    padding: 1.25rem 1rem 1rem 1rem;
    border-bottom: 1px solid rgba(255,255,255,0.12);
    margin-bottom: 0.5rem;
">
    <div style="
        width: 40px; height: 40px;
        background: {PRIMARY};
        border-radius: 8px;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.2rem; margin-bottom: 0.75rem;
    ">💼</div>
    <div style="
        font-size: 1rem; font-weight: 700;
        color: {WHITE}; line-height: 1.2;
        font-family: {_FONT_STACK};
    ">ICW Concur<br>History Explorer</div>
    <div style="
        font-size: 0.72rem; color: rgba(255,255,255,0.5);
        margin-top: 4px; letter-spacing: 0.3px;
    ">Read-only · Historical Data</div>
</div>
"""


def apply_workday_theme() -> None:
    """
    Inject all Workday CSS and the sidebar brand block.
    Call once at the top of each page's render() function.
    """
    st.markdown(_WORKDAY_CSS, unsafe_allow_html=True)
    st.sidebar.markdown(_SIDEBAR_BRAND, unsafe_allow_html=True)
