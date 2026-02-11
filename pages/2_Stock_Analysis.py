"""Stock Analysis — Single stock deep dive with unified view."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from core import loader, scorer, signals

st.set_page_config(page_title="Stock Analysis", page_icon="🔍", layout="wide")

with st.sidebar:
    st.header("Navigation")
    st.page_link("app.py", label="Home", icon="🏠")
    st.page_link("pages/2_Stock_Analysis.py", label="Stock Analysis", icon="🔍")
    st.page_link("pages/3_Stock_Action_Sheet.py", label="Stock Sheet", icon="📋")
    st.page_link("pages/4_Import_Data.py", label="Import Data", icon="📥")
    st.divider()

dates = loader.get_dates(limit=60)
if not dates:
    st.error("No data."); st.stop()

params = st.query_params
symbols = sorted(loader.get_symbols())
default_idx = 0
if "symbol" in params:
    try:
        default_idx = symbols.index(params["symbol"])
    except ValueError:
        pass

sel_sym = st.selectbox("Select Stock", symbols, index=default_idx)

@st.cache_data(ttl=300)
def _load_stock_history(sym, date_list):
    rows = []
    for i, d in enumerate(date_list):
        s = loader.get_stock(sym, d)
        if s:
            s["score"] = scorer.base_score(s)
            cv = scorer.outrunner_conviction(s)
            s["conviction"] = cv["conviction"]
            if i > 0:
                prev = loader.get_stock(sym, date_list[i - 1])
                s = signals.enrich_oi_change_pct(s, prev)
            else:
                s["call_oi_change_pct"] = None
                s["put_oi_change_pct"] = None
            rows.append(s)
    return rows

hist = _load_stock_history(sel_sym, tuple(dates))
if not hist:
    st.warning(f"No data for {sel_sym}."); st.stop()

hdf = pd.DataFrame(hist)
latest = hdf.iloc[-1]
view_date = latest.get("date", dates[-1] if dates else "")
mcap = latest.get("mcap_category", "")
conv = scorer.outrunner_conviction(latest.to_dict())

# ── Header + metrics ─────────────────────────────────────────
st.subheader(f"{sel_sym} — {latest.get('stock_name', '')} | {mcap} | {view_date}")
m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
m1.metric("Close", f"₹{latest.get('close',0):,.2f}")
m2.metric("Change", f"{latest.get('change_pct',0):+.2f}%")
m3.metric("Score", int(latest.get("score", 0)))
m4.metric("Conviction", f"{conv['conviction']}/{conv['max_conviction']}")
m5.metric("PCR", f"{latest.get('pcr',0):.2f}", delta=f"{latest.get('pcr_change_1d',0):+.2f}")
m6.metric("Volume", f"{latest.get('volume_times',0):.2f}x")
m7.metric("Delivery", f"{latest.get('delivery_times',0):.2f}x")
st.caption(f"OI Trend: `{latest.get('oi_trend','')}` | Sector: {latest.get('sector','')}")

# ── Unified chart: Price + Score + Conviction + PCR + OI Chg + Vol + Dlv ───
# ── Data series selector (user-defined, multiple) ───
SERIES_OPTIONS = [
    "Close",
    "Score",
    "Conviction",
    "PCR",
    "OI Chg %",
    "Vol(x)",
    "Dlv(x)",
    "Call OI vs Put OI",
]
selected_series = st.multiselect(
    "Select data series",
    options=SERIES_OPTIONS,
    default=SERIES_OPTIONS,
    key="stock_analysis_series",
)

if not selected_series:
    st.caption("Select at least one data series above.")
else:
    n = len(selected_series)
    row_heights = [1.5 if s == "Close" else 0.8 for s in selected_series]
    fig = make_subplots(
        rows=n, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        subplot_titles=selected_series,
        row_heights=row_heights,
    )

    x = pd.to_datetime(hdf["date"])
    for idx, ser in enumerate(selected_series, 1):
        if ser == "Close":
            fig.add_trace(go.Scatter(x=x, y=hdf["close"], name="Close", line=dict(color="#6366f1", width=2), showlegend=False), row=idx, col=1)
        elif ser == "Score":
            fig.add_trace(go.Bar(x=x, y=hdf["score"], marker_color=["#22c55e" if v >= 20 else "#94a3b8" for v in hdf["score"]], showlegend=False), row=idx, col=1)
            fig.add_hline(y=20, row=idx, col=1, line_dash="dash", line_color="#22c55e")
        elif ser == "Conviction":
            fig.add_trace(go.Bar(x=x, y=hdf["conviction"], marker_color="#6366f1", showlegend=False), row=idx, col=1)
        elif ser == "PCR":
            fig.add_trace(go.Scatter(x=x, y=hdf["pcr"], name="PCR", line=dict(color="#f59e0b", width=2), showlegend=False), row=idx, col=1)
            fig.add_hline(y=1.0, row=idx, col=1, line_dash="dash", line_color="#94a3b8")
        elif ser == "OI Chg %":
            oi_chg = hdf["oi_change_pct"].fillna(0)
            fig.add_trace(go.Bar(x=x, y=oi_chg, marker_color=["#22c55e" if v > 0 else "#ef4444" for v in oi_chg], showlegend=False), row=idx, col=1)
        elif ser == "Vol(x)":
            fig.add_trace(go.Bar(x=x, y=hdf["volume_times"], marker_color="#3b82f6", showlegend=False), row=idx, col=1)
            fig.add_hline(y=1.5, row=idx, col=1, line_dash="dash", line_color="#22c55e")
        elif ser == "Dlv(x)":
            fig.add_trace(go.Bar(x=x, y=hdf["delivery_times"], marker_color="#06b6d4", showlegend=False), row=idx, col=1)
            fig.add_hline(y=2.0, row=idx, col=1, line_dash="dash", line_color="#22c55e")
        elif ser == "Call OI vs Put OI":
            if "cumulative_call_oi" in hdf.columns:
                fig.add_trace(go.Scatter(x=x, y=hdf["cumulative_call_oi"], name="Call OI", line=dict(color="#ef4444", width=2), showlegend=True), row=idx, col=1)
            if "cumulative_put_oi" in hdf.columns:
                fig.add_trace(go.Scatter(x=x, y=hdf["cumulative_put_oi"], name="Put OI", line=dict(color="#22c55e", width=2), showlegend=True), row=idx, col=1)

    fig.update_layout(
        height=max(400, 80 * n),
        margin=dict(t=40, b=10, l=50, r=20),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="#1e1e2e",
        paper_bgcolor="#0e1117",
        font=dict(color="#fafafa", size=10),
    )
    fig.update_annotations(font=dict(color="#fafafa"))
    for idx in range(1, n + 1):
        fig.update_xaxes(showgrid=False, tickfont=dict(size=9, color="#94a3b8"), row=idx, col=1)
        fig.update_yaxes(showgrid=True, gridcolor="#2d2d3d", tickfont=dict(size=9, color="#94a3b8"), row=idx, col=1)

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

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
    if "call_oi_change_pct" in hdf.columns:
        show_cols.append("call_oi_change_pct")
    if "put_oi_change_pct" in hdf.columns:
        show_cols.append("put_oi_change_pct")
    st.dataframe(hdf[[c for c in show_cols if c in hdf.columns]].sort_values("date", ascending=False),
                 width="stretch", height=400)
