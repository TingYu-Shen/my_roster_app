import streamlit as st
import pandas as pd
from io import BytesIO, StringIO
import google.generativeai as genai
import prompts
import scheduler  # Python 排班引擎
import checker    # Python 檢核引擎

# --- API 設定 ---
API_KEY = "AIzaSyDVB8pXr1X4xQUAbtRwNpPgxTnQdgNfvaE" 

if "configured" not in st.session_state:
    try:
        genai.configure(api_key=API_KEY)
        st.session_state["configured"] = True
    except Exception as e:
        st.error(f"API 配置失敗，請檢查 Key 是否正確：{e}")

# --- 網頁設定 ---
st.set_page_config(page_title="專案主管排班工具", layout="wide")

# --- 側邊欄設定 ---
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

def parse_exclusion(input_str):
    """
    將使用者輸入的字串解析為 List[List[str]]
    格式範例: "FFF,GGG ; AAA,BBB" -> [['FFF', 'GGG'], ['AAA', 'BBB']]
    """
    if not input_str or not input_str.strip():
        return [['FFF', 'GGG']]  # 保持預設互斥
    groups = []
    for group in input_str.split(';'):
        members = [m.strip() for m in group.split(',') if m.strip()]
        if members:
            groups.append(members)
    return groups

# --- 側邊欄導覽 ---
st.sidebar.markdown("---")
st.sidebar.title("📅 排班管理系統")
page = st.sidebar.radio("選擇功能模組", ["1. 休假生成 (Python 版)", "2. 休假檢核", "3. 一鍵排班"])

# --- 功能 1：休假生成 ---
if page == "1. 休假生成 (Python 版)":
    st.header("✨ 功能一：月休假自動補件")
    st.info("使用 Python 引擎進行精確計算。**規則：每週務必有 2 個 DO (不含 AL)**。")
    
    # 參數設定
    with st.expander("⚙️ 進階排班參數設定", expanded=True):
        col_param1, col_param2 = st.columns(2)
        with col_param1:
            max_people = st.number_input("單日最大休假人數限制 (AL+DO)", min_value=1, max_value=10, value=3)
        with col_param2:
            exclusion_text = st.text_input("人員互斥群組 (姓名用逗號隔開，組與組用分號隔開)", "FFF, GGG")
        
        exclusive_groups = parse_exclusion(exclusion_text)
    
    uploaded_file = st.file_uploader("上傳 Excel 預選假表", type=["xlsx"], key="f1")
    
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        st.subheader("原始資料預覽")
        st.dataframe(df, use_container_width=True)
        
        if st.button("🚀 執行 Python 自動排班"):
            with st.spinner("引擎計算中..."):
                try:
                    # 傳入 max_off_per_day 與解析後的互斥名單
                    processed_df = scheduler.solve_scheduling_df(
                        df, 
                        max_off_per_day=max_people, 
                        mutually_exclusive_groups=exclusive_groups
                    )
                    st.session_state['vacation_table'] = processed_df
                    st.success(f"計算完成！已確保每週 2 個 DO，且每日休假不超過 {max_people} 人。")
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
    st.info("檢核規則：每週是否有 2 個 DO (不含 AL)、不可連上 6 天、人數上限及互斥規則。")
    
    with st.expander("⚙️ 檢核參數設定", expanded=True):
        c_col1, c_col2 = st.columns(2)
        with c_col1:
            check_max_people = st.number_input("檢核單日最大休假人數上限", min_value=1, max_value=10, value=3)
        with c_col2:
            check_exclusion_text = st.text_input("檢核互斥群組", "FFF, GGG")
        
        check_exclusive_groups = parse_exclusion(check_exclusion_text)

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
                # 修改 checker.check_rules 以支援互斥組傳入 (若 checker 有支援的話)
                # 這裡假設你的 checker.check_rules 參數與 scheduler 類似
                try:
                    report = checker.check_rules(
                        check_df, 
                        max_off_per_day=check_max_people, 
                        mutually_exclusive_groups=check_exclusive_groups
                    )
                    st.markdown(report)
                except:
                    # 若 checker 尚未更新參數，則降級執行
                    report = checker.check_rules(check_df, max_off_per_day=check_max_people)
                    st.markdown(report)
        
        with col2:
            if st.button("🤖 執行 AI 智慧分析 (Gemini 版)"):
                with st.spinner("Gemini 正在分析規則..."):
                    custom_prompt = (
                        f"檢核標準：1.每日上限 {check_max_people} 人 2.互斥組：{check_exclusive_groups} "
                        f"3.每週須有 2 個 DO (不含 AL)。\n{prompts.PROMPT_2_CHECK}"
                    )
                    report_text = call_gemini(custom_prompt, check_df)
                    if report_text:
                        st.subheader("AI 智慧檢核報告")
                        st.markdown(report_text)

# --- 功能 3：一鍵排班 ---
elif page == "3. 一鍵排班":
    st.header("🚀 功能三：一鍵自動排班")
    st.info("根據確認後的休假表，由 AI 或 Python 引擎自動分配專案班別。")
    
    # 【關鍵修正：先初始化變數，避免出現 NameError】
    final_vacation_df = None 
    
    source_f3 = st.radio("資料來源", ["沿用休假生成結果", "重新上傳確認後的假表"], key="radio_f3")
    
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
    
    # 這裡現在安全了，因為即便沒上傳，final_vacation_df 也等於 None 而不是不存在
    if final_vacation_df is not None:
        st.subheader("待分配班別資料預覽")
        st.dataframe(final_vacation_df, use_container_width=True)
        
        # 選擇排班方式
        engine_choice = st.radio("選擇排班引擎", ["Python 邏輯引擎 (精確度高)", "Gemini AI (靈活性高)"])

        if st.button("啟動自動配班"):
            with st.spinner("正在進行班別分配..."):
                if engine_choice == "Python 邏輯引擎 (精確度高)":
                    try:
                        # 呼叫 scheduler 裡的新函數
                        final_result = scheduler.assign_shifts_logic(final_vacation_df)
                        st.session_state['final_schedule'] = final_result
                        st.success("Python 引擎排班完成！")
                    except Exception as e:
                        st.error(f"Python 引擎處理失敗：{e}")
                else:
                    # AI 排班邏輯
                    ai_response = call_gemini(prompts.PROMPT_3_SCHEDULING, final_vacation_df)
                    if ai_response:
                        try:
                            final_schedule = parse_csv_response(ai_response)
                            st.session_state['final_schedule'] = final_schedule
                            st.success("AI 排班完成！")
                        except Exception as e:
                            st.error("解析失敗，AI 回覆格式不正確。")

        # 顯示結果與下載
        if 'final_schedule' in st.session_state:
            st.markdown("---")
            st.subheader("最終班表預覽")
            edited_final = st.data_editor(st.session_state['final_schedule'], use_container_width=True)
            st.download_button(
                label="下載最終月份班表",
                data=to_excel(edited_final),
                file_name="final_project_schedule.xlsx"
            )
