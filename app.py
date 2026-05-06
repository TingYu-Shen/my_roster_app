import streamlit as st
import pandas as pd
from io import BytesIO, StringIO
import google.generativeai as genai
import prompts
import scheduler  # Python 排班引擎
import checker    # Python 檢核引擎

# --- API 設定 ---
# 從 secrets.toml 檔案中自動讀取金鑰
my_key = st.secrets["GEMINI_API_KEY"]

if "configured" not in st.session_state:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        st.session_state["configured"] = True
    except Exception as e:
        st.error(f"API 配置失敗，請檢查 Key 是否正確：{e}")

# --- 網頁設定 ---
st.set_page_config(page_title="專案主管排班工具", layout="wide")

# --- 側邊欄設定 (更新為你指定的最新模型路徑) ---
model_map = {
    "Gemini 3.1 Pro (最新預覽)": "models/gemini-3.1-pro-preview",
    "Gemini 3.1 Flash Lite (極速預覽)": "models/gemini-3.1-flash-lite-preview",
    "Gemini 3.0 Pro (進階預覽)": "models/gemini-3-pro-preview",
    "Gemini 3.0 Flash (平衡預覽)": "models/gemini-3-flash-preview",
    "Gemini 2.5 Flash Lite (效能優化)": "models/gemini-2.5-flash-lite",
    "Gemini 1.5 Pro (穩定備援)": "models/gemini-1.5-pro",
    "Gemini 1.5 Flash (極速備援)": "models/gemini-1.5-flash"
}

st.sidebar.title("🤖 AI 模型設定")
model_option = st.sidebar.selectbox("選擇使用 Model", list(model_map.keys()))

# --- 共用函數 ---
def call_gemini(prompt_text, data_df):
    """
    統一呼叫 Gemini 的入口
    """
    try:
        model = genai.GenerativeModel(model_map[model_option])
        input_csv = data_df.to_csv(index=False)
        full_prompt = f"{prompt_text}\n\n原始資料（CSV格式）：\n{input_csv}"
        
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        st.error(f"AI 處理失敗：{str(e)}")
        return None

def parse_csv_response(text):
    clean_text = text.replace("```csv", "").replace("```", "").strip()
    return pd.read_csv(StringIO(clean_text))

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# --- 側邊欄導覽 ---
st.sidebar.markdown("---")
st.sidebar.title("📅 排班管理系統")
page = st.sidebar.radio("選擇功能模組", ["1. 休假生成 (Python 版)", "2. 休假檢核", "3. 一鍵排班"])

# --- 功能 1：休假生成 ---
if page == "1. 休假生成 (Python 版)":
    st.header("✨ 功能一：月休假自動補件")
    st.info("使用 Python 引擎進行精確計算，自動補齊每週 2 天休假 (DO)。")
    
    # 參數設定
    with st.expander("⚙️ 進階排班參數設定", expanded=True):
        max_people = st.number_input("單日最大休假人數限制 (AL+DO)", min_value=1, max_value=10, value=3)
    
    uploaded_file = st.file_uploader("上傳 Excel 預選假表", type=["xlsx"], key="f1")
    
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        st.subheader("原始資料預覽")
        st.dataframe(df, use_container_width=True)
        
        if st.button("🚀 執行 Python 自動排班"):
            with st.spinner("引擎計算中..."):
                try:
                    # 調用 scheduler 並傳入自定義人數限制
                    processed_df = scheduler.solve_scheduling_df(df, max_off_per_day=max_people)
                    st.session_state['vacation_table'] = processed_df
                    st.success(f"計算完成！已確保每日休假不超過 {max_people} 人。")
                except Exception as e:
                    st.error(f"程式計算出錯：{e}")
        
        if 'vacation_table' in st.session_state:
            st.subheader("生成結果 (可直接於下方微調)")
            edited_df = st.data_editor(st.session_state['vacation_table'], use_container_width=True)
            st.download_button(
                "下載結果 Excel", 
                data=to_excel(edited_df), 
                file_name="monthly_vacation_plan.xlsx"
            )

