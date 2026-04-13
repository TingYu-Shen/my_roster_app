import streamlit as st
import pandas as pd
from openai import OpenAI

# 1. 初始化
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except:
    st.error("請在 Streamlit Secrets 中設定 OPENAI_API_KEY")

# --- 2. 核心 AI 函數 (在此段落加入規則) ---
def ask_ai_about_roster(df, task_type, max_off):
    # 資料清理：確保空值被視為上班，並轉為字串讓 AI 閱讀
    df_filled = df.fillna("上班")
    df_str = df_filled.to_markdown(index=False)
    
    # 這裡就是關鍵：根據不同的功能區塊，注入「每日最多 X 人」的指令
    if task_type == "休假生成":
        instruction = f"請填補空白處為『休』。規則：每日(縱向)總休假人數不可超過 {max_off} 人，且員工(橫向)需符合勞基法不連上6天。"
    elif task_type == "休假檢核":
        instruction = f"請檢查：1. 每日(縱向)是否有人數超過 {max_off} 人的日期？ 2. 員工(橫向)是否有連上超過 6 天的情況？"
    else:
        instruction = f"請參考休假表產出排班。每日(縱向)休假上限為 {max_off} 人。"

    prompt = f"""
    你是一位台灣客服中心排班專家。
    數據格式：橫向為日期(1-31)，縱向為員工姓名。內容『休』代表休假，『上班』代表出勤。
    
    【班表數據】
    {df_str}
    
    【你的任務】
    {instruction}
    
    請以專業、條列式的方式回覆結果。
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": "你是一個精確的數據分析師"},
                  {"role": "user", "content": prompt}],
        temperature=0.1
    )
    return response.choices[0].message.content

# --- 3. UI 介面 ---
st.title("🤖 AI 排班助理")

# 側邊欄加入參數控制
with st.sidebar:
    st.header("⚙️ 規則設定")
    # 將「3人」做成可調參數
    max_off = st.slider("每日最高休假人數上限", 1, 5, 3)
    st.info(f"當前設定：每天最多 {max_off} 人休假")

# 功能分頁
tab1, tab2, tab3 = st.tabs(["🏖️ 休假生成", "🔍 休假檢核", "⚡ 一鍵排班"])

with tab1:
    st.subheader("1. 休假生成")
    file1 = st.file_uploader("上傳預選休範本", type=['xlsx'], key="u1")
    if file1 and st.button("開始生成"):
        df1 = pd.read_excel(file1)
        # 調用函數時傳入 max_off
        result = ask_ai_about_roster(df1, "休假生成", max_off)
        st.markdown(result)

with tab2:
    st.subheader("2. 休假檢核")
    file2 = st.file_uploader("上傳待檢核班表", type=['xlsx'], key="u2")
    if file2 and st.button("執行檢核"):
        df2 = pd.read_excel(file2)
        # 調用函數時傳入 max_off
        result = ask_ai_about_roster(df2, "休假檢核", max_off)
        st.markdown(result)
