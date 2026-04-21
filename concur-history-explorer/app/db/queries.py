"""
Core query layer for Concur History Explorer.

All public functions accept a sqlite3.Connection and return a DataFrame or dict.
All SQL uses parameterized queries — never string-interpolated user input.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd

from app.db.connection import get_connection
from app.db.constants import (
    TBL_CATEGORIES, TBL_EMPLOYEE, TBL_ENTRY, TBL_FTS, TBL_REPORT,
    Cat, Emp, Fts, Rpe, Rpt,
)
from app.utils.image_handler import find_receipt_image


# ---------------------------------------------------------------------------
# Filter TypedDict
# ---------------------------------------------------------------------------

class ExpenseFilters(dict):
    """
    Optional filter keys:
        date_start      str  YYYY-MM-DD
        date_end        str  YYYY-MM-DD
        cost_center     str  exact match
        org_unit_1..6   str  exact match
        amount_min      float
        amount_max      float
        expense_type    str  EXP_KEY value
        expense_group   str  ICW group name
        expense_category str ICW category name
        employee_name   str  partial match on first/last
        approval_status str  status code e.g. A_APPR
    """


# ---------------------------------------------------------------------------
# Shared SQL fragments
# ---------------------------------------------------------------------------

_BASE_FROM = f"""
    FROM {TBL_ENTRY} re
    JOIN {TBL_REPORT} r   ON re.{Rpe.RPT_KEY} = r.{Rpt.KEY}
    JOIN {TBL_EMPLOYEE} e ON r.{Rpt.EMP_KEY}  = e.{Emp.KEY}
    LEFT JOIN {TBL_CATEGORIES} c ON re.{Rpe.EXP_KEY} = c.{Cat.CATEGORY_NAME}
"""

_SEARCH_SELECT = f"""
        e.{Emp.FIRST_NAME}         AS first_name,
        e.{Emp.LAST_NAME}          AS last_name,
        e.{Emp.ID}                 AS emp_id,
        r.{Rpt.RPT_ID}             AS rpt_id,
        r.{Rpt.NAME}               AS report_name,
        r.{Rpt.SUBMIT_DATE}        AS submit_date,
        re.{Rpe.TX_DATE}           AS transaction_date,
        re.{Rpe.EXP_KEY}           AS exp_key,
        c.{Cat.CATEGORY_NAME}      AS icw_category,
        c.{Cat.GROUP_NAME}         AS icw_group,
        re.{Rpe.VENDOR_DESC}       AS vendor_description,
        re.{Rpe.DESCRIPTION}       AS description,
        re.{Rpe.POSTED_AMOUNT}     AS posted_amount,
        re.{Rpe.CLAIMED_AMOUNT}    AS claimed_amount,
        re.{Rpe.APPROVED_AMOUNT}   AS approved_amount,
        re.{Rpe.CRN_KEY}           AS currency,
        r.{Rpt.COST_CENTER}        AS cost_center,
        e.{Emp.ORG_UNIT_1}         AS org_unit_1,
        r.{Rpt.STATUS_CODE}        AS approval_status,
        re.{Rpe.KEY}               AS rpe_key,
        r.{Rpt.KEY}                AS rpt_key,
        re.{Rpe.RECEIPT_IMAGE_ID}  AS receipt_image_id,
        re.{Rpe.ERECEIPT_IMAGE_ID} AS ereceipt_image_id
