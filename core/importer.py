"""CSV importer — upserts into Derivative_Analytics.derivative_data
and reorganises per‑stock collections + stocks_summary."""

from __future__ import annotations
import csv, io, re
from datetime import datetime
from pathlib import Path
from core import db


# ── Date parsing ────────────────────────────────────────────

def _parse_date(raw: str) -> str:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%d/%b/%Y", "%d/%B/%Y", "%d/%m/%Y",
                "%d-%b-%Y", "%d-%B-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw


# ── CSV field extraction ────────────────────────────────────

def _float(val: str | None) -> float:
    if not val:
        return 0.0
    try:
        return float(val.strip().replace(",", ""))
    except ValueError:
        return 0.0


def _row_to_doc(row: dict, date_override: str | None = None,
                symbol_override: str | None = None) -> dict | None:
    """Convert a single CSV row to a MongoDB document."""
    symbol = symbol_override or row.get("Symbol", "").strip()
    if not symbol:
        return None

    date_str = date_override or _parse_date(
        row.get("Date", "") or row.get("date", "")
    )
    if not date_str:
        return None

    return {
        "date":                  date_str,
        "symbol":                symbol,
        "stock_name":            row.get("Stock Name", "") or row.get("stock_name", ""),
        "lot_size":              _float(row.get("Lot Size") or row.get("lot_size")),
        "sector_name":           row.get("Sector Name", "") or row.get("sector_name", ""),
        "industry_name":         row.get("Industry Name", "") or row.get("industry_name", ""),
        "mcap_category":         row.get("MCap Category", "") or row.get("mcap_category", ""),
        "close":                 _float(row.get("Close") or row.get("close")),
        "chg_pct":               _float(row.get("Chg %") or row.get("Change %") or row.get("chg_pct")),
        "cumulative_future_oi":  _float(row.get("Cumulative Future OI") or row.get("cumulative_future_oi")),
        "oi_chg_pct":            _float(row.get("OI Chg %") or row.get("Future OI Change %") or row.get("oi_chg_pct")),
        "volume_times":          _float(row.get("Volume (Times)") or row.get("Volume Times(x)") or row.get("volume_times")),
        "delivery_times":        _float(row.get("Delivery (Times)") or row.get("Delivery Times(x)") or row.get("delivery_times")),
        "cumulative_call_oi":    _float(row.get("Cumulative Call OI") or row.get("cumulative_call_oi")),
        "cumulative_put_oi":     _float(row.get("Cumulative Put OI") or row.get("cumulative_put_oi")),
        "put_call_ratio":        _float(row.get("Put Call Ratio (PCR)") or row.get("PCR") or row.get("put_call_ratio")),
        "pcr_change_1d":         _float(row.get("PCR Change 1D") or row.get("pcr_change_1d")),
        "oi_trend":              (row.get("OI Trend", "") or row.get("Derivative Trend", "") or row.get("oi_trend", "")).strip(),
        "imported_at":           datetime.now().isoformat(),
        "source":                "csv_upload",
    }


# ── Public import function ──────────────────────────────────

def import_csv(text: str) -> tuple[int, int, list[str]]:
    """Import CSV text into DB.  Returns (new, updated, errors)."""
    lines = text.splitlines()

    # Find the header row (skip preamble lines)
    header_idx = None
    for i, line in enumerate(lines):
        low = line.lower()
        if "symbol" in low and ("date" in low or "close" in low or "oi_trend" in low):
            header_idx = i
            break
    if header_idx is None:
        # Assume first line is header
        header_idx = 0

    reader = csv.DictReader(lines[header_idx:])
    coll = db.main_coll()

    new = upd = 0
    errors: list[str] = []
    affected: set[str] = set()

    for row in reader:
        doc = _row_to_doc(row)
        if not doc:
            continue
        try:
            r = coll.update_one(
                {"date": doc["date"], "symbol": doc["symbol"]},
                {"$set": doc},
                upsert=True,
            )
            affected.add(doc["symbol"])
            if r.upserted_id:
                new += 1
            else:
                upd += 1
        except Exception as e:
            errors.append(f"{doc.get('symbol', '?')} {doc.get('date', '?')}: {e}")

    # Rebuild only affected stock collections (fast for cloud MongoDB)
    if affected:
        _rebuild_stock_collections(affected)

    return new, upd, errors


def _rebuild_stock_collections(affected_symbols: set[str] | None = None):
    """Re‑populate stock_<SYMBOL> collections and stocks_summary.
    Only rebuilds affected symbols for speed (important for cloud MongoDB)."""
    coll = db.main_coll()
    d = db.deriv_db()

    symbols = affected_symbols or set(coll.distinct("symbol"))
    summary_coll = db.summary_coll()

    from pymongo import UpdateOne

    for sym in symbols:
        target = d[f"stock_{sym}"]
        docs = list(coll.find({"symbol": sym}).sort("date", 1))
        if not docs:
            continue

        # Bulk upsert for speed
        ops = []
        for doc in docs:
            doc_copy = dict(doc)
            doc_copy.pop("_id", None)
            ops.append(UpdateOne(
                {"date": doc_copy["date"]},
                {"$set": doc_copy},
                upsert=True,
            ))
        if ops:
            target.bulk_write(ops, ordered=False)

        # Update summary
        latest = docs[-1]
        summary_coll.update_one(
            {"symbol": sym},
            {"$set": {
                "symbol": sym,
                "stock_name": latest.get("stock_name", ""),
                "sector_name": latest.get("sector_name", ""),
                "industry_name": latest.get("industry_name", ""),
                "mcap_category": latest.get("mcap_category", ""),
                "lot_size": latest.get("lot_size", 0),
                "record_count": len(docs),
                "latest_date": latest["date"],
            }},
            upsert=True,
        )
