"""
Translate Concur DDL (Oracle/SQL Server syntax) to SQLite-compatible DDL,
then create all tables and indexes.
"""

import re
import sqlite3
import logging
from pathlib import Path

from app.db.constants import TBL_EMPLOYEE, TBL_REPORT, TBL_ENTRY, TBL_CATEGORIES, TBL_FTS, Emp, Rpt, Rpe, Fts

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type mapping: Oracle / SQL Server → SQLite
# ---------------------------------------------------------------------------
_TYPE_MAP = [
    (r"\bNVARCHAR2?\s*\(\d+\)", "TEXT"),
    (r"\bVARCHAR2?\s*\(\d+\)", "TEXT"),
    (r"\bCHAR\s*\(\d+\)", "TEXT"),
    (r"\bNUMBER\s*\(\d+\s*,\s*\d+\)", "REAL"),
    (r"\bNUMBER\s*\(\d+\)", "INTEGER"),
    (r"\bNUMBER\b", "REAL"),
    (r"\bFLOAT\b", "REAL"),
    (r"\bDECIMAL\s*\(\d+\s*,\s*\d+\)", "REAL"),
    (r"\bINT\b", "INTEGER"),
    (r"\bBIGINT\b", "INTEGER"),
    (r"\bSMALLINT\b", "INTEGER"),
    (r"\bTINYINT\b", "INTEGER"),
    (r"\bBIT\b", "INTEGER"),
    (r"\bDATETIME2?\b", "TEXT"),
    (r"\bDATETIMEOFFSET\b", "TEXT"),
    (r"\bTIMESTAMP.*?(?=\s|,|\))", "TEXT"),
    (r"\bDATE\b", "TEXT"),
    (r"\bTIME\b", "TEXT"),
    (r"\bCLOB\b", "TEXT"),
    (r"\bNCLOB\b", "TEXT"),
    (r"\bBLOB\b", "BLOB"),
    (r"\bRAW\s*\(\d+\)", "BLOB"),
    (r"\bUNIQUEIDENTIFIER\b", "TEXT"),
    (r"\bXML\b", "TEXT"),
    (r"\bIMAGE\b", "BLOB"),
    (r"\bMONEY\b", "REAL"),
    (r"\bSMALLMONEY\b", "REAL"),
]

_STRIP_CLAUSES = re.compile(
    r"\bDEFAULT\s+\S+|"
    r"\bCONSTRAINT\s+\w+\s+(?:PRIMARY KEY|UNIQUE|CHECK|REFERENCES)[^,)]*|"
    r"\bCHECK\s*\([^)]*\)|"
    r"\bREFERENCES\s+\w+\s*\([^)]*\)|"
    r"\bON\s+(?:DELETE|UPDATE)\s+\w+|"
    r"\bNOT\s+FOR\s+REPLICATION|"
    r"\bIDENTITY\s*\(\d+\s*,\s*\d+\)|"
    r"\bIDENTITY\b|"
    r"\bAUTOINCREMENT\b|"
    r"\bAUTO_INCREMENT\b|"
    r"\bWITH\s*\([^)]*\)|"
    r"\bON\s+\[\w+\]",
    re.IGNORECASE,
)


def _translate_ddl(sql: str) -> str | None:
    """Convert a single CREATE TABLE statement to SQLite syntax. Returns None to skip."""
    sql = sql.strip().rstrip(";")

    # Skip non-CREATE-TABLE statements
    if not re.match(r"CREATE\s+TABLE", sql, re.IGNORECASE):
        return None

    # Remove schema prefix: dbo.TableName → TableName
    sql = re.sub(r"CREATE\s+TABLE\s+(?:\w+\.)?(\w+)", r"CREATE TABLE IF NOT EXISTS \1", sql, flags=re.IGNORECASE)

    # Strip Oracle storage / tablespace clauses after the closing paren
    sql = re.sub(r"\)\s*(?:TABLESPACE|STORAGE|PCTFREE|INITRANS|LOGGING|NOCOMPRESS|CACHE|ENABLE).*$", ")", sql, flags=re.IGNORECASE | re.DOTALL)

    # Apply type replacements
    for pattern, replacement in _TYPE_MAP:
        sql = re.sub(pattern, replacement, sql, flags=re.IGNORECASE)

    # Strip unsupported column/table constraints
    sql = _STRIP_CLAUSES.sub("", sql)

    # Collapse multiple spaces
    sql = re.sub(r"[ \t]{2,}", " ", sql)

    return sql


