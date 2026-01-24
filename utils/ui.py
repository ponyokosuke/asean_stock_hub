import streamlit as st

# 国ごとの表示名設定
COUNTRY_NAMES = {
    "SG": "Singapore 🇸🇬",
    "MY": "Malaysia 🇲🇾",
    "VN": "Vietnam 🇻🇳",
    "ID": "Indonesia 🇮🇩",
    "TH": "Thailand 🇹🇭",
    "PH": "Philippines 🇵🇭"
}

def render_country_selector():
    """サイドバーに国選択メニューを表示し、選択された国コードを返す"""
    st.sidebar.header("Settings")
    
    # 選択肢の作成
    options = list(COUNTRY_NAMES.keys())
    
    # セッションステートがなければ初期化
    if "target_country" not in st.session_state:
        st.session_state["target_country"] = "SG"
    
    current_index = 0
    if st.session_state["target_country"] in options:
        current_index = options.index(st.session_state["target_country"])
    
    # ラジオボタン表示
    selected = st.sidebar.radio(
        "Target Country",
        options,
        index=current_index,
        format_func=lambda x: COUNTRY_NAMES[x]
    )
    
    # 保存して返す
    st.session_state["target_country"] = selected
    return selected