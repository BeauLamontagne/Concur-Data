"""
Sample data generator for Concur History Explorer.

Usage:
    python -m app.utils.sample_data
    python -m app.utils.sample_data --num-reports 10000 --output ./db/concur_history.db
"""

from __future__ import annotations

import argparse
import logging
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from app.utils.logger import setup_logging, get_logger

setup_logging()
logger = get_logger("concur.sample_data")

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

COST_CENTERS = [
    ("CC-1001", "Marketing"),
    ("CC-2001", "Claims"),
    ("CC-3001", "Underwriting"),
    ("CC-4001", "IT"),
    ("CC-5001", "Finance"),
    ("CC-6001", "HR"),
    ("CC-7001", "Legal"),
    ("CC-8001", "Operations"),
    ("CC-9001", "Actuarial"),
    ("CC-1101", "Commercial Lines"),
    ("CC-1201", "Personal Lines"),
    ("CC-1301", "Risk Management"),
    ("CC-1401", "Compliance"),
    ("CC-1501", "Agency Relations"),
    ("CC-1601", "Customer Service"),
    ("CC-1701", "Product Development"),
    ("CC-1801", "Investments"),
    ("CC-1901", "Reinsurance"),
    ("CC-2101", "Executive"),
    ("CC-2201", "Facilities"),
]

DEPARTMENTS = [
    "Claims",
    "Underwriting",
    "Marketing & Sales",
    "Information Technology",
    "Finance & Accounting",
    "Human Resources",
    "Legal & Compliance",
    "Operations",
]

ORG_UNIT_2 = ["West Region", "Central Region", "East Region", "Corporate"]
ORG_UNIT_3 = ["Field", "Home Office", "Remote"]

FIRST_NAMES = [
    "James","Mary","John","Patricia","Robert","Jennifer","Michael","Linda",
    "William","Barbara","David","Elizabeth","Richard","Susan","Joseph","Jessica",
    "Thomas","Sarah","Charles","Karen","Christopher","Lisa","Daniel","Nancy",
    "Matthew","Betty","Anthony","Margaret","Mark","Sandra","Donald","Ashley",
    "Steven","Dorothy","Paul","Kimberly","Andrew","Emily","Kenneth","Donna",
    "George","Michelle","Joshua","Carol","Kevin","Amanda","Brian","Melissa",
    "Edward","Deborah","Ronald","Stephanie","Timothy","Rebecca","Jason","Sharon",
    "Jeffrey","Laura","Ryan","Cynthia","Gary","Kathleen","Jacob","Amy",
    "Nicholas","Angela","Eric","Shirley","Jonathan","Anna","Stephen","Brenda",
    "Larry","Pamela","Justin","Emma","Scott","Nicole","Brandon","Helen",
    "Frank","Samantha","Benjamin","Katherine","Raymond","Christine","Gregory","Debra",
    "Samuel","Rachel","Patrick","Carolyn","Alexander","Janet","Jack","Catherine",
]

LAST_NAMES = [
    "Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
    "Rodriguez","Martinez","Hernandez","Lopez","Gonzalez","Wilson","Anderson","Thomas",
    "Taylor","Moore","Jackson","Martin","Lee","Perez","Thompson","White",
    "Harris","Sanchez","Clark","Ramirez","Lewis","Robinson","Walker","Young",
    "Allen","King","Wright","Scott","Torres","Nguyen","Hill","Flores",
    "Green","Adams","Nelson","Baker","Hall","Rivera","Campbell","Mitchell",
    "Carter","Roberts","Phillips","Evans","Turner","Torres","Parker","Collins",
    "Edwards","Stewart","Flores","Morris","Nguyen","Murphy","Rivera","Cook",
    "Morgan","Peterson","Cooper","Reed","Bailey","Bell","Gomez","Kelly",
    "Howard","Ward","Cox","Diaz","Richardson","Wood","Watson","Brooks",
    "Bennett","Gray","James","Reyes","Cruz","Hughes","Price","Myers",
    "Long","Foster","Sanders","Ross","Morales","Powell","Sullivan","Russell",
]

