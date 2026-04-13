import streamlit as st
import pandas as pd
from openai import OpenAI
import io

# API 初始化
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except:
    st.error("請在 Streamlit Secrets 中設定 OPENAI_API_KEY")

# --- AI 核心處理函數 ---

def ask_ai_about_roster(df, task_description):
    # 將 DataFrame 的空值填充為 "勤"，明確告知 AI 狀態
    df_filled = df.fillna("勤")
    
    # 轉換成 Markdown 格式
    df_str = df_filled.to_markdown(index=False)
    
    prompt = f"""
    你是一位台灣客服中心的排班專家，熟悉《勞基法》與排班實務。
    以下是 2026 年 1 月的預選休假表（橫向為 1-31 日，縱向為員工）：
    
    {df_str}
    
    任務需求：{task_description}
    
    請以『條列式摘要』說明檢核結果，並在最後提供一個『建議修正後的表格』。
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": "你是一個嚴謹的排班數據分析師。"},
                  {"role": "user", "content": prompt}],
        temperature=0.1 # 調低隨機性，確保排班邏輯一致
    )
    return response.choices[0].message.content

# --- UI 邏輯調整 ---

st.title("📅 客服排班助理 - 第二階段")

tab1, tab2, tab3 = st.tabs(["🏖️ 休假生成", "🔍 休假檢核", "⚡ 一鍵排班"])

with tab1:
    st.subheader("1. 休假生成")
    file1 = st.file_uploader("上傳員工休假意願 (Excel/CSV)", type=['xlsx', 'csv'], key="u1")
    if file1:
        df1 = pd.read_excel(file1) if file1.name.endswith('xlsx') else pd.read_csv(file1)
        if st.button("AI 自動協調休假"):
            with st.spinner("正在協調人力與休假..."):
                task = "根據這份意願清單，產出一份完整的休假表。規則：每天至少保留 60% 的人力在線，若有衝突，請公平分配。"
                result = ask_ai_about_roster(df1, task)
                st.markdown(result)

with tab2:
    st.subheader("2. 休假檢核")
    file2 = st.file_uploader("上傳待檢核班表", type=['xlsx', 'csv'], key="u2")
    if file2:
        df2 = pd.read_excel(file2) if file2.name.endswith('xlsx') else pd.read_csv(file2)
        if st.button("執行 AI 合規檢核"):
            with st.spinner("正在掃描勞基法與排班規則..."):
                task = """檢查此班表是否符合以下規則：
                1. 員工不可連續工作超過 6 天。
                2. 每日早班至少要有 2 位資深人員。
                3. 若有違反，請明確列出姓名與日期。"""
                result = ask_ai_about_roster(df2, task)
                st.markdown(result)

with tab3:
    st.subheader("3. 一鍵排班")
    st.write("此功能將結合休假表與人力預估，生成正式班表。")
    # 此處邏輯類推...