def translate_ddl_file(ddl_text: str) -> list[str]:
    """Split a DDL file into individual statements and translate each."""
    # Split on statement boundaries (semicolons or GO)
    raw_statements = re.split(r";\s*\n|^\s*GO\s*$", ddl_text, flags=re.MULTILINE)
    results = []
    for stmt in raw_statements:
        stmt = stmt.strip()
        if not stmt:
            continue
        translated = _translate_ddl(stmt)
        if translated:
            results.append(translated)
    return results


# ---------------------------------------------------------------------------
# Hardcoded fallback DDL for the three key tables (used when DDL.zip absent)
# ---------------------------------------------------------------------------
CORE_TABLES_DDL = """
CREATE TABLE IF NOT EXISTS ct_employee (
    EMP_KEY TEXT PRIMARY KEY,
    EMP_ID TEXT,
    LOGIN_ID TEXT,
    FIRST_NAME TEXT,
    MIDDLE_NAME TEXT,
    MI TEXT,
    LAST_NAME TEXT,
    EMAIL_ADDRESS TEXT,
    CRN_KEY TEXT,
    LOCALE_CODE TEXT,
    CTRY_CODE TEXT,
    CTRY_SUB_CODE TEXT,
    LEDGER_KEY TEXT,
    LN_KEY TEXT,
    ACTIVE TEXT,
    ORG_UNIT_1 TEXT,
    ORG_UNIT_2 TEXT,
    ORG_UNIT_3 TEXT,
    ORG_UNIT_4 TEXT,
    ORG_UNIT_5 TEXT,
    ORG_UNIT_6 TEXT,
    CUSTOM1 TEXT, CUSTOM2 TEXT, CUSTOM3 TEXT, CUSTOM4 TEXT, CUSTOM5 TEXT,
    CUSTOM6 TEXT, CUSTOM7 TEXT, CUSTOM8 TEXT, CUSTOM9 TEXT, CUSTOM10 TEXT,
    CUSTOM11 TEXT, CUSTOM12 TEXT, CUSTOM13 TEXT, CUSTOM14 TEXT, CUSTOM15 TEXT,
    CUSTOM16 TEXT, CUSTOM17 TEXT, CUSTOM18 TEXT, CUSTOM19 TEXT, CUSTOM20 TEXT,
    CUSTOM21 TEXT,
    SYNC_GUID TEXT,
    LAST_MODIFIED TEXT,
    PMT_METHOD_CODE TEXT,
    CASH_ADVANCE_ACCOUNT_CODE TEXT,
    BI_MANAGER_KEY TEXT,
    BI_HIER_NODE_KEY TEXT,
    IS_TEST_EMP TEXT,
    SYSTEM_RECORD TEXT
);

CREATE TABLE IF NOT EXISTS ct_report (
    RPT_KEY TEXT PRIMARY KEY,
    EMP_KEY TEXT,
    RPT_ID TEXT,
    RPT_NAME TEXT,
    SUBMIT_DATE TEXT,
    APPROVAL_STATUS_CODE TEXT,
    APPROVAL_STATUS_NAME TEXT,
    APPROVED_DATE TEXT,
    TOTAL_CLAIMED_AMOUNT REAL,
    TOTAL_APPROVED_AMOUNT REAL,
    TOTAL_POSTED_AMOUNT REAL,
    CRN_KEY TEXT,
    LEDGER_KEY TEXT,
    COST_CENTER TEXT,
    ORG_UNIT_1 TEXT,
    ORG_UNIT_2 TEXT,
    ORG_UNIT_3 TEXT,
    ORG_UNIT_4 TEXT,
    ORG_UNIT_5 TEXT,
    ORG_UNIT_6 TEXT,
    CREATION_DATE TEXT,
    LAST_MODIFIED TEXT,
    SYNC_GUID TEXT,
    CUSTOM1 TEXT, CUSTOM2 TEXT, CUSTOM3 TEXT, CUSTOM4 TEXT, CUSTOM5 TEXT,
    CUSTOM6 TEXT, CUSTOM7 TEXT, CUSTOM8 TEXT, CUSTOM9 TEXT, CUSTOM10 TEXT,
    CUSTOM11 TEXT, CUSTOM12 TEXT, CUSTOM13 TEXT, CUSTOM14 TEXT, CUSTOM15 TEXT,
    CUSTOM16 TEXT, CUSTOM17 TEXT, CUSTOM18 TEXT, CUSTOM19 TEXT, CUSTOM20 TEXT
);

CREATE TABLE IF NOT EXISTS ct_report_entry (
    RPE_KEY TEXT PRIMARY KEY,
    RPT_KEY TEXT,
    TRANSACTION_TYPE TEXT,
    EXP_KEY TEXT,
    FORM_KEY TEXT,
    RECEIPT_RECEIVED TEXT,
    RECEIPT_TYPE TEXT,
    RECEIPT_REQUIRED TEXT,
    TRANSACTION_AMOUNT REAL,
    IMAGE_REQUIRED TEXT,
    CRN_KEY TEXT,
    EXCHANGE_RATE REAL,
    EXCHANGE_RATE_DIRECTION TEXT,
    POSTED_AMOUNT REAL,
    IS_PERSONAL TEXT,
    TRAVEL_ALLOWANCE TEXT,
    FOREIGN_OR_DOMESTIC TEXT,
    HAS_VAT TEXT,
    ATTENDEE_COUNT INTEGER,
    COMMENT_COUNT INTEGER,
    EXCEPTION_COUNT INTEGER,
    TRANSACTION_DATE TEXT,
    CLAIMED_AMOUNT REAL,
    ADJUSTED_AMOUNT REAL,
    APPROVED_AMOUNT REAL,
    JOURNAL_SPLITTING_AMOUNT REAL,
    DESCRIPTION TEXT,
    VEN_LI_KEY TEXT,
    VENDOR_DESCRIPTION TEXT,
    LN_KEY TEXT,
    PARENT_RPE_KEY TEXT,
    CCT_KEY TEXT,
    ALLOCATION_STATE TEXT,
    ALLOCATION_VERSION TEXT,
    ORG_UNIT_1 TEXT, ORG_UNIT_2 TEXT, ORG_UNIT_3 TEXT,
    ORG_UNIT_4 TEXT, ORG_UNIT_5 TEXT, ORG_UNIT_6 TEXT,
    FROM_LOCATION TEXT,
    TO_LOCATION TEXT,
    CUSTOM1 TEXT, CUSTOM2 TEXT, CUSTOM3 TEXT, CUSTOM4 TEXT, CUSTOM5 TEXT,
    CUSTOM6 TEXT, CUSTOM7 TEXT, CUSTOM8 TEXT, CUSTOM9 TEXT, CUSTOM10 TEXT,
    CUSTOM11 TEXT, CUSTOM12 TEXT, CUSTOM13 TEXT, CUSTOM14 TEXT, CUSTOM15 TEXT,
    CUSTOM16 TEXT, CUSTOM17 TEXT, CUSTOM18 TEXT, CUSTOM19 TEXT, CUSTOM20 TEXT,
    CUSTOM21 TEXT, CUSTOM22 TEXT, CUSTOM23 TEXT, CUSTOM24 TEXT, CUSTOM25 TEXT,
    CUSTOM26 TEXT, CUSTOM27 TEXT, CUSTOM28 TEXT, CUSTOM29 TEXT, CUSTOM30 TEXT,
    CUSTOM31 TEXT, CUSTOM32 TEXT, CUSTOM33 TEXT, CUSTOM34 TEXT, CUSTOM35 TEXT,
    CUSTOM36 TEXT, CUSTOM37 TEXT, CUSTOM38 TEXT, CUSTOM39 TEXT, CUSTOM40 TEXT,
    SYNC_GUID TEXT,
    LAST_MODIFIED TEXT,
    TICKET_NUMBER TEXT,
    AIRLINE_SVC_CODE TEXT,
    CAR_RENTAL_DAYS INTEGER,
    ERECEIPT_IMAGE_POSTED TEXT,
    ERECEIPT_TYPE TEXT,
    IS_BILLABLE TEXT,
    RECEIPT_IMAGE_ID TEXT,
    ERECEIPT_IMAGE_ID TEXT,
    TOTAL_TAX_POSTED_AMOUNT REAL,
    TOTAL_TAX_ADJUSTED_AMOUNT REAL,
    TOTAL_RECLAIM_POSTED_AMOUNT REAL,
    TOTAL_RECLAIM_ADJUSTED_AMOUNT REAL,
    HOTEL_CHECKIN_DATE TEXT,
    HOTEL_CHECKOUT_DATE TEXT,
    CREATION_DATE TEXT,
    BUDGET_ACCRUAL_DATE TEXT,
    MERCHANT_TAX_ID TEXT
);
"""

