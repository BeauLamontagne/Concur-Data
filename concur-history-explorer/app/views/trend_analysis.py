"""
Spend Trends & Forecasting Support — Stories B2, B3.
Multi-year trend comparison and budget validation.
"""

from __future__ import annotations

import io
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import theme
from app.db.connection import db_exists, get_connection
from app.db.queries import (
    ExpenseFilters,
    get_filter_options,
    get_spend_summary,
    get_trend_data,
)
from app.utils.formatters import fmt_currency, fmt_currency_compact

# ── Session-state keys ────────────────────────────────────────────────────────
_SS_YEARS = "ta_years"
_SS_GROUP = "ta_group"
_SS_GRAN  = "ta_granularity"

_GROUP_OPTIONS = [
    "icw_expense_group",
    "icw_expense_category",
    "org_unit_1",
]
_GROUP_LABELS = {
    "icw_expense_group":    "ICW Expense Group",
    "icw_expense_category": "ICW Expense Category",
    "org_unit_1":           "Department (ORG_UNIT_1)",
}


def _init_state(available_years: list[str]) -> None:
    defaults_: dict = {
        _SS_YEARS: available_years[:3] if len(available_years) >= 3 else available_years,
        _SS_GROUP: "icw_expense_group",
        _SS_GRAN:  "Monthly",
    }
    for k, v in defaults_.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _available_years(opts: dict) -> list[str]:
    dmin = opts.get("date_min") or "2018-01-01"
    dmax = opts.get("date_max") or str(date.today())
    try:
        y_min = int(dmin[:4])
        y_max = int(dmax[:4])
    except Exception:
        y_min, y_max = 2018, date.today().year
    return [str(y) for y in range(y_max, y_min - 1, -1)]


# ── Tab 1: Trend charts ───────────────────────────────────────────────────────

