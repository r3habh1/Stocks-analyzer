#!/usr/bin/env python3
"""
Outrunner Backtest — Do our picks actually move big the next day?

For an options trader, the stock needs to MOVE. This script:
1. Picks top stocks each day using Score Sweet Spot
2. Checks next-day OHLC: open→high, open→low, open→close
3. Classifies each pick as Outrunner / Moderate / Dud
4. Analyzes WHAT factors separate outrunners from duds
5. Gives a clear verdict on whether our picks work for options

An "outrunner" = stock moves ≥1.5% intraday from open (either direction
is tradeable for options, but ideally in the predicted bullish direction).
"""

import sys
from pathlib import Path
from collections import defaultdict

# So we can import core.* without streamlit
import types
_fake_st = types.ModuleType("streamlit")
def _passthrough(*a, **k):
    if a and callable(a[0]):
        return a[0]
    return lambda f: f
_fake_st.cache_resource = _passthrough
_fake_st.cache_data = _passthrough
sys.modules["streamlit"] = _fake_st

from core.loader import DataCache
from core.scorer import base_score, score_breakdown, BULLISH

# ── Config ──────────────────────────────────────────────────
TOP_N        = 3          # how many stocks we pick per day
OUTRUNNER    = 1.5        # % move from open to qualify as outrunner
MODERATE     = 0.8        # % move from open to qualify as moderate
DAYS         = 60         # how many days of data

# ── Load data ───────────────────────────────────────────────
print("Loading 60 days of data...")
cache = DataCache()
cache.load(DAYS)
print(f"  Dates: {cache.dates[0]} → {cache.dates[-1]}  ({len(cache.dates)} days)")
print(f"  Symbols: {len(cache.symbols)}")
print()

# ── Run picks and track next-day outcome ────────────────────

all_picks = []       # every pick with full context
outrunners = []
moderates = []
duds = []

for i, dt in enumerate(cache.dates):
    if i + 1 >= len(cache.dates):
        break  # need next day

    next_dt = cache.dates[i + 1]

    # Pick stocks using Sweet Spot (score 20-34)
    candidates = []
    for sym, s in cache.data.get(dt, {}).items():
        vol = s.get("volume_times", 0)
        pcr = s.get("pcr", 1)
        if vol < 0.7 and pcr >= 1:
            continue
        sc = base_score(s)
        if 20 <= sc <= 34:
            candidates.append((sym, sc, s))
    candidates.sort(key=lambda x: x[1], reverse=True)

    for sym, sc, s in candidates[:TOP_N]:
        close = s.get("close", 0)
        if close <= 0:
            continue

        # Next day OHLC
        ohlc = cache.ohlc.get(sym, {}).get(next_dt)
        nxt_deriv = cache.data.get(next_dt, {}).get(sym)

        if not ohlc or ohlc["open"] <= 0:
            continue

        nxt_open  = ohlc["open"]
        nxt_high  = ohlc["high"]
        nxt_low   = ohlc["low"]
        nxt_close = ohlc["close"] if ohlc["close"] > 0 else (
            nxt_deriv["close"] if nxt_deriv and nxt_deriv.get("close", 0) > 0 else 0
        )

        # Sanity check (skip splits / bad data)
        gap = abs((nxt_open - close) / close * 100)
        if gap > 20:
            continue

        # Calculate intraday moves from open
        up_move   = (nxt_high - nxt_open) / nxt_open * 100   # max upside %
        down_move = (nxt_open - nxt_low) / nxt_open * 100    # max downside %
        close_chg = (nxt_close - nxt_open) / nxt_open * 100  # open→close %
        range_pct = (nxt_high - nxt_low) / nxt_open * 100    # total range %

        # For bullish picks: up_move is what matters most
        # But for options, even down_move is tradeable (buy puts)
        max_move = max(up_move, down_move)

        # Classify
        if max_move >= OUTRUNNER:
            label = "OUTRUNNER"
        elif max_move >= MODERATE:
            label = "MODERATE"
        else:
            label = "DUD"

        # Was the move in our predicted direction (bullish)?
        direction_correct = close_chg > 0

        bd = score_breakdown(s)

        pick = {
            "pick_date":   dt,
            "next_date":   next_dt,
            "symbol":      sym,
            "score":       sc,
            "close":       close,
            "oi_trend":    s.get("oi_trend", ""),
            "pcr":         s.get("pcr", 0),
            "pcr_chg":     s.get("pcr_change_1d", 0),
            "oi_chg_pct":  s.get("oi_change_pct", 0),
            "vol_times":   s.get("volume_times", 0),
            "dlv_times":   s.get("delivery_times", 0),
            "change_pct":  s.get("change_pct", 0),
            "mcap":        s.get("mcap_category", ""),
            "sector":      s.get("sector", ""),
            # next day
            "nxt_open":    round(nxt_open, 2),
            "nxt_high":    round(nxt_high, 2),
            "nxt_low":     round(nxt_low, 2),
            "nxt_close":   round(nxt_close, 2),
            "up_move":     round(up_move, 2),
            "down_move":   round(down_move, 2),
            "close_chg":   round(close_chg, 2),
            "range_pct":   round(range_pct, 2),
            "max_move":    round(max_move, 2),
            "label":       label,
            "direction_ok": direction_correct,
            # score breakdown
            "bd_oi_trend":  bd.get("OI Trend", 0),
            "bd_pcr":       bd.get("PCR", 0),
            "bd_oi_chg":    bd.get("OI Change", 0),
            "bd_volume":    bd.get("Volume", 0),
            "bd_delivery":  bd.get("Delivery", 0),
            "bd_momentum":  bd.get("Momentum", 0),
            "bd_bonus":     bd.get("Bonus", 0),
        }

        all_picks.append(pick)
        if label == "OUTRUNNER":
            outrunners.append(pick)
        elif label == "MODERATE":
            moderates.append(pick)
        else:
            duds.append(pick)