ICW_CATEGORIES_DDL = """
CREATE TABLE IF NOT EXISTS icw_expense_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name TEXT NOT NULL,
    category_name TEXT NOT NULL,
    description TEXT,
    instructions TEXT
);
"""

def _idx(name: str, table: str, col: str) -> str:
    return f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({col})"


INDEXES_DDL = [
    # ct_employee
    _idx("idx_emp_firstname",  TBL_EMPLOYEE, Emp.FIRST_NAME),
    _idx("idx_emp_lastname",   TBL_EMPLOYEE, Emp.LAST_NAME),
    _idx("idx_emp_id",         TBL_EMPLOYEE, Emp.ID),
    _idx("idx_emp_org1",       TBL_EMPLOYEE, Emp.ORG_UNIT_1),
    _idx("idx_emp_org2",       TBL_EMPLOYEE, Emp.ORG_UNIT_2),
    _idx("idx_emp_org3",       TBL_EMPLOYEE, Emp.ORG_UNIT_3),
    _idx("idx_emp_org4",       TBL_EMPLOYEE, Emp.ORG_UNIT_4),
    _idx("idx_emp_org5",       TBL_EMPLOYEE, Emp.ORG_UNIT_5),
    _idx("idx_emp_org6",       TBL_EMPLOYEE, Emp.ORG_UNIT_6),
    # ct_report
    _idx("idx_rpt_empkey",     TBL_REPORT, Rpt.EMP_KEY),
    _idx("idx_rpt_id",         TBL_REPORT, Rpt.RPT_ID),
    _idx("idx_rpt_submit",     TBL_REPORT, Rpt.SUBMIT_DATE),
    _idx("idx_rpt_approval",   TBL_REPORT, Rpt.STATUS_CODE),
    _idx("idx_rpt_ledger",     TBL_REPORT, Rpt.LEDGER_KEY),
    _idx("idx_rpt_costcenter", TBL_REPORT, Rpt.COST_CENTER),
    # ct_report_entry
    _idx("idx_rpe_rptkey",     TBL_ENTRY, Rpe.RPT_KEY),
    _idx("idx_rpe_txdate",     TBL_ENTRY, Rpe.TX_DATE),
    _idx("idx_rpe_expkey",     TBL_ENTRY, Rpe.EXP_KEY),
    _idx("idx_rpe_vendor",     TBL_ENTRY, Rpe.VENDOR_DESC),
    _idx("idx_rpe_posted",     TBL_ENTRY, Rpe.POSTED_AMOUNT),
    _idx("idx_rpe_claimed",    TBL_ENTRY, Rpe.CLAIMED_AMOUNT),
    _idx("idx_rpe_receipt",    TBL_ENTRY, Rpe.RECEIPT_IMAGE_ID),
    _idx("idx_rpe_ereceipt",   TBL_ENTRY, Rpe.ERECEIPT_IMAGE_ID),
    _idx("idx_rpe_org1",       TBL_ENTRY, Rpe.ORG_UNIT_1),
    _idx("idx_rpe_org2",       TBL_ENTRY, Rpe.ORG_UNIT_2),
    _idx("idx_rpe_org3",       TBL_ENTRY, Rpe.ORG_UNIT_3),
    _idx("idx_rpe_org4",       TBL_ENTRY, Rpe.ORG_UNIT_4),
    _idx("idx_rpe_org5",       TBL_ENTRY, Rpe.ORG_UNIT_5),
    _idx("idx_rpe_org6",       TBL_ENTRY, Rpe.ORG_UNIT_6),
]

