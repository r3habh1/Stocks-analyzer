"""Manual — How to use the Trading Dashboard to find swing & options stocks."""

import streamlit as st

st.set_page_config(page_title="Manual", page_icon="📖", layout="wide")

with st.sidebar:
    st.header("Navigation")
    st.page_link("app.py", label="Home", icon="🏠")
    st.page_link("pages/1_Stock_Analysis.py", label="Stock Analysis", icon="🔍")
    st.page_link("pages/2_Backtest.py", label="Backtest", icon="🔬")
    st.page_link("pages/3_Import_Data.py", label="Import Data", icon="📥")
    st.page_link("pages/4_Manual.py", label="Manual", icon="📖")
    st.divider()

st.title("📖 Trading Dashboard — Manual")
st.caption("A step-by-step guide to finding swing and options stocks using this app.")

st.divider()

# ── Step 1 ──────────────────────────────────────────────────
st.header("Step 1: Import Today's Data")
st.markdown("""
Go to **Import Data** in the sidebar. Upload your daily **Derivative Analytics CSV**.

The app **upserts** — it adds new records and updates existing ones without deleting history.
After import, go back to the **Home** page to see fresh data.
""")

st.divider()

# ── Step 2 ──────────────────────────────────────────────────
st.header("Step 2: Read the Daily Summary & Bullish vs Bearish")
st.markdown("""
The blue box at the top gives you the big picture in one sentence:

- How many stocks are **bullish vs bearish** today
- Whether sentiment **improved or weakened** vs yesterday
- **Avg PCR** and **Avg Change** across the market
- Count of **trend flips**, **PCR extremes**, **delivery spikes**

**Bullish vs Bearish** chart (just below) shows the trend over time for your MCap filter.
Use the **View date** in the sidebar to see past days.

**What to look for:** If bullish % is improving day-over-day and Avg PCR is below 0.7,
the market is leaning bullish — favor long/call setups.
""")

st.divider()

# ── Step 3 ──────────────────────────────────────────────────
st.header("Step 3: Check Key Metrics")
st.markdown("""
The 6 metrics row gives you a quick health check:

| Metric | Meaning |
|--------|---------|
| **Bullish / Bearish** | Overall market tilt (NewLong + ShortCover vs NewShort + LongCover) |
| **Avg PCR** | Below 0.7 = market is call-heavy (bullish). Above 1.0 = put-heavy (bearish) |
| **Avg Change** | Is the market up or down today? |
| **Avg Volume** | Above 1.0x = higher than average activity |
| **Avg Delivery** | Above 1.0x = real money flow, not just speculation |
""")

st.divider()

# ── Step 4 ──────────────────────────────────────────────────
st.header("Step 4: Set Your Filters")
st.markdown("""
Choose **Market Cap** (All / Large / Mid / Small Cap) and **Time Range** (Today, 3 Days, 5 Days, 10 Days, 21 Days).

**For swing trading:**
- Start with **5 Days** to see which sectors are rotating
- **Mid Cap** often has the best swing setups — more volatile, enough liquidity
- Switch to **10-21 Days** to confirm longer-term sector trends

These filters affect **Bullish vs Bearish**, **Sector Rotation**, **Distributions**, and **Quick Picks / Stock Sheet**.
The Key Metrics and Alerts always show all stocks (unfiltered).
""")

st.divider()

# ── Step 5 ──────────────────────────────────────────────────
st.header("Step 5: Sector Rotation — Find the Hot Sectors")
st.markdown("**Bullish vs Bearish** (above) shows the overall trend over time. **Sector Rotation** is your most important section. Click a sector row to see its stocks.")

st.markdown("""
| Column | What It Tells You |
|--------|-------------------|
| **Agg Chg %** | Average price change in the sector |
| **Chg Δ** | Price change momentum shift vs N days ago |
| **Bull%** | % of stocks with bullish OI trend (NewLong or ShortCover) |
| **Bull Δ** | How much Bull% changed vs N days ago. Green = sector improving |
| **Vol(x)** | Above 1.5x = institutional participation (highlighted) |
| **Dlv(x)** | Above 1.5x = real buying (highlighted) |
| **PCR** | Below 0.7 = call writers confident. Sweet spot for longs |
| **PCR Δ** | PCR shift. Declining PCR = growing bullish confidence |
| **Agg Call OI Chg%** | Call OI change vs previous day |
| **Agg Put OI Chg%** | Put OI change vs previous day |
| **Direction** | Improving (Bull Δ > 10), Declining (< -10), or Stable — color-coded |

**Ideal sector for swing:** High Bull%, low PCR (< 0.7), rising Agg Chg%, Vol/Dlv above 1.5x.
""")

