"""Signal detection — OI trend flips, sector rotation, PCR extremes,
delivery spikes, multi-day streaks."""

from __future__ import annotations
from collections import defaultdict
import pandas as pd
from core.scorer import base_score, outrunner_conviction, BULLISH

# ── OI Trend Flip Detection ────────────────────────────────

BEARISH_TRENDS = {"NewShort", "LongCover"}


def compute_sector_direction(now: dict, past: dict, prev: dict,
                             chg_delta: float, agg_call_chg: float | None,
                             agg_put_chg: float | None,
                             threshold: float = 0.3) -> tuple[str, float]:
    """Composite direction from delivery, volume, fut OI, change delta, change %,
    call OI, put OI. Returns (Direction, score)."""
    # Normalize each metric to -1..1 contribution
    def _norm(v: float, pos_good: bool = True) -> float:
        if v is None: return 0
        # rough normalization: 1.5+ -> 1, 1.0 -> 0, 0.5 -> -0.5
        if pos_good:
            if v >= 1.5: return 1
            if v >= 1.0: return (v - 1) * 2  # 0..1
            if v >= 0.5: return -0.5
            return -1
        else:
            return -_norm(v, True)

    dlv_now = now.get("avg_dlv", 0) or 0
    dlv_past = past.get("avg_dlv", dlv_now) or 0
    dlv_delta = dlv_now - dlv_past
    vol_now = now.get("avg_vol", 0) or 0
    vol_past = past.get("avg_vol", vol_now) or 0
    vol_delta = vol_now - vol_past
    avg_chg = now.get("avg_chg", 0) or 0
    oi_chg = now.get("avg_oi_chg", 0) or 0

    score = 0.0
    # Delivery: > 1.5 is good
    score += _norm(dlv_now) * 0.2
    score += (1 if dlv_delta > 0.1 else (-1 if dlv_delta < -0.1 else 0)) * 0.15
    # Volume: > 1.5 is good
    score += _norm(vol_now) * 0.2
    score += (1 if vol_delta > 0.1 else (-1 if vol_delta < -0.1 else 0)) * 0.15
    # Change %: positive is good
    score += (1 if avg_chg > 1 else (-1 if avg_chg < -1 else 0)) * 0.2
    # Chg delta: positive is good
    score += (1 if chg_delta > 0.5 else (-1 if chg_delta < -0.5 else 0)) * 0.15
    # Fut OI (avg_oi_chg): positive is good
    score += (1 if oi_chg > 2 else (-1 if oi_chg < -2 else 0)) * 0.15
    # Call OI chg: positive = bullish
    if agg_call_chg is not None:
        score += (1 if agg_call_chg > 2 else (-1 if agg_call_chg < -2 else 0)) * 0.1
    # Put OI chg: negative = bullish (put unwinding)
    if agg_put_chg is not None:
        score += (-1 if agg_put_chg > 2 else (1 if agg_put_chg < -2 else 0)) * 0.1

    direction = "Improving" if score > threshold else ("Declining" if score < -threshold else "Stable")
    return direction, round(score, 2)


def _pct_chg(curr: float, prev: float) -> float | None:
    """Return (curr - prev) / prev * 100 if prev > 0, else None."""
    if prev is None or prev == 0:
        return None
    curr = curr or 0
    return round((curr - prev) / prev * 100, 2)


def enrich_oi_change_pct(stock: dict, prev_stock: dict | None) -> dict:
    """Add call_oi_change_pct and put_oi_change_pct computed from cumulative OI (today vs yesterday)."""
    s = dict(stock)
    if prev_stock:
        prev_call = prev_stock.get("cumulative_call_oi") or 0
        prev_put = prev_stock.get("cumulative_put_oi") or 0
        curr_call = s.get("cumulative_call_oi") or 0
        curr_put = s.get("cumulative_put_oi") or 0
        s["call_oi_change_pct"] = _pct_chg(curr_call, prev_call)
        s["put_oi_change_pct"] = _pct_chg(curr_put, prev_put)
    else:
        s["call_oi_change_pct"] = None
        s["put_oi_change_pct"] = None
    return s


