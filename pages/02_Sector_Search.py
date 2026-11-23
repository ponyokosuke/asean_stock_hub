import streamlit as st
from datetime import datetime
from utils.ui import render_country_selector
from utils.processors import get_processor
from utils.sector_master import load_master, load_meta, SECTORS
from utils.analysis import run_financial_analysis

# --- 1. Page Config (必ず最初) ---
st.set_page_config(page_title="Version 2: Sector Search", layout="wide")

# --- 2. 認証機能 (utilsから読み込む) ---
from utils.auth import check_password
if not check_password():
    st.stop()

# --- 3. Sidebar (Country Selection) ---
country_code = render_country_selector()
processor = get_processor(country_code)

with st.sidebar:
    st.divider()
    st.info(f"Mode: {country_code} ({processor.currency})")
    debug_mode = st.checkbox("Debug Mode")

# --- 4. Main Area ---
st.title(f"🏭 Version 2: Sector Search ({country_code})")

st.markdown("""
Search for companies in specific sectors and generate a financial report **identical to Version 1**.
""")

# セクターマスタ (GitHub Actions が毎日更新) を読み込む
master = load_master()
meta = load_meta()
country_df = master[master["country"] == country_code]

if country_df.empty:
    st.warning(
        f"No company list is available for {country_code} (Yahoo Finance does not provide a screener for this market). "
        "Please use **Version 1** with an uploaded CSV instead."
    )
    st.stop()

st.caption(f"Sector master: {len(country_df)} listed companies in {country_code} · last updated {meta.get('updated_at', 'unknown')}")

# ★ Multi-select Input for Sectors (件数つき)
sector_counts = country_df["sector"].value_counts()
sector_options = [s for s in SECTORS + ["Unknown"] if s in sector_counts]
selected_sectors = st.multiselect(
    "Select Target Sectors",
    options=sector_options,
    format_func=lambda s: f"{s} ({sector_counts[s]})",
    placeholder="Choose sectors (e.g., Technology, Real Estate)"
)
keyword = st.text_input("Filter by company name (optional)", placeholder="e.g. Berhad, Tech")

if not selected_sectors:
    st.info("Select at least one sector to see the companies.")
    st.stop()

hits = country_df[country_df["sector"].isin(selected_sectors)]
if keyword:
    hits = hits[hits["name"].str.contains(keyword, case=False, regex=False)]

if hits.empty:
    st.warning("No companies found matching the specified sectors.")
    st.stop()

# --- 5. 銘柄一覧 (チェックで対象を選択) ---
table = hits[["symbol", "name", "sector"]].rename(
    columns={"symbol": "Code", "name": "Name of Company", "sector": "Sector"}
)
table.insert(0, "Select", True)
edited = st.data_editor(
    table,
    hide_index=True,
    use_container_width=True,
    disabled=["Code", "Name of Company", "Sector"],
    key=f"hits_{country_code}_{'|'.join(selected_sectors)}_{keyword}",
)
selected_codes = edited.loc[edited["Select"], "Code"].tolist()

col_a, col_b = st.columns(2)
with col_a:
    st.download_button(
        f"📄 Download code list ({len(selected_codes)})",
        data="\n".join(selected_codes),
        file_name=f"Codes_{country_code}_{datetime.today().strftime('%Y-%m-%d')}.csv",
        mime="text/csv",
        disabled=not selected_codes,
    )
with col_b:
    start = st.button(f"Start Financial Analysis ({len(selected_codes)} companies) 🚀", disabled=not selected_codes)

if len(selected_codes) > 100:
    st.caption("⏱ Large selections take a long time (several seconds per company). Consider narrowing down first.")

# --- 6. Execution ---
if start:
    try:
        run_financial_analysis(selected_codes, processor, country_code, "Version_2")
    except Exception as e:
        st.error(f"❌ Error: {e}")
        if debug_mode:
            st.exception(e)
