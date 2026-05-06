import pandas as pd

def check_rules(df, max_off_per_day=3):
    """
    對排班表進行精確規則檢核
    df: 寬表格
    max_off_per_day: 使用者設定的每日休假人數上限
    """
    if '姓名' in df.columns:
        df = df.set_index('姓名')
    
    # 轉換日期欄位
    date_cols = []
    for col in df.columns:
        try:
            pd.to_datetime(col)
            date_cols.append(col)
        except:
            continue
            
    date_objs = pd.to_datetime(date_cols)
    
    # 建立週次分組
    weeks = {}
    for d_str, d_obj in zip(date_cols, date_objs):
        iso = d_obj.isocalendar()
        week_id = f"{iso[0]}-W{iso[1]:02d}"
        if week_id not in weeks:
            weeks[week_id] = []
        weeks[week_id].append(d_str)

    errors_week_do = []    
    errors_day_limit = []  
    errors_consecutive = [] 

    # --- 檢核 (一) 每週 DO ≠ 2 ---
    for name in df.index:
        for week_id, week_dates in weeks.items():
            week_range = f"{week_dates[0]}~{week_dates[-1]}"
            # 統計該週 DO 的數量
            do_count = (df.loc[name, week_dates] == 'DO').sum()
            if do_count != 2:
                errors_week_do.append(f"- {name}：{week_id} ({week_range})，該週 DO = {do_count}")

    # --- 檢核 (二) 每日 AL+DO > 使用者設定的限制 ---
    for d in date_cols:
        # 使用 fillna('') 避免空值干擾
        off_count = df[d].fillna('').isin(['AL', 'DO']).sum()
        if off_count > max_off_per_day:
            errors_day_limit.append(f"- {d}：AL+DO 總計 {off_count} 人 (上限 {max_off_per_day} 人)")

    # --- 檢核 (三) 非 DO 連續天數 >= 6 ---
    for name in df.index:
        schedule = df.loc[name, date_cols].values
        consecutive_work = 0
        start_date = None
        
        for i, status in enumerate(schedule):
            if status != 'DO':
                if consecutive_work == 0:
                    start_date = date_cols[i]
                consecutive_work += 1
            else:
                if consecutive_work >= 6:
                    errors_consecutive.append(f"- {name}：區間({start_date} ~ {date_cols[i-1]})，連續工作 {consecutive_work} 天")
                consecutive_work = 0
        
        if consecutive_work >= 6:
            errors_consecutive.append(f"- {name}：區間({start_date} ~ {date_cols[-1]})，連續工作 {consecutive_work} 天")

    # 格式化輸出報告
    report = f"### 📋 系統精確檢核報告 (設定上限：{max_off_per_day} 人)\n\n"
    
    report += "#### （一）每週 DO ≠ 2 的人員\n"
    report += "\n".join(errors_week_do) if errors_week_do else "✅ 全員符合規範"
    report += "\n\n"

    report += f"#### （二）每日 AL+DO > {max_off_per_day} 的日期\n"
    report += "\n".join(errors_day_limit) if errors_day_limit else "✅ 全日期符合規範"
    report += "\n\n"

    report += "#### （三）非 DO 連續天數 >= 6 的人員及日期\n"
    report += "\n".join(errors_consecutive) if errors_consecutive else "✅ 全員符合勞基防線"
    
    return report