# ── RESULTS ─────────────────────────────────────────────────
total = len(all_picks)
if total == 0:
    print("No picks generated. Check data.")
    sys.exit(1)

n_out = len(outrunners)
n_mod = len(moderates)
n_dud = len(duds)

print("=" * 70)
print("  OUTRUNNER BACKTEST — Do Our Picks Move for Options?")
print("=" * 70)
print(f"  Strategy:  Score Sweet Spot (20-34)  |  Top {TOP_N} / day")
print(f"  Period:    {cache.dates[0]} → {cache.dates[-2]}  ({len(cache.dates)-1} trading days)")
print(f"  Total picks analyzed: {total}")
print()

# ── 1. Hit Rate ─────────────────────────────────────────────
print("─" * 70)
print("  1. OUTRUNNER HIT RATE")
print("─" * 70)
print(f"  OUTRUNNER (≥{OUTRUNNER}% move):  {n_out:>3} picks  ({n_out/total*100:5.1f}%)")
print(f"  MODERATE  (≥{MODERATE}% move):  {n_mod:>3} picks  ({n_mod/total*100:5.1f}%)")
print(f"  DUD       (<{MODERATE}% move):  {n_dud:>3} picks  ({n_dud/total*100:5.1f}%)")
print(f"  Actionable (OUT+MOD):    {n_out+n_mod:>3} picks  ({(n_out+n_mod)/total*100:5.1f}%)")
print()

# Direction accuracy
dir_ok = sum(1 for p in all_picks if p["direction_ok"])
out_dir = sum(1 for p in outrunners if p["direction_ok"])
print(f"  Direction correct (closed green):  {dir_ok}/{total}  ({dir_ok/total*100:.1f}%)")
if outrunners:
    print(f"  Outrunners that closed green:      {out_dir}/{n_out}  ({out_dir/n_out*100:.1f}%)")
print()

# ── 2. Average Moves ────────────────────────────────────────
print("─" * 70)
print("  2. AVERAGE NEXT-DAY MOVES")
print("─" * 70)

def avg(lst, key):
    vals = [p[key] for p in lst]
    return sum(vals) / len(vals) if vals else 0

