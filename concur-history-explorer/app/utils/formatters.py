"""Currency, date, and display formatting helpers."""

from datetime import datetime, date


def fmt_currency(value, symbol: str = "$") -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{symbol}{v:,.2f}"


def fmt_currency_compact(value) -> str:
    """Format large dollar amounts as $1.2M, $34.5K, etc."""
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    if abs(v) >= 1_000_000:
        return f"${v/1_000_000:.1f}M"
    if abs(v) >= 1_000:
        return f"${v/1_000:.1f}K"
    return f"${v:,.2f}"


def fmt_date(value, fmt: str = "%b %d, %Y") -> str:
    if value is None:
        return "—"
    if isinstance(value, (datetime, date)):
        return value.strftime(fmt)
    s = str(value).strip()
    if not s or s.lower() in ("none", "null", "nan", ""):
        return "—"
    for parse_fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(s[:19], parse_fmt).strftime(fmt)
        except ValueError:
            continue
    return s  # return raw string if unparseable


def fmt_date_short(value) -> str:
    return fmt_date(value, "%m/%d/%Y")


def fmt_name(first: str | None, last: str | None) -> str:
    parts = [p for p in (first, last) if p and str(p).strip() not in ("", "None", "nan")]
    return " ".join(parts) if parts else "Unknown"


def fmt_approval_status(code: str | None) -> str:
    mapping = {
        "A_NOTF": "Not Submitted",
        "A_PEND": "Pending Approval",
        "A_APPR": "Approved",
        "A_EXTV": "Sent for Payment",
        "A_PAID": "Paid",
        "A_RESU": "Recalled",
        "A_BACK": "Sent Back",
        "A_CANC": "Cancelled",
    }
    if not code:
        return "Unknown"
    return mapping.get(str(code).upper(), str(code))


def fmt_bool(value) -> str:
    if value in (True, 1, "1", "Y", "YES", "TRUE", "true"):
        return "Yes"
    if value in (False, 0, "0", "N", "NO", "FALSE", "false"):
        return "No"
    return "—"


def truncate(text: str | None, max_len: int = 60) -> str:
    if not text or str(text).strip() in ("", "None", "nan"):
        return "—"
    s = str(text).strip()
    return s if len(s) <= max_len else s[:max_len - 1] + "…"
