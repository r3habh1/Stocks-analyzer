"""Scoring engine + outrunner conviction."""

from __future__ import annotations

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
