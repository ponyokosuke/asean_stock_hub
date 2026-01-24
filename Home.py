import streamlit as st
import os
from dotenv import load_dotenv

# Load API Key
load_dotenv()

st.set_page_config(
    page_title="ASEAN Stock Hub",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🌏 ASEAN Stock Analysis Hub")

st.markdown("""
### Welcome
Please select a tool from the sidebar on the left.

* **Version 1: Financial Data**
    * Financial Analysis & AI Segment Analysis
* **Version 2: Sector Search**
    * Sector Screening
* **Version 3: AI Judge**
    * IT Business Verification & Classification
* **Compare Lists**
    * Compare Stock Lists (Diff Tool)

### Initial Setup
Please select the **Target Country** from the "Settings" in the sidebar.
""")

# Initialize Session State
if "target_country" not in st.session_state:
    st.session_state["target_country"] = "SG"