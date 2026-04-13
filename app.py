import streamlit as st
import google.generativeai as genai
import pandas as pd

# 設定頁面
st.set_page_config(page_title="客服排班工具", layout="wide")
st.title("📅 客服中心排班助手")

# API 設定
with st.sidebar:
    api_key = st.text_input("請輸入 Gemini API Key", type="password")
    if api_key:
        genai.configure(api_key=api_key)

# 上傳檔案
uploaded_file = st.file_uploader("上傳專員名單 (Excel 或 CSV)", type=["csv", "xlsx"])

if uploaded_file:
    st.success("檔案上傳成功！")
    # 這裡先放個簡單的預覽
    df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)
    st.write(df.head())
