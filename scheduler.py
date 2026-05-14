import pandas as pd
import itertools
from datetime import datetime
from collections import Counter

# --- 功能一：自動補假邏輯 ---
def get_updated_streak(current_streak, name, week_dates, df):
    s = current_streak
    for d in week_dates:
        val = str(df.loc[name, d]).strip().upper()
        if val in ['AL', 'DO', 'OFF']: # 增加 OFF 判定
            s = 0
        else:
            s += 1
    return s

def find_best_valid_streak_combo(combos, start_streak, week_dates, df, name):
    best_c = None
    min_total_off = float('inf')
    for combo in combos:
        temp_streak = start_streak
        is_valid = True
        for d in week_dates:
            original_val = str(df.loc[name, d]).strip().upper()
            # 修正判定：只要不是空的，且標記為假，就重置 streak
            is_off = (original_val in ['AL', 'DO', 'OFF']) or (d in combo)
            if is_off:
                temp_streak = 0
            else:
                temp_streak += 1
                if temp_streak > 5:
                    is_valid = False
                    break
        if is_valid:
            score = sum(df[d].astype(str).str.strip().str.upper().isin(['AL', 'DO']).sum() for d in combo)
            if score < min_total_off:
                min_total_off = score
                best_c = combo
    return best_c

def solve_scheduling_df(df, max_off_per_day=3, mutually_exclusive_groups=None):
    if mutually_exclusive_groups is None:
        mutually_exclusive_groups = [['HHH', 'III']]

    if '姓名' in df.columns:
        df = df.set_index('姓名')

    # 轉為字串物件避免 NaN 判定錯誤
    df = df.astype(object)

    # 1. 精準日期提取
    date_cols = [col for col in df.columns if not pd.isna(pd.to_datetime(col, errors='coerce'))]
    if not date_cols:
        print("錯誤：找不到有效的日期欄位")
        return df.reset_index()

    date_cols_sorted = sorted(date_cols, key=lambda x: pd.to_datetime(x))
    
    # 2. 週分組
    weeks = {}
    for original_col in date_cols_sorted:
        iso = pd.to_datetime(original_col).isocalendar()
        week_id = f"{iso[0]}-W{iso[1]:02d}"
        weeks.setdefault(week_id, []).append(original_col)

    result_df_wide = df.copy()
    
    for name in result_df_wide.index:
        streak = 0
        for week_id in sorted(weeks.keys()):
            week_dates = weeks[week_id]
            
            # 統計現有 DO (忽略大小寫與空格)
            current_vals = result_df_wide.loc[name, week_dates].astype(str).str.strip().str.upper()
            existing_dos = [d for d in week_dates if current_vals[d] == 'DO']
            
            needed = 2 - len(existing_dos)
            
            if needed <= 0:
                streak = get_updated_streak(streak, name, week_dates, result_df_wide)
                continue

            # 關鍵修改：更寬鬆的空白格判定
            all_empty_dates = []
            for d in week_dates:
                val = str(result_df_wide.loc[name, d]).strip().upper()
                # 判定為「可補假」的空格：NaN, 空字串, 或是不含 AL/DO 的其他標記
                if val in ['NAN', '', 'NONE', '0', '0.0']:
                    all_empty_dates.append(d)

            placed_combination = None

            # 階段 1 & 2 邏輯
            strict_avail = []
            for d in all_empty_dates:
                daily_off_count = result_df_wide[d].astype(str).str.strip().str.upper().isin(['AL', 'DO']).sum()
                if daily_off_count < max_off_per_day:
                    strict_avail.append(d)

            if len(strict_avail) >= needed:
                combos = list(itertools.combinations(strict_avail, needed))
                placed_combination = find_best_valid_streak_combo(combos, streak, week_dates, result_df_wide, name)
            
            if placed_combination is None and len(all_empty_dates) >= needed:
                combos = list(itertools.combinations(all_empty_dates, needed))
                placed_combination = find_best_valid_streak_combo(combos, streak, week_dates, result_df_wide, name)

            if placed_combination:
                for d in placed_combination:
                    result_df_wide.at[name, d] = 'DO'
            
            streak = get_updated_streak(streak, name, week_dates, result_df_wide)

    return result_df_wide.reset_index()