def detect_trend_flips(data: dict, dates: list[str]) -> list[dict]:
    """Find stocks whose OI trend flipped from bearish→bullish today."""
    if len(dates) < 2:
        return []
    today, yesterday = dates[-1], dates[-2]
    flips = []
    for sym, s_today in data.get(today, {}).items():
        s_yest = data.get(yesterday, {}).get(sym)
        if not s_yest:
            continue
        t_today = s_today.get("oi_trend", "")
        t_yest = s_yest.get("oi_trend", "")
        if t_yest in BEARISH_TRENDS and t_today in BULLISH:
            flips.append({
                "symbol": sym,
                "prev_trend": t_yest,
                "new_trend": t_today,
                "close": s_today.get("close", 0),
                "change_pct": s_today.get("change_pct", 0),
                "pcr": s_today.get("pcr", 0),
                "volume_times": s_today.get("volume_times", 0),
                "delivery_times": s_today.get("delivery_times", 0),
                "sector": s_today.get("sector", ""),
                "mcap_category": s_today.get("mcap_category", ""),
                "score": base_score(s_today),
                "conviction": outrunner_conviction(s_today)["conviction"],
            })
    flips.sort(key=lambda x: x["conviction"], reverse=True)
    return flips


# ── Sector Rotation Tracker ─────────────────────────────────

def sector_rotation(data: dict, dates: list[str], window: int = 5,
                    mcap_filter: str = "All") -> list[dict]:
    """Full sector dashboard: OI, PCR, volume, delivery, price change
    compared over *window* days, optionally filtered by MCap."""
    if len(dates) < 2:
        return []
    if window == 0:
        window = 0  # current day only
    elif len(dates) < window + 1:
        window = max(len(dates) - 1, 1)

    def _filter(date):
        items = data.get(date, {}).values()
        if mcap_filter != "All":
            items = [s for s in items if s.get("mcap_category") == mcap_filter]
        return list(items)

    def _sector_stats(stocks):
        by_sec = defaultdict(lambda: {
            "count": 0, "bull": 0,
            "chg_sum": 0, "pcr_sum": 0, "vol_sum": 0, "dlv_sum": 0,
            "oi_chg_sum": 0, "call_oi_sum": 0, "put_oi_sum": 0,
        })
        for s in stocks:
            sec = s.get("sector", "?")
            d = by_sec[sec]
            d["count"] += 1
            if s.get("oi_trend", "") in BULLISH:
                d["bull"] += 1
            d["chg_sum"] += s.get("change_pct", 0)
            d["pcr_sum"] += s.get("pcr", 0)
            d["vol_sum"] += s.get("volume_times", 0)
            d["dlv_sum"] += s.get("delivery_times", 0)
            d["oi_chg_sum"] += s.get("oi_change_pct", 0)
            d["call_oi_sum"] += s.get("cumulative_call_oi") or 0
            d["put_oi_sum"] += s.get("cumulative_put_oi") or 0
        result = {}
        for sec, d in by_sec.items():
            n = d["count"]
            if n == 0:
                continue
            result[sec] = {
                "count": n,
                "bull_pct": round(d["bull"] / n * 100, 1),
                "avg_chg": round(d["chg_sum"] / n, 2),
                "avg_pcr": round(d["pcr_sum"] / n, 2),
                "avg_vol": round(d["vol_sum"] / n, 2),
                "avg_dlv": round(d["dlv_sum"] / n, 2),
                "avg_oi_chg": round(d["oi_chg_sum"] / n, 2),
                "call_oi_sum": d["call_oi_sum"],
                "put_oi_sum": d["put_oi_sum"],
            }
        return result

    now_stocks = _filter(dates[-1])
    prev_date = dates[-2] if len(dates) >= 2 else None
    prev_data = data.get(prev_date, {}) if prev_date else {}

    stats_now = _sector_stats(now_stocks)
    # Group stocks by sector for drill-down; enrich with computed call/put OI change %
    sector_stocks: dict[str, list[dict]] = defaultdict(list)
    for s in now_stocks:
        prev_s = prev_data.get(s.get("symbol", ""))
        s_enriched = enrich_oi_change_pct(s, prev_s)
        sec = s.get("sector", "?")
        sector_stocks[sec].append({
            "symbol": s_enriched.get("symbol", ""),
            "change_pct": s_enriched.get("change_pct", 0),
            "oi_trend": s_enriched.get("oi_trend", ""),
            "pcr": s_enriched.get("pcr", 0),
            "volume_times": s_enriched.get("volume_times", 0),
            "delivery_times": s_enriched.get("delivery_times", 0),
            "score": base_score(s_enriched),
            "cumulative_call_oi": s_enriched.get("cumulative_call_oi"),
            "cumulative_put_oi": s_enriched.get("cumulative_put_oi"),
            "cumulative_future_oi": s_enriched.get("cumulative_future_oi"),
            "oi_change_pct": s_enriched.get("oi_change_pct", 0),
            "call_oi_change_pct": s_enriched.get("call_oi_change_pct"),
            "put_oi_change_pct": s_enriched.get("put_oi_change_pct"),
            "pcr_change_1d": s_enriched.get("pcr_change_1d", 0),
            "mcap_category": s_enriched.get("mcap_category", ""),
        })

    if window > 0:
        past_idx = max(0, len(dates) - window - 1)
        past_stocks = _filter(dates[past_idx])
        stats_past = _sector_stats(past_stocks)
    else:
        stats_past = {}

    # For Agg Call/Put OI Chg%: always use previous day when available (even when window=0)
    stats_prev_day = {}
    if len(dates) >= 2:
        prev_day_stocks = _filter(dates[-2])
        stats_prev_day = _sector_stats(prev_day_stocks)

    rotations = []
    for sec, now in stats_now.items():
        past = stats_past.get(sec, {})
        prev = stats_prev_day.get(sec, past)
        pcr_delta = now["avg_pcr"] - past.get("avg_pcr", now["avg_pcr"])
        chg_delta = now["avg_chg"] - past.get("avg_chg", 0)

        now_call = now.get("call_oi_sum") or 0
        now_put = now.get("put_oi_sum") or 0
        past_call = prev.get("call_oi_sum") or 0
        past_put = prev.get("put_oi_sum") or 0
        agg_call_chg = _pct_chg(now_call, past_call) if past_call else None
        agg_put_chg = _pct_chg(now_put, past_put) if past_put else None

        direction, direction_score = compute_sector_direction(
            now, past, prev, chg_delta, agg_call_chg, agg_put_chg
        )

        rotations.append({
            "Sector": sec,
            "Stocks": now["count"],
            "stocks_list": sector_stocks.get(sec, []),
            "Agg Chg %": round(now["avg_chg"], 2),
            "Chg Δ": round(chg_delta, 2),
            "Vol(x)": round(now["avg_vol"], 2),
            "Dlv(x)": round(now["avg_dlv"], 2),
            "PCR": round(now["avg_pcr"], 2),
            "PCR Δ": round(pcr_delta, 2),
            "Agg Call OI": int(now_call),
            "Agg Call OI Chg%": agg_call_chg,
            "Agg Put OI": int(now_put),
            "Agg Put OI Chg%": agg_put_chg,
            "Direction": direction,
            "direction_score": direction_score,
        })
    rotations.sort(key=lambda x: (x["direction_score"], x["Agg Chg %"]), reverse=True)
    return rotations


