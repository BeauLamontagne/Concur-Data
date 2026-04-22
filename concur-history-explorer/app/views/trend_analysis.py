"""
Year-over-Year Comparison — Stories B2, B3.
Annual spend comparison and budget validation for historical archive.
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
    get_budget_comparison,
    get_filter_options,
    get_spend_summary,
)
from app.utils.formatters import fmt_currency, fmt_currency_compact

# ── Session-state keys ────────────────────────────────────────────────────────
_SS_YEARS     = "ta_years"
_SS_GROUP     = "ta_group"
_SS_DIM_TYPE  = "ta_budget_dim_type"
_SS_DIM_VAL   = "ta_budget_dim_val"
_SS_PROPOSED  = "ta_proposed_amt"
_SS_BV_RESULT = "ta_budget_result"

_GROUP_OPTIONS = [
    "icw_expense_group",
    "icw_expense_category",
    "cost_center",
    "org_unit_1",
]
_GROUP_LABELS = {
    "icw_expense_group":    "ICW Expense Group",
    "icw_expense_category": "ICW Expense Category",
    "cost_center":          "Cost Center",
    "org_unit_1":           "Department (ORG_UNIT_1)",
}

_DIM_BUDGET = {
    "cost_center":          "Cost Center",
    "icw_expense_category": "ICW Expense Category",
    "icw_expense_group":    "ICW Expense Group",
    "org_unit_1":           "Department (ORG_UNIT_1)",
}


def _init_state(available_years: list[str]) -> None:
    defaults: dict = {
        _SS_YEARS:     available_years[:3] if len(available_years) >= 3 else available_years,
        _SS_GROUP:     "icw_expense_group",
        _SS_DIM_TYPE:  "cost_center",
        _SS_DIM_VAL:   "",
        _SS_PROPOSED:  0.0,
        _SS_BV_RESULT: None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _available_years(opts: dict) -> list[str]:
    dmin = opts.get("date_min") or "2018-01-01"
    dmax = opts.get("date_max") or str(date.today())
    try:
        y_min, y_max = int(dmin[:4]), int(dmax[:4])
    except Exception:
        y_min, y_max = 2018, date.today().year
    return [str(y) for y in range(y_max, y_min - 1, -1)]


# ── YoY comparison ────────────────────────────────────────────────────────────

def _render_yoy(conn, selected_years: list[str], group_by: str) -> None:
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

    combined   = pd.concat(dfs, ignore_index=True)
    group_col  = group_by
    years_sorted = sorted(selected_years)

    pivot = combined.pivot_table(
        index=group_col, columns="year", values="total_amount", aggfunc="sum"
    ).reset_index().fillna(0)

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
        **theme.get_plotly_layout(height=420),
        title_text=f"Annual Spend by {_GROUP_LABELS.get(group_by, group_by)}",
        barmode="group",
        xaxis_title=_GROUP_LABELS.get(group_by, group_by),
        yaxis_title="Posted Amount ($)",
    )
    fig.update_xaxes(tickangle=-30)
    st.plotly_chart(fig, use_container_width=True)

    # Delta table
    st.markdown(
        '<div class="wd-section-label" style="margin-top:1rem;">Year-over-Year Delta</div>',
        unsafe_allow_html=True,
    )

    delta_rows = []
    for _, row in pivot.iterrows():
        r: dict = {_GROUP_LABELS.get(group_col, group_col): row[group_col]}
        for yr in years_sorted:
            r[yr] = fmt_currency(row.get(yr, 0))
        if len(years_sorted) >= 2:
            prev_yr  = years_sorted[-2]
            curr_yr  = years_sorted[-1]
            prev_v   = float(row.get(prev_yr, 0))
            curr_v   = float(row.get(curr_yr, 0))
            dollar_chg = curr_v - prev_v
            pct_chg  = (dollar_chg / prev_v * 100) if prev_v else 0
            r["$ Change (YoY)"] = fmt_currency(dollar_chg)
            r["% Change (YoY)"] = f"{pct_chg:+.1f}%"
            r["_pct_raw"] = pct_chg
        delta_rows.append(r)

    if delta_rows:
        delta_df = pd.DataFrame(delta_rows)

        def _color_pct(val):
            try:
                v = float(str(val).replace("%", "").replace("+", ""))
                if v < 0:
                    return f"color:{theme.SUCCESS};font-weight:600"
                if v > 0:
                    return f"color:{theme.DANGER};font-weight:600"
            except Exception:
                pass
            return ""

        pct_col    = "% Change (YoY)"
        display_df = delta_df.drop(columns=["_pct_raw"], errors="ignore")
        styled     = (
            display_df.style.applymap(_color_pct, subset=[pct_col])
            if pct_col in display_df.columns
            else display_df.style
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)

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


# ── Budget validation ─────────────────────────────────────────────────────────

def _render_budget(conn, opts: dict) -> None:
    st.markdown('<div class="wd-card">', unsafe_allow_html=True)
    st.markdown('<div class="wd-card-header">Budget Assumption Validator</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns([2, 3, 2, 1])

    with c1:
        dim_type = st.selectbox(
            "Dimension",
            list(_DIM_BUDGET.keys()),
            format_func=_DIM_BUDGET.get,
            key=_SS_DIM_TYPE,
        )

    with c2:
        dim_key = st.session_state[_SS_DIM_TYPE]
        if dim_key == "cost_center":
            dim_vals = opts.get("cost_centers", [])
        elif dim_key == "icw_expense_category":
            dim_vals = opts.get("expense_categories", [])
        elif dim_key == "icw_expense_group":
            dim_vals = opts.get("expense_groups", [])
        else:
            dim_vals = opts.get("org_units", {}).get("org_unit_1", [])

        dim_val = st.selectbox(
            _DIM_BUDGET.get(dim_key, dim_key),
            ["— select —"] + dim_vals,
            key=_SS_DIM_VAL,
        )

    with c3:
        proposed = st.number_input(
            "Proposed Budget ($)",
            min_value=0.0,
            value=float(st.session_state[_SS_PROPOSED] or 0),
            step=1000.0,
            format="%.2f",
            key=_SS_PROPOSED,
        )

    with c4:
        st.markdown("<br>", unsafe_allow_html=True)
        validate = st.button("Validate", type="primary", use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

    if validate:
        if dim_val == "— select —":
            st.warning("Please select a dimension value.")
        else:
            with st.spinner("Analyzing historical data…"):
                result = get_budget_comparison(conn, dim_key, dim_val, proposed)
            st.session_state[_SS_BV_RESULT] = result

    result = st.session_state.get(_SS_BV_RESULT)
    if not result:
        st.markdown(
            f'<div style="text-align:center;padding:1.5rem;color:{theme.MEDIUM_GRAY};">'
            f'Select a dimension and proposed amount, then click <b>Validate</b>.</div>',
            unsafe_allow_html=True,
        )
        return

    # Results
    hist_avg  = result["historical_avg"]
    hist_min  = result["historical_min"]
    hist_max  = result["historical_max"]
    last_yr   = result["last_year_actual"]
    proposed  = result["proposed"]
    delta_avg = result["delta_vs_avg"]
    delta_lst = result["delta_vs_last_year"]
    warning   = result["warning"]
    in_range  = result["within_range"]

    if warning:
        status_icon, status_msg, status_cls = (
            "🚫",
            f"Significantly above historical max by {((proposed/hist_max - 1)*100):.1f}%",
            "wd-budget-over",
        )
    elif not in_range:
        pct_over = (proposed / hist_max - 1) * 100 if hist_max else 0
        status_icon, status_msg, status_cls = (
            "⚠️",
            f"Above historical max by {pct_over:.1f}%",
            "wd-budget-warn",
        )
    elif proposed < hist_min:
        pct_below = (1 - proposed / hist_min) * 100 if hist_min else 0
        status_icon, status_msg, status_cls = (
            "ℹ️",
            f"Below historical minimum by {pct_below:.1f}%",
            "",
        )
    else:
        status_icon, status_msg, status_cls = "✅", "Within historical range", "wd-budget-ok"

    st.markdown(
        f"""
        <div class="wd-card" style="margin-top:1rem;">
          <div class="wd-card-header">Validation Result — {dim_val}</div>
          <div class="{status_cls}" style="font-size:1.05rem;margin-bottom:0.75rem;">
            {status_icon} {status_msg}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
    with mc1:
        theme.styled_metric_card("Proposed", fmt_currency_compact(proposed))
    with mc2:
        theme.styled_metric_card("Historical Avg", fmt_currency_compact(hist_avg), border_color=theme.MEDIUM_BLUE)
    with mc3:
        theme.styled_metric_card("Historical Min", fmt_currency_compact(hist_min), border_color=theme.SUCCESS)
    with mc4:
        theme.styled_metric_card("Historical Max", fmt_currency_compact(hist_max), border_color=theme.DANGER)
    with mc5:
        theme.styled_metric_card("Last Year Actual", fmt_currency_compact(last_yr), border_color=theme.ACCENT_TEAL)

    # Bullet chart
    fig_b = go.Figure()
    fig_b.add_shape(type="rect", x0=hist_min, x1=hist_max, y0=-0.3, y1=0.3,
                    fillcolor=theme.LIGHT_BLUE, line_width=0)
    fig_b.add_shape(type="rect", x0=hist_min, x1=hist_avg, y0=-0.15, y1=0.15,
                    fillcolor=theme.MEDIUM_BLUE, line_width=0, opacity=0.4)
    fig_b.add_shape(type="line", x0=last_yr, x1=last_yr, y0=-0.4, y1=0.4,
                    line={"color": theme.SUCCESS, "width": 2, "dash": "dot"})
    fig_b.add_shape(type="line", x0=proposed, x1=proposed, y0=-0.45, y1=0.45,
                    line={"color": theme.DANGER if warning else theme.PRIMARY, "width": 3})
    fig_b.update_layout(
        **theme.get_plotly_layout("Proposed vs. Historical Range", height=130),
        xaxis_title="Posted Amount ($)",
        yaxis={"visible": False, "range": [-0.5, 0.5]},
        showlegend=False,
        margin={"l": 40, "r": 20, "t": 40, "b": 40},
        annotations=[
            {"x": proposed, "y": 0.48, "text": f"<b>Proposed<br>{fmt_currency_compact(proposed)}</b>",
             "showarrow": False, "font": {"color": theme.DARK_BLUE, "size": 11}, "yanchor": "bottom"},
            {"x": last_yr, "y": -0.5, "text": f"Last Year<br>{fmt_currency_compact(last_yr)}",
             "showarrow": False, "font": {"color": theme.SUCCESS, "size": 10}, "yanchor": "top"},
        ],
    )
    st.plotly_chart(fig_b, use_container_width=True)

    # Year-by-year bar chart
    yby = result.get("year_by_year", {})
    if yby:
        yby_df = pd.DataFrame({"Year": list(yby.keys()), "Actual": list(yby.values())})
        bar_colors = [
            theme.DANGER if v > hist_max else (theme.SUCCESS if v < hist_min else theme.PRIMARY)
            for v in yby_df["Actual"]
        ]
        fig_h = go.Figure(go.Bar(
            x=yby_df["Year"], y=yby_df["Actual"],
            marker_color=bar_colors,
            text=yby_df["Actual"].apply(fmt_currency_compact),
            textposition="outside",
            hovertemplate="%{x}<br>$%{y:,.2f}<extra></extra>",
        ))
        fig_h.add_shape(
            type="line", x0=-0.5, x1=len(yby_df) - 0.5, y0=proposed, y1=proposed,
            line={"color": theme.DARK_BLUE, "width": 2, "dash": "dash"},
        )
        fig_h.update_layout(
            **theme.get_plotly_layout("Historical Actuals by Year", height=280),
            yaxis_title="Posted Amount ($)",
        )
        st.plotly_chart(fig_h, use_container_width=True)

    # Export
    export_data = {
        "Dimension":          [dim_val],
        "Proposed Budget":    [proposed],
        "Historical Average": [hist_avg],
        "Historical Min":     [hist_min],
        "Historical Max":     [hist_max],
        "Last Year Actual":   [last_yr],
        "Delta vs Avg":       [delta_avg],
        "Delta vs Last Year": [delta_lst],
        "Status":             [status_msg],
    }
    yby_export = (
        pd.DataFrame({"Year": list(yby.keys()), "Actual": list(yby.values())})
        if yby else pd.DataFrame()
    )
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        pd.DataFrame(export_data).T.reset_index().rename(
            columns={"index": "Metric", 0: "Value"}
        ).to_excel(writer, sheet_name="Validation Summary", index=False)
        if not yby_export.empty:
            yby_export.to_excel(writer, sheet_name="Year-by-Year", index=False)
    st.download_button(
        "📥 Export Validation (Excel)",
        data=buf.getvalue(),
        file_name=f"budget_validation_{date.today()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ── Main render ───────────────────────────────────────────────────────────────

def render() -> None:
    theme.apply_workday_theme()
    theme.styled_header(
        "📈 Year-over-Year Comparison",
        subtitle="Compare historical spend across fiscal years and validate budget assumptions.",
    )

    if not db_exists():
        st.info("No database found. Run the ingest command first.")
        st.code("python -m app.db.ingest --data-dir ./data", language="bash")
        return

    conn  = get_connection()
    opts  = get_filter_options(conn)
    avail = _available_years(opts)
    _init_state(avail)

    # Controls card
    with st.container():
        st.markdown('<div class="wd-card">', unsafe_allow_html=True)
        st.markdown('<div class="wd-card-header">Analysis Parameters</div>', unsafe_allow_html=True)
        cc1, cc2 = st.columns(2)
        with cc1:
            st.multiselect(
                "Years to compare",
                avail,
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
        st.markdown("</div>", unsafe_allow_html=True)

    years    = st.session_state[_SS_YEARS]
    group_by = st.session_state[_SS_GROUP]

    # YoY comparison section
    _render_yoy(conn, years, group_by)

    # Budget validation section
    st.divider()
    st.markdown(
        f'<div style="font-size:1rem;font-weight:700;color:{theme.DARK_BLUE};'
        f'margin-bottom:0.75rem;">Budget Validation</div>',
        unsafe_allow_html=True,
    )
    _render_budget(conn, opts)

    conn.close()
