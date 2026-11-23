import streamlit as st
import os
from dotenv import load_dotenv

# --- 1. Page Config (必ず一番最初に書く！) ---
st.set_page_config(
    page_title="ASEAN Stock Hub",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. 認証機能 ---
# Page Configのあとに書く必要があります
from utils.auth import check_password
if not check_password():
    st.stop()

# --- 3. Main Logic ---
# Load API Key
load_dotenv()

st.title("🌏 ASEAN Stock Analysis Hub")

st.markdown("""
### Welcome
Please select a tool from the sidebar on the left.

📘 **New here?** Open the **User Guide** in the sidebar for step-by-step instructions.

* **Version 1: Financial Data**
    * Financial Analysis & AI Segment Analysis
* **Version 2: Sector Search**
    * Sector Screening
* **Version 3: AI Judge**
    * IT Business Verification & Classification
* **Compare Lists**
    * Compare Stock Lists (Diff Tool)
* **Specification**
    * System specification and known limitations

### Initial Setup
Please select the **Target Country** from the "Settings" in the sidebar.
""")

# Initialize Session State
if "target_country" not in st.session_state:
    st.session_state["target_country"] = "SG"