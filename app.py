"""
Trading Dashboard — Home / Market Pulse + Sector Rotation
Run:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from core import loader, scorer, signals, recommender, chart_utils

_USE_TV = False
try:
    from streamlit_lightweight_charts import renderLightweightCharts
    _USE_TV = True
except ImportError:
    pass

# Session state
if "selected_sector" not in st.session_state:
    st.session_state.selected_sector = None
if "sector_df_key" not in st.session_state:
    st.session_state.sector_df_key = 0
if "watchlist" not in st.session_state:
    st.session_state.watchlist = set()

st.set_page_config(page_title="Trading Dashboard", page_icon="📈", layout="wide")

# ── Sidebar: Navigation ───────────────────────────────────────
with st.sidebar:
    st.header("Navigation")
    st.page_link("app.py", label="Home", icon="🏠")
    st.page_link("pages/2_Stock_Analysis.py", label="Stock Analysis", icon="🔍")
    st.page_link("pages/3_Stock_Action_Sheet.py", label="Stock Sheet", icon="📋")
    st.page_link("pages/4_Import_Data.py", label="Import Data", icon="📥")
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

# ── Quick filters (MCap for Top 7 / Action Sheet) ─────────────
fc1, fc2 = st.columns(2)
with fc1:
    mcap_filter = st.selectbox("Market Cap", ["All", "Large Cap", "Mid Cap", "Small Cap"], key="mcap_home")
with fc2:
    window = st.selectbox("Window", [3, 5, 10, 21], format_func=lambda x: f"{x}d", index=1, key="sector_window")

# ── Sector Rotation ──────────────────────────────────────────
st.subheader(f"Sector Rotation — {mcap_filter}")
st.caption("Click a sector row to see its stocks (same page)")
rot = signals.sector_rotation(sig_data, dates_up_to_view, window, mcap_filter)

if rot:
    sector_to_stocks = {r["Sector"]: r.get("stocks_list", []) for r in rot}
    rot_display = [{k: v for k, v in r.items() if k != "stocks_list"} for r in rot]
    rdf = pd.DataFrame(rot_display)

    # Sector rotation table — click a row to see its stocks (same page)
    fmt_map = {"Agg Chg %": "{:+.2f}", "Chg Δ": "{:+.2f}",
               "Vol(x)": "{:.2f}", "Dlv(x)": "{:.2f}", "PCR": "{:.2f}", "PCR Δ": "{:+.2f}",
               "Agg Call OI": "{:,.0f}", "Agg Put OI": "{:,.0f}",
               "Agg Call OI Chg%": "{:+.2f}", "Agg Put OI Chg%": "{:+.2f}"}
    chg_cols = [c for c in rdf.columns if "Chg" in c or "Δ" in c]
    styled = (rdf.style
              .format({k: v for k, v in fmt_map.items() if k in rdf.columns}, na_rep="—")
              .map(
                  lambda v: "color: #22c55e" if v is not None and isinstance(v, (int, float)) and v > 0
                  else "color: #ef4444" if v is not None and isinstance(v, (int, float)) and v < 0 else "",
                  subset=chg_cols))
    # Highlight OI trend (Direction) — Improving=green, Declining=red
    if "Direction" in rdf.columns:
        def _dir_color(v):
            if v == "Improving": return "background-color: rgba(34,197,94,0.25); font-weight: 600"
            if v == "Declining": return "background-color: rgba(239,68,68,0.25); font-weight: 600"
            return ""
        styled = styled.map(lambda v: _dir_color(v) if isinstance(v, str) else "", subset=["Direction"])
    # Highlight Vol(x) and Dlv(x) when above 1.5
    for col in ["Vol(x)", "Dlv(x)"]:
        if col in rdf.columns:
            styled = styled.map(
                lambda v: "background-color: rgba(34,197,94,0.3); font-weight: 600" if v is not None and isinstance(v, (int, float)) and v >= 1.5 else "",
                subset=[col])
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
                s_full = dict(s, symbol=sym)
                conv = scorer.outrunner_conviction(s_full)["conviction"] if sym else 0
                rows.append({
                    "Symbol": f"/Stock_Analysis?symbol={sym}",
                    "Conv": conv,
                    "Score": s.get("score", 0),
                    "Chg%": s.get("change_pct"),
                    "Vol(x)": s.get("volume_times", 0),
                    "Dlv(x)": s.get("delivery_times", 0),
                    "Fut OI": s.get("cumulative_future_oi"),
                    "Fut OI Chg%": s.get("oi_change_pct"),
                    "Call OI": s.get("cumulative_call_oi"),
                    "Call OI Chg%": s.get("call_oi_change_pct"),
                    "Put OI": s.get("cumulative_put_oi"),
                    "Put OI Chg%": s.get("put_oi_change_pct"),
                    "PCR": s.get("pcr", 0),
                    "PCR Chg": s.get("pcr_change_1d"),
                    "OI Trend": s.get("oi_trend", ""),
                    "MCap": s.get("mcap_category", ""),
                })
            sdf = pd.DataFrame(rows)
            schg_cols = [c for c in sdf.columns if "Chg" in c]
            sfmt = {c: "{:+.1f}" for c in ["Chg%", "Fut OI Chg%", "Call OI Chg%", "Put OI Chg%"] if c in sdf.columns}
            sfmt.update({c: "{:+.2f}" for c in ["PCR Chg"] if c in sdf.columns})
            sfmt.update({c: "{:.2f}" for c in ["Vol(x)", "Dlv(x)", "PCR"] if c in sdf.columns})
            sfmt.update({c: "{:,.0f}" for c in ["Fut OI", "Call OI", "Put OI"] if c in sdf.columns})
            _scolor = lambda s: ["color: #22c55e" if v is not None and isinstance(v, (int, float)) and v > 0
                                 else "color: #ef4444" if v is not None and isinstance(v, (int, float)) and v < 0 else "" for v in s]
            styled_s = sdf.style.format(sfmt, na_rep="—")
            if schg_cols:
                styled_s = styled_s.apply(_scolor, subset=schg_cols)
            # Highlight OI Trend, Vol(x), Dlv(x) when above 1.5
            if "OI Trend" in sdf.columns:
                _oi_color = lambda v: "background-color: rgba(34,197,94,0.2)" if v in ("NewLong", "ShortCover") else "background-color: rgba(239,68,68,0.2)" if v in ("NewShort", "LongCover") else ""
                styled_s = styled_s.map(lambda v: _oi_color(v) if isinstance(v, str) else "", subset=["OI Trend"])
            for col in ["Vol(x)", "Dlv(x)"]:
                if col in sdf.columns:
                    styled_s = styled_s.map(lambda v: "background-color: rgba(34,197,94,0.3); font-weight: 600" if v is not None and isinstance(v, (int, float)) and v >= 1.5 else "", subset=[col])
            st.dataframe(styled_s, width="stretch", hide_index=True,
                         column_config={"Symbol": st.column_config.LinkColumn(
                             "Symbol", display_text=r".*symbol=([^&]+)")})
        else:
            st.caption("No stocks in this sector.")
else:
    st.caption("No sector data for this filter.")

st.divider()

# ── Top 7 Picks (Outrunner) ───────────────────────────────────
st.subheader(f"Top 7 Picks — {view_date} (Outrunner Strategy)")
top7 = recommender.get_top_picks(sig_data, dates_up_to_view, view_date, mcap_filter, top_n=7)
if top7:
    for i, p in enumerate(top7, 1):
        sym = p["symbol"]
        sigs = " ".join(f"[{s}]" for s in p.get("signals", [])) or "—"
        chg = p.get("change_pct")
        chg_str = f"{chg:+.1f}%" if chg is not None else "—"
        tv_url = f"https://www.tradingview.com/chart/?symbol=NSE%3A{sym.upper()}"
        st.markdown(
            f"**#{i}** [{sym}](/Stock_Analysis?symbol={sym}) — Conv: {p['conviction']} | Score: {p['score']} | Chg: {chg_str} | {sigs} | [TradingView]({tv_url})"
        )
else:
    st.caption("No picks in sweet spot (score 20–34) for this filter.")

# ── Historical Top 7 Performance ──────────────────────────────
hist_perf = recommender.get_historical_top7_performance(sig_data, dates_up_to_view, lookback_days=5)
if hist_perf:
    with st.expander(f"Last 5 days: {hist_perf['green_count']}/{hist_perf['total_picks']} green, avg {hist_perf['avg_chg_pct']:+.1f}%"):
        for d in hist_perf.get("details", [])[:10]:
            st.caption(f"{d['date']} {d['symbol']}: {d['pnl_pct']:+.1f}%")

st.divider()

# ── Alerts (below all) ─────────────────────────────────────────
st.subheader("🔔 Alerts & Signals")
alert_type = st.selectbox(
    "Alert Type",
    ["All", "OI Trend Flips", "PCR Extremes", "Delivery Spikes", "3+ Day Streaks"],
    key="home_alert_type",
)

def _filter_mcap(items, mcap):
    if mcap == "All":
        return items
    return [x for x in items if x.get("mcap_category") == mcap]

flips = _filter_mcap(signals.detect_trend_flips(sig_data, dates_up_to_view), mcap_filter)
ext = signals.pcr_extremes(sig_data, view_date)
low_pcr = _filter_mcap(ext["low_pcr"], mcap_filter)
high_pcr = _filter_mcap(ext["high_pcr"], mcap_filter)
spikes = _filter_mcap(signals.delivery_spikes(sig_data, view_date, 2.0), mcap_filter)
streaks = _filter_mcap(signals.score_streaks(sig_data, dates_up_to_view, 3), mcap_filter)

n_flips, n_pcr = len(flips), len(low_pcr) + len(high_pcr)
n_spikes, n_streaks = len(spikes), len(streaks)
st.caption(f"**{view_date}** | {mcap_filter} | {n_flips} flips · {n_pcr} PCR extremes · {n_spikes} delivery spikes · {n_streaks} streaks")

if alert_type in ("All", "OI Trend Flips"):
    st.markdown("**OI Trend Flips (Bearish → Bullish)**")
    if flips:
        flips_df = pd.DataFrame(flips)
        flips_df["symbol"] = flips_df["symbol"].apply(lambda s: f"/Stock_Analysis?symbol={s}")
        display_cols = ["symbol", "prev_trend", "new_trend", "conviction", "change_pct", "pcr", "sector"]
        st.dataframe(flips_df[[c for c in display_cols if c in flips_df.columns]], hide_index=True,
                    column_config={"symbol": st.column_config.LinkColumn("Symbol", display_text=r".*symbol=([^&]+)")})
    else:
        st.caption("No bullish flips for this filter.")

if alert_type in ("All", "PCR Extremes"):
    st.markdown("**PCR Extremes**")
    c1, c2 = st.columns(2)
    with c1:
        st.caption("Low PCR ≤ 0.5")
        if low_pcr:
            ldf = pd.DataFrame(low_pcr)[["symbol", "pcr", "change_pct", "oi_trend", "sector"]]
            ldf["symbol"] = ldf["symbol"].apply(lambda s: f"/Stock_Analysis?symbol={s}")
            st.dataframe(ldf, hide_index=True, column_config={"symbol": st.column_config.LinkColumn("Symbol", display_text=r".*symbol=([^&]+)")})
        else:
            st.caption("None")
    with c2:
        st.caption("High PCR ≥ 1.5")
        if high_pcr:
            hdf = pd.DataFrame(high_pcr)[["symbol", "pcr", "change_pct", "oi_trend", "sector"]]
            hdf["symbol"] = hdf["symbol"].apply(lambda s: f"/Stock_Analysis?symbol={s}")
            st.dataframe(hdf, hide_index=True, column_config={"symbol": st.column_config.LinkColumn("Symbol", display_text=r".*symbol=([^&]+)")})
        else:
            st.caption("None")

if alert_type in ("All", "Delivery Spikes"):
    st.markdown("**Delivery Spikes (≥ 2x)**")
    if spikes:
        spdf = pd.DataFrame(spikes)[["symbol", "delivery_times", "volume_times", "score", "change_pct", "oi_trend", "sector"]]
        spdf["symbol"] = spdf["symbol"].apply(lambda s: f"/Stock_Analysis?symbol={s}")
        st.dataframe(spdf, hide_index=True, column_config={"symbol": st.column_config.LinkColumn("Symbol", display_text=r".*symbol=([^&]+)")})
    else:
        st.caption("No delivery spikes.")

if alert_type in ("All", "3+ Day Streaks"):
    st.markdown("**3+ Day Streaks (Score 20–34)**")
    if streaks:
        stdf = pd.DataFrame(streaks)[["symbol", "streak_days", "conviction", "score", "change_pct", "oi_trend", "sector"]]
        stdf["symbol"] = stdf["symbol"].apply(lambda s: f"/Stock_Analysis?symbol={s}")
        st.dataframe(stdf, hide_index=True, column_config={"symbol": st.column_config.LinkColumn("Symbol", display_text=r".*symbol=([^&]+)")})
    else:
        st.caption("No multi-day streaks.")


