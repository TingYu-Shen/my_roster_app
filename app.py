import streamlit as st
import pandas as pd
from io import BytesIO, StringIO
import google.generativeai as genai
from datetime import datetime
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
    if not input_str or not input_str.strip():
        return [['FFF', 'GGG']]
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
    
    with st.expander("⚙️ 進階排班參數設定", expanded=True):
        col_param1, col_param2 = st.columns(2)
        with col_param1:
            max_people = st.number_input("單日最大休假人數限制 (AL+DO)", min_value=1, max_value=10, value=3)
        with col_param2:
            exclusion_text = st.text_input("人員互斥群組 (姓名用逗號隔開，組與組用分號隔開)", "HHH, III")
        
        exclusive_groups = parse_exclusion(exclusion_text)
    
    uploaded_file = st.file_uploader("上傳 Excel 預選假表", type=["xlsx"], key="f1")
    
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        st.subheader("原始資料預覽")
        st.dataframe(df, use_container_width=True)
        
        if st.button("🚀 執行 Python 自動排班"):
            with st.spinner("引擎計算中..."):
                try:
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
            check_exclusion_text = st.text_input("檢核互斥群組", "HHH, III")
        
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
                try:
                    report = checker.check_rules(
                        check_df, 
                        max_off_per_day=check_max_people, 
                        mutually_exclusive_groups=check_exclusive_groups
                    )
                    st.markdown(report)
                except:
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
    st.info("根據確認後的休假表，由 Python 引擎自動分配專案班別，並同時符合最少與最多人數限制。")

    with st.expander("🛠️ 班別需求與員工權限自定義", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**1. 班別人數需求設定 (必填)**")
            
            # 最低需求輸入
            st.caption("🔹 設定各班別每日【最低】人數 (格式：班別:人數)")
            default_min_demand = "A08:1\nA09:1\nA10:1\nA12:1\nA14:1\nA23:1"
            min_demand_input = st.text_area("最低需求清單", value=default_min_demand, height=100)
            
            # 新增：最高上限輸入
            st.caption("🔸 設定各班別每日【最高】上限 (格式：班別:人數)")
            default_max_demand = "A23:1\nA08:2" 
            max_demand_input = st.text_area("最高上限清單 (不填則無限制)", value=default_max_demand, height=100)
            
            target_total = st.number_input("關鍵班每日總需求人數 (Total)", min_value=1, value=6)
        
        with col2:
            st.markdown("**2. 員工技能/權限與【排班優先序】**")
            st.caption("💡 這裡的人員順序越前面，越優先分配關鍵班別")
            default_caps = (
                "AAA:A12,A14\n"
                "BBB:A14,A12\n"
                "CCC:A12,A10\n"
                "DDD:A08\n"
                "EEE:A09,A08,A10\n"
                "FFF:A10,A12,A14\n"
                "GGG:A09,A10\n"
                "HHH:A23,A21\n"
                "III:A23,A21"
            )
            caps_text = st.text_area("人員權限設定 (依序排列)", value=default_caps, height=265)

    final_vacation_df = None 
    source_f3 = st.radio("資料來源", ["沿用休假生成結果", "重新上傳確認後的假表"], key="radio_f3", horizontal=True)
    
    if source_f3 == "沿用休假生成結果":
        if 'vacation_table' in st.session_state:
            final_vacation_df = st.session_state['vacation_table'].copy()
        else:
            st.warning("目前暫無暫存資料，請先執行「功能一」或選擇「重新上傳」。")
    else:
        uploaded_file = st.file_uploader("上傳最終確認休假表", type=["xlsx"], key="f3")
        if uploaded_file:
            final_vacation_df = pd.read_excel(uploaded_file)
    
    if final_vacation_df is not None:
        st.subheader("待分配班別資料預覽")
        st.dataframe(final_vacation_df, use_container_width=True)
        
        engine_choice = st.radio("選擇排班引擎", ["Python 邏輯引擎 (精確度高)", "Gemini AI (靈活性高)"], horizontal=True)

        if st.button("啟動自動配班", type="primary"):
            with st.spinner("正在進行分配..."):
                if engine_choice == "Python 邏輯引擎 (精確度高)":
                    try:
                        # 1. 解析需求配置 (包含 Min 與 Max)
                        min_demand_dict = {line.split(":")[0].strip(): int(line.split(":")[1].strip()) 
                                         for line in min_demand_input.split('\n') if ":" in line}
                        
                        max_demand_dict = {line.split(":")[0].strip(): int(line.split(":")[1].strip()) 
                                         for line in max_demand_input.split('\n') if ":" in line}
                        
                        st.session_state['demand_config'] = {
                            "min_demand": min_demand_dict, 
                            "max_demand": max_demand_dict,
                            "total_priority_target": target_total
                        }
                        
                        # 2. 解析員工權限
                        current_staff_caps = {}
                        staff_order = []
                        for line in caps_text.split('\n'):
                            if ":" in line:
                                name, shifts = line.split(":")
                                name = name.strip()
                                current_staff_caps[name] = [s.strip() for s in shifts.split(",")]
                                staff_order.append(name)
                        st.session_state['staff_caps'] = current_staff_caps
                        
                        # 3. 排序與準備資料
                        name_col = '姓名' if '姓名' in final_vacation_df.columns else 'Name'
                        final_vacation_df[name_col] = pd.Categorical(final_vacation_df[name_col], categories=staff_order, ordered=True)
                        final_vacation_df = final_vacation_df.sort_values(name_col).reset_index(drop=True)
                        
                        # 4. 執行配班 (調用新版支援上限邏輯的 v4 引擎)
                        from scheduler import assign_shifts_logic_v4
                        final_result = assign_shifts_logic_v4(
                            final_vacation_df, 
                            st.session_state['staff_caps'], 
                            st.session_state['demand_config']
                        )
                        st.session_state['final_schedule'] = final_result
                        st.success("✅ 已根據人數下限與上限完成自動配班！")
                        st.dataframe(final_result, use_container_width=True)
                        
                    except Exception as e:
                        st.error(f"❌ 處理失敗：{e}")

# --- 第四步驟：結果顯示與優化區塊 ---
        if 'final_schedule' in st.session_state:
            st.markdown("---")
            st.subheader("📍 第一階段：原始配班結果")
            st.info("這是根據需求人數與員工權限初步分配的結果。")
            
            # 1. 顯示原始配班結果 (不帶顏色)
            st.dataframe(st.session_state['final_schedule'], use_container_width=True)
            
            # 2. 順班優化按鈕區
            st.markdown("### 🪄 第二階段：順班優化調整")
            col_opt1, col_opt2 = st.columns([1, 3])
            
            with col_opt1:
                run_smooth = st.button("🚀 執行順班優化", type="secondary")
            
            if run_smooth:
                if 'staff_caps' in st.session_state:
                    with st.spinner("優化中..."):
                        from scheduler import smooth_shifts_v4
                        # 執行優化，取得優化後的 DF 與 變動標記
                        optimized_df, change_mask = smooth_shifts_v4(
                            st.session_state['final_schedule'], 
                            st.session_state['staff_caps']
                        )
                        # 將優化後的結果存入另一個 state，避免覆蓋掉原始結果以便對照
                        st.session_state['optimized_schedule'] = optimized_df
                        st.session_state['change_mask'] = change_mask
                        st.success("優化完成！請查看下方對照結果。")
                else:
                    st.error("找不到權限設定，請重新執行初步配班。")

            # 3. 如果有優化結果，則顯示優化後的區塊
            if 'optimized_schedule' in st.session_state:
                st.markdown("---")
                st.subheader("✨ 順班優化結果 (對照表)")
                st.caption("橘色背景：代表為了順班(同班次優先或由早到晚)而進行過人員對調的班次。")
                
                opt_df = st.session_state['optimized_schedule']
                mask_df = st.session_state['change_mask']

                # 定義上色函數
                def style_optimized(data):
                    style_matrix = pd.DataFrame('', index=data.index, columns=data.columns)
                    for col in data.columns:
                        if col in mask_df.columns:
                            style_matrix[col] = mask_df[col].apply(
                                lambda x: 'background-color: #FFB366; color: black; font-weight: bold;' if x is True else ''
                            )
                    return style_matrix

                # 顯示優化後的表格
                st.dataframe(opt_df.style.apply(style_optimized, axis=None), use_container_width=True)
                
                # 提供優化後的版本下載
                st.download_button(
                    label="📥 下載優化後的最終班表 (Excel)",
                    data=to_excel(opt_df),
                    file_name=f"optimized_schedule_{datetime.now().strftime('%m%d')}.xlsx",
                    key="download_opt"
                )
