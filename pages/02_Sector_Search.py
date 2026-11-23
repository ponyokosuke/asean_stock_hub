import streamlit as st
from datetime import datetime
from utils.ui import render_country_selector
from utils.processors import get_processor
from utils.sector_master import load_master, load_meta, SECTORS
from utils.analysis import run_financial_analysis, show_result

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

# ★ 分類の選択: 公式セクター (data/official) があればそちらも選べる
has_official = (country_df["official_sector"] != "").any()
sector_col = "sector"
if has_official:
    basis = st.radio("Sector classification", ["Yahoo Finance", "Official (exchange)"], horizontal=True)
    if basis.startswith("Official"):
        sector_col = "official_sector"
else:
    st.caption("Sectors follow Yahoo Finance's classification, which differs from the exchange's official sectors.")

# ★ Multi-select Input for Sectors (件数つき)
sector_counts = country_df[sector_col].replace("", "Unknown").value_counts()
if sector_col == "sector":
    sector_options = [s for s in SECTORS + ["Unknown"] if s in sector_counts]
else:
    sector_options = sorted(sector_counts.index)
selected_sectors = st.multiselect(
    "Select Target Sectors",
    options=sector_options,
    format_func=lambda s: f"{s} ({sector_counts[s]})",
    placeholder="Choose sectors (e.g., Technology, Real Estate)"
)

# ★ 市場区分フィルタ (MY: Main / ACE / LEAP)
selected_boards = []
board_counts = country_df["board"].value_counts()
if (country_df["board"] != "").any():
    selected_boards = st.multiselect(
        "Market / Board",
        options=list(board_counts.index),
        default=list(board_counts.index),
        format_func=lambda b: f"{b} ({board_counts[b]})",
        help="'ACE (unverified)': 0xxx codes are usually ACE Market, but companies that moved to the Main Market keep their code. "
             "Add confirmed boards to data/official/{country}.csv to fix them.",
    )

keyword = st.text_input("Filter by company name (optional)", placeholder="e.g. Berhad, Tech")

if not selected_sectors:
    st.info("Select at least one sector to see the companies.")
    st.stop()

hits = country_df[country_df[sector_col].replace("", "Unknown").isin(selected_sectors)]
if selected_boards:
    hits = hits[hits["board"].isin(selected_boards)]
if keyword:
    hits = hits[hits["name"].str.contains(keyword, case=False, regex=False)]

if hits.empty:
    st.warning("No companies found matching the specified sectors.")
    st.stop()

# --- 5. 銘柄一覧 (チェックで対象を選択) ---
show_cols = {"symbol": "Code", "name": "Name of Company", "board": "Board", "sector": "Sector (Yahoo)",
             "official_sector": "Sector (Official)"}
if not (hits["board"] != "").any():
    show_cols.pop("board")
if not has_official:
    show_cols.pop("official_sector")
table = hits[list(show_cols)].rename(columns=show_cols)
table.insert(0, "Select", True)
edited = st.data_editor(
    table,
    hide_index=True,
    width="stretch",
    disabled=list(show_cols.values()),
    key=f"hits_{country_code}_{sector_col}_{'|'.join(selected_sectors)}_{'|'.join(selected_boards)}_{keyword}",
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

# 直近の結果を表示 (ダウンロード後も消えない)
show_result("Version_2", country_code)