# --- 功能三：班別分配引擎 ---
def assign_shifts_logic_v4(df, staff_capabilities, demand_config):
    new_df = df.copy().astype(object)
    name_col = '姓名' if '姓名' in df.columns else 'Name'
    if name_col in new_df.columns:
        new_df = new_df.set_index(name_col)

    # 讀取配置
    min_demand = demand_config.get("min_demand", {})
    max_demand = demand_config.get("max_demand", {})  # 新增：上限設定
    total_priority_target = demand_config.get("total_priority_target", 0)
    priority_shifts = list(min_demand.keys())

    for date in new_df.columns:
        # 找出當天需要排班的人員
        need_shift_names = [
            name for name in new_df.index 
            if str(new_df.at[name, date]).strip() in ["", "nan", "None"] or pd.isna(new_df.at[name, date])
        ]
        
        # 統計當天已存在的班別次數
        used_shifts_today = [str(v).strip() for v in new_df[date].fillna('') if str(v).strip() != '']
        shift_counts = Counter(used_shifts_today)

        for name in need_shift_names:
            if name not in staff_capabilities:
                continue
            
            my_caps = staff_capabilities[name]
            pick = None

            # --- 策略 1：優先滿足「最小需求 (Min Demand)」 ---
            # 條件：我有這項能力、該班別還沒達標、且「尚未達到上限」
            for s, required_n in min_demand.items():
                current_count = shift_counts[s]
                limit_n = max_demand.get(s, float('inf')) # 若沒設上限則視為無限
                
                if s in my_caps and current_count < required_n and current_count < limit_n:
                    pick = s
                    break 
            
            # --- 策略 2：滿足總體優先目標 (Priority Target) ---
            if not pick:
                current_total_priority = sum(shift_counts[s] for s in priority_shifts)
                if current_total_priority < total_priority_target:
                    # 篩選出具備優先班別能力，且該班別尚未達到上限的人
                    potential_priority = [
                        s for s in my_caps 
                        if s in priority_shifts and shift_counts[s] < max_demand.get(s, float('inf'))
                    ]
                    if potential_priority:
                        pick = potential_priority[0]

            # --- 策略 3：一般分配 ---
            if not pick:
                # 排除掉當天已達上限的班別
                potential_others = [
                    s for s in my_caps 
                    if shift_counts[s] < max_demand.get(s, float('inf'))
                ]
                
                if potential_others:
                    # 盡量選今天還沒出現過的班別（增加多樣性），但仍需符合上限
                    not_used_yet = [s for s in potential_others if s not in used_shifts_today]
                    pick = not_used_yet[0] if not_used_yet else potential_others[0]

            # 最終寫入
            if pick:
                new_df.at[name, date] = pick
                used_shifts_today.append(pick)
                shift_counts[pick] += 1

    return new_df.reset_index()


# --- 功能四：順班優化邏輯 ---

def smooth_shifts_v4(df, staff_capabilities):
    """
    進行班別順向調整：
    1. 同班次優先 (解決 A-B-A 孤島問題)
    2. 由早到晚排序 (避免 晚-早 跳班)
    回傳: (優化後的DF, 變動標記Mask)
    """
    optimized_df = df.copy()
    name_col = '姓名' if '姓名' in optimized_df.columns else 'Name'
    if name_col in optimized_df.columns:
        optimized_df = optimized_df.set_index(name_col)
    
    # 建立一個與班表同形狀的布林矩陣，記錄哪些儲存格被改動過
    changed_mask = pd.DataFrame(False, index=optimized_df.index, columns=optimized_df.columns)
    
    # 定義班別早晚順序
    shift_order = ['A08', 'A09', 'A10', 'A12', 'A14', 'A21', 'A23']
    order_map = {s: i for i, s in enumerate(shift_order)}
    
    # 取得日期欄位並排序
    date_cols = [col for col in optimized_df.columns if col not in ['姓名', 'Name', '員工編號']]
    try:
        date_cols = sorted(date_cols, key=lambda x: pd.to_datetime(x))
    except:
        pass

    # 執行兩次掃描以確保優化徹底
    for _ in range(2):
        # 規則 1：同班次優先 (孤島處理 A12-A08-A12 -> A12-A12-A12)
        for i in range(len(date_cols) - 2):
            d1, d2, d3 = date_cols[i], date_cols[i+1], date_cols[i+2]
            
            for name in optimized_df.index:
                s1, s2, s3 = str(optimized_df.at[name, d1]), str(optimized_df.at[name, d2]), str(optimized_df.at[name, d3])
                
                if s1 == s3 and s1 != s2 and s1 in shift_order and s2 in shift_order:
                    for other_name in optimized_df.index:
                        if other_name == name: continue
                        
                        other_s2 = str(optimized_df.at[other_name, d2])
                        if other_s2 == s1:
                            if s2 in staff_capabilities.get(other_name, []):
                                # 執行互換
                                optimized_df.at[name, d2] = s1
                                optimized_df.at[other_name, d2] = s2
                                # 記錄變動位置
                                changed_mask.at[name, d2] = True
                                changed_mask.at[other_name, d2] = True
                                break

        # 規則 2：由早到晚 (避免晚接早)
        for i in range(len(date_cols) - 1):
            d1, d2 = date_cols[i], date_cols[i+1]
            for name in optimized_df.index:
                s1, s2 = str(optimized_df.at[name, d1]), str(optimized_df.at[name, d2])
                
                if s1 in order_map and s2 in order_map:
                    if order_map[s1] > order_map[s2]:
                        for other_name in optimized_df.index:
                            if other_name == name: continue
                            
                            other_s2 = str(optimized_df.at[other_name, d2])
                            if other_s2 in order_map:
                                if order_map[other_s2] >= order_map[s1]:
                                    if s2 in staff_capabilities.get(other_name, []):
                                        # 執行互換
                                        optimized_df.at[name, d2] = other_s2
                                        optimized_df.at[other_name, d2] = s2
                                        # 記錄變動位置
                                        changed_mask.at[name, d2] = True
                                        changed_mask.at[other_name, d2] = True
                                        break
                                        
    return optimized_df.reset_index(), changed_mask.reset_index()