st.info("**Pro tip:** The bar chart shows Bull Δ visually — sectors on the right (green) "
        "are improving. The scatter plot maps Price Change vs PCR Change — "
        "top-right quadrant (price up + PCR rising) needs caution; "
        "bottom-right (price up + PCR falling) is the sweet spot.")

st.divider()

# ── Step 6 ──────────────────────────────────────────────────
st.header("Step 6: Distributions — Confirm Your Thesis")
st.markdown("""
These charts show the distribution of all stocks (filtered by MCap and Time Range), in 3-per-row layout:

**Row 1:** OI Trend (pie) | Price Change % | Volume (≥1.5x highlighted)  
**Row 2:** Delivery (≥1.5x highlighted) | Call OI Change % | Put OI Change %  
**Row 3:** PCR (reference lines at 0.5, 1.0, 1.5; ≥1.5 highlighted)

When you change the **Time Range**, distributions aggregate data across all days in that range.
""")

st.divider()

# ── Step 7 ──────────────────────────────────────────────────
st.header("Step 7: Alerts & Signals — Find Individual Stocks")
st.markdown("""
Now you narrow down to specific stocks. All symbols are **clickable** — they take you
to the full Stock Analysis page.

**1. OI Trend Flips**
Stocks that just flipped from bearish to bullish today. A stock going from
`NewShort` → `NewLong` means shorts are covering and new longs are entering.
This is a **strong momentum signal** — these are fresh setups.

**2. PCR Extremes**
- *Low PCR (≤ 0.5):* Put writers are very confident this stock goes up.
  Good for **buying calls** or swing longs.
- *High PCR (≥ 1.5):* Heavy put buying. Could mean fear — good for
  **buying puts** or staying away from longs.

**3. Delivery Spikes (≥ 2x)**
Institutions are taking delivery. This is real money, not F&O speculation.
**High delivery + bullish OI trend = strong swing candidate.**

**4. 3+ Day Streaks**
Stocks that have been in the scoring sweet spot (20-34) for 3+ consecutive days.
Persistent conviction = higher probability setup. These are the most reliable.
""")

st.divider()

# ── Step 8 ──────────────────────────────────────────────────
st.header("Step 8: Quick Picks & Stock Sheet — Your Shortlist")
st.markdown("""
Two **tabs** at the bottom of the Home page:

**Quick Picks** — Top 10 stocks in the sweet spot (Score 20–34), sorted by **Conviction + Score**.
Higher conviction = higher probability of a big next-day move. Focus on **Conv > 12**.

**Stock Sheet** — All stocks for your filter (MCap + view date), sorted by conviction + score.
Use this as a full action sheet to scan the entire universe.

Both tables show OI, PCR, Vol, Delivery, and OI Trend. Click any symbol to jump to full Stock Analysis.
""")

st.divider()

# ── Step 9 ──────────────────────────────────────────────────
st.header("Step 9: Stock Analysis — Deep Dive Before Trading")
st.markdown("""
Once you click a stock, the header shows **Symbol | MCap | View Date**. You see its full history:

| Chart | What to Look For |
|-------|-----------------|
| **Price** | Is it trending up or consolidating? Avoid stocks already up 5%+ today |
| **Score** | Has it consistently been above 20? Green bars = in sweet spot |
| **Conviction** | Is today's conviction a spike or sustained? Green (≥12) is strong |
| **OI Change %** | Green bars = participants building positions. Consistent green = strong |
| **PCR Trend** | Is PCR declining (bullish) or rising? Below 0.5 dotted line = extreme |
| **Volume** | Any recent spikes above 1.5x threshold? |
| **Delivery** | Spikes above 2.0x = institutional conviction |
| **OI Trend Timeline** | Pattern of NewLong/ShortCover days (green/blue squares) |

**Conviction Breakdown** at the bottom shows which factors are contributing most
to the stock's conviction score — helps you understand *why* the stock is ranked high.
""")

