import pandas as pd
import itertools
from datetime import datetime

# --- 功能一：自動補假邏輯 (原本的 solve_scheduling_df) ---

def solve_scheduling_df(df, max_off_per_day=3, mutually_exclusive_groups=None):
    """
    確保每人每周務必補滿 2 個 DO (不包含/不扣除 AL)。
    """
    if mutually_exclusive_groups is None:
        mutually_exclusive_groups = [['FFF', 'GGG']]

    if '姓名' in df.columns:
        df = df.set_index('姓名')

    df = df.astype(object)

    # 1. 提取並排序日期
    date_cols = []
    for col in df.columns:
        try:
            pd.to_datetime(col)
            date_cols.append(col)
        except:
            continue

    if not date_cols:
        return df.reset_index()

    temp_date_map = {col: pd.to_datetime(col) for col in date_cols}
    date_cols_sorted = sorted(date_cols, key=lambda x: temp_date_map[x])
    
    # 2. 按 ISO 周分組
    weeks = {}
    for original_col in date_cols_sorted:
        d_obj = temp_date_map[original_col]
        iso = d_obj.isocalendar()
        week_id = f"{iso[0]}-W{iso[1]:02d}"
        if week_id not in weeks:
            weeks[week_id] = []
        weeks[week_id].append(original_col)

    result_df_wide = df.copy()
    names = result_df_wide.index.tolist()

    for name in names:
        streak = 0 
        for week_id, week_dates in weeks.items():
            current_vals = result_df_wide.loc[name, week_dates].fillna('')
            existing_dos = [d for d in week_dates if str(current_vals[d]).strip() == 'DO']
            needed = max(0, 2 - len(existing_dos))
            
            all_empty_dates = [d for d in week_dates if pd.isna(result_df_wide.loc[name, d]) or str(result_df_wide.loc[name, d]).strip() == '']
            placed_combination = None

            # 第一階段：嘗試滿足所有限制
            strict_avail = []
            for d in all_empty_dates:
                if result_df_wide[d].fillna('').isin(['AL', 'DO']).sum() >= max_off_per_day:
                    continue
                conflict = False
                for group in mutually_exclusive_groups:
                    if name in group:
                        for other in group:
                            if other != name and other in result_df_wide.index:
                                if str(result_df_wide.loc[other, d]).strip() in ['AL', 'DO']:
                                    conflict = True; break
                    if conflict: break
                if not conflict:
                    strict_avail.append(d)

            for n in range(needed, len(all_empty_dates) + 1):
                combos = list(itertools.combinations(strict_avail, n))
                best = find_best_valid_streak_combo(combos, streak, week_dates, result_df_wide, name)
                if best is not None:
                    placed_combination = best
                    break
            
            # 第二階段：強制保底
            if placed_combination is None and needed > 0:
                for n in range(needed, len(all_empty_dates) + 1):
                    combos = list(itertools.combinations(all_empty_dates, n))
                    best = find_best_valid_streak_combo(combos, streak, week_dates, result_df_wide, name)
                    if best is not None:
                        placed_combination = best
                        break

            if placed_combination is not None:
                for d in placed_combination:
                    result_df_wide.at[name, d] = 'DO'
            
            for d in week_dates:
                val = result_df_wide.loc[name, d]
                if pd.notna(val) and str(val).strip() in ['AL', 'DO']:
                    streak = 0
                else:
                    streak += 1

    return result_df_wide.reset_index()

def find_best_valid_streak_combo(combos, start_streak, week_dates, df, name):
    best_c = None
    min_total_off = float('inf')
    for combo in combos:
        temp_streak = start_streak
        is_valid = True
        for d in week_dates:
            is_off = (str(df.loc[name, d]).strip() in ['AL', 'DO']) or (d in combo)
            if is_off:
                temp_streak = 0
            else:
                temp_streak += 1
                if temp_streak > 5:
                    is_valid = False; break
        if is_valid:
            score = sum(df[d].fillna('').isin(['AL', 'DO']).sum() for d in combo)
            if score < min_total_off:
                min_total_off = score
                best_c = combo
    return best_c


# --- 功能三：班別分配引擎 (Python 版 PROMPT 轉化) ---

def assign_shifts_logic(df):
    """
    優化版班別分配引擎
    策略：先計算當天哪些人是空白，優先分配 Priority 班別給前 4 名可用員工，
    其餘員工分配 Secondary 班別。
    """
    if '姓名' in df.columns:
        df = df.set_index('姓名')
    elif 'Name' in df.columns:
        df = df.set_index('Name')

    new_df = df.copy().astype(object)
    
    staff_group_1 = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    staff_group_2 = ["FFF", "GGG"]
    
    priority_shifts = ["A08", "A12", "A14", "A23"]
    secondary_shifts = ["A09", "A10", "A21"]

    for date in new_df.columns:
        # 1. 找出當天哪些人需要排班（目前是空白的）
        need_shift_names = []
        for name in new_df.index:
            val = str(new_df.at[name, date]).strip()
            if val in ["", "nan", "None"] or pd.isna(new_df.at[name, date]):
                need_shift_names.append(name)
        
        # 2. 計算當天「已經固定」的 Priority 班別 (例如原本 Excel 就填好的)
        current_vals = new_df[date].fillna('').tolist()
        existing_priority_count = sum(1 for v in current_vals if v in priority_shifts)
        
        # 3. 追蹤當天已被使用的具體班別
        used_shifts_today = [v for v in current_vals if v != '']

        # 4. 開始分配
        assigned_priority_count = existing_priority_count
        
        for name in need_shift_names:
            # 取得該員工的可用班別池
            if name in staff_group_1:
                my_priority = ["A08", "A12", "A14"]
                my_secondary = ["A09", "A10"]
            elif name in staff_group_2:
                my_priority = ["A23"]
                my_secondary = ["A21"]
            else:
                continue

            # 決定要從哪個池子選班
            # 如果 Priority 班還沒滿 4 個，優先從 Priority 池選
            choices = []
            if assigned_priority_count < 4:
                choices = [s for s in my_priority if s not in used_shifts_today]
                
            # 如果 Priority 池沒班了，或者已經滿 4 人，則從 Secondary 池選
            if not choices:
                choices = [s for s in my_secondary if s not in used_shifts_today]

            # 執行填入
            if choices:
                pick = choices[0]
                new_df.at[name, date] = pick
                used_shifts_today.append(pick)
                if pick in priority_shifts:
                    assigned_priority_count += 1

    return new_df.reset_index()
