import streamlit as st
import os

def check_password():
    """
    パスワード認証を行う関数。
    認証が済んでいなければ入力画面を表示し、処理を止める (Falseを返す)。
    認証済み、またはパスワード未設定なら True を返す。
    """
    
    # 1. パスワードの取得 (st.secrets 優先、なければ os.environ)
    correct_password = None
    
    # Streamlit CloudのSecretsを確認
    if "APP_PASSWORD" in st.secrets:
        correct_password = st.secrets["APP_PASSWORD"]
    # なければ環境変数を確認 (.env)
    elif "APP_PASSWORD" in os.environ:
        correct_password = os.environ.get("APP_PASSWORD")
        
    # パスワードが設定されていない場合は認証なしで通す
    if not correct_password:
        return True

    # 2. セッションステートでログイン状態を管理
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    # 3. パスワード入力画面
    st.markdown("### 🔒 Please login")
    input_password = st.text_input("Password", type="password", key="auth_input")
    
    if st.button("Log in"):
        if input_password == correct_password:
            st.session_state["password_correct"] = True
            st.rerun() # 再読み込みしてメイン画面へ
        else:
            st.error("❌ Password incorrect")
            
    # 認証完了までは False を返す
    return False