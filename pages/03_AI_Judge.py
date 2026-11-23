import streamlit as st
import pandas as pd
import time
import os
import json
import yfinance as yf
from google import genai 
from datetime import datetime
from utils.ui import render_country_selector
from utils.processors import get_processor
from utils.sector_master import load_master, SECTORS
from utils.analysis import run_financial_analysis, show_result

# --- 1. Page Config (必ず最初！) ---
st.set_page_config(page_title="Version 3: AI Judge", layout="wide")

# --- 2. 認証機能 (共通パーツを使用) ---
# これにより、Homeでログイン済みならここはスキップされます
from utils.auth import check_password
if not check_password():
    st.stop()

# --- Constants & Config ---
PROMPTS_DIR = "prompts"
PROMPT_FILE = os.path.join(PROMPTS_DIR, "it_judge_prompt.txt")

if not os.path.exists(PROMPTS_DIR):
    os.makedirs(PROMPTS_DIR)

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

# --- 3. API Key Handling (Cloud対応) ---
env_gemini_key = None
if "GEMINI_API_KEY" in st.secrets:
    env_gemini_key = st.secrets["GEMINI_API_KEY"]
elif "GEMINI_API_KEY" in os.environ:
    env_gemini_key = os.environ.get("GEMINI_API_KEY")

# --- 4. Sidebar (Settings) ---
country_code = render_country_selector()
processor = get_processor(country_code)

if "current_prompt" not in st.session_state:
    if os.path.exists(PROMPT_FILE):
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            st.session_state.current_prompt = f.read()
    else:
        st.session_state.current_prompt = DEFAULT_SYSTEM_PROMPT

with st.sidebar:
    st.divider()
    st.info(f"Mode: {country_code} ({processor.currency})")
    
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

# --- 5. Main Area ---
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

# --- Target Sectors (セクターマスタから候補を絞り込む) ---
country_df = load_master()
country_df = country_df[country_df["country"] == country_code]
sector_counts = country_df["sector"].value_counts()
judge_sectors = st.multiselect(
    "Target Sectors (companies to send to the AI)",
    options=[s for s in SECTORS + ["Unknown"] if s in sector_counts],
    default=[s for s in ["Technology", "Communication Services"] if s in sector_counts],
    format_func=lambda s: f"{s} ({sector_counts[s]})",
)

# --- Functions ---
def fetch_summaries(codes, progress_bar, status_text):
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
                data_list.append({"code": code, "name": name, "summary": summary})
        except Exception:
            pass
        time.sleep(0.3)
    return data_list

def batch_judge_it_sector(targets, prompt_template, progress_bar, status_text):
    if not env_gemini_key:
        st.error("Gemini API Key is missing. Check .env or Secrets.")
        return []

    client = genai.Client(api_key=env_gemini_key)
    all_results = []
    batch_size = 30
    total_targets = len(targets)
    
    log_container = st.container()
    log_container.write("--- AI Judgment Log ---")
    
    for i in range(0, total_targets, batch_size):
        batch = targets[i : i + batch_size]
        current_idx = min(i + batch_size, total_targets)
        status_text.text(f"🤖 AI Judging ({i+1} - {current_idx} / {total_targets})...")
        progress_bar.progress(current_idx / total_targets)

        input_data_text = ""
        for item in batch:
            s = item['summary'][:800].replace("\n", " ")
            input_data_text += f"Code: {item['code']}\nSummary: {s}...\n---\n"
        
        full_prompt = f"{prompt_template}\n\n### TARGET COMPANIES DATA\n{input_data_text}"
        
        try:
            response = client.models.generate_content(model='gemini-2.5-flash', contents=full_prompt)
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            
            try:
                result_json = json.loads(clean_text)
            except json.JSONDecodeError:
                start = clean_text.find("{")
                end = clean_text.rfind("}") + 1
                if start != -1 and end != -1:
                    clean_text = clean_text[start:end]
                    result_json = json.loads(clean_text)
                else:
                    continue

            for item in batch:
                code = item['code']
                if code in result_json:
                    res = result_json[code]
                    verdict = res.get("verdict", "No")
                    item['Verdict'] = verdict
                    item['Category'] = res.get("category", "N/A")
                    item['Reason'] = res.get("reason", "")
                    all_results.append(item)
                    if verdict == "Yes":
                        log_container.write(f"✅ **{code}** ({item['name']}): {res.get('category')} - {res.get('reason')}")
            time.sleep(1)
        except Exception as e:
            if debug_mode: st.warning(f"Batch Error: {e}")
            time.sleep(2)
    return all_results

# --- 6. Execution Logic ---
if st.button("Start AI Judgment & Analysis 🚀"):
    country_candidates = country_df[country_df["sector"].isin(judge_sectors)]["symbol"].tolist()
    
    if not country_candidates:
        st.error(f"No stock codes found for {country_code} in the selected sectors.")
    else:
        try:
            status_text = st.empty()
            progress_bar = st.progress(0)
            
            st.info(f"Step 1: Retrieving Business Summaries for {len(country_candidates)} companies...")
            data_with_summary = fetch_summaries(country_candidates, progress_bar, status_text)
            
            if not data_with_summary:
                st.error("Could not retrieve summaries. Please try again.")
                st.stop()
                
            st.info(f"Step 2: AI Analyzing {len(data_with_summary)} companies with your prompt...")
            judged_results = batch_judge_it_sector(data_with_summary, st.session_state.current_prompt, progress_bar, status_text)
            
            yes_companies = [item for item in judged_results if item.get('Verdict') == "Yes"]
            
            if not yes_companies:
                st.warning("No companies were judged as 'Yes' (IT-related).")
            else:
                st.success(f"Found {len(yes_companies)} IT-related companies! Starting full financial analysis...")
                time.sleep(1)
                
                run_financial_analysis(
                    [c["code"] for c in yes_companies], processor, country_code, "Version_3_AI_Judge",
                    extra_fields={c["code"]: {"Category Classification/YahooFin": c.get("Category", "") + " (AI Judged)"}
                                  for c in yes_companies},
                )

        except Exception as e:
            st.error(f"❌ Error: {e}")
            if debug_mode: st.exception(e)

# 直近の結果を表示 (ダウンロード後も消えない)
show_result("Version_3_AI_Judge", country_code)
