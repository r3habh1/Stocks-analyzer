"""Data loading helpers built on top of core.db."""

from __future__ import annotations
import pandas as pd
from collections import defaultdict
import streamlit as st
from core import db


# ── helpers ──────────────────────────────────────────────────


def get_dates(limit: int | None = 60) -> list[str]:
    """Return available dates sorted ascending.
    limit=None → all dates; limit=N → last N dates."""
    dates = db.main_coll().distinct("date")
    dates.sort(reverse=True)
    if limit is not None:
        dates = dates[:limit]
    return sorted(dates)


def get_latest_date() -> str | None:
    doc = db.main_coll().find_one(sort=[("date", -1)])
    return doc["date"] if doc else None


def get_symbols() -> list[str]:
    return [s["symbol"] for s in db.summary_coll().find({})]


def get_all_for_date(date: str) -> list[dict]:
    """All stocks on a given date, field‑mapped."""
    symbols = get_symbols()
    docs = list(db.main_coll().find({"date": date, "symbol": {"$in": symbols}}))
    return [db.map_fields(d) for d in docs]


def get_stock(symbol: str, date: str) -> dict | None:
    doc = db.stock_coll(symbol).find_one({"date": date})
    return db.map_fields(doc)


def date_df(date: str) -> pd.DataFrame:
    """Return a DataFrame of all stocks for *date*, ready for display."""
    rows = get_all_for_date(date)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df


# ── bulk loader (for backtesting) ───────────────────────────


class DataCache:
    """In‑memory cache of all derivative + OHLC data for fast backtesting."""

    MAX_GAP = 20.0  # max sane open‑vs‑close gap %

    def __init__(self):
        self.data: dict[str, dict[str, dict]] = defaultdict(dict)
        self.ohlc: dict[str, dict[str, dict]] = defaultdict(dict)
        self.dates: list[str] = []
        self.symbols: list[str] = []

    def load(self, days: int = 60):
        self.dates = get_dates(days)
        self.symbols = get_symbols()

        for doc in db.main_coll().find({"date": {"$in": self.dates}}):
            m = db.map_fields(doc)
            self.data[m["date"]][m["symbol"]] = m

        for sym in self.symbols:
            for doc in db.ohlc_coll(sym).find({"date": {"$in": self.dates}}):
                self.ohlc[sym][doc["date"]] = {
                    "open": doc.get("open", 0),
                    "high": doc.get("high", 0),
                    "low": doc.get("low", 0),
                    "close": doc.get("close", 0),
                }

    # ── price helpers ───

    def exit_price(self, symbol, entry_close, exit_date):
        """1‑day: (entry_actual, exit_actual) or None."""
        sd = self.data.get(exit_date, {}).get(symbol)
        if not sd or sd.get("close", 0) == 0:
            return None
        exit_c = sd["close"]
        ohlc = self.ohlc.get(symbol, {}).get(exit_date)
        entry = entry_close
        if ohlc and ohlc["open"] > 0:
            gap = abs((ohlc["open"] - entry_close) / entry_close * 100)
            if gap <= self.MAX_GAP:
                entry = ohlc["open"]
        if abs((exit_c - entry) / entry * 100) > self.MAX_GAP:
            return None
        return entry, exit_c

    def multi_exit(self, symbol, entry_close, idx, hold):
        eidx = idx + hold
        if eidx >= len(self.dates):
            return None
        sd = self.data.get(self.dates[eidx], {}).get(symbol)
        if not sd or sd.get("close", 0) == 0:
            return None
        exit_c = sd["close"]
        nxt = idx + 1
        if nxt >= len(self.dates):
            return None
        ohlc = self.ohlc.get(symbol, {}).get(self.dates[nxt])
        entry = entry_close
        if ohlc and ohlc["open"] > 0:
            gap = abs((ohlc["open"] - entry_close) / entry_close * 100)
            if gap <= self.MAX_GAP:
                entry = ohlc["open"]
        if abs((exit_c - entry) / entry * 100) > self.MAX_GAP * hold:
            return None
        return entry, exit_c

    def sector_bullish(self, date):
        bull = {"NewLong", "ShortCover"}
        sc = defaultdict(lambda: {"t": 0, "b": 0})
        for s in self.data.get(date, {}).values():
            sec = s.get("sector", "?")
            sc[sec]["t"] += 1
            if s.get("oi_trend", "") in bull:
                sc[sec]["b"] += 1
        return {k: v["b"] / v["t"] if v["t"] else 0 for k, v in sc.items()}