"""

# Valid group-by keys → SQL expressions (safe to interpolate; never from user input)
_GROUP_EXPRS: dict[str, str] = {
    "cost_center":          f"r.{Rpt.COST_CENTER}",
    "org_unit_1":           f"e.{Emp.ORG_UNIT_1}",
    "org_unit_2":           f"e.{Emp.ORG_UNIT_2}",
    "org_unit_3":           f"e.{Emp.ORG_UNIT_3}",
    "icw_expense_group":    f"c.{Cat.GROUP_NAME}",
    "icw_expense_category": f"c.{Cat.CATEGORY_NAME}",
    "expense_type":         f"re.{Rpe.EXP_KEY}",
    "employee":             f"e.{Emp.LAST_NAME} || ', ' || e.{Emp.FIRST_NAME}",
    "month":                f"strftime('%Y-%m', re.{Rpe.TX_DATE})",
    "quarter": (
        f"strftime('%Y', re.{Rpe.TX_DATE}) || '-Q' || "
        f"CASE "
        f"WHEN CAST(strftime('%m', re.{Rpe.TX_DATE}) AS INTEGER) BETWEEN 1 AND 3 THEN '1' "
        f"WHEN CAST(strftime('%m', re.{Rpe.TX_DATE}) AS INTEGER) BETWEEN 4 AND 6 THEN '2' "
        f"WHEN CAST(strftime('%m', re.{Rpe.TX_DATE}) AS INTEGER) BETWEEN 7 AND 9 THEN '3' "
        f"ELSE '4' END"
    ),
    "year": f"strftime('%Y', re.{Rpe.TX_DATE})",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fts_query(term: str) -> str:
    """Escape and format a user search term for FTS5 MATCH."""
    words = [w.replace('"', '""').strip() for w in term.split() if w.strip()]
    return " ".join(f'"{w}"' for w in words) if words else '""'


def _build_filters(filters: ExpenseFilters | None) -> tuple[str, list[Any]]:
    """Return (AND_clause_fragment, params) from a filters dict."""
    if not filters:
        return "", []

    clauses: list[str] = []
    params: list[Any] = []

    if filters.get("date_start"):
        clauses.append(f"re.{Rpe.TX_DATE} >= ?")
        params.append(filters["date_start"])
    if filters.get("date_end"):
        clauses.append(f"re.{Rpe.TX_DATE} <= ?")
        params.append(filters["date_end"])
    if filters.get("cost_center"):
        clauses.append(f"r.{Rpt.COST_CENTER} = ?")
        params.append(filters["cost_center"])
    for i in range(1, 7):
        val = filters.get(f"org_unit_{i}")
        if val:
            clauses.append(f"e.ORG_UNIT_{i} = ?")
            params.append(val)
    if filters.get("amount_min") is not None:
        clauses.append(f"re.{Rpe.POSTED_AMOUNT} >= ?")
        params.append(filters["amount_min"])
    if filters.get("amount_max") is not None:
        clauses.append(f"re.{Rpe.POSTED_AMOUNT} <= ?")
        params.append(filters["amount_max"])
    if filters.get("expense_type"):
        clauses.append(f"re.{Rpe.EXP_KEY} = ?")
        params.append(filters["expense_type"])
    if filters.get("expense_group"):
        clauses.append(f"c.{Cat.GROUP_NAME} = ?")
        params.append(filters["expense_group"])
    if filters.get("expense_category"):
        clauses.append(f"c.{Cat.CATEGORY_NAME} = ?")
        params.append(filters["expense_category"])
    if filters.get("employee_name"):
        like = f"%{filters['employee_name']}%"
        clauses.append(
            f"(e.{Emp.FIRST_NAME} LIKE ? OR e.{Emp.LAST_NAME} LIKE ?"
            f" OR e.{Emp.FIRST_NAME} || ' ' || e.{Emp.LAST_NAME} LIKE ?)"
        )
        params.extend([like, like, like])
    if filters.get("approval_status"):
        clauses.append(f"r.{Rpt.STATUS_CODE} = ?")
        params.append(filters["approval_status"])

    fragment = (" AND " + " AND ".join(clauses)) if clauses else ""
    return fragment, params


def _validated_group_expr(group_by: str) -> str:
    """Return the SQL expression for a group_by key; raise if unknown."""
    if group_by not in _GROUP_EXPRS:
        raise ValueError(f"Invalid group_by '{group_by}'. Choose from: {list(_GROUP_EXPRS)}")
    return _GROUP_EXPRS[group_by]


# ---------------------------------------------------------------------------
# 1. search_expenses
# ---------------------------------------------------------------------------

def search_expenses(
    conn: sqlite3.Connection,
    search_term: str = "",
    filters: ExpenseFilters | None = None,
    offset: int = 0,
    limit: int = 100,
) -> tuple[pd.DataFrame, int]:
    """
    Full-text + filtered search across expense entries.

    Returns (results_df, total_count). total_count excludes LIMIT/OFFSET
    and is used by the UI for pagination controls.
    """
    filter_sql, filter_params = _build_filters(filters)
    use_fts = bool(search_term and search_term.strip())

    if use_fts:
        fts_expr = _fts_query(search_term)
        data_sql = f"""
            WITH fts_hits AS (
                SELECT {Fts.RPE_KEY} AS rpe_key
                FROM {TBL_FTS}
                WHERE {TBL_FTS} MATCH ?
            )
            SELECT {_SEARCH_SELECT}
            {_BASE_FROM}
            JOIN fts_hits fh ON re.{Rpe.KEY} = fh.rpe_key
            WHERE 1=1 {filter_sql}
            ORDER BY re.{Rpe.TX_DATE} DESC
            LIMIT ? OFFSET ?
        """
        count_sql = f"""
            WITH fts_hits AS (
                SELECT {Fts.RPE_KEY} AS rpe_key
                FROM {TBL_FTS}
                WHERE {TBL_FTS} MATCH ?
            )
            SELECT COUNT(*)
            {_BASE_FROM}
            JOIN fts_hits fh ON re.{Rpe.KEY} = fh.rpe_key
            WHERE 1=1 {filter_sql}
        """
        data_params = [fts_expr, *filter_params, limit, offset]
        count_params = [fts_expr, *filter_params]
    else:
        data_sql = f"""
            SELECT {_SEARCH_SELECT}
            {_BASE_FROM}
            WHERE 1=1 {filter_sql}
            ORDER BY re.{Rpe.TX_DATE} DESC
            LIMIT ? OFFSET ?
        """
        count_sql = f"""
            SELECT COUNT(*)
            {_BASE_FROM}
            WHERE 1=1 {filter_sql}
        """
        data_params = [*filter_params, limit, offset]
        count_params = filter_params

    try:
        total = conn.execute(count_sql, count_params).fetchone()[0]
        df = pd.read_sql_query(data_sql, conn, params=data_params)
    except Exception:
        if use_fts:
            # FTS syntax error — fall back to non-FTS with same filters
            return search_expenses(conn, "", filters, offset, limit)
        raise

    return df, total


# ---------------------------------------------------------------------------
# 2. get_report_detail
# ---------------------------------------------------------------------------

def get_report_detail(conn: sqlite3.Connection, rpt_key: str) -> dict:
    """
    Return full detail for one expense report.

    Keys: report, employee, entries, images.
    Returns empty dict if rpt_key not found.
    """
    row = conn.execute(
        f"""
        SELECT
            r.*,
            e.{Emp.FIRST_NAME}  AS emp_first_name,
            e.{Emp.LAST_NAME}   AS emp_last_name,
            e.{Emp.EMAIL}       AS emp_email,
            e.{Emp.ID}          AS emp_id,
            e.{Emp.ORG_UNIT_1}  AS emp_org_unit_1,
            e.{Emp.ORG_UNIT_2}  AS emp_org_unit_2,
            e.{Emp.ORG_UNIT_3}  AS emp_org_unit_3,
            e.{Emp.ORG_UNIT_4}  AS emp_org_unit_4,
            e.{Emp.ORG_UNIT_5}  AS emp_org_unit_5,
            e.{Emp.ORG_UNIT_6}  AS emp_org_unit_6
        FROM {TBL_REPORT} r
        JOIN {TBL_EMPLOYEE} e ON r.{Rpt.EMP_KEY} = e.{Emp.KEY}
        WHERE r.{Rpt.KEY} = ?
        """,
        (rpt_key,),
    ).fetchone()

    if not row:
        return {}

    row_dict = dict(row)
    report = {k: v for k, v in row_dict.items() if not k.startswith("emp_")}
    employee = {
        "first_name": row_dict.get("emp_first_name"),
        "last_name":  row_dict.get("emp_last_name"),
        "email":      row_dict.get("emp_email"),
        "emp_id":     row_dict.get("emp_id"),
        "org_unit_1": row_dict.get("emp_org_unit_1"),
        "org_unit_2": row_dict.get("emp_org_unit_2"),
        "org_unit_3": row_dict.get("emp_org_unit_3"),
        "org_unit_4": row_dict.get("emp_org_unit_4"),
        "org_unit_5": row_dict.get("emp_org_unit_5"),
        "org_unit_6": row_dict.get("emp_org_unit_6"),
    }

    entry_rows = conn.execute(
        f"""
        SELECT re.*,
               c.{Cat.CATEGORY_NAME} AS icw_category,
               c.{Cat.GROUP_NAME}    AS icw_group,
               c.{Cat.INSTRUCTIONS}  AS icw_instructions
        FROM {TBL_ENTRY} re
        LEFT JOIN {TBL_CATEGORIES} c ON re.{Rpe.EXP_KEY} = c.{Cat.CATEGORY_NAME}
        WHERE re.{Rpe.RPT_KEY} = ?
        ORDER BY re.{Rpe.TX_DATE}, re.{Rpe.KEY}
        """,
        (rpt_key,),
    ).fetchall()

    entries = [dict(e) for e in entry_rows]

    images = []
    for entry in entries:
        path = find_receipt_image(entry.get(Rpe.RECEIPT_IMAGE_ID), entry.get(Rpe.ERECEIPT_IMAGE_ID))
        if path:
            images.append({"rpe_key": entry.get(Rpe.KEY), "path": str(path)})

    return {"report": report, "employee": employee, "entries": entries, "images": images}


# ---------------------------------------------------------------------------
# 3. get_expense_entry_detail
# ---------------------------------------------------------------------------

def get_expense_entry_detail(conn: sqlite3.Connection, entry_key: str) -> dict:
    """
    Return full detail for a single expense line item.

    Keys: entry, report, employee, category.
    Returns empty dict if entry_key not found.
    """
    row = conn.execute(
        f"""
        SELECT re.*,
               r.{Rpt.RPT_ID}        AS rpt_id,
               r.{Rpt.NAME}          AS report_name,
               r.{Rpt.SUBMIT_DATE}   AS submit_date,
               r.{Rpt.STATUS_CODE}   AS approval_status,
               r.{Rpt.COST_CENTER}   AS cost_center,
               r.{Rpt.TOTAL_APPROVED} AS report_total_approved,
               e.{Emp.FIRST_NAME}    AS emp_first_name,
               e.{Emp.LAST_NAME}     AS emp_last_name,
               e.{Emp.EMAIL}         AS emp_email,
               e.{Emp.ID}            AS emp_id,
               e.{Emp.ORG_UNIT_1}    AS emp_org_unit_1,
               e.{Emp.ORG_UNIT_2}    AS emp_org_unit_2,
               e.{Emp.ORG_UNIT_3}    AS emp_org_unit_3,
               c.{Cat.CATEGORY_NAME} AS icw_category,
               c.{Cat.GROUP_NAME}    AS icw_group,
               c.{Cat.DESCRIPTION}   AS icw_description,
               c.{Cat.INSTRUCTIONS}  AS icw_instructions
        FROM {TBL_ENTRY} re
        JOIN {TBL_REPORT} r   ON re.{Rpe.RPT_KEY} = r.{Rpt.KEY}
        JOIN {TBL_EMPLOYEE} e ON r.{Rpt.EMP_KEY}  = e.{Emp.KEY}
        LEFT JOIN {TBL_CATEGORIES} c ON re.{Rpe.EXP_KEY} = c.{Cat.CATEGORY_NAME}
        WHERE re.{Rpe.KEY} = ?
        """,
        (entry_key,),
    ).fetchone()

    if not row:
        return {}

    d = dict(row)
    entry = {k: v for k, v in d.items()
             if not k.startswith(("rpt_id", "report_", "submit_", "approval_",
                                  "cost_center", "emp_", "icw_"))}
    return {
        "entry": entry,
        "report": {
            "rpt_id":               d.get("rpt_id"),
            "report_name":          d.get("report_name"),
            "submit_date":          d.get("submit_date"),
            "approval_status":      d.get("approval_status"),
            "cost_center":          d.get("cost_center"),
            "report_total_approved": d.get("report_total_approved"),
        },
        "employee": {
            "first_name":  d.get("emp_first_name"),
            "last_name":   d.get("emp_last_name"),
            "email":       d.get("emp_email"),
            "emp_id":      d.get("emp_id"),
            "org_unit_1":  d.get("emp_org_unit_1"),
            "org_unit_2":  d.get("emp_org_unit_2"),
            "org_unit_3":  d.get("emp_org_unit_3"),
        },
        "category": {
            "icw_category":     d.get("icw_category"),
            "icw_group":        d.get("icw_group"),
            "icw_description":  d.get("icw_description"),
            "icw_instructions": d.get("icw_instructions"),
        },
    }


# ---------------------------------------------------------------------------
# 4. get_spend_summary
# ---------------------------------------------------------------------------

def get_spend_summary(
    conn: sqlite3.Connection,
    group_by: str | list[str] = "cost_center",
    filters: ExpenseFilters | None = None,
) -> pd.DataFrame:
    """
    Aggregated spend grouped by one or more dimensions.

    group_by accepts a key or list of keys from:
        cost_center, org_unit_1..3, icw_expense_group, icw_expense_category,
        expense_type, employee, month, quarter, year

    Returns columns: group_value(s), total_amount, transaction_count,
                     avg_amount, report_count.
    """
    if isinstance(group_by, str):
        group_by = [group_by]

    exprs = [(_validated_group_expr(g), g) for g in group_by]
    select_parts = [f"{expr} AS {alias}" for expr, alias in exprs]
    group_clause = ", ".join(expr for expr, _ in exprs)

    filter_sql, filter_params = _build_filters(filters)

    sql = f"""
        SELECT
            {', '.join(select_parts)},
            SUM(re.{Rpe.POSTED_AMOUNT})  AS total_amount,
            COUNT(*)                      AS transaction_count,
            AVG(re.{Rpe.POSTED_AMOUNT})  AS avg_amount,
            COUNT(DISTINCT r.{Rpt.KEY})  AS report_count
        {_BASE_FROM}
        WHERE re.{Rpe.POSTED_AMOUNT} IS NOT NULL {filter_sql}
        GROUP BY {group_clause}
        ORDER BY total_amount DESC
    """
    return pd.read_sql_query(sql, conn, params=filter_params)


# ---------------------------------------------------------------------------
# 5. get_trend_data
# ---------------------------------------------------------------------------

def get_trend_data(
    conn: sqlite3.Connection,
    group_by: str = "icw_expense_group",
    time_granularity: str = "month",
    filters: ExpenseFilters | None = None,
) -> pd.DataFrame:
    """
    Time-series aggregation for trend charts.

    time_granularity: "month" or "quarter"
    group_by: any key from _GROUP_EXPRS (used as the breakdown dimension)

    Returns: period, year, group_value, total_amount, transaction_count.
    """
    if time_granularity not in ("month", "quarter"):
        raise ValueError("time_granularity must be 'month' or 'quarter'")

    period_expr = _GROUP_EXPRS[time_granularity]
    group_expr = _validated_group_expr(group_by)
    year_expr = _GROUP_EXPRS["year"]
    filter_sql, filter_params = _build_filters(filters)

    sql = f"""
        SELECT
            {period_expr}   AS period,
            {year_expr}     AS year,
            {group_expr}    AS group_value,
            SUM(re.{Rpe.POSTED_AMOUNT})  AS total_amount,
            COUNT(*)                      AS transaction_count
        {_BASE_FROM}
        WHERE re.{Rpe.TX_DATE} IS NOT NULL
          AND re.{Rpe.POSTED_AMOUNT} IS NOT NULL
          {filter_sql}
        GROUP BY period, year, group_value
        ORDER BY period, group_value
    """
    return pd.read_sql_query(sql, conn, params=filter_params)


# ---------------------------------------------------------------------------
# 6. get_budget_comparison
# ---------------------------------------------------------------------------

def get_budget_comparison(
    conn: sqlite3.Connection,
    dimension: str,
    dimension_value: str,
    proposed_amount: float,
) -> dict:
    """
    Compare a proposed annual spend against historical actuals.

    dimension: "cost_center" or "icw_expense_category"
    dimension_value: the specific cost center code or ICW category name
    proposed_amount: the amount being budgeted for the upcoming year

    Returns: historical_avg, historical_min, historical_max, last_year_actual,
             year_by_year, proposed, delta_vs_avg, delta_vs_last_year,
             within_range, warning (True if >20% above historical max).
    """
    _DIM_MAP = {
        "cost_center":          f"r.{Rpt.COST_CENTER}",
        "icw_expense_category": f"c.{Cat.CATEGORY_NAME}",
        "icw_expense_group":    f"c.{Cat.GROUP_NAME}",
        "org_unit_1":           f"e.{Emp.ORG_UNIT_1}",
    }
    if dimension not in _DIM_MAP:
        raise ValueError(f"dimension must be one of {list(_DIM_MAP)}")

    dim_expr = _DIM_MAP[dimension]

    sql = f"""
        SELECT
            strftime('%Y', re.{Rpe.TX_DATE}) AS year,
            SUM(re.{Rpe.POSTED_AMOUNT})       AS total_amount
        {_BASE_FROM}
        WHERE {dim_expr} = ?
          AND re.{Rpe.TX_DATE} IS NOT NULL
          AND re.{Rpe.POSTED_AMOUNT} IS NOT NULL
        GROUP BY year
        ORDER BY year
    """
    rows = conn.execute(sql, (dimension_value,)).fetchall()

    if not rows:
        return {
            "historical_avg": 0, "historical_min": 0, "historical_max": 0,
            "last_year_actual": 0, "year_by_year": {},
            "proposed": proposed_amount, "delta_vs_avg": proposed_amount,
            "delta_vs_last_year": proposed_amount, "within_range": True, "warning": False,
        }

    year_by_year = {r["year"]: r["total_amount"] for r in rows}
    amounts = list(year_by_year.values())
    hist_avg = sum(amounts) / len(amounts)
    hist_min = min(amounts)
    hist_max = max(amounts)
    last_year = amounts[-1]

    return {
        "historical_avg":      round(hist_avg, 2),
        "historical_min":      round(hist_min, 2),
        "historical_max":      round(hist_max, 2),
        "last_year_actual":    round(last_year, 2),
        "year_by_year":        year_by_year,
        "proposed":            proposed_amount,
        "delta_vs_avg":        round(proposed_amount - hist_avg, 2),
        "delta_vs_last_year":  round(proposed_amount - last_year, 2),
        "within_range":        proposed_amount <= hist_max,
        "warning":             proposed_amount > hist_max * 1.20,
    }


# ---------------------------------------------------------------------------
# 7. get_filter_options  (module-level cache)
# ---------------------------------------------------------------------------

_filter_cache: dict | None = None


def get_filter_options(conn: sqlite3.Connection | None = None) -> dict:
    """
    Return distinct values for all UI filter dropdowns.

    Result is cached in-process after the first call.
    Call clear_filter_cache() after re-ingest to refresh.
    """
    global _filter_cache
    if _filter_cache is not None:
        return _filter_cache

    if conn is None:
        conn = get_connection()

    def _distinct(sql: str, params: list | None = None) -> list:
        rows = conn.execute(sql, params or []).fetchall()
        return [r[0] for r in rows if r[0] is not None]

    cost_centers = _distinct(
        f"SELECT DISTINCT {Rpt.COST_CENTER} FROM {TBL_REPORT} "
        f"WHERE {Rpt.COST_CENTER} IS NOT NULL ORDER BY {Rpt.COST_CENTER}"
    )

    org_units: dict[str, list] = {}
    for i in range(1, 7):
        col = f"ORG_UNIT_{i}"
        org_units[f"org_unit_{i}"] = _distinct(
            f"SELECT DISTINCT {col} FROM {TBL_EMPLOYEE} "
            f"WHERE {col} IS NOT NULL ORDER BY {col}"
        )

    expense_types = _distinct(
        f"""
        SELECT DISTINCT re.{Rpe.EXP_KEY} || ' — ' || COALESCE(c.{Cat.CATEGORY_NAME}, re.{Rpe.EXP_KEY})
        FROM {TBL_ENTRY} re
        LEFT JOIN {TBL_CATEGORIES} c ON re.{Rpe.EXP_KEY} = c.{Cat.CATEGORY_NAME}
        WHERE re.{Rpe.EXP_KEY} IS NOT NULL
        ORDER BY 1
        """
    )

    expense_groups = _distinct(
        f"SELECT DISTINCT {Cat.GROUP_NAME} FROM {TBL_CATEGORIES} ORDER BY {Cat.GROUP_NAME}"
    )

    expense_categories = _distinct(
        f"SELECT DISTINCT {Cat.CATEGORY_NAME} FROM {TBL_CATEGORIES} ORDER BY {Cat.CATEGORY_NAME}"
    )

    employees = _distinct(
        f"""
        SELECT DISTINCT {Emp.LAST_NAME} || ', ' || {Emp.FIRST_NAME}
        FROM {TBL_EMPLOYEE}
        WHERE {Emp.LAST_NAME} IS NOT NULL
        ORDER BY {Emp.LAST_NAME}, {Emp.FIRST_NAME}
        """
    )

    date_range_row = conn.execute(
        f"SELECT MIN({Rpe.TX_DATE}), MAX({Rpe.TX_DATE}) FROM {TBL_ENTRY}"
    ).fetchone()

    approval_statuses = _distinct(
        f"SELECT DISTINCT {Rpt.STATUS_CODE} FROM {TBL_REPORT} "
        f"WHERE {Rpt.STATUS_CODE} IS NOT NULL ORDER BY {Rpt.STATUS_CODE}"
    )

    _filter_cache = {
        "cost_centers":        cost_centers,
        "org_units":           org_units,
        "expense_types":       expense_types,
        "expense_groups":      expense_groups,
        "expense_categories":  expense_categories,
        "employees":           employees,
        "date_min":            date_range_row[0] if date_range_row else None,
        "date_max":            date_range_row[1] if date_range_row else None,
        "approval_statuses":   approval_statuses,
    }
    return _filter_cache


def clear_filter_cache() -> None:
    """Invalidate the filter options cache (call after re-ingest)."""
    global _filter_cache
    _filter_cache = None


# ---------------------------------------------------------------------------
# 8. export_to_dataframe
# ---------------------------------------------------------------------------

_EXPORT_SELECT = f"""
        e.{Emp.FIRST_NAME}          AS "First Name",
        e.{Emp.LAST_NAME}           AS "Last Name",
        e.{Emp.ID}                  AS "Employee ID",
        e.{Emp.EMAIL}               AS "Email",
        e.{Emp.ORG_UNIT_1}          AS "Department",
        r.{Rpt.RPT_ID}              AS "Report ID",
        r.{Rpt.NAME}                AS "Report Name",
        r.{Rpt.SUBMIT_DATE}         AS "Submit Date",
        r.{Rpt.STATUS_CODE}         AS "Approval Status",
        r.{Rpt.COST_CENTER}         AS "Cost Center",
        re.{Rpe.TX_DATE}            AS "Transaction Date",
        re.{Rpe.EXP_KEY}            AS "Expense Type Code",
        c.{Cat.CATEGORY_NAME}       AS "ICW Category",
        c.{Cat.GROUP_NAME}          AS "ICW Group",
        re.{Rpe.VENDOR_DESC}        AS "Vendor",
        re.{Rpe.DESCRIPTION}        AS "Description",
        re.{Rpe.TX_AMOUNT}          AS "Transaction Amount",
        re.{Rpe.CLAIMED_AMOUNT}     AS "Claimed Amount",
        re.{Rpe.POSTED_AMOUNT}      AS "Posted Amount",
        re.{Rpe.APPROVED_AMOUNT}    AS "Approved Amount",
        re.{Rpe.CRN_KEY}            AS "Currency",
        re.{Rpe.IS_PERSONAL}        AS "Personal",
        re.{Rpe.IS_BILLABLE}        AS "Billable",
        re.{Rpe.RECEIPT_REQUIRED}   AS "Receipt Required",
        re.{Rpe.RECEIPT_RECEIVED}   AS "Receipt Received",
        re.{Rpe.FROM_LOCATION}      AS "From Location",
        re.{Rpe.TO_LOCATION}        AS "To Location",
        re.{Rpe.HOTEL_CHECKIN}      AS "Hotel Check-In",
        re.{Rpe.HOTEL_CHECKOUT}     AS "Hotel Check-Out",
        re.{Rpe.CAR_RENTAL_DAYS}    AS "Car Rental Days",
        re.{Rpe.ATTENDEE_COUNT}     AS "Attendee Count",
        re.{Rpe.EXCEPTION_COUNT}    AS "Exception Count",
        re.{Rpe.KEY}                AS "Entry Key",
        r.{Rpt.KEY}                 AS "Report Key"
"""


def export_to_dataframe(
    conn: sqlite3.Connection,
    query_type: str = "search",
    filters: ExpenseFilters | None = None,
    group_by: str = "cost_center",
    time_granularity: str = "month",
) -> pd.DataFrame:
    """
    Non-paginated export for CSV/Excel download.

    query_type: "search"        — full entry-level export with all columns
                "spend_summary" — aggregated spend grouped by group_by
                "trend"         — time-series data
    """
    if query_type == "spend_summary":
        return get_spend_summary(conn, group_by, filters)

    if query_type == "trend":
        return get_trend_data(conn, group_by, time_granularity, filters)

    # Default: full entry-level export
    filter_sql, filter_params = _build_filters(filters)
    sql = f"""
        SELECT {_EXPORT_SELECT}
        {_BASE_FROM}
        WHERE 1=1 {filter_sql}
        ORDER BY re.{Rpe.TX_DATE} DESC, e.{Emp.LAST_NAME}, e.{Emp.FIRST_NAME}
    """
    return pd.read_sql_query(sql, conn, params=filter_params)
