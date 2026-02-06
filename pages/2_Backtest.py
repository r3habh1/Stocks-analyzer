"""Backtest — run strategies and compare performance."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from core import loader, scorer

st.set_page_config(page_title="Backtest", page_icon="🔬", layout="wide")

with st.sidebar:
    st.header("Navigation")
    st.page_link("app.py", label="Home", icon="🏠")
    st.page_link("pages/1_Stock_Analysis.py", label="Stock Analysis", icon="🔍")
    st.page_link("pages/2_Backtest.py", label="Backtest", icon="🔬")
    st.page_link("pages/3_Import_Data.py", label="Import Data", icon="📥")
    st.page_link("pages/4_Manual.py", label="Manual", icon="📖")

st.title("🔬 Strategy Backtester")

c1, c2, c3, c4 = st.columns(4)
days = c1.selectbox("Days", [30, 45, 60], index=2)
top_n = c2.selectbox("Top N", [1, 2, 3, 5], index=2)
hold = c3.selectbox("Hold (days)", [1, 2, 3, 5], index=1)
capital = c4.number_input("Capital / trade", value=100_000, step=10_000)

run = st.button("Run Backtest", type="primary", width="stretch")

if run:
    with st.spinner("Loading data..."):
        cache = loader.DataCache(); cache.load(days)

    results = {}
    progress = st.progress(0)
    strats = list(scorer.STRATEGIES.items())

    for i, (name, fn) in enumerate(strats):
        with st.spinner(f"Testing {name}..."):
            results[name] = scorer.run_backtest(cache, fn, top_n=top_n,
                                                hold=hold, capital=capital)
        progress.progress((i + 1) / len(strats))
    progress.empty()

    st.subheader("Strategy Comparison")
    comp = []
    for name, r in results.items():
        comp.append({
            "Strategy": name, "Trades": r["total_trades"],
            "Win Rate": f"{r['win_rate']:.1f}%",
            "Profit Factor": r["profit_factor"],
            "Return %": f"{r['return_pct']:+.2f}%",
            "Total P&L": f"₹{r['total_pnl']:,.0f}",
            "Avg Win %": f"{r['avg_win_pct']:+.2f}%",
            "Avg Loss %": f"{r['avg_loss_pct']:+.2f}%",
            "Max DD": f"₹{r['max_dd']:,.0f}",
        })
    st.dataframe(pd.DataFrame(comp), width="stretch")

    st.subheader("Equity Curves")
    fig = go.Figure()
    colors = ["#6366f1", "#22c55e", "#f59e0b", "#ef4444"]
    for i, (name, r) in enumerate(results.items()):
        eq = r["equity"]
        if eq:
            fig.add_trace(go.Scatter(x=[p["date"] for p in eq],
                                      y=[p["equity"] for p in eq],
                                      name=name, line=dict(color=colors[i % 4])))
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(margin=dict(t=10, b=10), height=400, yaxis_title="P&L (₹)")
    st.plotly_chart(fig, width="stretch")

    best_name = max(results, key=lambda k: results[k]["profit_factor"])
    best = results[best_name]
    st.subheader(f"Monthly — {best_name}")
    if best["monthly"]:
        mrows = []
        for m, d in sorted(best["monthly"].items()):
            wr = d["wins"] / d["trades"] * 100 if d["trades"] else 0
            mrows.append({"Month": m, "P&L": d["pnl"], "Trades": d["trades"],
                          "Wins": d["wins"], "Win Rate": f"{wr:.0f}%"})
        mdf = pd.DataFrame(mrows)
        fig = px.bar(mdf, x="Month", y="P&L", color="P&L",
                     color_continuous_scale=["#ef4444", "#fbbf24", "#22c55e"],
                     text="P&L")
        fig.update_traces(texttemplate="₹%{text:,.0f}", textposition="outside")
        fig.update_layout(margin=dict(t=10, b=10), height=300, showlegend=False)
        st.plotly_chart(fig, width="stretch")

    with st.expander(f"📋 Trade Log — {best_name}"):
        tdf = pd.DataFrame(best["trades"]).sort_values("date", ascending=False)
        st.dataframe(tdf, width="stretch", height=500)
