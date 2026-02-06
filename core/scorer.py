"""Scoring engine + strategy implementations."""

from __future__ import annotations
from collections import defaultdict
from core.loader import DataCache

BULLISH = {"NewLong", "ShortCover"}

OI_SCORES = {
    "NewLong": 8, "NewShort": -8,
    "ShortCover": 8, "LongCover": -8,
    "Neutral": 0,
}


def base_score(s: dict) -> int:
    """Compute composite score for one stock dict (mapped fields)."""
    sc = OI_SCORES.get(s.get("oi_trend", ""), 0)

    pcr = s.get("pcr", 0)
    pcr_chg = s.get("pcr_change_1d", 0)
    if pcr < 0.7:      sc += 7
    elif pcr <= 0.9:    sc += 6
    elif pcr <= 1.0:    sc += 3
    elif pcr > 1.2:     sc -= 3
    if pcr_chg > 0.1:   sc -= 3
    elif pcr_chg < -0.1: sc += 3
    elif pcr_chg < 0 and pcr < 1.0: sc += 2

    oi = s.get("oi_change_pct", 0)
    if   oi > 10: sc += 8
    elif oi > 5:  sc += 5
    elif oi > 2:  sc += 3
    elif oi > 0:  sc += 1
    elif oi <= -5: sc -= 3

    vol = s.get("volume_times", 0)
    if   vol > 2.0: sc += 5
    elif vol > 1.5: sc += 4
    elif vol > 1.2: sc += 2
    elif vol > 1.0: sc += 1
    elif vol <= 0.7: sc -= 2

    dlv = s.get("delivery_times", 0)
    if   dlv > 2.0: sc += 7
    elif dlv > 1.5: sc += 5
    elif dlv > 1.2: sc += 3
    elif dlv > 1.0: sc += 2
    elif dlv <= 0.7: sc -= 2

    chg = s.get("change_pct", 0)
    if   chg > 3:   sc += 5
    elif chg > 1:   sc += 2
    elif chg > -1:  sc += 0
    elif chg > -3:  sc -= 1
    else:           sc -= 3

    if pcr < 1.0 and vol > 1.0 and dlv > 1.0 and chg > 0:
        sc += 2
    return sc


def score_breakdown(s: dict) -> dict:
    """Return per‑factor breakdown for display."""
    pcr = s.get("pcr", 0); pcr_chg = s.get("pcr_change_1d", 0)
    oi = s.get("oi_change_pct", 0); vol = s.get("volume_times", 0)
    dlv = s.get("delivery_times", 0); chg = s.get("change_pct", 0)

    bd = {}
    bd["OI Trend"] = OI_SCORES.get(s.get("oi_trend", ""), 0)

    v = 0
    if pcr < 0.7: v = 7
    elif pcr <= 0.9: v = 6
    elif pcr <= 1.0: v = 3
    elif pcr > 1.2: v = -3
    if pcr_chg > 0.1: v -= 3
    elif pcr_chg < -0.1: v += 3
    elif pcr_chg < 0 and pcr < 1.0: v += 2
    bd["PCR"] = v

    if oi > 10: bd["OI Change"] = 8
    elif oi > 5: bd["OI Change"] = 5
    elif oi > 2: bd["OI Change"] = 3
    elif oi > 0: bd["OI Change"] = 1
    elif oi <= -5: bd["OI Change"] = -3
    else: bd["OI Change"] = 0

    if vol > 2: bd["Volume"] = 5
    elif vol > 1.5: bd["Volume"] = 4
    elif vol > 1.2: bd["Volume"] = 2
    elif vol > 1.0: bd["Volume"] = 1
    elif vol <= 0.7: bd["Volume"] = -2
    else: bd["Volume"] = 0

    if dlv > 2: bd["Delivery"] = 7
    elif dlv > 1.5: bd["Delivery"] = 5
    elif dlv > 1.2: bd["Delivery"] = 3
    elif dlv > 1.0: bd["Delivery"] = 2
    elif dlv <= 0.7: bd["Delivery"] = -2
    else: bd["Delivery"] = 0

    if chg > 3: bd["Momentum"] = 5
    elif chg > 1: bd["Momentum"] = 2
    elif chg > -1: bd["Momentum"] = 0
    elif chg > -3: bd["Momentum"] = -1
    else: bd["Momentum"] = -3

    bonus = 2 if (pcr < 1 and vol > 1 and dlv > 1 and chg > 0) else 0
    bd["Bonus"] = bonus
    return bd


