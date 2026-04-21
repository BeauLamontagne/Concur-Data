# Concur History Explorer

A read-only Streamlit app for ICW Group accounting to search and explore 7 years of historical SAP Concur expense data.

## Quick Start

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Drop your Concur zip files into ./data/
#    - Disconnect.zip
#    - DDL.zip
#    - Extract_images_*.zip  (one or more)

# 4. Run the ingest (builds the SQLite database)
python -m app.db.ingest --data-dir ./data

# 5. Launch the app
streamlit run app/main.py
```

## Data Format

The ingest pipeline expects SAP Concur data exports in three zip formats:

| File | Contents |
|------|----------|
| `Disconnect.zip` | Pipe-delimited `.dat` files, one per table |
| `DDL.zip` | SQL CREATE TABLE scripts (Oracle/SQL Server syntax auto-translated to SQLite) |
| `Extract_images_*.zip` | Receipt image files referenced by `RECEIPT_IMAGE_ID` |

## Project Structure

```
concur-history-explorer/
├── app/
│   ├── main.py              # Streamlit entry point + navigation
│   ├── theme.py             # Workday-inspired color/style constants
│   ├── db/
│   │   ├── connection.py    # SQLite connection helper
│   │   ├── schema.py        # DDL translation + table/index creation
│   │   └── ingest.py        # Zip extraction, .dat loading, FTS indexing
│   ├── pages/               # One module per UI page
│   └── utils/
│       ├── expense_categories.py  # ICW expense taxonomy
│       ├── formatters.py          # Currency/date helpers
│       └── image_handler.py       # Receipt image lookup
├── data/                    # Drop Concur zip files here
├── db/                      # SQLite database + extracted images (git-ignored)
└── .streamlit/config.toml   # Theme configuration
```

## Re-ingesting Data

The ingest is idempotent — re-running drops and recreates all tables:

```bash
python -m app.db.ingest --data-dir ./data
```

## Database

SQLite is used for the local prototype. The database lives at `db/concur.db`.

Key performance features:
- WAL journal mode
- Indexes on all high-frequency filter columns
- FTS5 full-text search across names, vendors, org units, and descriptions