def sector_time_series(data: dict, dates: list[str],
                       mcap_filter: str = "All") -> dict[str, pd.DataFrame]:
    """Per-sector time series for charting. Returns {sector: DataFrame with date, close, volume_times, delivery_times, fut_oi, call_oi, put_oi, pcr, oi_change_pct, change_pct}."""
    def _filter(date):
        items = data.get(date, {}).values()
        if mcap_filter != "All":
            items = [s for s in items if s.get("mcap_category") == mcap_filter]
        return list(items)

    by_sector_date: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for dt in dates:
        stocks = _filter(dt)
        for s in stocks:
            sec = s.get("sector", "?")
            by_sector_date[sec][dt].append(s)

    result = {}
    for sec, date_stocks in by_sector_date.items():
        rows = []
        for dt in sorted(date_stocks.keys()):
            stocks = date_stocks[dt]
            if not stocks:
                continue
            n = len(stocks)
            rows.append({
                "date": dt,
                "close": sum(s.get("close", 0) or 0 for s in stocks) / n,
                "volume_times": sum(s.get("volume_times", 0) or 0 for s in stocks) / n,
                "delivery_times": sum(s.get("delivery_times", 0) or 0 for s in stocks) / n,
                "fut_oi": sum(s.get("cumulative_future_oi", 0) or 0 for s in stocks),
                "call_oi": sum(s.get("cumulative_call_oi", 0) or 0 for s in stocks),
                "put_oi": sum(s.get("cumulative_put_oi", 0) or 0 for s in stocks),
                "pcr": sum(s.get("pcr", 0) or 0 for s in stocks) / n,
                "oi_change_pct": sum(s.get("oi_change_pct", 0) or 0 for s in stocks) / n,
                "change_pct": sum(s.get("change_pct", 0) or 0 for s in stocks) / n,
            })
        if rows:
            result[sec] = pd.DataFrame(rows)
    return result


