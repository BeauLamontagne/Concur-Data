"""Year-over-Year — compare annual spend across selected years."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import theme
from app.db.connection import db_exists, get_connection
from app.db.queries import ExpenseFilters, get_filter_options, get_spend_summary
from app.utils.formatters import fmt_currency, fmt_currency_compact

# Session-state keys
_SS_YEARS    = "yoy_years"
_SS_COST_CTR = "yoy_cost_center"
_SS_RESULTS  = "yoy_results"
_SS_PARAMS   = "yoy_params"


def _init_state(avail_years: list[str]) -> None:
    defaults: dict = {
        _SS_YEARS:    avail_years,
        _SS_COST_CTR: "(All)",
        _SS_RESULTS:  None,
        _SS_PARAMS:   None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _avail_years(opts: dict) -> list[str]:
    try:
        y_min = int((opts.get("date_min") or "2018-01-01")[:4])
        y_max = int((opts.get("date_max") or str(date.today()))[:4])
    except Exception:
        y_min, y_max = 2018, date.today().year
    return [str(y) for y in range(y_max, y_min - 1, -1)]


def _render_controls(opts: dict, avail_years: list[str]) -> bool:
    """Render parameters panel. Returns True when Generate is clicked."""
    st.markdown('<div class="wd-card">', unsafe_allow_html=True)
    st.markdown('<div class="wd-card-header">Parameters</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns([3, 2, 1])

    with c1:
        st.multiselect(
            "Years to compare",
            avail_years,
            default=st.session_state[_SS_YEARS],
            key=_SS_YEARS,
        )

    with c2:
        cost_centers = ["(All)"] + opts.get("cost_centers", [])
        st.selectbox("Cost Center", cost_centers, key=_SS_COST_CTR)

    with c3:
        st.markdown("<br>", unsafe_allow_html=True)
        generate = st.button("Generate", type="primary", use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)
    return generate


def render() -> None:
    theme.apply_workday_theme()

    theme.styled_header(
        "Year-over-Year",
        subtitle="Select years and an optional cost center, then click Generate.",
    )

    if not db_exists():
        st.info("No database found. Run the ingest command first.")
        st.code("python -m app.db.ingest --data-dir ./data", language="bash")
        return

    conn = get_connection()
    opts = get_filter_options(conn)
    avail_years = _avail_years(opts)
    _init_state(avail_years)

    generate = _render_controls(opts, avail_years)

    if generate:
        selected_years = st.session_state[_SS_YEARS]
        if not selected_years:
            st.warning("Select at least one year.")
            conn.close()
            return
        st.session_state[_SS_PARAMS] = {
            "years":       sorted(selected_years),
            "cost_center": st.session_state[_SS_COST_CTR],
        }
        st.session_state[_SS_RESULTS] = "pending"

    if st.session_state[_SS_RESULTS] is None:
        st.markdown(
            f'<div style="text-align:center;padding:2.5rem;color:{theme.MEDIUM_GRAY};">'
            f'Select years and optional cost center above, then click <b>Generate</b>.</div>',
            unsafe_allow_html=True,
        )
        conn.close()
        return

    params = st.session_state[_SS_PARAMS]
    selected_years = params["years"]
    cc = params["cost_center"]

    filters: ExpenseFilters = {}
    if cc and cc != "(All)":
        filters["cost_center"] = cc

    with st.spinner("Loading data…"):
        df_all = get_spend_summary(conn, group_by="year", filters=filters or None)

    st.session_state[_SS_RESULTS] = "done"

    if df_all.empty:
        st.warning("No data found.")
        conn.close()
        return

    df = df_all[df_all["year"].astype(str).isin(selected_years)].copy()
    df = df.sort_values("year")

    if df.empty:
        st.warning("No data for the selected years.")
        conn.close()
        return

    st.divider()

    # Summary metrics
    c1, c2, c3 = st.columns(3)
    with c1:
        theme.styled_metric_card("Total Spend", fmt_currency_compact(df["total_amount"].sum()))
    with c2:
        theme.styled_metric_card("Total Reports", f"{int(df['report_count'].sum()):,}",
                                 border_color=theme.MEDIUM_BLUE)
    with c3:
        theme.styled_metric_card("Years Shown", str(len(df)),
                                 border_color=theme.ACCENT_TEAL)

    st.divider()

    # Bar chart — years on x-axis, spend on y-axis
    colors = theme.get_chart_colors()
    bar_colors = [colors[i % len(colors)] for i in range(len(df))]

    fig = go.Figure(go.Bar(
        x=df["year"].astype(str),
        y=df["total_amount"],
        marker_color=bar_colors,
        text=df["total_amount"].apply(fmt_currency_compact),
        textposition="outside",
        hovertemplate="%{x}<br>$%{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(
        height=380,
        paper_bgcolor=theme.WHITE,
        plot_bgcolor=theme.WHITE,
        font={"color": theme.DARK_GRAY},
        xaxis_title="Year",
        yaxis_title="Total Posted Amount ($)",
        showlegend=False,
        margin={"l": 60, "r": 20, "t": 30, "b": 50},
        xaxis={"tickfont": {"size": 13}, "linecolor": "#D1D5DB"},
        yaxis={"gridcolor": theme.LIGHT_GRAY, "linecolor": "#D1D5DB"},
    )
    st.plotly_chart(fig, use_container_width=True)

    # Table
    st.divider()
    display = df.copy()
    display["Year"]             = display["year"].astype(str)
    display["Total Spend"]      = display["total_amount"].apply(fmt_currency)
    display["# Reports"]        = display["report_count"].astype(int)
    display["# Transactions"]   = display["transaction_count"].astype(int)
    display["Avg Transaction"]  = display["avg_amount"].apply(fmt_currency)

    if len(df) >= 2:
        vals = df["total_amount"].tolist()
        yrs  = df["year"].astype(str).tolist()
        yoy_chg = ["—"]
        for i in range(1, len(vals)):
            prev = vals[i - 1]
            curr = vals[i]
            delta = curr - prev
            pct   = (delta / prev * 100) if prev else 0
            sign  = "+" if delta >= 0 else ""
            yoy_chg.append(f"{sign}{pct:.1f}%  ({fmt_currency(delta)})")
        display["YoY Change"] = yoy_chg

    out_cols = ["Year", "Total Spend", "# Reports", "# Transactions", "Avg Transaction"]
    if "YoY Change" in display.columns:
        out_cols.append("YoY Change")

    st.dataframe(display[out_cols], use_container_width=True, hide_index=True)

    st.download_button(
        "📥 Export CSV",
        data=display[out_cols].to_csv(index=False).encode(),
        file_name=f"yoy_spend_{date.today()}.csv",
        mime="text/csv",
    )

    conn.close()
