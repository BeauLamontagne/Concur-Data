# ICW Group — Concur History Explorer

A read-only Streamlit application for browsing and searching 7 years of historical
SAP Concur expense data following ICW Group's transition to Workday.

---

## Background

ICW Group migrated from SAP Concur to Workday. A full historical data extract was
received in September 2026 containing pipe-delimited `.dat` files and DDL definitions.
Finance and Audit stakeholders require ongoing access to this archive for:

- Audit & compliance lookups (7-year regulatory retention)
- Spend review and budget benchmarking
- Ad-hoc employee expense history queries

This tool replaces an MS Access approach with a purpose-built read-only explorer
styled to match the Workday visual language.

---

## User Stories

**Audit & Compliance**

| ID | As a… | I want to… | So that… |
|----|-------|-----------|---------|
| A1 | Finance auditor | search expenses by employee name or cost center | I can respond to audit requests within 15 days |
| A2 | Finance auditor | view full expense report detail with receipt images | I have complete documentation for audit findings |
| A3 | Finance auditor | export filtered results to Excel | I can share findings with auditors and legal |

**Spend Review & Budgeting**

| ID | As a… | I want to… | So that… |
|----|-------|-----------|---------|
| B1 | Finance manager | see annual spend by cost center and department | I can benchmark against proposed budgets |
| B2 | Finance manager | compare year-over-year trends by expense category | I can identify anomalies and plan accurately |
| B3 | Finance manager | enter a proposed budget amount and see historical context | I can justify or challenge budget requests |

---

## Quick Start

**Requirements:** Python 3.11+, ~500 MB disk space for sample data

```bash
# 1. Clone and set up environment
git clone <repo-url>
cd concur-history-explorer
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Generate sample data (replace with real Concur data for production)
python -m app.utils.sample_data --num-reports 50000

# 3. (Optional) Set a password
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit secrets.toml and set app_password

# 4. Run the app
streamlit run app/main.py
# Open http://localhost:8501
```

**With real Concur data:**

```bash
# Place zip files in ./data/
#   Disconnect.zip          pipe-delimited .dat files
#   DDL.zip                 SQL CREATE TABLE scripts
#   Extract_images_*.zip    receipt image archives

python -m app.db.ingest --data-dir ./data
streamlit run app/main.py
```

---

## Docker

```bash
# Build and run
docker compose up --build

# Generate sample data inside the container
docker compose exec app python -m app.utils.sample_data --num-reports 50000
```

The compose file mounts `./data`, `./db`, and `./logs` as volumes so the database
and logs persist across container restarts.

---

## Architecture

```
concur-history-explorer/
├── app/
│   ├── main.py               # Streamlit entry point, nav, auth gate
│   ├── theme.py              # Workday visual system (colors, CSS, components)
│   ├── db/
│   │   ├── constants.py      # Single source of truth for table/column names
│   │   ├── connection.py     # SQLite connection (WAL mode, 64 MB cache)
│   │   ├── schema.py         # DDL translator + FTS5 schema
│   │   ├── ingest.py         # CLI ingest from Concur zip/dat files
│   │   └── queries.py        # All read queries (cached via @st.cache_data)
│   ├── pages/
│   │   ├── login.py          # Password gate
│   │   ├── home.py           # Dashboard — KPIs and charts
│   │   ├── audit_search.py   # Expense search with FTS5 + filters
│   │   ├── spend_review.py   # Aggregated spend analysis
│   │   ├── trend_analysis.py # Year-over-year trends and budget comparison
│   │   └── admin.py          # DB management and table browser
│   └── utils/
│       ├── expense_categories.py  # ICW Group 7-group / 32-category taxonomy
│       ├── formatters.py          # Currency, date, status formatting
│       ├── image_handler.py       # Receipt image lookup
│       ├── logger.py              # Rotating file + console logging
│       └── sample_data.py         # Sample data generator (PoC only)
├── db/                       # SQLite file + receipt images (gitignored)
├── data/                     # Concur zip/dat source files (gitignored)
├── logs/                     # Application logs (gitignored)
├── Dockerfile
├── docker-compose.yml
├── MIGRATION.md              # AWS migration path (Phases 1–3)
└── requirements.txt
```

**Data model (core tables):**

| Table | Key | Description |
|-------|-----|-------------|
| `ct_employee` | `EMP_KEY` | Employee master — name, email, org units |
| `ct_report` | `RPT_KEY` | Expense report header — dates, status, cost center |
| `ct_report_entry` | `RPE_KEY` | Individual expense line items — amounts, category, vendor |
| `icw_expense_categories` | `category_name` | ICW Group 7-group taxonomy (seed data) |
| `fts_expenses` | — | FTS5 virtual table for full-text search |

---

## Data Format

| File | Contents |
|------|----------|
| `Disconnect.zip` | Pipe-delimited `.dat` files, one per table |
| `DDL.zip` | SQL CREATE TABLE scripts (Oracle/SQL Server → SQLite auto-translated) |
| `Extract_images_*.zip` | Receipt image files referenced by `RECEIPT_IMAGE_ID` |

---

## Authentication

Default password: `icw-concur-2024`

To change it, create `.streamlit/secrets.toml`:

```toml
app_password = "your-strong-password"
```

**Production note:** This simple gate is suitable for a VPN-restricted internal tool
with 3 named users. For external or higher-security access, replace with Amazon Cognito
(see `MIGRATION.md`).

---

## Security Notes

- **Read-only:** The application makes no write operations to the database.
- **PII:** `ct_employee` contains employee names and emails.
  `ct_report_entry` contains expense amounts and vendor names.
  In production, enforce encryption at rest (RDS storage encryption) and
  restrict network access to corporate IPs.
- **Parameterized queries:** All SQL uses bound parameters — no string interpolation
  of user input.
- **Audit logging:** All searches and exports are logged to `logs/app.log`.

---

## Re-ingesting Data

The ingest is idempotent — re-running drops and recreates all tables:

```bash
python -m app.db.ingest --data-dir ./data
```

---

## Screenshots

*(Add screenshots after first deployment)*

| Dashboard | Expense Search | Spend Review |
|-----------|---------------|-------------|
| *KPI cards + charts* | *FTS + filters + detail view* | *Group-by aggregation + drill-down* |

---

## Access

Up to **3 business users** from the ICW Group Finance Travel/Expense team.
Contact Finance IT to request access or reset the password.
