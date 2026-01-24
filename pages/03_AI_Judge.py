import streamlit as st
import pandas as pd
import time
import os
import json
import yfinance as yf
from google import genai # ★最新ライブラリに変更
from datetime import datetime
from utils.ui import render_country_selector
from utils.processors import get_processor

# 銘柄リストのインポート
try:
    from utils.stock_codes import ALL_ASEAN_CODES
except ImportError:
    st.error("⚠️ Critical Error: `utils/stock_codes.py` was not found.")
    st.stop()

# --- Constants & Config ---
PROMPTS_DIR = "prompts"
PROMPT_FILE = os.path.join(PROMPTS_DIR, "it_judge_prompt.txt")

# ディレクトリ作成
if not os.path.exists(PROMPTS_DIR):
    os.makedirs(PROMPTS_DIR)

# デフォルトのシステムプロンプト (初期値)
DEFAULT_SYSTEM_PROMPT = """You are a financial analyst specializing in technology sector classification.
Your task is to analyze the provided 'Summary of Business' for multiple companies and determine if they qualify as an **"IT-related Company"** based on the strict criteria below.

### 1. CRITERIA FOR INCLUSION (Verdict: "Yes")
Classify as "Yes" ONLY if the company's CORE business falls into one of these categories:
* **Software & IT Services:** Software development, SaaS, ERP, CRM, System Integration (SI), IT Consulting, Managed Services, Cybersecurity, AI, IoT.
* **Hardware & Technology Equipment:** Manufacturing or distributing enterprise IT hardware (servers, network equipment), Semiconductors, Electronic components for computing.
* **Telecommunications:** Telecommunication carriers, ISPs, Network infrastructure providers, Data Centers.

### 2. CRITERIA FOR EXCLUSION (Verdict: "No")
Classify as "No" if the company is merely a USER of IT, or if IT is secondary:
* **Fintech / Digital Banking:** (Exclude if core is financial services).
* **E-commerce Retail:** (Exclude if primarily selling physical goods).
* **General Manufacturing:** (Exclude unless strictly IT-related).

### 3. CRITERIA FOR AMBIGUITY (Verdict: "Grey")
Classify as "Grey" if the company has a mix of IT and non-IT businesses, and it is difficult to determine which is dominant, or if the summary is too vague.

### 4. OUTPUT FORMAT
Return a **valid JSON object**. 
The keys must be the STOCK_CODE.
The values must be an object with: "verdict", "category", and "reason".

{
  "STOCK_CODE": {
    "verdict": "Yes",  // Options: "Yes", "No", "Grey"
    "category": "Software", // Options: "Software", "IT Services", "Hardware", "Telecom", "Mixed", "N/A"
    "reason": "A concise explanation in **ENGLISH** (1-2 sentences) justifying the verdict." 
  }
}
"""

# --- Page Config ---
st.set_page_config(page_title="Version 3: AI Judge", layout="wide")

# --- 1. Authentication ---
env_password = os.environ.get("APP_PASSWORD")
env_gemini_key = os.environ.get("GEMINI_API_KEY")

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

# --- 2. Sidebar (Settings) ---
country_code = render_country_selector()
processor = get_processor(country_code)

# プロンプトの読み込みロジック
if "current_prompt" not in st.session_state:
    if os.path.exists(PROMPT_FILE):
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            st.session_state.current_prompt = f.read()
    else:
        st.session_state.current_prompt = DEFAULT_SYSTEM_PROMPT

with st.sidebar:
    st.divider()
    st.info(f"Mode: {country_code} ({processor.currency})")
    
    # ★ Default Prompt Management
    with st.expander("🛠 Manage Default Prompt"):
        st.write("Save the current prompt shown in the main area as the new default.")
        if st.button("Save Current Prompt as Default"):
            with open(PROMPT_FILE, "w", encoding="utf-8") as f:
                f.write(st.session_state.current_prompt)
            st.success("Default prompt updated!")
            time.sleep(1)
            st.rerun()
        
        if st.button("Reset to System Original"):
            st.session_state.current_prompt = DEFAULT_SYSTEM_PROMPT
            if os.path.exists(PROMPT_FILE):
                os.remove(PROMPT_FILE)
            st.rerun()

    st.divider()
    debug_mode = st.checkbox("Debug Mode")

# --- 3. Main Area ---
st.title(f"🤖 Version 3: AI Judge ({country_code})")
st.markdown("""
AI automatically retrieves business summaries and determines if companies are **IT-related**.
Companies judged as **"Yes"** will be analyzed in detail (identical to Version 1).
""")

# --- Prompt Editor ---
st.subheader("📝 AI Instructions (Prompt)")
user_prompt = st.text_area(
    "Edit the instructions for the AI below:",
    value=st.session_state.current_prompt,
    height=300,
    key="prompt_input"
)
st.session_state.current_prompt = user_prompt

# --- Functions ---
def fetch_summaries(codes, progress_bar, status_text):
    """Yahoo FinanceからSummaryを取得"""
    data_list = []
    total = len(codes)
    
    for i, code in enumerate(codes):
        status_text.text(f"Fetching Summary ({i+1}/{total}): {code}...")
        progress_bar.progress((i + 1) / (total + 1))
        
        try:
            ticker = yf.Ticker(code)
            info = ticker.info
            summary = info.get('longBusinessSummary', '')
            name = info.get('longName', code)
            
            if summary:
                data_list.append({
                    "code": code,
                    "name": name,
                    "summary": summary
                })
        except Exception:
            pass
        
        time.sleep(0.1)
    return data_list

