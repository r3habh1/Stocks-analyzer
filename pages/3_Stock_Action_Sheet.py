"""Stock Action Sheet — Full ranked list with all available data."""

import streamlit as st
import pandas as pd
from core import loader, recommender

st.set_page_config(page_title="Stock Action Sheet", page_icon="📋", layout="wide")

with st.sidebar:
    st.header("Navigation")
    st.page_link("app.py", label="Home", icon="🏠")
    st.page_link("pages/2_Stock_Analysis.py", label="Stock Analysis", icon="🔍")
    st.page_link("pages/3_Stock_Action_Sheet.py", label="Stock Sheet", icon="📋")
    st.page_link("pages/4_Import_Data.py", label="Import Data", icon="📥")
    st.divider()

# ── Load data (defaults: last 60 days, All MCap) ─────────────────
dates = loader.get_dates(limit=60)
if not dates:
    st.error("No data."); st.stop()

with st.sidebar:
    st.subheader("View")
    view_date = st.selectbox(
        "View date",
        options=dates[::-1],
        index=0,
        format_func=lambda d: f"{d} (today)" if dates and d == dates[-1] else d,
    )
    st.caption(f"Data up to {view_date}")

dates_up_to_view = [d for d in dates if d <= view_date]
mcap_filter = "All"

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

action_sheet = recommender.get_action_sheet(
    sig_data, dates_up_to_view, view_date,
    mcap_filter=mcap_filter,
    min_conv=0,
    min_score=0,
    watchlist=None,
)

st.subheader(f"Stock Action Sheet — {view_date}")

if action_sheet:
    rows = []
    for i, p in enumerate(action_sheet, 1):
        sigs = ", ".join(p.get("signals", [])) or "—"
        rows.append({
            "Rank": i,
            "Symbol": f"/Stock_Analysis?symbol={p['symbol']}",
            "Stock Name": p.get("stock_name", ""),
            "Close": p.get("close", 0),
            "Chg%": p.get("change_pct"),
            "Conv": p["conviction"],
            "Score": p["score"],
            "Signals": sigs,
            "Vol(x)": p.get("volume_times", 0),
            "Dlv(x)": p.get("delivery_times", 0),
            "Fut OI Chg%": p.get("oi_change_pct"),
            "Call OI Chg%": p.get("call_oi_change_pct"),
            "Put OI Chg%": p.get("put_oi_change_pct"),
            "PCR": p.get("pcr", 0),
            "PCR Chg": p.get("pcr_change_1d"),
            "Cum Fut OI": p.get("cumulative_future_oi"),
            "Cum Call OI": p.get("cumulative_call_oi"),
            "Cum Put OI": p.get("cumulative_put_oi"),
            "OI Trend": p.get("oi_trend", ""),
            "MCap": p.get("mcap_category", ""),
            "Sector": p.get("sector", ""),
            "Industry": p.get("industry", ""),
            "Lot Size": p.get("lot_size"),
        })
    as_df = pd.DataFrame(rows)
    chg_cols = [c for c in as_df.columns if "Chg" in c]
    fmt = {c: "{:+.1f}" for c in ["Chg%", "Fut OI Chg%", "Call OI Chg%", "Put OI Chg%"] if c in as_df.columns}
    fmt.update({c: "{:+.2f}" for c in ["PCR Chg"] if c in as_df.columns})
    fmt.update({c: "{:.2f}" for c in ["Vol(x)", "Dlv(x)", "PCR"] if c in as_df.columns})
    fmt.update({c: "{:,.2f}" for c in ["Close"] if c in as_df.columns})
    fmt.update({c: "{:,.0f}" for c in ["Cum Fut OI", "Cum Call OI", "Cum Put OI", "Lot Size"] if c in as_df.columns})
    styled = as_df.style.format(fmt, na_rep="—")
    if chg_cols:
        def _sc(s):
            return ["color: #22c55e" if v is not None and isinstance(v, (int, float)) and v > 0
                    else "color: #ef4444" if v is not None and isinstance(v, (int, float)) and v < 0 else "" for v in s]
        styled = styled.apply(_sc, subset=chg_cols)
    if "OI Trend" in as_df.columns:
        styled = styled.map(lambda v: "background-color: rgba(34,197,94,0.2)" if v in ("NewLong", "ShortCover") else "background-color: rgba(239,68,68,0.2)" if v in ("NewShort", "LongCover") else "", subset=["OI Trend"])
    for col in ["Vol(x)", "Dlv(x)"]:
        if col in as_df.columns:
            styled = styled.map(lambda v: "background-color: rgba(34,197,94,0.3); font-weight: 600" if v is not None and isinstance(v, (int, float)) and v >= 1.5 else "", subset=[col])
    st.dataframe(styled, width="stretch", hide_index=True, height=500,
                 column_config={"Symbol": st.column_config.LinkColumn("Symbol", display_text=r".*symbol=([^&]+)")})
else:
    st.caption("No stocks for this filter.")
