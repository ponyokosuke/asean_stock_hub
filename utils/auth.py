import hmac
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

def check_password():
    """
    パスワード認証を行う関数。
    認証が済んでいなければ入力画面を表示し、処理を止める (Falseを返す)。
    認証済みなら True を返す。
    パスワード未設定の場合は誰も入れないようにする (fail closed)。
    """
    
    # 1. パスワードの取得 (st.secrets 優先、なければ os.environ)
    correct_password = None
    
    # Streamlit CloudのSecretsを確認
    if "APP_PASSWORD" in st.secrets:
        correct_password = st.secrets["APP_PASSWORD"]
    # なければ環境変数を確認 (.env)
    elif "APP_PASSWORD" in os.environ:
        correct_password = os.environ.get("APP_PASSWORD")
        
    # パスワードが設定されていない場合はアクセスを拒否する
    if not correct_password:
        st.error("🔒 Access is disabled: APP_PASSWORD is not configured. "
                 "Set it in Streamlit Cloud → App settings → Secrets (or in .env when running locally).")
        return False

    # 2. セッションステートでログイン状態を管理
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    # 3. パスワード入力画面
    st.markdown("### 🔒 Please login")
    input_password = st.text_input("Password", type="password", key="auth_input")
    
    if st.button("Log in"):
        if hmac.compare_digest(input_password.encode(), str(correct_password).encode()):
            st.session_state["password_correct"] = True
            st.rerun() # 再読み込みしてメイン画面へ
        else:
            st.error("❌ Password incorrect")
            
    # 認証完了までは False を返す
    return False