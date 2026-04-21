"""
Single source of truth for all database table names and column names.

Every module that issues SQL or references schema identifiers imports from here.
Never hardcode table or column name strings in queries, indexes, or UI pages.
"""

# ── Table names ───────────────────────────────────────────────────────────────

TBL_EMPLOYEE   = "ct_employee"
TBL_REPORT     = "ct_report"
TBL_ENTRY      = "ct_report_entry"
TBL_CATEGORIES = "icw_expense_categories"
TBL_FTS        = "fts_expenses"

# Convenience tuple for iterating all core Concur tables
CORE_TABLES = (TBL_EMPLOYEE, TBL_REPORT, TBL_ENTRY)


# ── ct_employee ───────────────────────────────────────────────────────────────

class Emp:
    KEY           = "EMP_KEY"
    ID            = "EMP_ID"
    LOGIN_ID      = "LOGIN_ID"
    FIRST_NAME    = "FIRST_NAME"
    MIDDLE_NAME   = "MIDDLE_NAME"
    MI            = "MI"
    LAST_NAME     = "LAST_NAME"
    EMAIL         = "EMAIL_ADDRESS"
    CRN_KEY       = "CRN_KEY"
    LOCALE_CODE   = "LOCALE_CODE"
    CTRY_CODE     = "CTRY_CODE"
    CTRY_SUB      = "CTRY_SUB_CODE"
    LEDGER_KEY    = "LEDGER_KEY"
    LN_KEY        = "LN_KEY"
    ACTIVE        = "ACTIVE"
    ORG_UNIT_1    = "ORG_UNIT_1"
    ORG_UNIT_2    = "ORG_UNIT_2"
    ORG_UNIT_3    = "ORG_UNIT_3"
    ORG_UNIT_4    = "ORG_UNIT_4"
    ORG_UNIT_5    = "ORG_UNIT_5"
    ORG_UNIT_6    = "ORG_UNIT_6"
    SYNC_GUID     = "SYNC_GUID"
    LAST_MODIFIED = "LAST_MODIFIED"
    PMT_METHOD    = "PMT_METHOD_CODE"
    CASH_ADV_ACCT = "CASH_ADVANCE_ACCOUNT_CODE"
    MANAGER_KEY   = "BI_MANAGER_KEY"
    HIER_NODE     = "BI_HIER_NODE_KEY"
    IS_TEST       = "IS_TEST_EMP"
    SYSTEM_RECORD = "SYSTEM_RECORD"

    ORG_UNITS = ("ORG_UNIT_1", "ORG_UNIT_2", "ORG_UNIT_3",
                 "ORG_UNIT_4", "ORG_UNIT_5", "ORG_UNIT_6")


# ── ct_report ─────────────────────────────────────────────────────────────────

class Rpt:
    KEY           = "RPT_KEY"
    EMP_KEY       = "EMP_KEY"
    RPT_ID        = "RPT_ID"
    NAME          = "RPT_NAME"
    SUBMIT_DATE   = "SUBMIT_DATE"
    STATUS_CODE   = "APPROVAL_STATUS_CODE"
    STATUS_NAME   = "APPROVAL_STATUS_NAME"
    APPROVED_DATE = "APPROVED_DATE"
    TOTAL_CLAIMED  = "TOTAL_CLAIMED_AMOUNT"
    TOTAL_APPROVED = "TOTAL_APPROVED_AMOUNT"
    TOTAL_POSTED   = "TOTAL_POSTED_AMOUNT"
    CRN_KEY       = "CRN_KEY"
    LEDGER_KEY    = "LEDGER_KEY"
    COST_CENTER   = "COST_CENTER"
    ORG_UNIT_1    = "ORG_UNIT_1"
    ORG_UNIT_2    = "ORG_UNIT_2"
    ORG_UNIT_3    = "ORG_UNIT_3"
    ORG_UNIT_4    = "ORG_UNIT_4"
    ORG_UNIT_5    = "ORG_UNIT_5"
    ORG_UNIT_6    = "ORG_UNIT_6"
    CREATION_DATE = "CREATION_DATE"
    LAST_MODIFIED = "LAST_MODIFIED"
    SYNC_GUID     = "SYNC_GUID"

    ORG_UNITS = ("ORG_UNIT_1", "ORG_UNIT_2", "ORG_UNIT_3",
                 "ORG_UNIT_4", "ORG_UNIT_5", "ORG_UNIT_6")


# ── ct_report_entry ───────────────────────────────────────────────────────────