def _render_trend_tab(conn, selected_years: list[str], group_by: str, granularity: str) -> None:
    if not selected_years:
        st.info("Select at least one year in the controls above.")
        return

    gran_key = "month" if granularity == "Monthly" else "quarter"
    all_filters: ExpenseFilters = {
        "date_start": f"{min(selected_years)}-01-01",
        "date_end":   f"{max(selected_years)}-12-31",
    }

    with st.spinner("Loading trend data…"):
        df = get_trend_data(conn, group_by=group_by, time_granularity=gran_key, filters=all_filters)

    if df.empty:
        st.info("No data for the selected years and filters.")
        return

    df["year"] = df["year"].astype(str)
    df = df[df["year"].isin(selected_years)]

    colors = theme.get_chart_colors()
    layout = theme.get_plotly_layout(height=420)

    # Group selector when there are many distinct group values
    group_vals = sorted(df["group_value"].dropna().unique().tolist())
    if len(group_vals) > 8:
        selected_groups = st.multiselect(
            f"Filter {_GROUP_LABELS.get(group_by, group_by)} (max 8)",
            group_vals,
            default=group_vals[:8],
            key="ta_group_filter",
        )
        df = df[df["group_value"].isin(selected_groups)]
    else:
        selected_groups = group_vals

    fig = go.Figure()
    for i, yr in enumerate(sorted(selected_years)):
        yr_df = df[df["year"] == yr].sort_values("period")
        if yr_df.empty:
            continue
        # Aggregate across all group values for the overall trend line
        yr_agg = yr_df.groupby("period", as_index=False)["total_amount"].sum()
        fig.add_trace(go.Scatter(
            x=yr_agg["period"],
            y=yr_agg["total_amount"],
            name=yr,
            mode="lines+markers",
            line={"color": colors[i % len(colors)], "width": 2},
            marker={"size": 6},
            hovertemplate=f"{yr} — %{{x}}<br>${{y:,.2f}}<extra></extra>",
        ))

    fig.update_layout(
        **layout,
        title_text=f"Spend by {granularity} — All Groups",
        xaxis_title=granularity,
        yaxis_title="Posted Amount ($)",
        legend_title="Year",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Per-group small multiples (when ≤4 groups)
    if 1 < len(selected_groups) <= 4:
        st.markdown(f'<div class="wd-section-label" style="margin-top:1rem;">By {_GROUP_LABELS.get(group_by, group_by)}</div>', unsafe_allow_html=True)
        cols = st.columns(min(len(selected_groups), 2))
        for gi, gval in enumerate(selected_groups):
            g_df = df[df["group_value"] == gval]
            fig_g = go.Figure()
            for i, yr in enumerate(sorted(selected_years)):
                yr_g = g_df[g_df["year"] == yr].sort_values("period")
                if yr_g.empty:
                    continue
                fig_g.add_trace(go.Scatter(
                    x=yr_g["period"], y=yr_g["total_amount"],
                    name=yr, mode="lines+markers",
                    line={"color": colors[i % len(colors)], "width": 2},
                    marker={"size": 5},
                ))
            fig_g.update_layout(**theme.get_plotly_layout(str(gval)[:40], height=260))
            with cols[gi % 2]:
                st.plotly_chart(fig_g, use_container_width=True)

    # Export
    st.download_button(
        "📥 Export Trend Data (CSV)",
        data=df.to_csv(index=False).encode(),
        file_name=f"trend_data_{date.today()}.csv",
        mime="text/csv",
    )


# ── Tab 2: Year-over-year comparison ─────────────────────────────────────────

def _render_yoy_tab(conn, selected_years: list[str], group_by: str) -> None:
    if len(selected_years) < 2:
        st.info("Select at least 2 years to compare.")
        return

    dfs = []
    for yr in selected_years:
        f: ExpenseFilters = {"date_start": f"{yr}-01-01", "date_end": f"{yr}-12-31"}
        yr_df = get_spend_summary(conn, group_by=group_by, filters=f)
        if not yr_df.empty:
            yr_df["year"] = yr
            dfs.append(yr_df)

    if not dfs:
        st.info("No data for the selected years.")
        return

    combined = pd.concat(dfs, ignore_index=True)
    group_col = group_by
    pivot = combined.pivot_table(
        index=group_col, columns="year", values="total_amount", aggfunc="sum"
    ).reset_index().fillna(0)

    years_sorted = sorted(selected_years)

    # Grouped bar chart
    colors = theme.get_chart_colors()
    fig = go.Figure()
    for i, yr in enumerate(years_sorted):
        if yr in pivot.columns:
            fig.add_trace(go.Bar(
                name=yr,
                x=pivot[group_col].astype(str),
                y=pivot[yr],
                marker_color=colors[i % len(colors)],
                hovertemplate=f"{yr}<br>%{{x}}<br>${{y:,.2f}}<extra></extra>",
            ))
    fig.update_layout(
        **theme.get_plotly_layout(height=400),
        title_text=f"Annual Spend by {_GROUP_LABELS.get(group_by, group_by)}",
        barmode="group",
        xaxis_title=_GROUP_LABELS.get(group_by, group_by),
        yaxis_title="Posted Amount ($)",
        xaxis={"tickangle": -30},
    )
    st.plotly_chart(fig, use_container_width=True)

    # Delta table
    st.markdown('<div class="wd-section-label" style="margin-top:1rem;">Year-over-Year Delta</div>', unsafe_allow_html=True)

    delta_rows = []
    for _, row in pivot.iterrows():
        r: dict = {_GROUP_LABELS.get(group_col, group_col): row[group_col]}
        for yr in years_sorted:
            r[yr] = fmt_currency(row.get(yr, 0))
        if len(years_sorted) >= 2:
            prev_yr = years_sorted[-2]
            curr_yr = years_sorted[-1]
            prev_v = float(row.get(prev_yr, 0))
            curr_v = float(row.get(curr_yr, 0))
            dollar_chg = curr_v - prev_v
            pct_chg = (dollar_chg / prev_v * 100) if prev_v else 0
            r["$ Change (YoY)"] = fmt_currency(dollar_chg)
            r["% Change (YoY)"] = f"{pct_chg:+.1f}%"
            r["_pct_raw"] = pct_chg
        delta_rows.append(r)

    if delta_rows:
        delta_df = pd.DataFrame(delta_rows)

        def _color_delta(val):
            try:
                v = float(str(val).replace("%", "").replace("+", ""))
                if v < 0:
                    return f"color: {theme.SUCCESS}; font-weight:600"
                if v > 0:
                    return f"color: {theme.DANGER}; font-weight:600"
            except Exception:
                pass
            return ""

        pct_col = "% Change (YoY)"
        display_df = delta_df.drop(columns=["_pct_raw"], errors="ignore")
        if pct_col in display_df.columns:
            styled = display_df.style.applymap(_color_delta, subset=[pct_col])
        else:
            styled = display_df.style

        st.dataframe(styled, use_container_width=True, hide_index=True)

        # Export
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            display_df.to_excel(writer, sheet_name="YoY Comparison", index=False)
            combined.to_excel(writer, sheet_name="Raw Data", index=False)
        st.download_button(
            "📥 Export YoY Comparison (Excel)",
            data=buf.getvalue(),
            file_name=f"yoy_comparison_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# ── Main render ───────────────────────────────────────────────────────────────

def render() -> None:
    theme.apply_workday_theme()

    theme.styled_header(
        "📈 Spend Trends & Forecasting Support",
        subtitle="Compare historical spend across years and validate budget assumptions.",
    )

    if not db_exists():
        st.info("No database found. Run the ingest command first.")
        st.code("python -m app.db.ingest --data-dir ./data", language="bash")
        return

    conn = get_connection()
    opts = get_filter_options(conn)

    avail_years = _available_years(opts)
    _init_state(avail_years)

    # ── Controls card ─────────────────────────────────────────────────────────
    with st.container():
        st.markdown('<div class="wd-card">', unsafe_allow_html=True)
        st.markdown('<div class="wd-card-header">Analysis Parameters</div>', unsafe_allow_html=True)

        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            selected_years = st.multiselect(
                "Years to compare",
                avail_years,
                default=st.session_state[_SS_YEARS],
                key=_SS_YEARS,
            )
        with cc2:
            st.selectbox(
                "Group By",
                _GROUP_OPTIONS,
                format_func=_GROUP_LABELS.get,
                key=_SS_GROUP,
            )
        with cc3:
            st.radio(
                "Time Granularity",
                ["Monthly", "Quarterly"],
                horizontal=True,
                key=_SS_GRAN,
            )

        st.markdown('</div>', unsafe_allow_html=True)

    st.divider()

    tab1, tab2 = st.tabs([
        "📈 Trend Charts",
        "📊 Year-over-Year Comparison",
    ])

    group_by    = st.session_state[_SS_GROUP]
    granularity = st.session_state[_SS_GRAN]
    years       = st.session_state[_SS_YEARS]

    with tab1:
        _render_trend_tab(conn, years, group_by, granularity)

    with tab2:
        _render_yoy_tab(conn, years, group_by)

    conn.close()
