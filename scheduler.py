import pandas as pd

from datetime import datetime



# 增加 max_off_per_day 參數，預設值設為 3

def solve_scheduling_df(df, max_off_per_day=3):

    """

    接收 Excel 寬表格，補件後維持原始「寬表格」格式輸出

    max_off_per_day: 調整單日最大休假人數限制

    """

    if '姓名' in df.columns:

        df = df.set_index('姓名')



    df = df.astype(object)



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

    weeks = {}

    for original_col, d_obj in temp_date_map.items():

        iso = d_obj.isocalendar()

        week_id = f"{iso[0]}-W{iso[1]:02d}"

        if week_id not in weeks:

            weeks[week_id] = []

        weeks[week_id].append(original_col)



    result_df_wide = df.copy()

    names = result_df_wide.index.tolist()



    for name in names:

        for week_id, week_dates in weeks.items():

            current_vals = result_df_wide.loc[name, week_dates].fillna('')

            current_offs = current_vals.isin(['AL', 'DO']).sum()

           

            if current_offs < 2:

                needed = 2 - current_offs

                potential_dates = [d for d in week_dates if pd.isna(result_df_wide.loc[name, d]) or str(result_df_wide.loc[name, d]).strip() == '']

                potential_dates.sort(key=lambda d: result_df_wide[d].fillna('').isin(['AL', 'DO']).sum())



                for d in potential_dates:

                    if needed <= 0: break

                   

                    # --- 關鍵修正：將 3 改為變數 max_off_per_day ---

                    if result_df_wide[d].fillna('').isin(['AL', 'DO']).sum() >= max_off_per_day:

                        continue

                       

                    if name in ['FFF', 'GGG']:

                        other = 'GGG' if name == 'FFF' else 'FFF'

                        if other in result_df_wide.index:

                            other_val = str(result_df_wide.loc[other, d]).strip()

                            if other_val in ['AL', 'DO']:

                                continue

                   

                    result_df_wide.at[name, d] = 'DO'

                    needed -= 1



    return result_df_wide.reset_index()