class Rpe:
    KEY                 = "RPE_KEY"
    RPT_KEY             = "RPT_KEY"
    TX_TYPE             = "TRANSACTION_TYPE"
    EXP_KEY             = "EXP_KEY"
    FORM_KEY            = "FORM_KEY"
    RECEIPT_RECEIVED    = "RECEIPT_RECEIVED"
    RECEIPT_TYPE        = "RECEIPT_TYPE"
    RECEIPT_REQUIRED    = "RECEIPT_REQUIRED"
    TX_AMOUNT           = "TRANSACTION_AMOUNT"
    IMAGE_REQUIRED      = "IMAGE_REQUIRED"
    CRN_KEY             = "CRN_KEY"
    EXCHANGE_RATE       = "EXCHANGE_RATE"
    EXCHANGE_DIR        = "EXCHANGE_RATE_DIRECTION"
    POSTED_AMOUNT       = "POSTED_AMOUNT"
    IS_PERSONAL         = "IS_PERSONAL"
    TRAVEL_ALLOWANCE    = "TRAVEL_ALLOWANCE"
    FOREIGN_OR_DOMESTIC = "FOREIGN_OR_DOMESTIC"
    HAS_VAT             = "HAS_VAT"
    ATTENDEE_COUNT      = "ATTENDEE_COUNT"
    COMMENT_COUNT       = "COMMENT_COUNT"
    EXCEPTION_COUNT     = "EXCEPTION_COUNT"
    TX_DATE             = "TRANSACTION_DATE"
    CLAIMED_AMOUNT      = "CLAIMED_AMOUNT"
    ADJUSTED_AMOUNT     = "ADJUSTED_AMOUNT"
    APPROVED_AMOUNT     = "APPROVED_AMOUNT"
    JOURNAL_AMT         = "JOURNAL_SPLITTING_AMOUNT"
    DESCRIPTION         = "DESCRIPTION"
    VEN_LI_KEY          = "VEN_LI_KEY"
    VENDOR_DESC         = "VENDOR_DESCRIPTION"
    LN_KEY              = "LN_KEY"
    PARENT_KEY          = "PARENT_RPE_KEY"
    CCT_KEY             = "CCT_KEY"
    ALLOC_STATE         = "ALLOCATION_STATE"
    ALLOC_VERSION       = "ALLOCATION_VERSION"
    ORG_UNIT_1          = "ORG_UNIT_1"
    ORG_UNIT_2          = "ORG_UNIT_2"
    ORG_UNIT_3          = "ORG_UNIT_3"
    ORG_UNIT_4          = "ORG_UNIT_4"
    ORG_UNIT_5          = "ORG_UNIT_5"
    ORG_UNIT_6          = "ORG_UNIT_6"
    FROM_LOCATION       = "FROM_LOCATION"
    TO_LOCATION         = "TO_LOCATION"
    SYNC_GUID           = "SYNC_GUID"
    LAST_MODIFIED       = "LAST_MODIFIED"
    TICKET_NUMBER       = "TICKET_NUMBER"
    AIRLINE_SVC         = "AIRLINE_SVC_CODE"
    CAR_RENTAL_DAYS     = "CAR_RENTAL_DAYS"
    ERECEIPT_POSTED     = "ERECEIPT_IMAGE_POSTED"
    ERECEIPT_TYPE       = "ERECEIPT_TYPE"
    IS_BILLABLE         = "IS_BILLABLE"
    RECEIPT_IMAGE_ID    = "RECEIPT_IMAGE_ID"
    ERECEIPT_IMAGE_ID   = "ERECEIPT_IMAGE_ID"
    TOTAL_TAX_POSTED    = "TOTAL_TAX_POSTED_AMOUNT"
    TOTAL_TAX_ADJ       = "TOTAL_TAX_ADJUSTED_AMOUNT"
    TOTAL_RECLAIM_POSTED = "TOTAL_RECLAIM_POSTED_AMOUNT"
    TOTAL_RECLAIM_ADJ   = "TOTAL_RECLAIM_ADJUSTED_AMOUNT"
    HOTEL_CHECKIN       = "HOTEL_CHECKIN_DATE"
    HOTEL_CHECKOUT      = "HOTEL_CHECKOUT_DATE"
    CREATION_DATE       = "CREATION_DATE"
    BUDGET_ACCRUAL      = "BUDGET_ACCRUAL_DATE"
    MERCHANT_TAX_ID     = "MERCHANT_TAX_ID"

    ORG_UNITS = ("ORG_UNIT_1", "ORG_UNIT_2", "ORG_UNIT_3",
                 "ORG_UNIT_4", "ORG_UNIT_5", "ORG_UNIT_6")


# ── icw_expense_categories ────────────────────────────────────────────────────

class Cat:
    ID            = "id"
    GROUP_NAME    = "group_name"
    CATEGORY_NAME = "category_name"
    DESCRIPTION   = "description"
    INSTRUCTIONS  = "instructions"


# ── fts_expenses ──────────────────────────────────────────────────────────────

class Fts:
    EMP_KEY     = "emp_key"
    RPT_KEY     = "rpt_key"
    RPE_KEY     = "rpe_key"
    FIRST_NAME  = "first_name"
    LAST_NAME   = "last_name"
    RPT_NAME    = "rpt_name"
    VENDOR_DESC = "vendor_description"
    DESCRIPTION = "description"
    ORG_UNIT_1  = "org_unit_1"
    ORG_UNIT_2  = "org_unit_2"
    ORG_UNIT_3  = "org_unit_3"
    ORG_UNIT_4  = "org_unit_4"
    ORG_UNIT_5  = "org_unit_5"
    ORG_UNIT_6  = "org_unit_6"
