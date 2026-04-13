import streamlit as st
import pandas as pd
from openai import OpenAI
import io

# 1. 初始化 OpenAI Client (新版語法)
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception as e:
    st.error("OpenAI API Key 未正確設定於 Secrets 中。")

# 頁面基本配置
st.set_page_config(page_title="AI 客服排班助理", layout="wide", page_icon="📅")

# --- 2. 核心 AI 處理函數 ---
def ask_ai_about_roster(df, task_type, max_off):
    # 資料清理：將空值轉為「-」方便 AI 閱讀，並轉為 Markdown 格式
    df_filled = df.fillna("-")
    df_str = df_filled.to_markdown(index=False)
    
    # 針對三個區塊設計不同的任務指令
    if task_type == "休假生成":
        instruction = f"請根據意願表填補空值為『休』。規則：每日(縱向日期欄)總休假人數不可超過 {max_off} 人，且需確保每位員工每月總休假天數大致平均。"
    elif task_type == "休假檢核":
        instruction = f"請檢查此班表：1. 每日(縱向)是否有日期超過 {max_off} 人休假？ 2. 員工(橫向)是否有人連續工作超過 6 天未安排休息？"
    else: # 一鍵排班
        instruction = f"根據已確認的休假表，為剩餘日期填入排班代碼(如:早、中、晚)。規則：每日休假上限 {max_off} 人，且每日各班次需有足夠人力。"

    try:
        # 新版 OpenAI API 呼叫方式
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "你是一位台灣客服中心排班專家，擅長處理 Excel 班表矩陣並嚴格執行規則。"},
                {"role": "user", "content": f"數據表格如下（橫向為日期，縱向為人員）：\n\n{df_str}\n\n任務需求：{instruction}\n請先給出分析結果，再提供更新後的表格。"}
            ],
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI 處理時發生錯誤：{str(e)}"

# --- 3. UI 介面實作 ---
st.title("🤖 AI 排班助理")

with st.sidebar:
    st.header("⚙️ 規則設定")
    max_off = st.slider("每日最高休假人數上限", 1, 5, 3)
    st.divider()
    st.info(f"💡 當前規則：每天最多 {max_off} 人休假")

tab1, tab2, tab3 = st.tabs(["🏖️ 休假生成", "🔍 休假檢核", "⚡ 一鍵排班"])

# 這裡以「休假生成」為例，其他區塊邏輯類推
with tab1:
    st.subheader("1. 休假生成")
    st.write("上傳主管預選休範本，由 AI 自動分配剩餘休假。")
    file1 = st.file_uploader("上傳 Excel (預選休範本)", type=['xlsx'], key="u1")
    
    if file1:
        df1 = pd.read_excel(file1)
        st.dataframe(df1.head(10), use_container_width=True) # 預覽前10筆
        
        if st.button("開始 AI 休假生成"):
            with st.spinner("AI 正在計算最佳休假組合..."):
                result = ask_ai_about_roster(df1, "休假生成", max_off)
                st.markdown("### AI 處理結果")
                st.markdown(result)

with tab2:
    st.subheader("2. 休假檢核")
    file2 = st.file_uploader("上傳完整班表進行檢核", type=['xlsx'], key="u2")
    if file2:
        df2 = pd.read_excel(file2)
        if st.button("執行 AI 合規檢核"):
            with st.spinner("正在掃描排班規則..."):
                result = ask_ai_about_roster(df2, "休假檢核", max_off)
                st.markdown(result)

with tab3:
    st.subheader("3. 一鍵排班")
    st.info("此功能會基於確定的休假表生成最終班表，建議於完成休假檢核後使用。")
    # 此處可加入類似 tab1 的實作