# ── Outrunner conviction (from backtest findings) ───────────
# Backtested 130 picks over 60 days. Key findings:
#   - 94.6% of picks moved enough for options (outrunner)
#   - ShortCover: 84% outrunner rate vs 64% NewLong
#   - Mid Cap: 80% outrunner rate, 3.03% avg range
#   - Volume ≥ 1.5x → higher outrunner rate
#   - Delivery ≥ 1.5x → higher outrunner rate
#   - Higher prev-day momentum = bigger next-day move
#   - Direction only 38% correct → straddles > directional

BEST_TRENDS = {"ShortCover", "NewLong"}


def outrunner_conviction(s: dict) -> dict:
    """Return conviction score + breakdown for outrunner probability.
    Higher conviction = more likely to be a big mover tomorrow."""
    conv = 0
    reasons = {}

    # OI Trend (biggest factor)
    trend = s.get("oi_trend", "")
    if trend == "ShortCover":
        conv += 4; reasons["OI Trend"] = (4, "Short squeeze — high outrunner rate")
    elif trend == "NewLong":
        conv += 3; reasons["OI Trend"] = (3, "Strong long buildup")
    else:
        reasons["OI Trend"] = (0, "Bearish/Neutral trend")

    # Market Cap (Mid > Large > Small)
    mcap = s.get("mcap_category", "")
    if mcap == "Mid Cap":
        conv += 3; reasons["MCap"] = (3, "Mid Cap — 80% outrunner, 3.0% range")
    elif mcap == "Large Cap":
        conv += 1; reasons["MCap"] = (1, "Large Cap — 64% outrunner")
    elif mcap == "Small Cap":
        conv += 1; reasons["MCap"] = (1, "Small Cap — 60% outrunner")
    else:
        reasons["MCap"] = (0, "Unknown cap")

    # Volume (2.90x avg for outrunners vs 2.20x duds)
    vol = s.get("volume_times", 0)
    if vol >= 2.0:
        conv += 3; reasons["Volume"] = (3, f"{vol:.1f}x — strong activity")
    elif vol >= 1.5:
        conv += 2; reasons["Volume"] = (2, f"{vol:.1f}x — above average")
    elif vol >= 1.0:
        conv += 1; reasons["Volume"] = (1, f"{vol:.1f}x — normal")
    else:
        reasons["Volume"] = (0, f"{vol:.1f}x — low volume")

    # Delivery (2.50x avg for outrunners vs 2.24x duds)
    dlv = s.get("delivery_times", 0)
    if dlv >= 2.0:
        conv += 3; reasons["Delivery"] = (3, f"{dlv:.1f}x — big hands buying")
    elif dlv >= 1.5:
        conv += 2; reasons["Delivery"] = (2, f"{dlv:.1f}x — good conviction")
    elif dlv >= 1.0:
        conv += 1; reasons["Delivery"] = (1, f"{dlv:.1f}x — normal")
    else:
        reasons["Delivery"] = (0, f"{dlv:.1f}x — low delivery")

    # Previous-day momentum (#1 score-breakdown factor, delta +1.12)
    chg = s.get("change_pct", 0)
    if chg >= 3.0:
        conv += 3; reasons["Momentum"] = (3, f"{chg:+.1f}% — strong momentum")
    elif chg >= 1.0:
        conv += 2; reasons["Momentum"] = (2, f"{chg:+.1f}% — positive trend")
    elif chg >= 0:
        conv += 1; reasons["Momentum"] = (1, f"{chg:+.1f}% — flat/mild")
    else:
        reasons["Momentum"] = (0, f"{chg:+.1f}% — negative")

    # PCR < 0.7 with dropping PCR = put writers confident
    pcr = s.get("pcr", 1)
    pcr_chg = s.get("pcr_change_1d", 0)
    if pcr < 0.7 and pcr_chg < 0:
        conv += 2; reasons["PCR Signal"] = (2, f"PCR {pcr:.2f} dropping — put writers confident")
    elif pcr < 0.9:
        conv += 1; reasons["PCR Signal"] = (1, f"PCR {pcr:.2f} — bullish zone")
    else:
        reasons["PCR Signal"] = (0, f"PCR {pcr:.2f} — neutral/bearish")

    # OI Change (buildup = institutional positioning)
    oi = s.get("oi_change_pct", 0)
    if oi >= 5:
        conv += 1; reasons["OI Buildup"] = (1, f"OI +{oi:.1f}% — strong positioning")
    else:
        reasons["OI Buildup"] = (0, f"OI {oi:+.1f}%")

    return {"conviction": conv, "max_conviction": 19, "reasons": reasons}


