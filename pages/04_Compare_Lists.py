import streamlit as st
import pandas as pd
import yfinance as yf
import time
import io
import os
from utils.ui import render_country_selector
from utils.processors import get_processor

# --- 1. Page Config (必ず最初) ---
st.set_page_config(page_title="Compare Lists", layout="wide")

# --- 2. 認証機能 (utilsから読み込む) ---
from utils.auth import check_password
if not check_password():
    st.stop()

# --- Functions ---
def load_codes_from_file(uploaded_file):
    """Excel/CSVから自動的に 'Code' 列を探して読み込む"""
    try:
        filename = uploaded_file.name.lower()
        df = None

        # 1. ファイル読み込み
        if filename.endswith('.csv'):
            # CSV: まずヘッダーなしで読んでみる
            df = pd.read_csv(uploaded_file, header=None)
            first_val = str(df.iloc[0, 0]).strip()
            # 1行目がヘッダーっぽいなら読み直す
            if first_val.lower() in ["code", "symbol", "ticker", "stock code"]:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file)
        else:
            # Excel: ヘッダーありとして読む
            df = pd.read_excel(uploaded_file)

        # 2. 'Code' 列の特定 (大文字小文字を無視して探す)
        target_col = None
        cols_map = {str(c).lower().strip(): c for c in df.columns}
        
        # 優先順位: Code > Stock Code > Symbol > Ticker
        search_keys = ["code", "stock code", "symbol", "ticker"]
        
        for key in search_keys:
            if key in cols_map:
                target_col = cols_map[key]
                break
        
        # 3. 列が見つからない場合のフォールバック (1列目を強制使用)
        if target_col is None:
            # データフレームの1列目を使用
            series = df.iloc[:, 0]
            # カラム名自体もデータかもしれないのでセットに追加
            codes = set(series.astype(str).str.strip())
            codes.add(str(df.columns[0]).strip())
        else:
            # 特定できた列を使用
            codes = set(df[target_col].astype(str).str.strip())

        # 4. クリーニング (nanやヘッダー文字を除外)
        cleaned = {
            c for c in codes 
            if c and c.lower() != 'nan' 
            and c.lower() not in ['code', 'stock code', 'symbol', 'ticker', 'unnamed: 0']
        }
        return cleaned

    except Exception as e:
        st.error(f"Error loading {uploaded_file.name}: {e}")
        return set()

def fetch_company_info_batch(codes, progress_bar, status_text):
    """差分銘柄の詳細情報をYahoo Financeから取得"""
    data = []
    total = len(codes)
    
    for i, code in enumerate(sorted(codes)):
        status_text.text(f"Fetching info ({i+1}/{total}): {code}...")
        progress_bar.progress((i + 1) / (total + 1))
        
        try:
            ticker = yf.Ticker(code)
            info = ticker.info
            data.append({
                "Code": code,
                "Name": info.get('longName', 'N/A'),
                "Sector": info.get('sector', 'N/A'),
                "Industry": info.get('industry', 'N/A'),
                "Business Summary": info.get('longBusinessSummary', 'N/A')
            })
        except Exception:
            data.append({
                "Code": code,
                "Name": "Error",
                "Sector": "-",
                "Industry": "-",
                "Business Summary": "Failed to fetch"
            })
        
        time.sleep(0.5)
        
    return pd.DataFrame(data)

# --- Sidebar ---
country_code = render_country_selector()
processor = get_processor(country_code)

with st.sidebar:
    st.divider()
    st.info(f"Mode: {country_code}")
    debug_mode = st.checkbox("Debug Mode")

# --- Main Area ---
st.title("⚖️ List Comparison Tool")
st.markdown("""
Compare output files from **Version 1, 2, or 3**.
Upload two files (Excel or CSV) to analyze which companies were added or dropped.
""")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📁 File A (Base)")
    st.markdown("e.g., **Version 1** Output (Original List)")
    file_a = st.file_uploader("Upload File A", type=["xlsx", "xls", "csv"], key="file_a")

with col2:
    st.subheader("📁 File B (Target)")
    st.markdown("e.g., **Version 3** Output (AI Result)")
    file_b = st.file_uploader("Upload File B", type=["xlsx", "xls", "csv"], key="file_b")

# --- Analysis Logic ---
if file_a and file_b:
    set_a = load_codes_from_file(file_a)
    set_b = load_codes_from_file(file_b)
    
    if not set_a or not set_b:
        st.warning("Could not extract stock codes. Please check if the files contain a 'Code' column.")
    else:
        # ベン図計算
        common = set_a & set_b
        only_a = set_a - set_b # AにあってBにない（脱落）
        only_b = set_b - set_a # BにあってAにない（新規）
        
        st.divider()
        st.subheader("📊 Comparison Result")
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Common (Both A & B)", f"{len(common)} codes", help="Companies present in BOTH files.")
        m2.metric("Only in File A", f"{len(only_a)} codes", delta=f"-{len(only_a)}", delta_color="inverse", help="Companies that disappeared in File B.")
        m3.metric("Only in File B", f"{len(only_b)} codes", delta=f"+{len(only_b)}", help="New companies found in File B.")

        # 詳細分析セクション
        st.divider()
        st.subheader("🔍 Deep Dive Analysis")
        st.write("Select a group to retrieve detailed business summaries.")
        
        analysis_target = st.radio(
            "Target Group:",
            ["Only in File A (Dropped / filtered out)", "Only in File B (Newly added)", "Common (Survivors)"]
        )
        
        target_codes = []
        if "Only in File A" in analysis_target:
            target_codes = only_a
        elif "Only in File B" in analysis_target:
            target_codes = only_b
        else:
            target_codes = common
        
        if target_codes:
            st.write(f"**Target Codes ({len(target_codes)}):** {', '.join(sorted(target_codes))}")
            
            if st.button(f"Fetch Details for {len(target_codes)} companies"):
                try:
                    prog_bar = st.progress(0)
                    status_txt = st.empty()
                    
                    df_result = fetch_company_info_batch(target_codes, prog_bar, status_txt)
                    
                    prog_bar.progress(100)
                    status_txt.success("Done!")
                    
                    # Excel Download
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_result.to_excel(writer, index=False, sheet_name="Analysis")
                    
                    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M")
                    st.download_button(
                        "📥 Download Analysis Excel",
                        data=output.getvalue(),
                        file_name=f"Comparison_Analysis_{timestamp}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
                    st.dataframe(df_result)
                    
                except Exception as e:
                    st.error(f"Error: {e}")
                    if debug_mode: st.exception(e)
        else:
            st.info("No codes found in this category.")

else:
    st.info("Please upload two files to start comparison.")