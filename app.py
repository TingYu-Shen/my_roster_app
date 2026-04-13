import streamlit as st
import pandas as pd
from openai import OpenAI
import json
import io

# 1. 初始化與頁面配置
st.set_page_config(page_title="AI 客服排班助理", layout="wide", page_icon="📅")

# 從 Streamlit Secrets 讀取 API Key
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception as e:
    st.error("請確認 Streamlit Secrets 中已設定 OPENAI_API_KEY")

# 2. 核心處理函數：使用 JSON 模式確保數據穩定轉回 Excel
def process_roster_with_ai(df, task_type, max_off):
    # 將原始數據轉為 CSV 格式字串，節省 Token 並讓 AI 好讀
    csv_data = df.fillna("-").to_csv(index=False)
    
    # 根據不同功能設定指令
    if task_type == "休假生成":
        task_prompt = f"請填補空白處為『休』。規則：每日(縱向日期)總休假人數不可超過 {max_off} 人，且需考慮員工休假公平性。"
    elif task_type == "休假檢核":
        task_prompt = f"請檢核此班表。規則：1.每日(縱向)休假不可超過 {max_off} 人。 2.員工(橫向)不可連續工作超過 6 天。"
    else: # 一鍵排班
        task_prompt = f"參考已確認休假，填入排班代碼(早/中/晚)。規則：每日休假上限 {max_off} 人，並確保各班次人力充足。"

    system_msg = "你是一個精確的台灣客服中心排班分析師。你必須僅以 JSON 格式回覆。"
    user_msg = f"""
    請處理以下班表數據：
    {csv_data}

    任務：{task_prompt}

    【輸出規範】
    必須回傳 JSON 物件，格式如下：
    {{
      "analysis": "這裡填寫分析摘要與規則違反說明",
      "updated_data": [ {{ "姓名": "...", "1": "休", "2": "-", ... }}, ... ]
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            response_format={ "type": "json_object" },
            temperature=0.1
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"AI 處理失敗: {str(e)}")
        return None

# 3. UI 介面實作
st.title("🤖 AI 客服排班助理")
st.markdown("針對專案主管設計的自動化排班工具，支援休假協調、合規檢核與快速排班。")

with st.sidebar:
    st.header("⚙️ 規則設定")
    max_off = st.slider("每日最高休假人數上限", 1, 10, 3)
    st.divider()
    st.info(f"💡 目前設定：每天最多 {max_off} 人休假")

# 定義功能區塊
tab1, tab2, tab3 = st.tabs(["🏖️ 休假生成", "🔍 休假檢核", "⚡ 一鍵排班"])

# 區塊 1：休假生成
with tab1:
    st.subheader("1. 休假生成")
    u1 = st.file_uploader("上傳『預選休範本』Excel", type=['xlsx'], key="u1")
    if u1:
        df1 = pd.read_excel(u1)
        st.write("原始資料預覽：")
        st.dataframe(df1.head(5), use_container_width=True)
        
        if st.button("🚀 開始執行休假生成"):
            with st.spinner("AI 正在計算並協調假位..."):
                result = process_roster_with_ai(df1, "休假生成", max_off)
                if result:
                    st.success("處理完成！")
                    st.info(f"**AI 分析摘要：**\n{result['analysis']}")
                    
                    # 轉換數據回 Excel 供下載
                    new_df = pd.DataFrame(result['updated_data'])
                    st.dataframe(new_df, use_container_width=True)
                    
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        new_df.to_excel(writer, index=False)
                    
                    st.download_button(
                        label="📥 下載產出的休假表",
                        data=output.getvalue(),
                        file_name="AI_休假生成結果.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

# 區塊 2：休假檢核
with tab2:
    st.subheader("2. 休假檢核")
    u2 = st.file_uploader("上傳『完整休假表』進行檢核", type=['xlsx'], key="u2")
    if u2:
        df2 = pd.read_excel(u2)
        if st.button("🔍 執行合規檢查"):
            with st.spinner("正在掃描規則違反項..."):
                result = process_roster_with_ai(df2, "休假檢核", max_off)
                if result:
                    st.warning(f"**檢核報告：**\n{result['analysis']}")
                    st.write("檢核數據預覽：")
                    st.dataframe(pd.DataFrame(result['updated_data']), use_container_width=True)

# 區塊 3：一鍵排班
with tab3:
    st.subheader("3. 一鍵正式排班")
    st.info("請上傳已確定的休假表，AI 將填入早/中/晚班代碼。")
    u3 = st.file_uploader("上傳最終休假表", type=['xlsx'], key="u3")
    if u3:
        df3 = pd.read_excel(u3)
        if st.button("🪄 生成正式排班表"):
             with st.spinner("正在優化班次分配..."):
                result = process_roster_with_ai(df3, "正式排班", max_off)
                if result:
                    st.info(result['analysis'])
                    final_df = pd.DataFrame(result['updated_data'])
                    st.dataframe(final_df, use_container_width=True)
                    
                    # 下載邏輯同上...
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        final_df.to_excel(writer, index=False)
                    st.download_button("📥 下載正式班表", output.getvalue(), "Final_Roster.xlsx")