def trade_suggestion(s: dict) -> dict:
    """Suggest trade type: Calls, Puts, or Straddle/Strangle.
    Based on outrunner backtest — direction only 38% correct on close,
    but stocks definitely MOVE. So we need to be smart."""
    trend = s.get("oi_trend", "")
    pcr = s.get("pcr", 1)
    pcr_chg = s.get("pcr_change_1d", 0)
    chg = s.get("change_pct", 0)
    vol = s.get("volume_times", 0)
    dlv = s.get("delivery_times", 0)

    # Count bullish signals for direction confidence
    bull_signals = 0
    if trend == "ShortCover":  bull_signals += 2  # strongest
    elif trend == "NewLong":   bull_signals += 1
    if pcr < 0.7 and pcr_chg < 0:      bull_signals += 2  # put writers leaving
    elif pcr < 0.9:                     bull_signals += 1
    if chg > 1.0:                       bull_signals += 1  # momentum
    if dlv > 1.5 and chg > 0:          bull_signals += 1  # delivery + green

    if bull_signals >= 5:
        return {
            "type": "BUY CALLS",
            "color": "#22c55e",
            "confidence": "HIGH",
            "reason": "Strong bullish convergence — trend + PCR + momentum aligned",
        }
    elif bull_signals >= 3:
        return {
            "type": "BUY CALLS",
            "color": "#86efac",
            "confidence": "MODERATE",
            "reason": "Multiple bullish signals but not fully confirmed",
        }
    else:
        return {
            "type": "STRADDLE",
            "color": "#6366f1",
            "confidence": "HIGH",
            "reason": "Stock will MOVE (94% rate) but direction unclear — play volatility",
        }


# ── Strategy functions ──────────────────────────────────────
# Each returns [(symbol, score, close_price), …] sorted desc.


def strat_outrunner(cache: DataCache, date: str, **_):
    """Best strategy — Outrunner optimized for options traders.
    Sweet Spot base (20-34) + conviction ranking."""
    out = []
    for sym, s in cache.data.get(date, {}).items():
        v = s.get("volume_times", 0); p = s.get("pcr", 1)
        if v < 0.7 and p >= 1: continue
        sc = base_score(s)
        if 20 <= sc <= 34:
            conv = outrunner_conviction(s)["conviction"]
            # Use conviction as primary sort, base score as tiebreaker
            out.append((sym, sc, s.get("close", 0), conv))
    out.sort(key=lambda x: (x[3], x[1]), reverse=True)
    # Return standard 3-tuple format for compatibility
    return [(sym, sc, cl) for sym, sc, cl, _ in out]


def strat_sweet_spot(cache: DataCache, date: str, **_):
    """Score Sweet Spot (20-34) ranked by base score."""
    out = []
    for sym, s in cache.data.get(date, {}).items():
        v = s.get("volume_times", 0); p = s.get("pcr", 1)
        if v < 0.7 and p >= 1: continue
        sc = base_score(s)
        if 20 <= sc <= 34:
            out.append((sym, sc, s.get("close", 0)))
    out.sort(key=lambda x: x[1], reverse=True)
    return out