def batch_judge_it_sector(targets, prompt_template, progress_bar, status_text):
    """Geminiで判定 (最新の google.genai ライブラリを使用)"""
    if not env_gemini_key:
        st.error("Gemini API Key is missing in .env")
        return []

    # ★ 最新のクライアント初期化
    client = genai.Client(api_key=env_gemini_key)
    
    all_results = []
    batch_size = 30
    total_targets = len(targets)
    
    # バッチ処理用コンテナ
    log_container = st.container()
    log_container.write("--- AI Judgment Log ---")
    
    for i in range(0, total_targets, batch_size):
        batch = targets[i : i + batch_size]
        current_idx = min(i + batch_size, total_targets)
        status_text.text(f"🤖 AI Judging ({i+1} - {current_idx} / {total_targets})...")
        progress_bar.progress(current_idx / total_targets)

        # 入力作成
        input_data_text = ""
        for item in batch:
            s = item['summary'][:800].replace("\n", " ")
            input_data_text += f"Code: {item['code']}\nSummary: {s}...\n---\n"
        
        full_prompt = f"""
        {prompt_template}

        ### TARGET COMPANIES DATA
        {input_data_text}
        """
        
        try:
            # ★ 最新の呼び出し方法
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=full_prompt
            )
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            
            # JSONパース
            try:
                result_json = json.loads(clean_text)
            except json.JSONDecodeError:
                start = clean_text.find("{")
                end = clean_text.rfind("}") + 1
                if start != -1 and end != -1:
                    clean_text = clean_text[start:end]
                    result_json = json.loads(clean_text)
                else:
                    continue # パース失敗時はこのバッチをスキップ

            for item in batch:
                code = item['code']
                if code in result_json:
                    res = result_json[code]
                    verdict = res.get("verdict", "No")
                    
                    # 結果を保存
                    item['Verdict'] = verdict
                    item['Category'] = res.get("category", "N/A")
                    item['Reason'] = res.get("reason", "")
                    
                    all_results.append(item)
                    
                    if verdict == "Yes":
                        log_container.write(f"✅ **{code}** ({item['name']}): {res.get('category')} - {res.get('reason')}")
            
            time.sleep(1)

        except Exception as e:
            if debug_mode:
                st.warning(f"Batch Error: {e}")
            time.sleep(2)
            
    return all_results

# --- 4. Execution Logic ---
if st.button("Start AI Judgment & Analysis 🚀"):
    # 1. 銘柄リスト取得
    country_candidates = [
        code for code in ALL_ASEAN_CODES 
        if code.endswith(processor.suffix)
    ]
    
    if not country_candidates:
        st.error(f"No stock codes found for {country_code}. Check `utils/stock_codes.py`.")
    else:
        try:
            status_text = st.empty()
            progress_bar = st.progress(0)
            
            # --- Phase 1: Retrieve Summaries ---
            st.info(f"Step 1: Retrieving Business Summaries for {len(country_candidates)} companies...")
            data_with_summary = fetch_summaries(country_candidates, progress_bar, status_text)
            
            if not data_with_summary:
                st.error("Could not retrieve summaries. Please try again.")
                st.stop()
                
            # --- Phase 2: AI Judgment ---
            st.info(f"Step 2: AI Analyzing {len(data_with_summary)} companies with your prompt...")
            judged_results = batch_judge_it_sector(
                data_with_summary, 
                st.session_state.current_prompt,
                progress_bar,
                status_text
            )
            
            # Filter "Yes" companies
            yes_companies = [item for item in judged_results if item.get('Verdict') == "Yes"]
            
            if not yes_companies:
                st.warning("No companies were judged as 'Yes' (IT-related).")
            else:
                st.success(f"Found {len(yes_companies)} IT-related companies! Starting full financial analysis...")
                time.sleep(1)
                
                # --- Phase 3: Financial Data (Version 1 Logic) ---
                all_financials = []
                total_yes = len(yes_companies)
                progress_bar.progress(0)
                
                for i, company in enumerate(yes_companies):
                    code = company['code']
                    status_text.text(f"Fetching Financial Data ({i+1}/{total_yes}): {code}...")
                    progress_bar.progress((i + 1) / (total_yes + 1))
                    
                    # Processor使用
                    raw = processor.get_stock_data(code)
                    if raw:
                        data = processor.extract_data(code, raw)
                        
                        # AI判定結果も付与しておく（Remarksなどに使うなら）
                        data["Category Classification/YahooFin"] = company.get('Category', '') + " (AI Judged)"
                        
                        all_financials.append(data)
                    
                    time.sleep(0.2)
                
                # --- Phase 4: Segment Extraction (ここに重要修正！) ---
                if all_financials:
                    status_text.text("🤖 Extracting detailed Business Segments (Version 1 Style)...")
                    # ★ これを呼び忘れていました！これでSegment列が埋まります
                    all_financials = processor.run_ai_analysis(all_financials)

                    # --- Phase 5: Excel Generation ---
                    status_text.text("📏 Formatting Excel (Version 1 Style)...")
                    
                    df = pd.DataFrame(all_financials)
                    df = processor.process_dataframe(df)
                    excel_data = processor.generate_excel_binary(df)
                    
                    progress_bar.progress(100)
                    status_text.success("✅ All processes completed!")
                    
                    # ファイル名生成
                    filename = f"Version_3_AI_Judge_{country_code}_{datetime.today().strftime('%Y-%m-%d')}.xlsx"
                    
                    st.download_button(
                        label="📥 Download Excel File",
                        data=excel_data,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
                    st.subheader("Results Preview")
                    st.dataframe(df)

        except Exception as e:
            st.error(f"❌ Error: {e}")
            if debug_mode:
                st.exception(e)