print(f"  {'Category':<15} {'Avg Up%':>8} {'Avg Down%':>10} {'Avg Range%':>11} {'Avg Close%':>11}")
print(f"  {'─'*15} {'─'*8} {'─'*10} {'─'*11} {'─'*11}")
print(f"  {'ALL PICKS':<15} {avg(all_picks,'up_move'):>+8.2f} {avg(all_picks,'down_move'):>10.2f} {avg(all_picks,'range_pct'):>11.2f} {avg(all_picks,'close_chg'):>+11.2f}")
if outrunners:
    print(f"  {'OUTRUNNERS':<15} {avg(outrunners,'up_move'):>+8.2f} {avg(outrunners,'down_move'):>10.2f} {avg(outrunners,'range_pct'):>11.2f} {avg(outrunners,'close_chg'):>+11.2f}")
if moderates:
    print(f"  {'MODERATE':<15} {avg(moderates,'up_move'):>+8.2f} {avg(moderates,'down_move'):>10.2f} {avg(moderates,'range_pct'):>11.2f} {avg(moderates,'close_chg'):>+11.2f}")
if duds:
    print(f"  {'DUDS':<15} {avg(duds,'up_move'):>+8.2f} {avg(duds,'down_move'):>10.2f} {avg(duds,'range_pct'):>11.2f} {avg(duds,'close_chg'):>+11.2f}")

# Compare vs random stocks (all stocks on same dates)
random_moves = []
for i, dt in enumerate(cache.dates):
    if i + 1 >= len(cache.dates):
        break
    next_dt = cache.dates[i + 1]
    for sym, s in cache.data.get(dt, {}).items():
        cl = s.get("close", 0)
        if cl <= 0:
            continue
        ohlc = cache.ohlc.get(sym, {}).get(next_dt)
        if not ohlc or ohlc["open"] <= 0 or ohlc["high"] <= 0:
            continue
        gap = abs((ohlc["open"] - cl) / cl * 100)
        if gap > 20:
            continue
        up = (ohlc["high"] - ohlc["open"]) / ohlc["open"] * 100
        dn = (ohlc["open"] - ohlc["low"]) / ohlc["open"] * 100
        rng = (ohlc["high"] - ohlc["low"]) / ohlc["open"] * 100
        nc = ohlc["close"] if ohlc["close"] > 0 else 0
        cc = (nc - ohlc["open"]) / ohlc["open"] * 100 if nc > 0 else 0
        random_moves.append({"up": up, "dn": dn, "rng": rng, "cc": cc})

if random_moves:
    ru = sum(r["up"] for r in random_moves) / len(random_moves)
    rd = sum(r["dn"] for r in random_moves) / len(random_moves)
    rr = sum(r["rng"] for r in random_moves) / len(random_moves)
    rc = sum(r["cc"] for r in random_moves) / len(random_moves)
    print(f"  {'RANDOM(all)':<15} {ru:>+8.2f} {rd:>10.2f} {rr:>11.2f} {rc:>+11.2f}")
    print()
    print(f"  Our picks avg range: {avg(all_picks,'range_pct'):.2f}%  vs  Random: {rr:.2f}%")
    edge = avg(all_picks, "range_pct") - rr
    print(f"  EDGE over random:    {edge:+.2f}% range")
print()

# ── 3. What makes an outrunner? Factor comparison ───────────
print("─" * 70)
print("  3. WHAT MAKES AN OUTRUNNER? (Factor Averages)")
print("─" * 70)

factors = [
    ("Score",       "score"),
    ("PCR",         "pcr"),
    ("PCR Change",  "pcr_chg"),
    ("OI Change%",  "oi_chg_pct"),
    ("Volume(x)",   "vol_times"),
    ("Delivery(x)", "dlv_times"),
    ("Prev Chg%",   "change_pct"),
]

print(f"  {'Factor':<15} {'Outrunner':>10} {'Moderate':>10} {'Dud':>10} {'Signal':>20}")
print(f"  {'─'*15} {'─'*10} {'─'*10} {'─'*10} {'─'*20}")

for name, key in factors:
    vo = avg(outrunners, key) if outrunners else 0
    vm = avg(moderates, key) if moderates else 0
    vd = avg(duds, key) if duds else 0

    # Determine signal direction
    if outrunners and duds:
        diff = vo - vd
        if abs(diff) > 0.1:
            if diff > 0:
                signal = f"Higher = better"
            else:
                signal = f"Lower = better"
        else:
            signal = "No clear signal"
    else:
        signal = "—"

    print(f"  {name:<15} {vo:>10.2f} {vm:>10.2f} {vd:>10.2f} {signal:>20}")

