"""
Trading Dashboard — Home / Market Pulse + Sector Rotation + Distributions
Run:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from core import loader, scorer, signals

# Session state for sector drill-down (same page, no redirect)
if "selected_sector" not in st.session_state:
    st.session_state.selected_sector = None
if "sector_df_key" not in st.session_state:
    st.session_state.sector_df_key = 0

st.set_page_config(page_title="Trading Dashboard", page_icon="📈", layout="wide")

# ── Sidebar: Navigation first (consistent across pages) ───────
with st.sidebar:
    st.header("Navigation")
    st.page_link("app.py", label="Home", icon="🏠")
    st.page_link("pages/1_Stock_Analysis.py", label="Stock Analysis", icon="🔍")
    st.page_link("pages/2_Backtest.py", label="Backtest", icon="🔬")
    st.page_link("pages/3_Import_Data.py", label="Import Data", icon="📥")
    st.page_link("pages/4_Manual.py", label="Manual", icon="📖")
    st.divider()

st.title("📈 Trading Dashboard")

# ── Load data ───────────────────────────────────────────────
try:
    latest = loader.get_latest_date()
except Exception as e:
    err = str(e)
    if "SSL" in err or "ServerSelectionTimeout" in err or "handshake" in err.lower():
        st.error(
            "**MongoDB connection failed** (SSL/TLS handshake error).\n\n"
            "**Try:**\n"
            "1. Check MongoDB Atlas IP whitelist (allow `0.0.0.0/0` for testing)\n"
            "2. Use Python 3.11 or 3.12 (3.13 can have SSL issues with Atlas)\n"
            "3. Disable VPN or try a different network\n"
            "4. Verify `MONGO_URI` in `.streamlit/secrets.toml`"
        )
    else:
        st.error(f"Database error: {err}")
    st.stop()

if not latest:
    st.error("No data in database. Go to **Import Data** to upload CSV.")
    st.stop()

all_stocks = loader.get_all_for_date(latest)
if not all_stocks:
    st.warning("No stock data for latest date."); st.stop()

# ── Date range filter ───────────────────────────────────────
all_available_dates = loader.get_dates(limit=None)
with st.sidebar:
    date_range_preset = st.selectbox(
        "Date Range",
        ["Last 30 days", "Last 60 days", "Last 90 days", "All", "Custom"],
        index=1,
        key="home_date_range",
    )
if date_range_preset == "Custom":
    from_idx = 0
    to_idx = len(all_available_dates) - 1 if all_available_dates else 0
    from_date = st.sidebar.selectbox("From", all_available_dates, index=from_idx)
    to_date = st.sidebar.selectbox("To", all_available_dates, index=to_idx)
    from_i = all_available_dates.index(from_date)
    to_i = all_available_dates.index(to_date)
    dates = all_available_dates[from_i : to_i + 1] if from_i <= to_i else all_available_dates[to_i : from_i + 1]
else:
    limit_map = {"Last 30 days": 30, "Last 60 days": 60, "Last 90 days": 90, "All": None}
    dates = loader.get_dates(limit=limit_map[date_range_preset])

@st.cache_data(ttl=300)
def _signal_data(date_list):
    from collections import defaultdict
    from core import db
    d = defaultdict(dict)
    for doc in db.main_coll().find({"date": {"$in": date_list}}):
        m = db.map_fields(doc)
        d[m["date"]][m["symbol"]] = m
    return dict(d)

sig_data = _signal_data(tuple(dates))

all_df = pd.DataFrame(all_stocks)
bullish_trends = scorer.BULLISH
bearish_trends = signals.BEARISH_TRENDS

# View date: pick which date to view (Alerts, Signals, Quick Picks, Key Metrics)
dates_sorted_newest_first = list(reversed(dates)) if dates else []
view_date = st.sidebar.selectbox(
    "View date",
    options=dates_sorted_newest_first,
    index=0,
    format_func=lambda x: f"{x} (latest)" if dates and x == dates[-1] else x,
    help="Change to see past alerts, signals, and quick picks for that date",
    key="view_date",
)
dates_up_to_view = [d for d in dates if d <= view_date] if view_date else []
view_stocks = list(sig_data.get(view_date, {}).values()) if view_date else []
view_df = pd.DataFrame(view_stocks) if view_stocks else all_df

with st.sidebar:
    date_range_label = f"{dates[0]} → {dates[-1]}" if dates else "—"
    st.caption(f"Stocks: {len(view_df)} | Dates: {len(dates)} | Range: {date_range_label}")

# ── Daily Summary ───────────────────────────────────────────
summary = signals.daily_summary(sig_data, dates_up_to_view) if dates_up_to_view else "No data for selected date."
st.info(summary)

# ── Key Metrics (unfiltered — all stocks for view date) ─────
n_bull = len(view_df[view_df["oi_trend"].isin(bullish_trends)]) if not view_df.empty else 0
n_bear = len(view_df[view_df["oi_trend"].isin(bearish_trends)]) if not view_df.empty else 0
avg_pcr = view_df["pcr"].mean() if not view_df.empty else 0
avg_change = view_df["change_pct"].mean() if not view_df.empty else 0
avg_vol = view_df["volume_times"].mean() if not view_df.empty else 0
avg_dlv = view_df["delivery_times"].mean() if not view_df.empty else 0

c1, c2, c3, c4, c5, c6 = st.columns(6)
n_total = len(view_df) if not view_df.empty else 1
c1.metric("Bullish", n_bull, f"{n_bull/n_total*100:.0f}%")
c2.metric("Bearish", n_bear, f"{n_bear/n_total*100:.0f}%")
c3.metric("Avg PCR", f"{avg_pcr:.2f}")
c4.metric("Avg Change", f"{avg_change:+.2f}%")
c5.metric("Avg Volume", f"{avg_vol:.2f}x")
c6.metric("Avg Delivery", f"{avg_dlv:.2f}x")

st.divider()

# ── Filters (MCap + Time Range) — above Sector Rotation ─────
ctrl1, ctrl2 = st.columns([1, 3])
mcap_filter = ctrl1.selectbox("Market Cap", ["All", "Large Cap", "Mid Cap", "Small Cap"])
time_range = ctrl2.radio("Time Range", ["Today", "3 Days", "5 Days", "10 Days", "21 Days"],
                         horizontal=True)

window_map = {"Today": 0, "3 Days": 3, "5 Days": 5, "10 Days": 10, "21 Days": 21}
window = window_map[time_range]

# Build filtered stock list for distributions (use view date; fallback to all_stocks if empty)
_stocks_for_filter = view_stocks if view_stocks else all_stocks
if mcap_filter == "All":
    filtered_stocks = _stocks_for_filter
else:
    filtered_stocks = [s for s in _stocks_for_filter if s.get("mcap_category") == mcap_filter]

# Quick Picks: use stocks from view date
quick_picks_date = view_date
quick_picks_stocks = view_stocks if view_stocks else all_stocks
if mcap_filter == "All":
    quick_picks_filtered = quick_picks_stocks
else:
    quick_picks_filtered = [s for s in quick_picks_stocks if s.get("mcap_category") == mcap_filter]

if not filtered_stocks:
    st.warning(f"No {mcap_filter} stocks found."); st.stop()

# Build distribution DataFrame — aggregate across selected time range (ending at view date)
if window == 0:
    dist_rows = filtered_stocks
else:
    range_dates = dates_up_to_view[-window:] if window <= len(dates_up_to_view) else dates_up_to_view
    dist_rows = []
    for dt in range_dates:
        for s in sig_data.get(dt, {}).values():
            if mcap_filter != "All" and s.get("mcap_category") != mcap_filter:
                continue
            dist_rows.append(s)

if not dist_rows:
    dist_rows = filtered_stocks

df = pd.DataFrame(dist_rows)

# ── Sector Rotation ──────────────────────────────────────────
st.subheader(f"Sector Rotation — {time_range} | {mcap_filter}")
st.caption("Click a sector row to see its stocks (same page)")

rot = signals.sector_rotation(sig_data, dates_up_to_view, window, mcap_filter)
if rot:
    sector_to_stocks = {r["Sector"]: r.get("stocks_list", []) for r in rot}
    rot_display = [{k: v for k, v in r.items() if k != "stocks_list"} for r in rot]
    rdf = pd.DataFrame(rot_display)

    # Sector rotation table — click a row to see its stocks (same page)
    styled = (rdf.style
              .format({
                  "Avg OI Chg%": "{:+.2f}", "OI Δ": "{:+.2f}",
                  "Bull%": "{:.1f}", "Bull Δ": "{:+.1f}", "Avg Chg%": "{:+.2f}",
                  "Chg Δ": "{:+.2f}", "Avg PCR": "{:.2f}", "PCR Δ": "{:+.2f}",
                  "Avg Vol(x)": "{:.2f}", "Avg Dlv(x)": "{:.2f}",
              })
              .map(
                  lambda v: "color: #22c55e" if isinstance(v, (int, float)) and v > 0
                  else "color: #ef4444" if isinstance(v, (int, float)) and v < 0 else "",
                  subset=["Bull Δ", "Chg Δ", "PCR Δ", "Avg OI Chg%", "OI Δ"]))
    event = st.dataframe(styled, width="stretch", hide_index=True, height=400,
                         on_select="rerun", selection_mode="single-row",
                         key=f"sector_rotation_df_{st.session_state.sector_df_key}")
    if hasattr(event, "selection") and event.selection and event.selection.rows:
        idx = event.selection.rows[0]
        st.session_state.selected_sector = rdf.iloc[idx]["Sector"]

    # Back button when sector selected
    if st.session_state.selected_sector:
        if st.button("← Back to Sector Rotation", key="sector_back"):
            st.session_state.selected_sector = None
            st.session_state.sector_df_key += 1
            st.rerun()
        st.subheader(f"Stocks in **{st.session_state.selected_sector}** — click symbol for analysis")
        stocks_in_sector = sector_to_stocks.get(st.session_state.selected_sector, [])
        if stocks_in_sector:
            stocks_in_sector.sort(key=lambda x: (x.get("score", 0), x.get("change_pct", 0)), reverse=True)
            rows = []
            for s in stocks_in_sector:
                sym = s.get("symbol", "")
                rows.append({
                    "Symbol": f"/Stock_Analysis?symbol={sym}",
                    "Score": s.get("score", 0),
                    "Chg%": f"{s.get('change_pct', 0):+.1f}",
                    "OI Trend": s.get("oi_trend", ""),
                    "PCR": f"{s.get('pcr', 0):.2f}",
                    "Vol(x)": f"{s.get('volume_times', 0):.2f}",
                    "Dlv(x)": f"{s.get('delivery_times', 0):.2f}",
                })
            sdf = pd.DataFrame(rows)
            st.dataframe(sdf, width="stretch", hide_index=True,
                         column_config={"Symbol": st.column_config.LinkColumn(
                             "Symbol", display_text=r".*symbol=([^&]+)")})
        else:
            st.caption("No stocks in this sector.")
    else:
        # Charts (only when no sector selected)
        ch1, ch2 = st.columns(2)
        with ch1:
            rdf_sorted = rdf.sort_values("Bull Δ", ascending=True)
            fig = px.bar(rdf_sorted, y="Sector", x="Bull Δ", orientation="h",
                         color="Bull Δ",
                         color_continuous_scale=["#ef4444", "#94a3b8", "#22c55e"],
                         text="Bull Δ",
                         title="OI Bullish % Change by Sector")
        fig.update_traces(texttemplate="%{text:+.0f}%", textposition="outside")
        fig.update_layout(margin=dict(t=40, b=10, l=10), height=350,
                          showlegend=False, yaxis_title="")
        st.plotly_chart(fig, width="stretch")

        with ch2:
            fig2 = px.scatter(rdf, x="Avg Chg%", y="PCR Δ",
                              size="Avg Vol(x)", color="Bull Δ",
                              hover_name="Sector", text="Sector",
                              color_continuous_scale=["#ef4444", "#94a3b8", "#22c55e"],
                              title="Sectors: Price Change vs PCR Change")
        fig2.update_traces(textposition="top center", textfont_size=9)
        fig2.update_layout(margin=dict(t=40, b=10, l=10), height=350)
        st.plotly_chart(fig2, width="stretch")
else:
    st.caption("No sector data for this filter.")

st.divider()

# ── Distributions (filtered by MCap) ────────────────────────
_dist_label = f"{time_range} | {mcap_filter}" if window > 0 else mcap_filter
st.subheader(f"Distributions — {_dist_label}")

d1, d2, d3 = st.columns(3)

with d1:
    trend_counts = df["oi_trend"].value_counts().reset_index()
    trend_counts.columns = ["OI Trend", "Count"]
    color_map = {
        "NewLong": "#22c55e", "ShortCover": "#06b6d4",
        "NewShort": "#ef4444", "LongCover": "#fb923c",
        "Neutral": "#94a3b8",
    }
    fig = px.pie(trend_counts, names="OI Trend", values="Count",
                 color="OI Trend", color_discrete_map=color_map, hole=0.4,
                 title="OI Trend")
    fig.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=280,
                      legend=dict(font=dict(size=9)))
    st.plotly_chart(fig, width="stretch")

with d2:
    fig = px.histogram(df, x="pcr", nbins=20, title="PCR Distribution",
                       color_discrete_sequence=["#f59e0b"])
    fig.add_vline(x=0.5, line_dash="dot", line_color="#22c55e",
                  annotation_text="Extreme Low")
    fig.add_vline(x=1.0, line_dash="dash", line_color="#ef4444",
                  annotation_text="PCR=1")
    fig.update_layout(margin=dict(t=40, b=10, l=10), height=280)
    st.plotly_chart(fig, width="stretch")

with d3:
    fig = px.histogram(df, x="change_pct", nbins=25, title="Price Change %",
                       color_discrete_sequence=["#6366f1"])
    fig.add_vline(x=0, line_dash="dash", line_color="white")
    fig.update_layout(margin=dict(t=40, b=10, l=10), height=280)
    st.plotly_chart(fig, width="stretch")

d4, d5 = st.columns(2)

with d4:
    fig = px.histogram(df, x="volume_times", nbins=20, title="Volume Multiplier",
                       color_discrete_sequence=["#06b6d4"])
    fig.add_vline(x=1.5, line_dash="dash", line_color="#22c55e",
                  annotation_text="1.5x")
    fig.update_layout(margin=dict(t=40, b=10, l=10), height=260)
    st.plotly_chart(fig, width="stretch")

with d5:
    fig = px.histogram(df, x="delivery_times", nbins=20, title="Delivery Multiplier",
                       color_discrete_sequence=["#8b5cf6"])
    fig.add_vline(x=2.0, line_dash="dash", line_color="#22c55e",
                  annotation_text="2.0x spike")
    fig.update_layout(margin=dict(t=40, b=10, l=10), height=260)
    st.plotly_chart(fig, width="stretch")

st.divider()

# ── Alerts & Signals (unfiltered — all stocks) ──────────────
st.subheader(f"Alerts & Signals — {view_date}")
a1, a2, a3, a4 = st.columns(4)

flips = signals.detect_trend_flips(sig_data, dates_up_to_view)
with a1:
    st.markdown("**OI Trend Flips**")
    if flips:
        for f in flips[:5]:
            st.markdown(
                f"[**{f['symbol']}**](/Stock_Analysis?symbol={f['symbol']}) "
                f"`{f['prev_trend']}` → `{f['new_trend']}`  \n"
                f"Conv: {f['conviction']} | {f['change_pct']:+.1f}%")
    else:
        st.caption("No bullish flips")

ext = signals.pcr_extremes(sig_data, view_date)
with a2:
    st.markdown("**PCR Extremes**")
    # Low PCR — put writers confident (potential calls)
    if ext["low_pcr"]:
        st.markdown(f"*Low PCR ≤ 0.5 ({len(ext['low_pcr'])}):*")
        for e in ext["low_pcr"][:3]:
            st.markdown(
                f"[**{e['symbol']}**](/Stock_Analysis?symbol={e['symbol']}) "
                f"PCR {e['pcr']:.2f} | `{e['oi_trend']}` | {e['change_pct']:+.1f}%")
    else:
        st.caption("No low PCR extremes")
    # High PCR — put buyers heavy (potential puts)
    if ext["high_pcr"]:
        st.markdown(f"*High PCR ≥ 1.5 ({len(ext['high_pcr'])}):*")
        for e in ext["high_pcr"][:3]:
            st.markdown(
                f"[**{e['symbol']}**](/Stock_Analysis?symbol={e['symbol']}) "
                f"PCR {e['pcr']:.2f} | `{e['oi_trend']}` | {e['change_pct']:+.1f}%")
    else:
        st.caption("No high PCR extremes")

spikes = signals.delivery_spikes(sig_data, view_date)
with a3:
    st.markdown("**Delivery Spikes (≥2x)**")
    if spikes:
        for s in spikes[:5]:
            st.markdown(
                f"[**{s['symbol']}**](/Stock_Analysis?symbol={s['symbol']}) "
                f"{s['delivery_times']:.1f}x dlv  \n"
                f"Score: {s['score']} | {s['change_pct']:+.1f}%")
    else:
        st.caption("No delivery spikes")

streaks = signals.score_streaks(sig_data, dates_up_to_view, 3)
with a4:
    st.markdown("**3+ Day Streaks**")
    if streaks:
        for s in streaks[:5]:
            st.markdown(
                f"[**{s['symbol']}**](/Stock_Analysis?symbol={s['symbol']}) "
                f"{s['streak_days']}d streak  \n"
                f"Conv: {s['conviction']} | Score: {s['score']}")
    else:
        st.caption("No multi-day streaks")

st.divider()

# ── Quick Picks (filtered by MCap, based on selected date) ────
st.subheader(f"Quick Picks — {quick_picks_date}")
st.caption("Click any stock symbol to view full analysis")
q1, q2 = st.columns(2)

STOCK_URL = "/Stock_Analysis?symbol={}"

with q1:
    st.markdown("**Top 5 Options Picks** (outrunner conviction)")
    opt_picks = []
    for s in quick_picks_filtered:
        sc = scorer.base_score(s)
        if 20 <= sc <= 34:
            conv = scorer.outrunner_conviction(s)
            opt_picks.append({
                "Symbol": STOCK_URL.format(s["symbol"]),
                "Conv": conv["conviction"],
                "Score": sc,
                "Close": f"₹{s.get('close',0):,.0f}",
                "Chg%": f"{s.get('change_pct',0):+.1f}",
                "OI Trend": s.get("oi_trend", ""),
                "MCap": s.get("mcap_category", ""),
            })
    opt_picks.sort(key=lambda x: x["Conv"], reverse=True)
    if opt_picks:
        odf = pd.DataFrame(opt_picks[:5])
        st.dataframe(odf, width="stretch", hide_index=True,
                     column_config={"Symbol": st.column_config.LinkColumn(
                         "Symbol", display_text=r".*symbol=(.+)$")})
    else:
        st.caption("No picks")

with q2:
    st.markdown("**Top 5 Swing Picks** (score ranked)")
    sw_picks = []
    for s in quick_picks_filtered:
        sc = scorer.base_score(s)
        if 20 <= sc <= 34:
            sw_picks.append({
                "Symbol": STOCK_URL.format(s["symbol"]),
                "Score": sc,
                "Close": f"₹{s.get('close',0):,.0f}",
                "Chg%": f"{s.get('change_pct',0):+.1f}",
                "OI Trend": s.get("oi_trend", ""),
                "PCR": f"{s.get('pcr',0):.2f}",
                "MCap": s.get("mcap_category", ""),
            })
    sw_picks.sort(key=lambda x: x["Score"], reverse=True)
    if sw_picks:
        sdf = pd.DataFrame(sw_picks[:5])
        st.dataframe(sdf, width="stretch", hide_index=True,
                     column_config={"Symbol": st.column_config.LinkColumn(
                         "Symbol", display_text=r".*symbol=(.+)$")})
    else:
        st.caption("No picks")
