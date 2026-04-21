"""Workday-inspired color palette and shared style constants."""

# Primary brand colors
PRIMARY = "#0875E1"
PRIMARY_DARK = "#0557A8"
PRIMARY_LIGHT = "#4DA3F5"

# Backgrounds
BG_PAGE = "#F5F5F5"
BG_CARD = "#FFFFFF"
BG_SIDEBAR = "#2D3748"

# Text
TEXT_PRIMARY = "#1F1F1F"
TEXT_SECONDARY = "#5A6472"
TEXT_MUTED = "#9AA5B4"
TEXT_ON_DARK = "#FFFFFF"

# Status colors
SUCCESS = "#2E7D32"
SUCCESS_LIGHT = "#E8F5E9"
WARNING = "#F57C00"
WARNING_LIGHT = "#FFF3E0"
DANGER = "#C62828"
DANGER_LIGHT = "#FFEBEE"
INFO = "#0288D1"
INFO_LIGHT = "#E1F5FE"

# Chart palette (sequential + categorical)
CHART_PALETTE = [
    "#0875E1",
    "#34A853",
    "#FBBC04",
    "#EA4335",
    "#9C27B0",
    "#00BCD4",
    "#FF6D00",
    "#607D8B",
]

# Approval status → badge color
APPROVAL_COLORS: dict[str, str] = {
    "A_APPR": SUCCESS,
    "A_PAID": SUCCESS,
    "A_EXTV": INFO,
    "A_PEND": WARNING,
    "A_NOTF": TEXT_SECONDARY,
    "A_BACK": DANGER,
    "A_RESU": DANGER,
    "A_CANC": TEXT_MUTED,
}


def status_badge_html(code: str | None, label: str) -> str:
    color = APPROVAL_COLORS.get(str(code or "").upper(), TEXT_SECONDARY)
    return (
        f'<span style="background:{color};color:#fff;padding:2px 10px;'
        f'border-radius:12px;font-size:0.78rem;font-weight:600;">{label}</span>'
    )


METRIC_CARD_CSS = """
<style>
.metric-card {
    background: #FFFFFF;
    border-radius: 8px;
    padding: 1.2rem 1.5rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    border-left: 4px solid #0875E1;
}
.metric-card .metric-value {
    font-size: 1.8rem;
    font-weight: 700;
    color: #1F1F1F;
}
.metric-card .metric-label {
    font-size: 0.82rem;
    color: #5A6472;
    margin-top: 2px;
}
</style>
"""


def metric_card_html(value: str, label: str, border_color: str = PRIMARY) -> str:
    return (
        f'<div class="metric-card" style="border-left-color:{border_color};">'
        f'<div class="metric-value">{value}</div>'
        f'<div class="metric-label">{label}</div>'
        f"</div>"
    )