def strat_multi_day(cache: DataCache, date: str, **_):
    """Must be in top-10 on previous day too."""
    idx = cache.dates.index(date) if date in cache.dates else -1
    if idx <= 0: return []
    prev = cache.dates[idx - 1]
    prev_scored = []
    for sym, s in cache.data.get(prev, {}).items():
        v = s.get("volume_times", 0); p = s.get("pcr", 1)
        if v < 0.7 and p >= 1: continue
        prev_scored.append((sym, base_score(s)))
    prev_scored.sort(key=lambda x: x[1], reverse=True)
    top10 = {x[0] for x in prev_scored[:10]}
    out = []
    for sym, s in cache.data.get(date, {}).items():
        if sym not in top10: continue
        out.append((sym, base_score(s), s.get("close", 0)))
    out.sort(key=lambda x: x[1], reverse=True)
    return out


def strat_baseline(cache: DataCache, date: str, **_):
    """Original scorer, pick highest scores."""
    out = []
    for sym, s in cache.data.get(date, {}).items():
        v = s.get("volume_times", 0); p = s.get("pcr", 1)
        if v < 0.7 and p >= 1: continue
        out.append((sym, base_score(s), s.get("close", 0)))
    out.sort(key=lambda x: x[1], reverse=True)
    return out


STRATEGIES = {
    "Outrunner (Best)":        strat_outrunner,
    "Score Sweet Spot":        strat_sweet_spot,
    "Multi-Day Confirmation":  strat_multi_day,
    "Baseline (Original)":     strat_baseline,
}


# ── Backtester ──────────────────────────────────────────────

def run_backtest(cache: DataCache, strat_fn, top_n=3, hold=2, capital=100_000):
    """Run a backtest and return stats dict + trades list."""
    trades, equity = [], []
    total_pnl = 0.0; total_inv = 0.0; running = 0.0

    for i, dt in enumerate(cache.dates):
        if i + hold >= len(cache.dates): break
        picks = strat_fn(cache, dt)[:top_n]
        for sym, sc, cl in picks:
            if cl <= 0: continue
            if hold == 1:
                r = cache.exit_price(sym, cl, cache.dates[i + 1])
                edt = cache.dates[i + 1]
            else:
                r = cache.multi_exit(sym, cl, i, hold)
                edt = cache.dates[i + hold]
            if not r: continue
            ent, ext = r
            sh = capital / ent
            pnl = (ext - ent) * sh
            pct = (ext - ent) / ent * 100
            trades.append({"date": dt, "exit_date": edt, "symbol": sym,
                           "score": sc, "entry": round(ent, 2),
                           "exit": round(ext, 2), "pnl": round(pnl, 2),
                           "pnl_pct": round(pct, 2)})
            total_pnl += pnl; total_inv += capital; running += pnl
        equity.append({"date": dt, "equity": running})

    if not trades:
        return {"trades": [], "total_trades": 0, "total_pnl": 0, "return_pct": 0,
                "win_rate": 0, "profit_factor": 0, "equity": equity,
                "avg_win_pct": 0, "avg_loss_pct": 0, "max_dd": 0, "monthly": {}}

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    gp = sum(t["pnl"] for t in wins)
    gl = abs(sum(t["pnl"] for t in losses))
    peak = mx_dd = 0
    for p in equity:
        if p["equity"] > peak: peak = p["equity"]
        dd = peak - p["equity"]
        if dd > mx_dd: mx_dd = dd

    monthly = defaultdict(lambda: {"pnl": 0, "trades": 0, "wins": 0})
    for t in trades:
        m = t["date"][:7]
        monthly[m]["pnl"] += t["pnl"]; monthly[m]["trades"] += 1
        if t["pnl"] > 0: monthly[m]["wins"] += 1

    return {
        "trades": trades, "equity": equity,
        "total_trades": len(trades),
        "total_pnl": round(total_pnl, 2),
        "total_invested": round(total_inv, 2),
        "return_pct": round(total_pnl / total_inv * 100, 2) if total_inv else 0,
        "win_rate": round(len(wins) / len(trades) * 100, 1),
        "profit_factor": round(gp / gl, 2) if gl else 0,
        "avg_win_pct": round(sum(t["pnl_pct"] for t in wins) / len(wins), 2) if wins else 0,
        "avg_loss_pct": round(sum(t["pnl_pct"] for t in losses) / len(losses), 2) if losses else 0,
        "max_dd": round(mx_dd, 2),
        "monthly": dict(monthly),
    }
