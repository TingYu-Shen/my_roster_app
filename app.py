import streamlit as st
import pandas as pd
from openai import OpenAI

# 頁面基本配置
st.set_page_config(page_title="AI 客服排班助理", layout="wide", page_icon="📅")

# 自定義 CSS 美化介面
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    </style>
    """, unsafe_allow_html=True)

# 側邊欄：功能選擇
with st.sidebar:
    st.title("🤖 排班助理系統")
    st.markdown("---")
    app_mode = st.radio(
        "請選擇核心功能：",
        ["1. 休假生成", "2. 休假檢核", "3. 一鍵排班"]
    )
    st.divider()
    st.info("💡 提示：請先在『系統設定』中配置 OpenAI API Key。")

# --- 功能區塊實作 ---

if app_mode == "1. 休假生成":
    st.header("🏖️ 休假生成器")
    st.write("上傳包含員工休假意願或初步假表的 Excel，AI 將協助產出完整休假班表。")
    
    uploaded_file = st.file_uploader("上傳 Excel (員工休假意願表)", type=["xlsx", "xls"])
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        st.write("預覽原始數據：")
        st.dataframe(df, use_container_width=True)
        
        if st.button("開始 AI 休假生成"):
            with st.spinner("AI 正在協調休假中..."):
                # 第二階段將在此串接 OpenAI Logic
                st.success("休假生成完畢！(測試版：目前僅為介面展示)")
                st.download_button("下載完整休假表", data="mock_data", file_name="vacation_plan.xlsx")

elif app_mode == "2. 休假檢核":
    st.header("🔍 休假合規檢核")
    st.write("依據產出的休假表，檢查是否符合勞基法或人力覆蓋率。")
    
    check_file = st.file_uploader("上傳完整休假表進行檢核", type=["xlsx", "xls"])
    if check_file:
        st.warning("正在掃描規則：1. 假日人力不得低於 5 人 2. 不可連續工作超過 6 天")
        if st.button("執行 AI 檢核"):
            # 這裡之後會放 AI 檢核邏輯
            st.error("檢核結果：發現 2 處異常（小明連上 7 天、週日人力不足）。")

elif app_mode == "3. 一鍵排班":
    st.header("⚡ 一鍵自動排班")
    st.write("根據最終確定的休假表與進線人力需求，生成正式班表。")
    
    col1, col2 = st.columns(2)
    with col1:
        v_file = st.file_uploader("步驟 A：上傳最終休假表", type=["xlsx"])
    with col2:
        d_file = st.file_uploader("步驟 B：上傳人力需求預測", type=["xlsx"])
        
    if v_file and d_file:
        if st.button("生成正式排班表"):
            st.info("AI 正在計算最佳排班組合...")
