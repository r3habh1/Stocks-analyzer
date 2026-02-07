"""Import Data — upload CSV to update the database."""

import streamlit as st
import pandas as pd
from core import importer, loader, db

st.set_page_config(page_title="Import Data", page_icon="📥", layout="wide")

with st.sidebar:
    st.header("Navigation")
    st.page_link("app.py", label="Home", icon="🏠")
    st.page_link("pages/1_Stock_Analysis.py", label="Stock Analysis", icon="🔍")
    st.page_link("pages/2_Backtest.py", label="Backtest", icon="🔬")
    st.page_link("pages/3_Import_Data.py", label="Import Data", icon="📥")
    st.page_link("pages/4_Manual.py", label="Manual", icon="📖")
    st.divider()

st.title("📥 Import CSV Data")

st.markdown("""
Upload your daily **Derivative Analytics CSV**. The importer will:
- **Add** new records  |  **Update** existing  |  **Never delete** history  
- **Call/Put OI Chg %** are computed from cumulative OI (today vs yesterday).
""")

st.divider()

col1, col2, col3, col4 = st.columns(4)
latest = loader.get_latest_date()
dates = loader.get_dates(100)
symbols = loader.get_symbols()

col1.metric("Latest Date", latest or "No data")
col2.metric("Trading Days", len(dates))
col3.metric("Stocks Tracked", len(symbols))
col4.metric("Total Records", db.main_coll().count_documents({}))

st.divider()
st.subheader("Upload CSV")

uploaded = st.file_uploader("Drop CSV here", type=["csv"], accept_multiple_files=True)
if uploaded:
    # Read all file contents upfront (before preview consumes the stream)
    file_contents = {}
    for f in uploaded:
        f.seek(0)
        file_contents[f.name] = f.read().decode("utf-8")
        f.seek(0)

    for f in uploaded:
        st.markdown(f"**{f.name}** ({f.size/1024:.1f} KB)")
        with st.expander("Preview"):
            try:
                text = file_contents[f.name]
                lines = text.splitlines()
                # Find actual header row (skip preamble)
                header_idx = 0
                for i, line in enumerate(lines):
                    if "Symbol" in line or "symbol" in line:
                        header_idx = i
                        break
                import io
                preview_df = pd.read_csv(io.StringIO("\n".join(lines[header_idx:])), nrows=10)
                st.dataframe(preview_df, width="stretch")
            except Exception as e:
                st.error(str(e))

    if st.button("Import All", type="primary", width="stretch"):
        total_new = total_upd = 0
        for name, text in file_contents.items():
            if not text.strip():
                st.error(f"`{name}`: Empty file, skipping")
                continue
            with st.spinner(f"Importing {name}..."):
                new, upd, errors = importer.import_csv(text)
                total_new += new; total_upd += upd
                st.success(f"`{name}`: {new} new, {upd} updated")
                if errors:
                    for e in errors[:10]:
                        st.error(e)
        c1, c2 = st.columns(2)
        c1.metric("New Records", total_new)
        c2.metric("Updated Records", total_upd)
        st.success("Done! Refresh dashboard to see new data.")
        st.cache_data.clear()
        st.cache_resource.clear()

st.divider()
st.subheader("Recent Data")
if dates:
    rows = [{"Date": d, "Records": db.main_coll().count_documents({"date": d})}
            for d in dates[-10:][::-1]]
    st.dataframe(pd.DataFrame(rows), width="stretch")

    # Industry breakdown for latest date (e.g. Page Industries / sector-specific imports)
    with st.expander("By Industry (latest date)"):
        latest_docs = list(db.main_coll().find({"date": latest}))
        if latest_docs:
            from collections import Counter
            industries = Counter(d.get("industry_name", "?") for d in latest_docs)
            ind_df = pd.DataFrame([
                {"Industry": k, "Stocks": v} for k, v in industries.most_common()
            ])
            st.dataframe(ind_df, width="stretch", hide_index=True)