# Score breakdown comparison
print()
print(f"  {'Score Factor':<15} {'Outrunner':>10} {'Dud':>10} {'Delta':>10}")
print(f"  {'─'*15} {'─'*10} {'─'*10} {'─'*10}")
bd_keys = [("OI Trend", "bd_oi_trend"), ("PCR", "bd_pcr"), ("OI Change", "bd_oi_chg"),
           ("Volume", "bd_volume"), ("Delivery", "bd_delivery"),
           ("Momentum", "bd_momentum"), ("Bonus", "bd_bonus")]
for name, key in bd_keys:
    vo = avg(outrunners, key) if outrunners else 0
    vd = avg(duds, key) if duds else 0
    delta = vo - vd
    marker = " <<<" if abs(delta) >= 1.0 else ""
    print(f"  {name:<15} {vo:>10.2f} {vd:>10.2f} {delta:>+10.2f}{marker}")

print()

# ── 4. OI Trend breakdown ──────────────────────────────────
print("─" * 70)
print("  4. OI TREND → OUTRUNNER RATE")
print("─" * 70)

trend_stats = defaultdict(lambda: {"total": 0, "out": 0, "mod": 0, "dud": 0,
                                    "avg_range": 0, "ranges": []})
for p in all_picks:
    t = p["oi_trend"]
    trend_stats[t]["total"] += 1
    trend_stats[t]["ranges"].append(p["range_pct"])
    if p["label"] == "OUTRUNNER":
        trend_stats[t]["out"] += 1
    elif p["label"] == "MODERATE":
        trend_stats[t]["mod"] += 1
    else:
        trend_stats[t]["dud"] += 1

print(f"  {'OI Trend':<25} {'Picks':>6} {'Out%':>6} {'Mod%':>6} {'Dud%':>6} {'AvgRange%':>10}")
print(f"  {'─'*25} {'─'*6} {'─'*6} {'─'*6} {'─'*6} {'─'*10}")
for t, s in sorted(trend_stats.items(), key=lambda x: x[1]["out"]/max(x[1]["total"],1), reverse=True):
    ar = sum(s["ranges"]) / len(s["ranges"]) if s["ranges"] else 0
    print(f"  {t:<25} {s['total']:>6} {s['out']/s['total']*100:>5.0f}% {s['mod']/s['total']*100:>5.0f}% {s['dud']/s['total']*100:>5.0f}% {ar:>10.2f}")

print()

# ── 5. MCap breakdown ──────────────────────────────────────
print("─" * 70)
print("  5. MARKET CAP → OUTRUNNER RATE")
print("─" * 70)

mcap_stats = defaultdict(lambda: {"total": 0, "out": 0, "ranges": []})
for p in all_picks:
    m = p["mcap"]
    mcap_stats[m]["total"] += 1
    mcap_stats[m]["ranges"].append(p["range_pct"])
    if p["label"] == "OUTRUNNER":
        mcap_stats[m]["out"] += 1

print(f"  {'MCap':<15} {'Picks':>6} {'Outrunner%':>11} {'AvgRange%':>10}")
print(f"  {'─'*15} {'─'*6} {'─'*11} {'─'*10}")
for m, s in sorted(mcap_stats.items(), key=lambda x: x[1]["out"]/max(x[1]["total"],1), reverse=True):
    ar = sum(s["ranges"]) / len(s["ranges"]) if s["ranges"] else 0
    print(f"  {m:<15} {s['total']:>6} {s['out']/s['total']*100:>10.1f}% {ar:>10.2f}")

print()

# ── 6. Sector breakdown ─────────────────────────────────────
print("─" * 70)
print("  6. SECTOR → OUTRUNNER RATE (top 10)")
print("─" * 70)

sec_stats = defaultdict(lambda: {"total": 0, "out": 0, "ranges": []})
for p in all_picks:
    sec = p["sector"]
    sec_stats[sec]["total"] += 1
    sec_stats[sec]["ranges"].append(p["range_pct"])
    if p["label"] == "OUTRUNNER":
        sec_stats[sec]["out"] += 1