# --- 功能 2：休假檢核 ---
elif page == "2. 休假檢核":
    st.header("🔍 功能二：休假合法性檢核")
    st.info("透過 Python 引擎進行 100% 精確檢核，亦可搭配 AI 進行智慧分析。")
    
    # 參數設定
    with st.expander("⚙️ 檢核參數設定", expanded=True):
        check_max_people = st.number_input("檢核單日最大休假人數上限", min_value=1, max_value=10, value=3, key="check_max")

    source = st.radio("資料來源", ["沿用前一功能結果", "重新上傳 Excel"])
    
    check_df = None
    if source == "沿用前一功能結果":
        if 'vacation_table' in st.session_state:
            check_df = st.session_state['vacation_table']
        else:
            st.warning("目前暫無暫存資料，請先執行功能一或選擇重新上傳。")
    else:
        uploaded_file = st.file_uploader("上傳待檢核 Excel", type=["xlsx"], key="f2")
        if uploaded_file:
            check_df = pd.read_excel(uploaded_file)

    if check_df is not None:
        st.subheader("待檢核資料預覽")
        st.dataframe(check_df, use_container_width=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🚀 執行系統精確檢核 (Python 版)"):
                # 調用 checker 並傳入使用者設定的人數上限
                report = checker.check_rules(check_df, max_off_per_day=check_max_people)
                st.markdown(report)
        
        with col2:
            if st.button("🤖 執行 AI 智慧分析 (Gemini 版)"):
                with st.spinner("Gemini 正在分析規則..."):
                    # 將自定義人數限制加入 Prompt
                    custom_prompt = f"請以「每日休假上限 {check_max_people} 人」為準進行檢核。\n{prompts.PROMPT_2_CHECK}"
                    report_text = call_gemini(custom_prompt, check_df)
                    if report_text:
                        st.subheader("AI 智慧檢核報告")
                        st.markdown(report_text)

# --- 功能 3：一鍵排班 ---
elif page == "3. 一鍵排班":
    st.header("🚀 功能三：一鍵自動排班")
    st.info("根據確認後的休假表，由 AI 自動分配專案班別。")
    
    # 新增：選擇資料來源
    source_f3 = st.radio("資料來源", ["沿用休假生成結果", "重新上傳確認後的假表"], key="radio_f3")
    
    final_vacation_df = None
    
    if source_f3 == "沿用休假生成結果":
        if 'vacation_table' in st.session_state:
            final_vacation_df = st.session_state['vacation_table']
            st.success("已成功沿用前一階段的休假資料。")
        else:
            st.warning("目前暫無暫存資料，請先執行「功能一」或選擇「重新上傳」。")
    else:
        uploaded_file = st.file_uploader("上傳最終確認休假表", type=["xlsx"], key="f3")
        if uploaded_file:
            final_vacation_df = pd.read_excel(uploaded_file)
    
    # 確保有資料才顯示後續按鈕
    if final_vacation_df is not None:
        st.subheader("待分配班別資料預覽")
        st.dataframe(final_vacation_df, use_container_width=True)
        
        if st.button("啟動 AI 自動配班"):
            with st.spinner("Gemini 正在媒合專案與人員..."):
                # 調用 call_gemini 進行配班
                ai_response = call_gemini(prompts.PROMPT_3_SCHEDULING, final_vacation_df)
                if ai_response:
                    try:
                        final_schedule = parse_csv_response(ai_response)
                        st.session_state['final_schedule'] = final_schedule
                        st.success("班表排定完成！")
                    except Exception as e:
                        st.error(f"解析失敗，可能是 AI 回覆格式不正確。")
                        st.text_area("AI 原始回覆內容", ai_response, height=200)
        
        # 顯示結果與下載按鈕
        if 'final_schedule' in st.session_state:
            st.markdown("---")
            st.subheader("最終班表預覽")
            edited_final = st.data_editor(st.session_state['final_schedule'], use_container_width=True)
            st.download_button(
                label="下載最終月份班表",
                data=to_excel(edited_final),
                file_name="final_project_schedule.xlsx"
            )