REPORT_TEMPLATES = [
    "{quarter} {year} Travel - {city}",
    "Agent Summit {year} - {city}",
    "Claims Conference {year}",
    "Underwriting Training - {city}",
    "{month} Business Travel",
    "Industry Conference {year}",
    "Client Visit - {city}",
    "Team Meeting - {city}",
    "Recruiting Trip - {city}",
    "Annual Convention {year}",
    "Regional Sales Meeting",
    "Training & Development - {city}",
    "{month} Expense Report",
    "Customer Visit - {city}",
    "Board Meeting Travel",
]

CITIES = [
    "San Diego","Los Angeles","San Francisco","Las Vegas","Phoenix",
    "Dallas","Chicago","New York","Atlanta","Seattle","Denver","Miami",
    "Boston","Nashville","Portland","Austin","Minneapolis","Orlando",
]

VENDORS = {
    "Airfare":                ["United Airlines","Delta Air Lines","Southwest Airlines","American Airlines","Alaska Airlines"],
    "Hotel":                  ["Marriott","Hilton","Hyatt","Holiday Inn","Sheraton","Westin","Embassy Suites","Hampton Inn"],
    "Meals – Travel":         ["Starbucks","Chick-fil-A","McDonald's","Chipotle","Panera Bread","Local Restaurant","Subway","The Cheesecake Factory"],
    "Car Rental":             ["Enterprise","Hertz","Avis","National","Budget","Alamo"],
    "Bus/Taxi/Train":         ["Uber","Lyft","Yellow Cab","Amtrak","Local Taxi","Via"],
    "Parking":                ["LAZ Parking","SP+","ABM Parking","Hotel Parking","Airport Parking"],
    "Mileage – Entered":      ["Mileage Reimbursement"],
    "Mileage – Google Maps":  ["Mileage Reimbursement"],
    "Tips":                   ["Tip","Gratuity"],
    "Tolls":                  ["E-ZPass","SunPass","FasTrak","Toll Booth"],
    "Travel Documents":       ["CVS Health","Walgreens","Embassy Services"],
    "Meals – Agent/Insured":  ["Morton's Steakhouse","Ruth's Chris","Capital Grille","Local Restaurant","Flemings","Nobu"],
    "Agent/Insured Relations":["Golf Club","Event Venue","Ticketmaster","Sports Authority","Spa Resort"],
    "Gifts – Agent/Insured":  ["Amazon","1-800-Flowers","Visa Gift Card","Nordstrom","Tiffany & Co"],
    "Corporate Marketing":    ["Convention Center","Event Management Co","Tradeshow Booth Vendor"],
    "Advertising":            ["Google Ads","LinkedIn","Local Newspaper","Promo Items Co","Signs Direct"],
    "Recruiting":             ["Indeed","LinkedIn","ZipRecruiter","Interview Space Rental"],
    "Employee Relations":     ["Party City","Costco","Event Space","Team Building Co"],
    "Meals – Employee":       ["Panera Bread","Chipotle","Local Deli","Catering Co","Cheesecake Factory"],
    "Conferences & Industry Events": ["Conference Registration","EventBrite","Industry Association"],
    "Continuing Education / Certifications": ["Coursera","CPCU Society","AICPCU","State Licensing Board"],
    "Leadership & Development Programs": ["Harvard Business Online","Dale Carnegie","Korn Ferry"],
    "Professional Skills Training": ["LinkedIn Learning","Skillsoft","Internal Training"],
    "Company Car – Gasoline": ["Chevron","Shell","ExxonMobil","Arco","76"],
    "Company Car – Car Wash": ["Car Wash Express","Mister Car Wash","Autobell"],
    "Company Car – Expense":  ["Jiffy Lube","Pep Boys","Discount Tire","Firestone"],
    "Dues/Subscriptions":     ["CPCU Society","IIABA","Insurance Journal","LinkedIn Premium"],
    "Office Supplies":        ["Staples","Office Depot","Amazon","Grainger"],
    "Postage/Freight":        ["USPS","FedEx","UPS","DHL"],
    "Printing":               ["FedEx Office","Staples Print","Local Print Shop"],
    "Laundry":                ["Guest Laundry","Local Cleaners"],
    "Airfare":                ["United Airlines","Delta Air Lines","Southwest Airlines","American Airlines"],
}

