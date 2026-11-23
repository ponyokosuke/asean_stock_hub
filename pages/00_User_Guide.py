import os
import re
import streamlit as st

# --- 1. Page Config (必ず最初) ---
st.set_page_config(page_title="User Guide", layout="wide")

# --- 2. 認証機能 ---
from utils.auth import check_password
if not check_password():
    st.stop()

# 使い方ガイドは docs/USER_GUIDE.md で管理 (GitHub で編集すると自動反映)
DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
GUIDE_PATH = os.path.join(DOCS_DIR, "USER_GUIDE.md")
# Markdown の画像 ![caption](images/xxx.jpg) を st.image で表示するために分割する
IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\((images/[^)]+)\)")

with open(GUIDE_PATH, encoding="utf-8") as f:
    guide = f.read()

st.download_button("📥 Download (Markdown)", data=guide, file_name="ASEAN_Stock_Hub_User_Guide.md", mime="text/markdown")

parts = IMAGE_PATTERN.split(guide)
# parts = [text, caption, path, text, caption, path, ..., text]
for i in range(0, len(parts), 3):
    if parts[i].strip():
        st.markdown(parts[i])
    if i + 2 < len(parts):
        caption, path = parts[i + 1], parts[i + 2]
        # 画面幅に合わせて縮小 (大きな画面では幅の3/4まで)
        col, _ = st.columns([3, 1])
        col.image(os.path.join(DOCS_DIR, path), caption=caption, width="stretch")