st.divider()

# ── Checklist ───────────────────────────────────────────────
st.header("The Ideal Swing Stock Checklist")
st.markdown("""
Before you take a trade, the stock should tick **6 or more** of these:
""")

checklist = [
    ("Score 20-34", "Sweet spot range from backtesting"),
    ("Conviction > 10", "High outrunner probability"),
    ("OI Trend: NewLong or ShortCover", "Bullish open interest positioning"),
    ("PCR < 0.7", "Put writers confident, call-heavy"),
    ("OI Change: Positive", "Fresh money entering, not unwinding"),
    ("Volume > 1.2x", "Above average participation"),
    ("Delivery > 1.5x", "Institutional buying, real money"),
    ("Sector: Hot rotating sector", "Positive Bull Δ in sector rotation"),
    ("Price Change: Not already up 5%+", "Avoid chasing — find early setups"),
]

for item, desc in checklist:
    st.checkbox(f"**{item}** — {desc}", value=False, disabled=True)

st.divider()

# ── Daily Workflow ──────────────────────────────────────────
st.header("Daily Workflow (5 Minutes)")
st.markdown("""
1. **Upload CSV** in Import Data
2. **Read Daily Summary** — bullish or bearish day?
3. **Check Bullish vs Bearish** chart — trend over time
4. **Check Sector Rotation** at 5 Days — which sectors are improving?
5. **Scan Alerts** — any trend flips or delivery spikes in hot sectors?
6. **Check Quick Picks tab** — top 10; switch to Stock Sheet for full scan
7. **Click into top candidates** — verify on Stock Analysis page
8. **Trade** the ones that tick 6+ items on the checklist above
""")

st.divider()

# ── Scoring Reference ──────────────────────────────────────
st.header("Scoring Reference")

with st.expander("How Score is Calculated (0-40+)"):
    st.markdown("""
| Factor | Points |
|--------|--------|
| **OI Trend** | NewLong/ShortCover: +8, NewShort/LongCover: -8 |
| **PCR** | < 0.7: +7, 0.7-0.9: +6, 0.9-1.0: +3, > 1.2: -3 |
| **PCR Change** | Falling (< -0.1): +3, Rising (> 0.1): -3 |
| **OI Change %** | > 10%: +8, > 5%: +5, > 2%: +3, > 0%: +1, < -5%: -3 |
| **Volume** | > 2.0x: +5, > 1.5x: +4, > 1.2x: +2 |
| **Delivery** | > 2.0x: +5, > 1.5x: +4, > 1.2x: +2 |

**Sweet Spot:** Score 20-34. Below 20 = weak. Above 34 = possibly overextended.
""")

with st.expander("How Conviction is Calculated (0-19)"):
    st.markdown("""
Conviction measures the probability of a big next-day move (outrunner).

| Factor | Max Points | What Triggers High Score |
|--------|-----------|------------------------|
| **OI Trend** | 4 | ShortCover (+4), NewLong (+3) |
| **Volume** | 4 | > 2.0x (+4), > 1.5x (+3) |
| **Delivery** | 4 | > 2.5x (+4), > 2.0x (+3) |
| **PCR** | 4 | < 0.5 (+4), < 0.7 (+3) |
| **OI Change** | 3 | > 10% (+3), > 5% (+2) |

**High conviction (≥ 12):** Strong probability of 3%+ next-day move.
**Medium (8-11):** Moderate probability. **Low (< 8):** Skip or wait.
""")

with st.expander("OI Trend Categories"):
    st.markdown("""
| OI Trend | Meaning | Signal |
|----------|---------|--------|
| **NewLong** | OI increasing + Price increasing | Bullish — fresh buying |
| **ShortCover** | OI decreasing + Price increasing | Bullish — shorts exiting |
| **NewShort** | OI increasing + Price decreasing | Bearish — fresh shorting |
| **LongCover** | OI decreasing + Price decreasing | Bearish — longs exiting |
""")