# (category_name, icw_group, amount_range, weight)
EXPENSE_CATEGORIES = [
    # Business Travel ~60%
    ("Airfare",                  "Business Travel",         (200,  1500), 12),
    ("Hotel",                    "Business Travel",         (100,  400),  12),
    ("Meals – Travel",           "Business Travel",         (15,   100),  10),
    ("Car Rental",               "Business Travel",         (40,   150),  7),
    ("Bus/Taxi/Train",           "Business Travel",         (10,   80),   6),
    ("Parking",                  "Business Travel",         (5,    40),   5),
    ("Mileage – Entered",        "Business Travel",         (10,   200),  4),
    ("Tips",                     "Business Travel",         (2,    20),   2),
    ("Tolls",                    "Business Travel",         (2,    15),   2),
    # Agent/Insured ~15%
    ("Meals – Agent/Insured",    "Agent/Insured",           (30,   200),  7),
    ("Agent/Insured Relations",  "Agent/Insured",           (50,   500),  4),
    ("Gifts – Agent/Insured",    "Agent/Insured",           (25,   200),  4),
    # Marketing ~10%
    ("Corporate Marketing",      "Marketing/Recruiting",    (100,  5000), 5),
    ("Advertising",              "Marketing/Recruiting",    (50,   2000), 3),
    ("Recruiting",               "Marketing/Recruiting",    (50,   500),  2),
    # Employee Relations ~5%
    ("Employee Relations",       "Employee Relations",      (20,   500),  3),
    ("Meals – Employee",         "Employee Relations",      (30,   300),  2),
    # L&D ~5%
    ("Conferences & Industry Events",       "Learning and Development", (200, 3000), 2),
    ("Continuing Education / Certifications","Learning and Development",(50,  1500), 2),
    ("Professional Skills Training",        "Learning and Development", (100, 2000), 1),
    # Company Car ~3%
    ("Company Car – Gasoline",   "Company Car",             (20,   80),   2),
    ("Company Car – Car Wash",   "Company Car",             (10,   30),   1),
    ("Company Car – Expense",    "Company Car",             (30,   500),  1),
    # Other ~2%
    ("Dues/Subscriptions",       "Other",                   (50,   500),  1),
    ("Office Supplies",          "Other",                   (5,    100),  1),
    ("Postage/Freight",          "Other",                   (5,    50),   1),
]

_cat_names   = [c[0] for c in EXPENSE_CATEGORIES]
_cat_weights = [c[3] for c in EXPENSE_CATEGORIES]
_cat_lookup  = {c[0]: c for c in EXPENSE_CATEGORIES}