FTS_DDL = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS {TBL_FTS} USING fts5(
    {Fts.EMP_KEY} UNINDEXED,
    {Fts.RPT_KEY} UNINDEXED,
    {Fts.RPE_KEY} UNINDEXED,
    {Fts.FIRST_NAME},
    {Fts.LAST_NAME},
    {Fts.RPT_NAME},
    {Fts.VENDOR_DESC},
    {Fts.DESCRIPTION},
    {Fts.ORG_UNIT_1},
    {Fts.ORG_UNIT_2},
    {Fts.ORG_UNIT_3},
    {Fts.ORG_UNIT_4},
    {Fts.ORG_UNIT_5},
    {Fts.ORG_UNIT_6},
    tokenize='porter unicode61'
);
"""


def apply_schema(conn: sqlite3.Connection, extra_ddl_statements: list[str] | None = None) -> None:
    """Create all tables, indexes, and FTS table."""
    cur = conn.cursor()

    for stmt in CORE_TABLES_DDL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            cur.execute(stmt)

    cur.execute(ICW_CATEGORIES_DDL)

    if extra_ddl_statements:
        for stmt in extra_ddl_statements:
            try:
                cur.execute(stmt)
            except sqlite3.Error as e:
                logger.warning("Skipping DDL statement (%s): %s", e, stmt[:80])

    for idx in INDEXES_DDL:
        cur.execute(idx)

    cur.execute(FTS_DDL)
    conn.commit()
    logger.info("Schema applied successfully.")
