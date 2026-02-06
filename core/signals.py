"""Signal detection — OI trend flips, sector rotation, PCR extremes,
delivery spikes, multi-day streaks.  All built from the DataCache."""

from __future__ import annotations
from collections import defaultdict
from core.scorer import base_score, outrunner_conviction, BULLISH

# ── OI Trend Flip Detection ────────────────────────────────

BEARISH_TRENDS = {"NewShort", "LongCover"}

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
            "oi_chg_sum": 0,
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
            }
        return result

    now_stocks = _filter(dates[-1])
    stats_now = _sector_stats(now_stocks)

    if window > 0:
        past_idx = max(0, len(dates) - window - 1)
        past_stocks = _filter(dates[past_idx])
        stats_past = _sector_stats(past_stocks)
    else:
        stats_past = {}

    rotations = []
    for sec, now in stats_now.items():
        past = stats_past.get(sec, {})
        bull_delta = now["bull_pct"] - past.get("bull_pct", now["bull_pct"])
        pcr_delta = now["avg_pcr"] - past.get("avg_pcr", now["avg_pcr"])
        chg_delta = now["avg_chg"] - past.get("avg_chg", 0)

        oi_chg_delta = now["avg_oi_chg"] - past.get("avg_oi_chg", 0)

        rotations.append({
            "Sector": sec,
            "Stocks": now["count"],
            "Avg OI Chg%": now["avg_oi_chg"],
            "OI Δ": round(oi_chg_delta, 2),
            "Bull%": now["bull_pct"],
            "Bull Δ": round(bull_delta, 1),
            "Avg Chg%": now["avg_chg"],
            "Chg Δ": round(chg_delta, 2),
            "Avg PCR": now["avg_pcr"],
            "PCR Δ": round(pcr_delta, 2),
            "Avg Vol(x)": now["avg_vol"],
            "Avg Dlv(x)": now["avg_dlv"],
            "Direction": "Improving" if bull_delta > 10 else
                         "Declining" if bull_delta < -10 else "Stable",
        })
    rotations.sort(key=lambda x: x["Bull Δ"], reverse=True)
    return rotations


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