ranked = sorted(sec_stats.items(), key=lambda x: x[1]["out"]/max(x[1]["total"],1), reverse=True)
print(f"  {'Sector':<30} {'Picks':>6} {'Outrunner%':>11} {'AvgRange%':>10}")
print(f"  {'─'*30} {'─'*6} {'─'*11} {'─'*10}")
for sec, s in ranked[:10]:
    ar = sum(s["ranges"]) / len(s["ranges"]) if s["ranges"] else 0
    print(f"  {sec:<30} {s['total']:>6} {s['out']/s['total']*100:>10.1f}% {ar:>10.2f}")

print()

# ── 7. Sample outrunners + duds ─────────────────────────────
print("─" * 70)
print("  7. SAMPLE OUTRUNNERS (best 10)")
print("─" * 70)
best = sorted(outrunners, key=lambda x: x["max_move"], reverse=True)[:10]
print(f"  {'Date':<12} {'Symbol':<12} {'Score':>5} {'OI Trend':<22} {'Up%':>6} {'Down%':>6} {'Range%':>7} {'Close%':>7}")
for p in best:
    print(f"  {p['pick_date']:<12} {p['symbol']:<12} {p['score']:>5} {p['oi_trend']:<22} {p['up_move']:>+6.2f} {p['down_move']:>6.2f} {p['range_pct']:>7.2f} {p['close_chg']:>+7.2f}")

print()
print("─" * 70)
print("  8. SAMPLE DUDS (worst 10)")
print("─" * 70)
worst = sorted(duds, key=lambda x: x["max_move"])[:10]
print(f"  {'Date':<12} {'Symbol':<12} {'Score':>5} {'OI Trend':<22} {'Up%':>6} {'Down%':>6} {'Range%':>7} {'Close%':>7}")
for p in worst:
    print(f"  {p['pick_date']:<12} {p['symbol']:<12} {p['score']:>5} {p['oi_trend']:<22} {p['up_move']:>+6.2f} {p['down_move']:>6.2f} {p['range_pct']:>7.2f} {p['close_chg']:>+7.2f}")

print()

# ── 9. RECOMMENDATIONS ──────────────────────────────────────
print("=" * 70)
print("  9. VERDICT & RECOMMENDATIONS")
print("=" * 70)

actionable_pct = (n_out + n_mod) / total * 100

print()
if actionable_pct >= 70:
    print("  VERDICT: STRONG — Our picks generate enough movement for options.")
elif actionable_pct >= 50:
    print("  VERDICT: DECENT — Majority of picks move, but room to improve.")
elif actionable_pct >= 30:
    print("  VERDICT: WEAK — Too many duds, needs filter refinement.")
else:
    print("  VERDICT: POOR — Strategy doesn't generate enough movement.")

print(f"  Actionable rate: {actionable_pct:.1f}%  ({n_out+n_mod}/{total} picks)")
print()

# Find best filters
print("  KEY FINDINGS:")
print()

# Best OI trend
best_trend = max(trend_stats.items(), key=lambda x: x[1]["out"]/max(x[1]["total"],1))
if best_trend[1]["total"] >= 5:
    pct = best_trend[1]["out"] / best_trend[1]["total"] * 100
    print(f"  - Best OI Trend:  {best_trend[0]}  ({pct:.0f}% outrunner rate)")

# Best mcap
best_mcap = max(mcap_stats.items(), key=lambda x: x[1]["out"]/max(x[1]["total"],1))
if best_mcap[1]["total"] >= 5:
    pct = best_mcap[1]["out"] / best_mcap[1]["total"] * 100
    print(f"  - Best MCap:      {best_mcap[0]}  ({pct:.0f}% outrunner rate)")

# Volume threshold
high_vol = [p for p in all_picks if p["vol_times"] >= 1.5]
low_vol  = [p for p in all_picks if p["vol_times"] < 1.0]
if high_vol and low_vol:
    hv_out = sum(1 for p in high_vol if p["label"] == "OUTRUNNER") / len(high_vol) * 100
    lv_out = sum(1 for p in low_vol if p["label"] == "OUTRUNNER") / len(low_vol) * 100
    print(f"  - Vol ≥1.5x:      {hv_out:.0f}% outrunner rate  ({len(high_vol)} picks)")
    print(f"  - Vol <1.0x:      {lv_out:.0f}% outrunner rate  ({len(low_vol)} picks)")

