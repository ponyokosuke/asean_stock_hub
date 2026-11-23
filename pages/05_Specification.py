import os
import streamlit as st

# --- 1. Page Config (必ず最初) ---
st.set_page_config(page_title="Specification", layout="wide")

# --- 2. 認証機能 ---
from utils.auth import check_password
if not check_password():
    st.stop()

# 仕様書は docs/SPECIFICATION.md で管理 (GitHub で編集すると自動反映)
SPEC_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "SPECIFICATION.md")

with open(SPEC_PATH, encoding="utf-8") as f:
    spec = f.read()

st.download_button("📥 Download (Markdown)", data=spec, file_name="ASEAN_Stock_Hub_Specification.md", mime="text/markdown")
st.markdown(spec)