# ── PCR Extreme Alerts ──────────────────────────────────────

def pcr_extremes(data: dict, date: str,
                 low_thresh: float = 0.5, high_thresh: float = 1.5) -> dict:
    """Find stocks at PCR extremes — potential reversal signals."""
    low, high = [], []
    for sym, s in data.get(date, {}).items():
        pcr = s.get("pcr", 1)
        entry = {
            "symbol": sym, "pcr": pcr,
            "pcr_change_1d": s.get("pcr_change_1d", 0),
            "close": s.get("close", 0),
            "change_pct": s.get("change_pct", 0),
            "oi_trend": s.get("oi_trend", ""),
            "sector": s.get("sector", ""),
            "mcap_category": s.get("mcap_category", ""),
        }
        if pcr <= low_thresh:
            low.append(entry)
        elif pcr >= high_thresh:
            high.append(entry)
    low.sort(key=lambda x: x["pcr"])
    high.sort(key=lambda x: x["pcr"], reverse=True)
    return {"low_pcr": low, "high_pcr": high}


# ── Delivery Spike Scanner ──────────────────────────────────

def delivery_spikes(data: dict, date: str, thresh: float = 2.0) -> list[dict]:
    """Stocks with delivery ≥ thresh today — institutional buying signal."""
    spikes = []
    for sym, s in data.get(date, {}).items():
        dlv = s.get("delivery_times", 0)
        if dlv >= thresh:
            spikes.append({
                "symbol": sym,
                "delivery_times": dlv,
                "volume_times": s.get("volume_times", 0),
                "close": s.get("close", 0),
                "change_pct": s.get("change_pct", 0),
                "oi_trend": s.get("oi_trend", ""),
                "pcr": s.get("pcr", 0),
                "sector": s.get("sector", ""),
                "mcap_category": s.get("mcap_category", ""),
                "score": base_score(s),
            })
    spikes.sort(key=lambda x: x["delivery_times"], reverse=True)
    return spikes


# ── Multi-Day Score Streak ──────────────────────────────────

def score_streaks(data: dict, dates: list[str],
                  min_days: int = 3, lo: int = 20, hi: int = 34) -> list[dict]:
    """Stocks in sweet-spot score range for ≥ min_days consecutive days."""
    if len(dates) < min_days:
        return []

    recent = dates[-min_days:]
    # count how many of the last min_days each symbol was in range
    sym_days = defaultdict(int)
    sym_latest = {}
    for d in recent:
        for sym, s in data.get(d, {}).items():
            sc = base_score(s)
            if lo <= sc <= hi:
                sym_days[sym] += 1
                sym_latest[sym] = s

    streaks = []
    for sym, count in sym_days.items():
        if count >= min_days:
            s = sym_latest[sym]
            streaks.append({
                "symbol": sym,
                "streak_days": count,
                "score": base_score(s),
                "conviction": outrunner_conviction(s)["conviction"],
                "close": s.get("close", 0),
                "change_pct": s.get("change_pct", 0),
                "oi_trend": s.get("oi_trend", ""),
                "pcr": s.get("pcr", 0),
                "volume_times": s.get("volume_times", 0),
                "delivery_times": s.get("delivery_times", 0),
                "sector": s.get("sector", ""),
                "mcap_category": s.get("mcap_category", ""),
            })
    streaks.sort(key=lambda x: (x["streak_days"], x["conviction"]), reverse=True)
    return streaks


# ── Daily Summary Generator ─────────────────────────────────