# Delivery threshold
high_dlv = [p for p in all_picks if p["dlv_times"] >= 1.5]
low_dlv  = [p for p in all_picks if p["dlv_times"] < 1.0]
if high_dlv and low_dlv:
    hd_out = sum(1 for p in high_dlv if p["label"] == "OUTRUNNER") / len(high_dlv) * 100
    ld_out = sum(1 for p in low_dlv if p["label"] == "OUTRUNNER") / len(low_dlv) * 100
    print(f"  - Dlv ≥1.5x:      {hd_out:.0f}% outrunner rate  ({len(high_dlv)} picks)")
    print(f"  - Dlv <1.0x:      {ld_out:.0f}% outrunner rate  ({len(low_dlv)} picks)")

# OI change threshold
high_oi = [p for p in all_picks if p["oi_chg_pct"] >= 5]
low_oi  = [p for p in all_picks if p["oi_chg_pct"] < 2]
if high_oi and low_oi:
    ho_out = sum(1 for p in high_oi if p["label"] == "OUTRUNNER") / len(high_oi) * 100
    lo_out = sum(1 for p in low_oi if p["label"] == "OUTRUNNER") / len(low_oi) * 100
    print(f"  - OI Chg ≥5%:     {ho_out:.0f}% outrunner rate  ({len(high_oi)} picks)")
    print(f"  - OI Chg <2%:     {lo_out:.0f}% outrunner rate  ({len(low_oi)} picks)")

# Previous day momentum
pos_mom = [p for p in all_picks if p["change_pct"] > 1.0]
neg_mom = [p for p in all_picks if p["change_pct"] < 0]
if pos_mom and neg_mom:
    pm_out = sum(1 for p in pos_mom if p["label"] == "OUTRUNNER") / len(pos_mom) * 100
    nm_out = sum(1 for p in neg_mom if p["label"] == "OUTRUNNER") / len(neg_mom) * 100
    print(f"  - Prev chg >1%:   {pm_out:.0f}% outrunner rate  ({len(pos_mom)} picks)")
    print(f"  - Prev chg <0%:   {nm_out:.0f}% outrunner rate  ({len(neg_mom)} picks)")

print()
print("  SUGGESTED FILTERS TO ADD:")
# Generate dynamic suggestions based on the data
suggestions = []

if high_vol and low_vol:
    hv_rate = sum(1 for p in high_vol if p["label"] == "OUTRUNNER") / len(high_vol) * 100
    lv_rate = sum(1 for p in low_vol if p["label"] == "OUTRUNNER") / len(low_vol) * 100
    if hv_rate > lv_rate + 10:
        suggestions.append(f"  - Prefer Volume ≥ 1.5x  (outrunner rate jumps from {lv_rate:.0f}% to {hv_rate:.0f}%)")

if high_dlv and low_dlv:
    hd_rate = sum(1 for p in high_dlv if p["label"] == "OUTRUNNER") / len(high_dlv) * 100
    ld_rate = sum(1 for p in low_dlv if p["label"] == "OUTRUNNER") / len(low_dlv) * 100
    if hd_rate > ld_rate + 10:
        suggestions.append(f"  - Prefer Delivery ≥ 1.5x  (outrunner rate jumps from {ld_rate:.0f}% to {hd_rate:.0f}%)")

if high_oi and low_oi:
    ho_rate = sum(1 for p in high_oi if p["label"] == "OUTRUNNER") / len(high_oi) * 100
    lo_rate = sum(1 for p in low_oi if p["label"] == "OUTRUNNER") / len(low_oi) * 100
    if ho_rate > lo_rate + 10:
        suggestions.append(f"  - Prefer OI Change ≥ 5%  (outrunner rate jumps from {lo_rate:.0f}% to {ho_rate:.0f}%)")

# MCap preference
for m, s in mcap_stats.items():
    if s["total"] >= 10:
        rate = s["out"] / s["total"] * 100
        ar = sum(s["ranges"]) / len(s["ranges"])
        if rate >= 70 and ar >= 2.0:
            suggestions.append(f"  - Focus on {m}  ({rate:.0f}% outrunner, {ar:.1f}% avg range)")

if suggestions:
    for s in suggestions:
        print(s)
else:
    print("  - No strong single-factor filter found. Consider multi-factor combos.")

print()
print("=" * 70)