APPROVAL_STATUSES = [
    ("A_APPR", 0.80),
    ("A_PEND", 0.05),
    ("A_BACK", 0.05),
    ("A_EXTV", 0.05),
    ("A_PAID", 0.05),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _weighted_choice(population, weights):
    return random.choices(population, weights=weights, k=1)[0]


def _rand_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def _seasonal_date(year: int) -> date:
    """More travel in Q1 and Q3."""
    quarter_weights = [30, 20, 30, 20]
    q = _weighted_choice([1, 2, 3, 4], quarter_weights)
    month = (q - 1) * 3 + random.randint(1, 3)
    month = max(1, min(12, month))
    try:
        d = date(year, month, random.randint(1, 28))
    except ValueError:
        d = date(year, month, 1)
    return d


def _report_name(tx_date: date) -> str:
    template = random.choice(REPORT_TEMPLATES)
    return template.format(
        quarter=f"Q{(tx_date.month - 1) // 3 + 1}",
        year=tx_date.year,
        month=tx_date.strftime("%B"),
        city=random.choice(CITIES),
    )


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def generate(db_path: Path, num_reports: int = 10000) -> None:
    logger.info("Generating sample data → %s", db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        db_path.unlink()

    # Re-use the real schema + category seeder
    from app.db.connection import get_connection
    from app.db.schema import apply_schema
    from app.db.ingest import _seed_icw_categories

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA cache_size=-64000")
    apply_schema(conn)
    _seed_icw_categories(conn)

    # ── Employees ─────────────────────────────────────────────────────────────
    logger.info("  Generating employees…")
    num_employees = 500
    employees = []
    used_emails: set[str] = set()

    for i in range(1, num_employees + 1):
        first = random.choice(FIRST_NAMES)
        last  = random.choice(LAST_NAMES)
        base_email = f"{first.lower()}.{last.lower()}@icwgroup.com"
        email = base_email
        suffix = 1
        while email in used_emails:
            email = f"{first.lower()}.{last.lower()}{suffix}@icwgroup.com"
            suffix += 1
        used_emails.add(email)

        cc_code, cc_name = random.choice(COST_CENTERS)
        dept = random.choice(DEPARTMENTS)
        active = "1" if random.random() < 0.80 else "0"

        employees.append((
            f"EMP{i:06d}",          # EMP_KEY
            f"E{i:05d}",            # EMP_ID
            email.split("@")[0],    # LOGIN_ID
            first, "", first[0],    # FIRST_NAME, MIDDLE_NAME, MI
            last,                   # LAST_NAME
            email,                  # EMAIL_ADDRESS
            "USD",                  # CRN_KEY
            "en_US", "US", "CA",    # LOCALE, CTRY, CTRY_SUB
            cc_code,                # LEDGER_KEY
            None,                   # LN_KEY
            active,                 # ACTIVE
            dept,                   # ORG_UNIT_1
            random.choice(ORG_UNIT_2),   # ORG_UNIT_2
            random.choice(ORG_UNIT_3),   # ORG_UNIT_3
            cc_name, cc_code,            # ORG_UNIT_4, ORG_UNIT_5
            None,                        # ORG_UNIT_6
        ))

    conn.executemany(
        """INSERT INTO ct_employee
           (EMP_KEY, EMP_ID, LOGIN_ID, FIRST_NAME, MIDDLE_NAME, MI, LAST_NAME,
            EMAIL_ADDRESS, CRN_KEY, LOCALE_CODE, CTRY_CODE, CTRY_SUB_CODE,
            LEDGER_KEY, LN_KEY, ACTIVE,
            ORG_UNIT_1, ORG_UNIT_2, ORG_UNIT_3, ORG_UNIT_4, ORG_UNIT_5, ORG_UNIT_6)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        employees,
    )
    conn.commit()
    logger.info("    %d employees inserted.", len(employees))

    # ── Reports & entries ─────────────────────────────────────────────────────
    logger.info("  Generating %d reports and entries…", num_reports)
    emp_keys = [e[0] for e in employees]

    year_range = list(range(2019, date.today().year + 1))
    reports_inserted = 0
    entries_inserted = 0
    rpe_key_counter = 1

    BATCH = 500

    for batch_start in range(0, num_reports, BATCH):
        batch_end = min(batch_start + BATCH, num_reports)
        report_rows = []
        entry_rows  = []

        for i in range(batch_start + 1, batch_end + 1):
            rpt_key    = f"RPT{i:08d}"
            rpt_id     = f"R{i:06d}"
            emp_key    = random.choice(emp_keys)
            emp        = next(e for e in employees if e[0] == emp_key)
            cc_code    = emp[12]  # LEDGER_KEY holds CC code
            org1       = emp[15]  # ORG_UNIT_1

            year       = random.choice(year_range)
            tx_date    = _seasonal_date(year)
            submit_date = tx_date + timedelta(days=random.randint(1, 14))

            status = _weighted_choice(
                [s[0] for s in APPROVAL_STATUSES],
                [s[1] for s in APPROVAL_STATUSES],
            )

            rpt_name = _report_name(tx_date)
            num_entries = random.randint(1, 10)
            total = 0.0

            for j in range(num_entries):
                cat_name = _weighted_choice(_cat_names, _cat_weights)
                _, icw_group, (lo, hi), _ = _cat_lookup[cat_name]
                amount = round(random.uniform(lo, hi), 2)
                total += amount

                vendors_for_cat = VENDORS.get(cat_name, ["Various"])
                vendor = random.choice(vendors_for_cat)

                entry_date = tx_date + timedelta(days=random.randint(0, 3))
                receipt_id = f"IMG{rpe_key_counter:08d}" if random.random() < 0.70 else None

                entry_rows.append((
                    f"RPE{rpe_key_counter:09d}",  # RPE_KEY
                    rpt_key,                       # RPT_KEY
                    "EXPENSE",                     # TRANSACTION_TYPE
                    cat_name,                      # EXP_KEY — matches icw_expense_categories.category_name
                    None,                          # FORM_KEY
                    "Y" if receipt_id else "N",    # RECEIPT_RECEIVED
                    "IMAGE" if receipt_id else None, # RECEIPT_TYPE
                    "Y",                           # RECEIPT_REQUIRED
                    amount,                        # TRANSACTION_AMOUNT
                    "Y",                           # IMAGE_REQUIRED
                    "USD",                         # CRN_KEY
                    1.0, "FROM",                   # EXCHANGE_RATE, DIRECTION
                    amount,                        # POSTED_AMOUNT
                    "N", "N", "D", "N",            # IS_PERSONAL, TRAVEL_ALLOWANCE, F_OR_D, HAS_VAT
                    random.randint(0, 10),         # ATTENDEE_COUNT
                    0, 0,                          # COMMENT_COUNT, EXCEPTION_COUNT
                    str(entry_date),               # TRANSACTION_DATE
                    amount, amount, amount,        # CLAIMED, ADJUSTED, APPROVED
                    None,                          # JOURNAL_SPLITTING_AMOUNT
                    f"{cat_name} expense",         # DESCRIPTION
                    None,                          # VEN_LI_KEY
                    vendor,                        # VENDOR_DESCRIPTION
                    None, None, None,              # LN_KEY, PARENT_RPE_KEY, CCT_KEY
                    "FULL", "1",                   # ALLOCATION_STATE, ALLOCATION_VERSION
                    org1, None, None, None, None, None,  # ORG_UNIT_1-6
                    None, None,                    # FROM_LOCATION, TO_LOCATION
                    None,                          # SYNC_GUID
                    str(tx_date),                  # LAST_MODIFIED
                    None, None, None,              # TICKET_NUMBER, AIRLINE_SVC, CAR_RENTAL_DAYS
                    None, None,                    # ERECEIPT_IMAGE_POSTED, ERECEIPT_TYPE
                    "N",                           # IS_BILLABLE
                    receipt_id, None,              # RECEIPT_IMAGE_ID, ERECEIPT_IMAGE_ID
                    None, None, None, None,        # TAX/RECLAIM amounts
                    None, None,                    # HOTEL_CHECKIN/CHECKOUT
                    str(tx_date),                  # CREATION_DATE
                    None, None,                    # BUDGET_ACCRUAL, MERCHANT_TAX_ID
                ))
                rpe_key_counter += 1

            report_rows.append((
                rpt_key, emp_key, rpt_id, rpt_name,
                str(submit_date), status, status,
                str(submit_date + timedelta(days=random.randint(1, 7))),
                total, total, total,
                "USD", cc_code, cc_code,
                org1, None, None, None, None, None,
                str(tx_date), str(tx_date), None,
            ))

        conn.executemany(
            """INSERT INTO ct_report
               (RPT_KEY, EMP_KEY, RPT_ID, RPT_NAME,
                SUBMIT_DATE, APPROVAL_STATUS_CODE, APPROVAL_STATUS_NAME, APPROVED_DATE,
                TOTAL_CLAIMED_AMOUNT, TOTAL_APPROVED_AMOUNT, TOTAL_POSTED_AMOUNT,
                CRN_KEY, LEDGER_KEY, COST_CENTER,
                ORG_UNIT_1, ORG_UNIT_2, ORG_UNIT_3, ORG_UNIT_4, ORG_UNIT_5, ORG_UNIT_6,
                CREATION_DATE, LAST_MODIFIED, SYNC_GUID)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            report_rows,
        )

        conn.executemany(
            """INSERT INTO ct_report_entry
               (RPE_KEY, RPT_KEY, TRANSACTION_TYPE, EXP_KEY, FORM_KEY,
                RECEIPT_RECEIVED, RECEIPT_TYPE, RECEIPT_REQUIRED,
                TRANSACTION_AMOUNT, IMAGE_REQUIRED, CRN_KEY,
                EXCHANGE_RATE, EXCHANGE_RATE_DIRECTION, POSTED_AMOUNT,
                IS_PERSONAL, TRAVEL_ALLOWANCE, FOREIGN_OR_DOMESTIC, HAS_VAT,
                ATTENDEE_COUNT, COMMENT_COUNT, EXCEPTION_COUNT,
                TRANSACTION_DATE, CLAIMED_AMOUNT, ADJUSTED_AMOUNT, APPROVED_AMOUNT,
                JOURNAL_SPLITTING_AMOUNT, DESCRIPTION, VEN_LI_KEY, VENDOR_DESCRIPTION,
                LN_KEY, PARENT_RPE_KEY, CCT_KEY, ALLOCATION_STATE, ALLOCATION_VERSION,
                ORG_UNIT_1, ORG_UNIT_2, ORG_UNIT_3, ORG_UNIT_4, ORG_UNIT_5, ORG_UNIT_6,
                FROM_LOCATION, TO_LOCATION,
                SYNC_GUID, LAST_MODIFIED, TICKET_NUMBER, AIRLINE_SVC_CODE, CAR_RENTAL_DAYS,
                ERECEIPT_IMAGE_POSTED, ERECEIPT_TYPE, IS_BILLABLE,
                RECEIPT_IMAGE_ID, ERECEIPT_IMAGE_ID,
                TOTAL_TAX_POSTED_AMOUNT, TOTAL_TAX_ADJUSTED_AMOUNT,
                TOTAL_RECLAIM_POSTED_AMOUNT, TOTAL_RECLAIM_ADJUSTED_AMOUNT,
                HOTEL_CHECKIN_DATE, HOTEL_CHECKOUT_DATE,
                CREATION_DATE, BUDGET_ACCRUAL_DATE, MERCHANT_TAX_ID)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                       ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            entry_rows,
        )
        conn.commit()
        reports_inserted += len(report_rows)
        entries_inserted += len(entry_rows)

        if batch_start % 5000 == 0 and batch_start > 0:
            logger.info("    %d reports / %d entries…", reports_inserted, entries_inserted)

    conn.commit()
    logger.info("    %d reports inserted.", reports_inserted)
    logger.info("    %d entries inserted.", entries_inserted)

    # ── FTS index ─────────────────────────────────────────────────────────────
    logger.info("  Building FTS index…")
    from app.db.ingest import _populate_fts
    _populate_fts(conn)

    # ── ANALYZE ───────────────────────────────────────────────────────────────
    conn.execute("ANALYZE")
    conn.commit()

    size_mb = db_path.stat().st_size / 1_048_576
    logger.info("Done. Database: %s  (%.1f MB)", db_path, size_mb)
    logger.info("  ct_employee:     %8d", num_employees)
    logger.info("  ct_report:       %8d", reports_inserted)
    logger.info("  ct_report_entry: %8d", entries_inserted)
    conn.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate sample Concur data for the PoC")
    parser.add_argument("--num-reports", type=int, default=10000)
    parser.add_argument(
        "--output", type=Path,
        default=Path(__file__).resolve().parents[3] / "db" / "concur.db",
    )
    args = parser.parse_args()
    generate(args.output, args.num_reports)


if __name__ == "__main__":
    main()
