"""Stock Analysis — Single stock deep dive."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from core import loader, scorer, signals

st.set_page_config(page_title="Stock Analysis", page_icon="🔍", layout="wide")

# ── Sidebar: Navigation first (consistent across pages) ─────────
with st.sidebar:
    st.header("Navigation")
    st.page_link("app.py", label="Home", icon="🏠")
    st.page_link("pages/1_Stock_Analysis.py", label="Stock Analysis", icon="🔍")
    st.page_link("pages/2_Backtest.py", label="Backtest", icon="🔬")
    st.page_link("pages/3_Import_Data.py", label="Import Data", icon="📥")
    st.page_link("pages/4_Manual.py", label="Manual", icon="📖")
    st.divider()

# ── Date range filter ────────────────────────────────────────
all_available_dates = loader.get_dates(limit=None)
if not all_available_dates:
    st.error("No data."); st.stop()

with st.sidebar:
    date_range_preset = st.selectbox(
        "Date Range",
        ["Last 30 days", "Last 60 days", "Last 90 days", "All", "Custom"],
        index=1,
        key="sa_date_range",
    )
if date_range_preset == "Custom":
    from_idx = 0
    to_idx = len(all_available_dates) - 1
    col1, col2 = st.sidebar.columns(2)
    from_date = col1.selectbox("From", all_available_dates, index=from_idx, key="sa_from")
    to_date = col2.selectbox("To", all_available_dates, index=to_idx, key="sa_to")
    from_i = all_available_dates.index(from_date)
    to_i = all_available_dates.index(to_date)
    dates = all_available_dates[from_i : to_i + 1] if from_i <= to_i else all_available_dates[to_i : from_i + 1]
else:
    limit_map = {"Last 30 days": 30, "Last 60 days": 60, "Last 90 days": 90, "All": None}
    dates = loader.get_dates(limit=limit_map[date_range_preset])

if not dates:
    st.error("No data for selected range."); st.stop()

with st.sidebar:
    st.caption(f"Showing {len(dates)} days: {dates[0]} → {dates[-1]}")

st.title("🔍 Stock Analysis")

# Get symbol from URL params or selectbox
params = st.query_params
symbols = sorted(loader.get_symbols())

default_idx = 0
if "symbol" in params:
    try:
        default_idx = symbols.index(params["symbol"])
    except ValueError:
        pass

sel_sym = st.selectbox("Select Stock", symbols, index=default_idx)

# Load all historical data for this stock
@st.cache_data(ttl=300)
def _load_stock_history(sym, date_list):
    rows = []
    for d in date_list:
        s = loader.get_stock(sym, d)
        if s:
            s["score"] = scorer.base_score(s)
            cv = scorer.outrunner_conviction(s)
            s["conviction"] = cv["conviction"]
            rows.append(s)
    return rows

hist = _load_stock_history(sel_sym, tuple(dates))

if not hist:
    st.warning(f"No data for {sel_sym}."); st.stop()

hdf = pd.DataFrame(hist)
latest = hdf.iloc[-1]

# ── Header ──────────────────────────────────────────────────
st.subheader(f"{sel_sym} — {latest.get('stock_name', '')}")

conv = scorer.outrunner_conviction(latest.to_dict())

m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
m1.metric("Close", f"₹{latest.get('close',0):,.2f}")
m2.metric("Change", f"{latest.get('change_pct',0):+.2f}%")
m3.metric("Score", int(latest.get("score", 0)))
m4.metric("Conviction", f"{conv['conviction']}/{conv['max_conviction']}")
m5.metric("PCR", f"{latest.get('pcr',0):.2f}",
          delta=f"{latest.get('pcr_change_1d',0):+.2f}")
m6.metric("Volume", f"{latest.get('volume_times',0):.2f}x")
m7.metric("Delivery", f"{latest.get('delivery_times',0):.2f}x")

st.caption(f"OI Trend: `{latest.get('oi_trend','')}` | "
           f"Sector: {latest.get('sector','')} | "
           f"MCap: {latest.get('mcap_category','')}")

st.divider()

# ── Row 1: Price + Score ────────────────────────────────────
r1, r2 = st.columns(2)

with r1:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hdf["date"], y=hdf["close"], name="Close",
                              line=dict(color="#6366f1", width=2)))
    fig.update_layout(title=f"{sel_sym} — Close Price", height=280,
                      margin=dict(t=35, b=10, l=40, r=10))
    st.plotly_chart(fig, width="stretch")

with r2:
    colors = ["#22c55e" if v >= 20 else "#94a3b8" for v in hdf["score"]]
    fig = go.Figure(go.Bar(x=hdf["date"], y=hdf["score"],
                            marker_color=colors, name="Score"))
    fig.add_hline(y=20, line_dash="dash", line_color="green",
                  annotation_text="Sweet Spot ≥20")
    fig.update_layout(title=f"{sel_sym} — Score Over Time", height=280,
                      margin=dict(t=35, b=10, l=40, r=10))
    st.plotly_chart(fig, width="stretch")

# ── Row 2: Conviction + OI Change ───────────────────────────
r3, r4 = st.columns(2)

with r3:
    cv_colors = ["#22c55e" if v >= 12 else "#eab308" if v >= 8 else "#94a3b8"
                 for v in hdf["conviction"]]
    fig = go.Figure(go.Bar(x=hdf["date"], y=hdf["conviction"],
                            marker_color=cv_colors))
    fig.update_layout(title=f"{sel_sym} — Conviction Over Time", height=280,
                      margin=dict(t=35, b=10, l=40, r=10),
                      yaxis_range=[0, 19])
    st.plotly_chart(fig, width="stretch")

with r4:
    oi_colors = ["#22c55e" if v > 0 else "#ef4444" for v in hdf["oi_change_pct"]]
    fig = go.Figure(go.Bar(x=hdf["date"], y=hdf["oi_change_pct"],
                            marker_color=oi_colors))
    fig.update_layout(title=f"{sel_sym} — OI Change %", height=280,
                      margin=dict(t=35, b=10, l=40, r=10))
    st.plotly_chart(fig, width="stretch")

# ── Row 3: PCR + Volume ─────────────────────────────────────
r5, r6 = st.columns(2)

with r5:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hdf["date"], y=hdf["pcr"], name="PCR",
                              line=dict(color="#f59e0b", width=2)))
    fig.add_hline(y=1.0, line_dash="dash", line_color="red",
                  annotation_text="PCR=1.0")
    fig.add_hline(y=0.5, line_dash="dot", line_color="green",
                  annotation_text="Extreme Low")
    fig.update_layout(title=f"{sel_sym} — PCR Trend", height=260,
                      margin=dict(t=35, b=10, l=40, r=10))
    st.plotly_chart(fig, width="stretch")

with r6:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=hdf["date"], y=hdf["volume_times"], name="Volume(x)",
                          marker_color="#6366f1"))
    fig.add_hline(y=1.5, line_dash="dash", line_color="#22c55e",
                  annotation_text="1.5x threshold")
    fig.update_layout(title=f"{sel_sym} — Volume Multiplier", height=260,
                      margin=dict(t=35, b=10, l=40, r=10))
    st.plotly_chart(fig, width="stretch")

# ── Row 4: Call OI vs Put OI + Delivery ───────────────────────
r7, r8 = st.columns(2)

with r7:
    # Call OI (red) and Put OI (green) in same chart
    if "cumulative_call_oi" in hdf.columns or "cumulative_put_oi" in hdf.columns:
        fig = go.Figure()
        if "cumulative_call_oi" in hdf.columns:
            fig.add_trace(go.Scatter(
                x=hdf["date"], y=hdf["cumulative_call_oi"], name="Call OI",
                line=dict(color="#ef4444", width=2)))
        if "cumulative_put_oi" in hdf.columns:
            fig.add_trace(go.Scatter(
                x=hdf["date"], y=hdf["cumulative_put_oi"], name="Put OI",
                line=dict(color="#22c55e", width=2)))
        fig.update_layout(title=f"{sel_sym} — Call OI vs Put OI", height=260,
                          margin=dict(t=35, b=10, l=40, r=10),
                          legend=dict(orientation="h", y=1.02))
        st.plotly_chart(fig, width="stretch")
    else:
        st.caption("Call/Put OI data not available.")

with r8:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=hdf["date"], y=hdf["delivery_times"], name="Delivery(x)",
                          marker_color="#06b6d4"))
    fig.add_hline(y=2.0, line_dash="dash", line_color="#22c55e",
                  annotation_text="2.0x spike level")
    fig.update_layout(title=f"{sel_sym} — Delivery Multiplier", height=260,
                      margin=dict(t=35, b=10, l=40, r=10))
    st.plotly_chart(fig, width="stretch")

# ── Row 5: OI Trend Timeline ──────────────────────────────────
with st.container():
    trend_color_map = {
        "NewLong": "#22c55e", "ShortCover": "#06b6d4",
        "NewShort": "#ef4444", "LongCover": "#fb923c",
        "Neutral": "#94a3b8",
    }
    fig = go.Figure()
    for trend, color in trend_color_map.items():
        mask = hdf["oi_trend"] == trend
        if mask.any():
            fig.add_trace(go.Scatter(
                x=hdf.loc[mask, "date"],
                y=hdf.loc[mask, "oi_trend"],
                mode="markers",
                marker=dict(color=color, size=14, symbol="square"),
                name=trend))
    fig.update_layout(title=f"{sel_sym} — OI Trend Timeline", height=260,
                      margin=dict(t=35, b=10, l=40, r=10),
                      yaxis_title="", showlegend=True,
                      legend=dict(font=dict(size=9), orientation="h", y=-0.3))
    st.plotly_chart(fig, width="stretch")

# ── Conviction Breakdown (latest) ───────────────────────────
st.subheader("Current Conviction Breakdown")
reasons = conv["reasons"]
for factor, (pts, reason) in reasons.items():
    bar = "🟢" * pts + "⚪" * (4 - pts) if pts > 0 else "⚪⚪⚪⚪"
    st.markdown(f"**{factor}** {bar} ({pts}/4) — {reason}")

# ── Full Data Table ─────────────────────────────────────────
with st.expander("📋 Full Historical Data"):
    show_cols = ["date", "close", "change_pct", "score", "conviction",
                 "oi_trend", "pcr", "pcr_change_1d", "oi_change_pct",
                 "volume_times", "delivery_times"]
    if "cumulative_call_oi" in hdf.columns:
        show_cols.append("cumulative_call_oi")
    if "cumulative_put_oi" in hdf.columns:
        show_cols.append("cumulative_put_oi")
    st.dataframe(hdf[[c for c in show_cols if c in hdf.columns]].sort_values("date", ascending=False),
                 width="stretch", height=400)
