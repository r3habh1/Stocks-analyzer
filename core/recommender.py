"""Outrunner-based recommendation engine — Top 7 picks and Stock Action Sheet."""

from __future__ import annotations
from core.scorer import base_score, outrunner_conviction, BULLISH
from core.signals import (
    signal_convergence,
    enrich_oi_change_pct,
)


def get_top_picks(
    sig_data: dict,
    dates: list[str],
    view_date: str,
    mcap_filter: str = "All",
    top_n: int = 7,
) -> list[dict]:
    """Outrunner-ranked picks with signals. Returns top N for view_date (sweet spot only)."""
    return get_action_sheet(
        sig_data, dates, view_date,
        mcap_filter=mcap_filter,
        min_conv=0,
        min_score=0,
        watchlist=None,
        sweet_spot_only=True,
    )[:top_n]


def get_action_sheet(
    sig_data: dict,
    dates: list[str],
    view_date: str,
    mcap_filter: str = "All",
    min_conv: int = 0,
    min_score: int = 0,
    watchlist: set[str] | None = None,
    sweet_spot_only: bool = False,
) -> list[dict]:
    """Full ranked list for manual analysis. Outrunner logic: Conviction + Score + Signal boost."""
    if not dates or view_date not in sig_data:
        return []

    prev_date = dates[-2] if len(dates) >= 2 else None
    prev_data = sig_data.get(prev_date, {}) if prev_date else {}
    sector_rot = _get_sector_bull_delta(sig_data, dates, view_date, mcap_filter)

    conv_map = signal_convergence(sig_data, dates, view_date)
    rows = []

    for sym, s in sig_data.get(view_date, {}).items():
        if mcap_filter != "All" and s.get("mcap_category") != mcap_filter:
            continue
        vol = s.get("volume_times", 0)
        pcr = s.get("pcr", 1)
        if vol < 0.7 and pcr >= 1:
            continue
        sc = base_score(s)
        if sweet_spot_only and (sc < 20 or sc > 34):
            continue
        s_enriched = enrich_oi_change_pct(s, prev_data.get(sym))
        cv = outrunner_conviction(s_enriched)
        conv = cv["conviction"]
        if conv < min_conv or sc < min_score:
            continue
        if watchlist and sym not in watchlist:
            continue

        signals = conv_map.get(sym, [])
        sector_dir_score = sector_rot.get(s.get("sector", "?"), 0)
        sector_bonus = 3 if sector_dir_score > 0.3 else (1 if sector_dir_score >= 0 else 0)
        conv_bonus = len(signals) * 2
        rec_score = conv + sc + conv_bonus + sector_bonus

        rows.append({
            "symbol": sym,
            "conviction": conv,
            "score": sc,
            "rec_score": rec_score,
            "signals": signals,
            "change_pct": s.get("change_pct"),
            "volume_times": s.get("volume_times", 0),
            "delivery_times": s.get("delivery_times", 0),
            "cumulative_future_oi": s.get("cumulative_future_oi"),
            "oi_change_pct": s.get("oi_change_pct"),
            "cumulative_call_oi": s.get("cumulative_call_oi"),
            "cumulative_put_oi": s.get("cumulative_put_oi"),
            "call_oi_change_pct": s_enriched.get("call_oi_change_pct"),
            "put_oi_change_pct": s_enriched.get("put_oi_change_pct"),
            "pcr": s.get("pcr", 0),
            "pcr_change_1d": s.get("pcr_change_1d", 0),
            "oi_trend": s.get("oi_trend", ""),
            "mcap_category": s.get("mcap_category", ""),
            "sector": s.get("sector", ""),
            "industry": s.get("industry", ""),
            "lot_size": s.get("lot_size"),
            "close": s.get("close", 0),
            "stock_name": s.get("stock_name", ""),
        })

    rows.sort(key=lambda x: (x["rec_score"], x["conviction"], x["score"]), reverse=True)
    return rows


def _get_sector_bull_delta(
    sig_data: dict,
    dates: list[str],
    view_date: str,
    mcap_filter: str,
) -> dict[str, float]:
    """Return {sector: direction_score} for sector boost."""
    from core.signals import sector_rotation
    if len(dates) < 2:
        return {}
    rot = sector_rotation(sig_data, dates, window=5, mcap_filter=mcap_filter)
    return {r["Sector"]: r.get("direction_score", 0) for r in rot}


def get_historical_top7_performance(
    sig_data: dict,
    dates: list[str],
    lookback_days: int = 5,
) -> dict | None:
    """Compute last week's Top 7 performance (close-to-close). Returns dict or None."""
    if len(dates) < lookback_days + 1:
        return None
    total_green = 0
    total_picks = 0
    chg_sum = 0.0
    details = []

    for i in range(-(lookback_days + 1), -1):
        if i + len(dates) < 0:
            continue
        dt = dates[i]
        next_dt = dates[i + 1]
        idx = len(dates) + i
        dates_up_to = dates[: idx + 2]
        picks = get_top_picks(sig_data, dates_up_to, dt, top_n=7)
        for p in picks:
            sym = p["symbol"]
            entry_close = p.get("close", 0)
            if entry_close <= 0:
                continue
            next_data = sig_data.get(next_dt, {}).get(sym)
            if not next_data:
                continue
            exit_close = next_data.get("close", 0)
            if exit_close <= 0:
                continue
            pct = (exit_close - entry_close) / entry_close * 100
            total_picks += 1
            if pct > 0:
                total_green += 1
            chg_sum += pct
            details.append({"date": dt, "symbol": sym, "pnl_pct": round(pct, 2)})

    if total_picks == 0:
        return None
    return {
        "total_picks": total_picks,
        "green_count": total_green,
        "green_pct": round(total_green / total_picks * 100, 0),
        "avg_chg_pct": round(chg_sum / total_picks, 2),
        "details": details[:10],
    }
