import streamlit as st
import pandas as pd
import os
from utils.ui import render_country_selector
from utils.processors import get_processor
from utils.codes import parse_codes
from utils.analysis import run_financial_analysis, show_result

# --- 1. Page Config (必ず一番最初！) ---
st.set_page_config(page_title="Version 1: Financial Data", layout="wide")

# --- 2. 認証機能 (utilsから読み込む) ---
from utils.auth import check_password
if not check_password():
    st.stop()

# --- Constants ---
TEMPLATE_DIR = "templates"
# デフォルトリストは GitHub リポジトリで管理 (Streamlit Cloud 上で保存しても再起動で消えるため)
GITHUB_TEMPLATE_URL = "https://github.com/ponyokosuke/asean_stock_hub/edit/main/templates/{}.csv"

# --- 3. Sidebar (Country & Template) ---
country_code = render_country_selector()
processor = get_processor(country_code)

template_path = os.path.join(TEMPLATE_DIR, f"{country_code}.csv")
default_codes = parse_codes(template_path, processor.suffix) if os.path.exists(template_path) else []

with st.sidebar:
    st.divider()
    st.info(f"Mode: {country_code} ({processor.currency})")

    with st.expander(f"📋 Default List ({len(default_codes)} items)"):
        if default_codes:
            st.dataframe(
                pd.DataFrame(default_codes, columns=["Stock Code"]),
                width="stretch",
                hide_index=True,
                height=200
            )
        else:
            st.info("List is empty.")
        st.caption(
            f"To change the default list permanently, edit "
            f"[templates/{country_code}.csv on GitHub]({GITHUB_TEMPLATE_URL.format(country_code)}). "
            "The app updates automatically after saving."
        )

    st.divider()
    debug_mode = st.checkbox("Debug Mode")

# --- 4. Main Area ---
st.title(f"📊 Version 1: Financial Data ({country_code})")

uploaded_file = st.file_uploader(f"Upload Stock List (CSV) for {country_code}", type=["csv"])

has_template = len(default_codes) > 0
default_label = (
    f"Use default list for {country_code} ({len(default_codes)} codes)" if has_template
    else f"Use default list for {country_code} (Not registered ⚠️)"
)
use_sample = st.checkbox(default_label, disabled=not has_template)

# --- 5. Execution ---
if st.button("Start Analysis 🚀"):
    if uploaded_file is not None:
        codes = parse_codes(uploaded_file, processor.suffix)
    elif use_sample and has_template:
        codes = default_codes
    else:
        codes = None

    if codes is None:
        st.error("Please upload a CSV file or select the default list.")
    elif not codes:
        st.error("No valid stock codes found in the CSV. Put one code per row in the first column (e.g. 0097 or 0097.KL).")
    else:
        try:
            run_financial_analysis(codes, processor, country_code, "Version_1")
        except Exception as e:
            st.error(f"❌ Error: {e}")
            if debug_mode:
                st.exception(e)

# 直近の結果を表示 (ダウンロード後も消えない)
show_result("Version_1", country_code)
