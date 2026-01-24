import streamlit as st
import pandas as pd
import time
import os
import shutil
from datetime import datetime
from utils.ui import render_country_selector
from utils.processors import get_processor

# --- Constants ---
TEMPLATE_DIR = "templates"
if not os.path.exists(TEMPLATE_DIR):
    os.makedirs(TEMPLATE_DIR)

# --- Page Config ---
st.set_page_config(page_title="Version 1: Financial Data", layout="wide")

# --- 1. Authentication ---
env_password = os.environ.get("APP_PASSWORD")

def check_password():
    if not env_password: return True
    if "password_correct" not in st.session_state:
        st.text_input("Please enter the password:", type="password", key="password_input")
        if st.session_state.get("password_input") == env_password:
            st.session_state["password_correct"] = True
            st.rerun()
        return False
    return True

if not check_password():
    st.stop()

# --- 2. Sidebar (Country & Template) ---
country_code = render_country_selector()
processor = get_processor(country_code)

# Template path
template_path = os.path.join(TEMPLATE_DIR, f"{country_code}.csv")

with st.sidebar:
    st.divider()
    st.info(f"Mode: {country_code} ({processor.currency})")
    
    # ★ Manage Default List (Add & Remove)
    with st.expander("🛠 Manage Default List"):
        st.write(f"Manage the default list for **{country_code}**.")

        # ---------------------------------------------------------
        # A. 既存リストの読み込み
        # ---------------------------------------------------------
        current_codes = []
        if os.path.exists(template_path):
            try:
                df_curr = pd.read_csv(template_path, header=None)
                # 文字列として読み込み、空白除去、ソート
                current_codes = sorted(df_curr[0].astype(str).str.strip().tolist())
            except Exception:
                current_codes = []

        # ---------------------------------------------------------
        # B. 追加機能 (Add)
        # ---------------------------------------------------------
        st.caption("➕ Add a single stock code")
        col_in, col_btn = st.columns([3, 1])
        with col_in:
            new_code_input = st.text_input("Enter Code", placeholder="e.g. 1155", label_visibility="collapsed")
        with col_btn:
            add_btn = st.button("Add")

        if add_btn and new_code_input:
            clean_code = new_code_input.strip()
            if clean_code in current_codes:
                st.warning(f"'{clean_code}' is already in the list.")
            else:
                current_codes.append(clean_code)
                # 保存
                pd.DataFrame(current_codes).to_csv(template_path, index=False, header=False)
                st.success(f"Added '{clean_code}'!")
                time.sleep(0.5)
                st.rerun()

        # ---------------------------------------------------------
        # C. 削除機能 (Remove) ★新規追加★
        # ---------------------------------------------------------
        if current_codes:
            st.write("---")
            st.caption("➖ Remove stock codes")
            
            # マルチセレクトで削除対象を選択
            codes_to_remove = st.multiselect(
                "Select codes to remove",
                options=current_codes,
                placeholder="Select codes to remove...",
                label_visibility="collapsed"
            )
            
            if st.button("Remove Selected") and codes_to_remove:
                # 削除対象以外を残す
                new_codes = [c for c in current_codes if c not in codes_to_remove]
                
                # 保存
                pd.DataFrame(new_codes).to_csv(template_path, index=False, header=False)
                st.success(f"Removed {len(codes_to_remove)} items!")
                time.sleep(0.5)
                st.rerun()

        # ---------------------------------------------------------
        # D. リストの中身を見る (View)
        # ---------------------------------------------------------
        st.write("---")
        if os.path.exists(template_path) and current_codes:
            with st.expander(f"👀 View Current List ({len(current_codes)} items)"):
                st.dataframe(
                    pd.DataFrame(current_codes, columns=["Stock Code"]),
                    use_container_width=True,
                    hide_index=True,
                    height=200
                )
        else:
            st.info("List is empty.")

        # ---------------------------------------------------------
        # E. ファイルごと上書き (Bulk Upload)
        # ---------------------------------------------------------
        st.write("---")
        st.caption("📤 Bulk Upload (Overwrite all)")
        new_template = st.file_uploader("Upload CSV", type=["csv"], key="template_uploader", label_visibility="collapsed")
        
        if new_template is not None:
            if st.button("Overwrite Default"):
                with open(template_path, "wb") as f:
                    f.write(new_template.getbuffer())
                st.success(f"Default list updated!")
                time.sleep(1)
                st.rerun()

    st.divider()
    debug_mode = st.checkbox("Debug Mode")

# --- 3. Main Area ---
# ★ Title with Version emphasized
st.title(f"📊 Version 1: Financial Data ({country_code})")

# File Uploader
uploaded_file = st.file_uploader(f"Upload Stock List (CSV) for {country_code}", type=["csv"])

# Template Logic
has_template = os.path.exists(template_path)
default_label = f"Use default list for {country_code} (Registered)" if has_template else f"Use default list for {country_code} (Not found ⚠️)"

use_sample = st.checkbox(default_label, disabled=not has_template)

# --- 4. Execution ---
if st.button("Start Analysis 🚀"):
    target_csv = None
    
    if uploaded_file is not None:
        target_csv = uploaded_file
    elif use_sample and has_template:
        target_csv = template_path
    
    if target_csv is None:
        st.error("Please upload a CSV file or select the default list.")
    else:
        try:
            status_text = st.empty()
            progress_bar = st.progress(0)
            
            # Read CSV
            df_input = pd.read_csv(target_csv, header=None)
            codes = df_input[0].astype(str).tolist()
            
            # Data Fetching Loop
            all_results = []
            total = len(codes)
            
            for i, code in enumerate(codes):
                code = code.strip()
                if "." not in code and processor.suffix:
                    code += processor.suffix
                    
                status_text.text(f"Processing ({i+1}/{total}): {code}...")
                progress_bar.progress((i + 1) / (total + 1))
                
                raw = processor.get_stock_data(code)
                if raw:
                    data = processor.extract_data(code, raw)
                    all_results.append(data)
                
                time.sleep(0.2)
            
            # AI & Formatting
            if all_results:
                status_text.text("🤖 Running AI Analysis...")
                all_results = processor.run_ai_analysis(all_results)
                
                df = pd.DataFrame(all_results)
                
                status_text.text("📏 Formatting data...")
                df = processor.process_dataframe(df)
                excel_data = processor.generate_excel_binary(df)
                
                progress_bar.progress(100)
                status_text.success("✅ All processes completed!")
                
                # Download
                filename = f"Version_1_{country_code}_{datetime.today().strftime('%Y-%m-%d')}.xlsx"
                st.download_button(
                    label="📥 Download Excel File",
                    data=excel_data,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                st.subheader("Preview")
                st.dataframe(df)
            else:
                st.warning("No data retrieved.")
                
        except Exception as e:
            st.error(f"❌ Error: {e}")
            if debug_mode:
                st.exception(e)