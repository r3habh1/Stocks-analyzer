"""Chart data adapters for TradingView Lightweight Charts format."""

from __future__ import annotations
import pandas as pd


def to_line_series(df: pd.DataFrame, time_col: str = "date", value_col: str = "value") -> list[dict]:
    """Convert DataFrame to [{time, value}] for Lightweight Charts Line/Area series."""
    return [
        {"time": str(row[time_col]), "value": float(row[value_col])}
        for _, row in df.iterrows()
    ]


def to_histogram_series(df: pd.DataFrame, time_col: str = "date", value_col: str = "value") -> list[dict]:
    """Convert DataFrame to [{time, value}] for Lightweight Charts Histogram series."""
    return [
        {"time": str(row[time_col]), "value": float(row[value_col])}
        for _, row in df.iterrows()
    ]


def price_to_series(df: pd.DataFrame, date_col: str = "date", close_col: str = "close") -> list[dict]:
    """Price (close) DataFrame to Line series."""
    return to_line_series(df.rename(columns={date_col: "date", close_col: "value"}), "date", "value")


def prepare_multi_series(df: pd.DataFrame, date_col: str, value_cols: list[str]) -> list[list[dict]]:
    """Prepare multiple series for overlaid chart. Returns list of series data."""
    result = []
    for col in value_cols:
        if col in df.columns:
            sub = df[[date_col, col]].rename(columns={date_col: "time", col: "value"})
            result.append(to_line_series(sub, "time", "value"))
    return result


def normalized_price_series(df: pd.DataFrame, date_col: str = "date", close_col: str = "close") -> list[dict]:
    """Normalize close prices to 100 at first date for relative performance comparison."""
    sub = df[[date_col, close_col]].dropna().sort_values(date_col)
    if sub.empty or sub[close_col].iloc[0] <= 0:
        return []
    base = float(sub[close_col].iloc[0])
    return [
        {"time": str(row[date_col]), "value": round(100 * float(row[close_col]) / base, 2)}
        for _, row in sub.iterrows()
    ]