def daily_summary(data: dict, dates: list[str]) -> str:
    """Generate a one-paragraph morning summary."""
    if not dates:
        return "No data available."
    today = dates[-1]
    stocks = data.get(today, {})
    if not stocks:
        return "No stock data for today."

    total = len(stocks)
    n_bull = sum(1 for s in stocks.values() if s.get("oi_trend", "") in BULLISH)
    n_bear = sum(1 for s in stocks.values() if s.get("oi_trend", "") in BEARISH_TRENDS)
    bull_pct = n_bull / total * 100 if total else 0

    # Previous day comparison
    prev_bull_pct = 0
    if len(dates) >= 2:
        yest = data.get(dates[-2], {})
        if yest:
            prev_bull_pct = sum(1 for s in yest.values()
                                if s.get("oi_trend", "") in BULLISH) / len(yest) * 100

    avg_pcr = sum(s.get("pcr", 0) for s in stocks.values()) / total
    avg_chg = sum(s.get("change_pct", 0) for s in stocks.values()) / total

    # Trend flips
    flips = detect_trend_flips(data, dates)
    # PCR extremes
    ext = pcr_extremes(data, today)
    # Delivery spikes
    spk = delivery_spikes(data, today, 2.0)
    # Streaks
    stk = score_streaks(data, dates, 3)

    lines = []
    lines.append(f"**{today}** — {n_bull} bullish ({bull_pct:.0f}%) vs {n_bear} bearish out of {total} stocks.")

    if prev_bull_pct > 0:
        delta = bull_pct - prev_bull_pct
        if abs(delta) > 2:
            lines.append(f"Sentiment {'improved' if delta > 0 else 'weakened'} from yesterday ({prev_bull_pct:.0f}% → {bull_pct:.0f}%).")

    lines.append(f"Avg PCR: {avg_pcr:.2f}, Avg Change: {avg_chg:+.2f}%.")

    if flips:
        top_flip = flips[0]
        lines.append(f"{len(flips)} trend flip(s) detected — top: **{top_flip['symbol']}** ({top_flip['prev_trend']} → {top_flip['new_trend']}).")

    if ext["low_pcr"]:
        lines.append(f"{len(ext['low_pcr'])} stock(s) at PCR extreme low (≤0.5) — put writers very confident.")

    if spk:
        lines.append(f"{len(spk)} delivery spike(s) (≥2.0x) — institutional buying detected.")

    if stk:
        lines.append(f"{len(stk)} stock(s) on {3}+ day sweet-spot streak — persistent conviction.")

    return " ".join(lines)


# ── Signal Convergence (for badges) ────────────────────────────────

def signal_convergence(
    data: dict,
    dates: list[str],
    view_date: str,
) -> dict[str, list[str]]:
    """Returns {symbol: [signal1, signal2, ...]} for stocks on view_date.
    Signals: Flip, PCR, Dlv, Streak, CallPut."""
    result: dict[str, list[str]] = {}
    if not dates or view_date not in data:
        return result

    flips = {f["symbol"] for f in detect_trend_flips(data, dates)}
    ext = pcr_extremes(data, view_date)
    pcr_syms = {e["symbol"] for e in ext["low_pcr"] + ext["high_pcr"]}
    spikes = {s["symbol"] for s in delivery_spikes(data, view_date, 2.0)}
    streaks = {s["symbol"] for s in score_streaks(data, dates, 3)}

    prev_date = dates[-2] if len(dates) >= 2 else None
    prev_data = data.get(prev_date, {}) if prev_date else {}

    for sym, s in data.get(view_date, {}).items():
        sigs = []
        if sym in flips:
            sigs.append("Flip")
        if sym in pcr_syms:
            sigs.append("PCR")
        if sym in spikes:
            sigs.append("Dlv")
        if sym in streaks:
            sigs.append("Streak")
        # Call/Put divergence
        cp = call_put_divergence(s, prev_data.get(sym))
        if cp == "bullish":
            sigs.append("CallPut")
        if sigs:
            result[sym] = sigs
    return result


def call_put_divergence(stock: dict, prev_stock: dict | None) -> str | None:
    """Bullish when call OI up + put OI down. Bearish when call down + put up."""
    if not prev_stock:
        return None
    prev_call = prev_stock.get("cumulative_call_oi") or 0
    prev_put = prev_stock.get("cumulative_put_oi") or 0
    curr_call = stock.get("cumulative_call_oi") or 0
    curr_put = stock.get("cumulative_put_oi") or 0
    if prev_call <= 0 or prev_put <= 0:
        return None
    call_chg = (curr_call - prev_call) / prev_call
    put_chg = (curr_put - prev_put) / prev_put
    if call_chg > 0.02 and put_chg < -0.02:
        return "bullish"
    if call_chg < -0.02 and put_chg > 0.02:
        return "bearish"
    return None
