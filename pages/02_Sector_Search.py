import streamlit as st
import pandas as pd
import time
import os
import yfinance as yf
from datetime import datetime
from utils.ui import render_country_selector
from utils.processors import get_processor

# Import Stock List
try:
    from utils.stock_codes import ALL_ASEAN_CODES
except ImportError:
    st.error("⚠️ Critical Error: `utils/stock_codes.py` was not found.")
    st.stop()

# --- Constants (Sector List) ---
SECTOR_OPTIONS = [
    "Basic Materials",
    "Communication Services",
    "Consumer Cyclical",
    "Consumer Defensive",
    "Energy",
    "Financial Services",
    "Healthcare",
    "Industrials",
    "Real Estate",
    "Technology",
    "Utilities"
]

# --- Page Config ---
st.set_page_config(page_title="Version 2: Sector Search", layout="wide")

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

# --- 2. Sidebar (Country Selection) ---
country_code = render_country_selector()
processor = get_processor(country_code)

with st.sidebar:
    st.divider()
    st.info(f"Mode: {country_code} ({processor.currency})")
    debug_mode = st.checkbox("Debug Mode")

# --- 3. Main Area ---
st.title(f"🏭 Version 2: Sector Search ({country_code})")

st.markdown("""
Search for companies in specific sectors and generate a financial report **identical to Version 1**.
""")

# ★ Multi-select Input for Sectors
selected_sectors = st.multiselect(
    "Select Target Sectors",
    options=SECTOR_OPTIONS,
    default=None,
    placeholder="Choose sectors (e.g., Technology, Real Estate)"
)

# --- 4. Execution Logic ---
if st.button("Start Screening & Analysis 🚀"):
    if not selected_sectors:
        st.error("Please select at least one sector.")
    else:
        try:
            # -------------------------------------------
            # Step 1: Filter Codes by Country
            # -------------------------------------------
            status_text = st.empty()
            progress_bar = st.progress(0)
            
            status_text.text("Filtering stock codes by country...")
            
            # Filter by country suffix (.SI, .KL, etc.)
            country_candidates = [
                code for code in ALL_ASEAN_CODES 
                if code.endswith(processor.suffix)
            ]
            
            if not country_candidates:
                st.error(f"No stock codes found for {country_code} (Suffix: {processor.suffix}). Please check `utils/stock_codes.py`.")
                st.stop()
            
            # -------------------------------------------
            # Step 2: Sector Screening (Yahoo Finance)
            # -------------------------------------------
            target_codes = []
            total_candidates = len(country_candidates)
            
            st.info(f"Screening {total_candidates} companies in {country_code} for sectors: {', '.join(selected_sectors)}...")
            
            # Container for logs
            log_container = st.container()
            log_container.write("--- Screening Results ---")

            for i, code in enumerate(country_candidates):
                progress_bar.progress((i + 1) / (total_candidates + 1))
                status_text.text(f"Screening ({i+1}/{total_candidates}): {code}...")
                
                try:
                    ticker = yf.Ticker(code)
                    # Fetch minimal info to check sector
                    info = ticker.info
                    company_sector = str(info.get('sector', 'Unknown'))
                    
                    # Check for match
                    is_match = False
                    if company_sector in selected_sectors:
                        is_match = True
                    
                    if is_match:
                        target_codes.append(code)
                        log_container.write(f"✅ Hit: **{code}** ({info.get('longName')}) - Sector: {company_sector}")
                        
                except Exception:
                    pass
                
                # Sleep to respect API limits
                time.sleep(0.1)

            # -------------------------------------------
            # Step 3: Full Data Analysis (Version 1 Logic)
            # -------------------------------------------
            if not target_codes:
                st.warning("No companies found matching the specified sectors.")
            else:
                st.success(f"Found {len(target_codes)} companies! Starting full financial analysis...")
                time.sleep(1)
                
                # Fetch full data like Version 1
                all_results = []
                total_targets = len(target_codes)
                
                progress_bar.progress(0) # Reset progress
                
                for i, code in enumerate(target_codes):
                    status_text.text(f"Fetching Financial Data ({i+1}/{total_targets}): {code}...")
                    progress_bar.progress((i + 1) / (total_targets + 1))
                    
                    # Use Processor for data extraction
                    raw = processor.get_stock_data(code)
                    if raw:
                        data = processor.extract_data(code, raw)
                        all_results.append(data)
                    
                    time.sleep(0.2)
                
                # AI Analysis & Formatting
                if all_results:
                    status_text.text("🤖 Running AI Analysis (Gemini)...")
                    all_results = processor.run_ai_analysis(all_results)
                    
                    df = pd.DataFrame(all_results)
                    
                    status_text.text("📏 Formatting Excel (Version 1 Style)...")
                    df = processor.process_dataframe(df)
                    excel_data = processor.generate_excel_binary(df)
                    
                    progress_bar.progress(100)
                    status_text.success("✅ All processes completed!")
                    
                    # ★ Filename Changed Here (Simplified)
                    # 例: Version_2_SG_2026-01-25.xlsx
                    filename = f"Version_2_{country_code}_{datetime.today().strftime('%Y-%m-%d')}.xlsx"
                    
                    st.download_button(
                        label="📥 Download Excel File",
                        data=excel_data,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
                    st.subheader("Data Preview")
                    st.dataframe(df)
        
        except Exception as e:
            st.error(f"❌ Error: {e}")
            if debug_mode:
                st.exception(e)