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
import json
import io

# ... 前方的初始化與配置保持不變 ...

def ask_ai_with_json(df, task_type, max_off):
    df_str = df.fillna("-").to_csv(index=False)
    
    # 強制要求 AI 輸出 JSON 格式，方便程式碼讀取
    prompt = f"""
    你是一位排班數據分析師。請處理以下 CSV 格式的班表：
    {df_str}
    
    任務：{task_type} (每日休假上限 {max_off} 人)。
    
    【輸出規範】
    請『僅』輸出一個 JSON 物件，格式如下：
    {{
      "analysis": "這裡填寫你的分析文字摘要",
      "updated_data": [ {{ "姓名": "...", "1": "休", "2": "上班", ... }}, ... ]
    }}
    不要包含 Markdown 代碼塊標籤，直接輸出 JSON 內容。
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={ "type": "json_object" }, # 強制輸出 JSON
        temperature=0.1
    )
    return json.loads(response.choices[0].message.content)

# --- UI 介面更新 ---

with tab1:
    st.subheader("1. 休假生成")
    file1 = st.file_uploader("上傳 Excel", type=['xlsx'], key="u1")
    if file1:
        df1 = pd.read_excel(file1)
        if st.button("開始 AI 生成"):
            with st.spinner("AI 處理中..."):
                result_json = ask_ai_with_json(df1, "填補休假", max_off)
                
                # 1. 顯示 AI 分析
                st.info(result_json['analysis'])
                
                # 2. 轉換回 DataFrame
                new_df = pd.DataFrame(result_json['updated_data'])
                st.write("生成結果預覽：")
                st.dataframe(new_df, use_container_width=True)
                
                # 3. 提供 Excel 下載
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    new_df.to_excel(writer, index=False)
                
                st.download_button(
                    label="📥 下載更新後的 Excel 班表",
                    data=output.getvalue(),
                    file_name="AI_Updated_Roster.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

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
