"""MongoDB connection — single shared connector."""

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import os
import streamlit as st

# Support both Streamlit secrets and env vars (for Render, etc.)
_MONGO_URI = os.environ.get("MONGO_URI") or st.secrets.get("MONGO_URI", "mongodb://localhost:27017/")
_DERIV_DB = "Derivative_Analytics"
_OHLC_DB = "fno_ohlc_data"

# Collection names
MAIN_COLLECTION = "derivative_data"
STOCKS_SUMMARY = "stocks_summary"

# Field mapping: DB field → app field
FIELD_MAP = {
    "chg_pct": "change_pct",
    "put_call_ratio": "pcr",
    "oi_chg_pct": "oi_change_pct",
    "sector_name": "sector",
    "industry_name": "industry",
}


def _client_kwargs():
    """Build MongoClient kwargs; use certifi CA for Atlas SSL handshake."""
    kwargs = {"serverSelectionTimeoutMS": 10000}
    uri = _MONGO_URI
    if "mongodb+srv://" in uri:
        try:
            import certifi
            kwargs["tlsCAFile"] = certifi.where()
        except ImportError:
            pass  # certifi not installed, use default
    return kwargs


@st.cache_resource
def get_client():
    """Cached MongoDB client (shared across the whole Streamlit app)."""
    client = MongoClient(_MONGO_URI, **_client_kwargs())
    client.admin.command("ping")
    return client


def deriv_db():
    return get_client()[_DERIV_DB]


def ohlc_db():
    return get_client()[_OHLC_DB]


def main_coll():
    return deriv_db()[MAIN_COLLECTION]


def stock_coll(symbol: str):
    return deriv_db()[f"stock_{symbol}"]


def ohlc_coll(symbol: str):
    return ohlc_db()[f"eod_{symbol}"]


def summary_coll():
    return deriv_db()[STOCKS_SUMMARY]


# Normalize Aggressive* trends → base form
_TREND_NORMALIZE = {
    "AggressiveNewLong": "NewLong",
    "AggressiveNewShort": "NewShort",
    "AggressiveShortCover": "ShortCover",
    "AggressiveLongCover": "LongCover",
}


def map_fields(doc: dict | None) -> dict | None:
    """Rename DB fields to friendly app names and normalize OI trends."""
    if not doc:
        return doc
    d = dict(doc)
    d.pop("_id", None)
    for old, new in FIELD_MAP.items():
        if old in d:
            d[new] = d.pop(old)
    # Strip "Aggressive" prefix from OI trends
    if "oi_trend" in d:
        d["oi_trend"] = _TREND_NORMALIZE.get(d["oi_trend"], d["oi_trend"])
    return d
