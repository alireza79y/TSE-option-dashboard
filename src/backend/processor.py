# process_options.py
import pandas as pd
import re
import pickle
from io import BytesIO
import os
from datetime import datetime, timedelta
import shutil
import jdatetime

# Holiday Settings 
OFFICIAL_HOLIDAYS = [
    '1403/11/22', 
    '1403/12/29', 
    '1404/01/01', 
    '1404/01/02', 
    '1404/01/03', 
    '1404/01/04', 
    '1404/01/12', 
    '1404/01/13', 
]

def calculate_working_days(start_date, end_date):
    """
    Calculate working days between two Jalali dates (excluding Thursdays, Fridays, and holidays).
    """
    if start_date >= end_date:
        return 0
    
    holidays_set = set(OFFICIAL_HOLIDAYS)
    working_days = 0
    current_date = start_date + timedelta(days=1)
    
    while current_date <= end_date:
        weekday = current_date.weekday()
        current_date_str = current_date.strftime("%Y/%m/%d")
        
        # weekday 3 is Thursday, 4 is Friday in Python's default calendar mapping for this context
        if weekday != 3 and weekday != 4 and current_date_str not in holidays_set:
            working_days += 1
            
        current_date += timedelta(days=1)
        
    return working_days

def process_options_from_temp(temp_file="temp_market_data.pkl"):
    """
    Process option data from the temporary file and generate the final Excel file.
    """
    try:
        # Load temporary data
        print(f" Loading temporary file: {temp_file}")
        with open(temp_file, 'rb') as f:
            temp_data = pickle.load(f)
        
        excel_content = temp_data['excel_content']
        header_row = temp_data['header_row']
        extracted_date = temp_data['extracted_date']
        extracted_time = temp_data['extracted_time']
        
        print(f"Processing data (Date: {extracted_date} - Time: {extracted_time})")

        # --- Convert report date to Date Object ---
        try:
            y_base, m_base, d_base = map(int, extracted_date.split('/'))
            report_date_obj = jdatetime.date(y_base, m_base, d_base)
        except Exception as e:
            print(f" Error in report date format: {e}")
            report_date_obj = jdatetime.date.today()
        
        # Read Excel file
        excel_data = BytesIO(excel_content)
        df = pd.read_excel(excel_data, header=header_row)
        
        # ========================================================
        #  New Section: Filter invalid rows (Cleaner)
        # ========================================================
        initial_count = len(df)
        print(f" Cleaning data (Initial count: {initial_count})...")
        
        # List of columns to check (Persian column names from source)
        buy_col = 'خرید - قیمت'
        sell_col = 'فروش - قیمت'
        last_col = 'آخرین معامله - مقدار'

        # Helper function to clean numeric columns
        def clean_numeric_col(df, col_name):
            if col_name in df.columns:
                # Convert to numeric (errors become NaN) and fill NaN with 0
                df[col_name] = pd.to_numeric(df[col_name], errors='coerce').fillna(0)
            return df

        # Apply filters
        if buy_col in df.columns:
            df = clean_numeric_col(df, buy_col)
            # Remove if 0 or 1
            df = df[~df[buy_col].isin([0, 1])]

        if sell_col in df.columns:
            df = clean_numeric_col(df, sell_col)
            # Remove if 0 or 1
            df = df[~df[sell_col].isin([0, 1])]

        if last_col in df.columns:
            df = clean_numeric_col(df, last_col)
            # Remove if exactly 1
            df = df[df[last_col] != 1]
            
        final_count = len(df)
        print(f" Cleaning done. Removed: {initial_count - final_count} | Remaining: {final_count}")
        # ========================================================

        # Reset index after dropping rows
        df.reset_index(drop=True, inplace=True)
        excel_data.seek(0)
        
        # --- Find 'Name' column ---
        name_column = None
        for col in df.columns:
            col_str = str(col).strip()
            if 'نام' in col_str:
                name_column = col
                break
        
        if not name_column:
            print(" 'Name' column not found.")
            return {'success': False, 'error': "'Name' column not found"}
        
        # --- Parse Option Patterns ---
        print("🔍 Parsing option patterns...")
        
        df['نوع'] = ''
        df['نام سهم'] = ''
        df['قیمت اعمال'] = ''
        df['تاریخ سررسید'] = ''
        df['روزهای کاری تا سررسید'] = ''
        
        counter = 0
        option_types_found = {'اختيارخ': 0, 'اختيارف': 0, 'اختيار': 0}
        
        for idx, row in df.iterrows():
            cell_value = str(row[name_column]).strip()
            
            if 'اختيار' in cell_value or 'اختیار' in cell_value:
                parts = [p.strip() for p in cell_value.split('-')]
                
                if len(parts) >= 3:
                    first_part = parts[0].strip()
                    
                    # Detect Type
                    if 'اختيارف' in first_part or 'اختیارف' in first_part:
                        option_type = 'اختيارف'
                        stock_name = first_part.replace('اختيارف', '').replace('اختیارف', '').strip()
                    elif 'اختيارخ' in first_part or 'اختیارخ' in first_part:
                        option_type = 'اختيارخ'
                        stock_name = first_part.replace('اختيارخ', '').replace('اختیارخ', '').strip()
                    elif 'اختيار' in first_part or 'اختیار' in first_part:
                        option_type = 'اختيار'
                        stock_name = first_part.replace('اختيار', '').replace('اختیار', '').strip()
                    else:
                        option_type = 'اختيار'
                        stock_name = first_part
                    
                    strike_price = parts[1].strip()
                    expiry_date = parts[2].strip()
                    
                    # Standardize Date
                    if re.match(r'^\d{2}/\d{2}/\d{2}$', expiry_date):
                        year, month, day = expiry_date.split('/')
                        expiry_date = f'14{year}/{month}/{day}' if int(year) < 50 else f'13{year}/{month}/{day}'
                    elif re.match(r'^\d{8}$', expiry_date):
                        expiry_date = f'{expiry_date[:4]}/{expiry_date[4:6]}/{expiry_date[6:8]}'
                    
                    # --- Calculate Working Days ---
                    working_days_left = 0
                    try:
                        y_exp, m_exp, d_exp = map(int, expiry_date.split('/'))
                        expiry_date_obj = jdatetime.date(y_exp, m_exp, d_exp)
                        working_days_left = calculate_working_days(report_date_obj, expiry_date_obj)
                    except:
                        working_days_left = 0 

                    df.at[idx, 'نوع'] = option_type
                    df.at[idx, 'نام سهم'] = stock_name
                    df.at[idx, 'قیمت اعمال'] = strike_price
                    df.at[idx, 'تاریخ سررسید'] = expiry_date
                    df.at[idx, 'روزهای کاری تا سررسید'] = working_days_left
                    
                    counter += 1
                    option_types_found[option_type] += 1
        
        # --- Filter Rows Containing Options ---
        has_option_data = (df['نوع'] != '') | (df['نام سهم'] != '')
        matching_rows = df[has_option_data].copy()
        
        print(f"Final parsed row count: {counter}")
        
        # --- Find Stock Price from Original File ---
        
        excel_data.seek(0)
        df_original = pd.read_excel(excel_data, header=header_row)
        
        symbol_column_original = None
        price_column_original = None
        
        for col in df_original.columns:
            col_str = str(col).strip()
            if 'نماد' in col_str:
                symbol_column_original = col
                break
        
        price_keywords = ['آخرین معامله', 'آخرین معامله - مقدار', 'قیمت آخرین معامله']
        for col in df_original.columns:
            col_str = str(col).strip()
            for keyword in price_keywords:
                if keyword in col_str:
                    price_column_original = col
                    break
            if price_column_original:
                break
        
        # Add stock price column
        matching_rows['قیمت سهم'] = ''
        
        if symbol_column_original and price_column_original:
            found_count = 0
            for idx, row in matching_rows.iterrows():
                symbol_name = str(row['نام سهم']).strip()
                # Search in original (full) data
                matching_row = df_original[df_original[symbol_column_original] == symbol_name]
                
                if not matching_row.empty:
                    price_value = matching_row.iloc[0][price_column_original]
                    matching_rows.at[idx, 'قیمت سهم'] = price_value
                    found_count += 1
                else:
                    matching_rows.at[idx, 'قیمت سهم'] = 'Not Found'
            
            print(f"📊 Base prices found: {found_count}")
        
        # --- Save Files ---
        safe_date = extracted_date.replace('/', '-')
        safe_time = extracted_time.replace(':', '-')
        main_filename = f"اختيار {safe_date} - {safe_time}.xlsx"
        
        print(f"💾 Saving main file: {main_filename}")
        matching_rows.to_excel(main_filename, index=False)
        
        # Metadata
        try:
            with pd.ExcelWriter(main_filename, engine='openpyxl', mode='a') as writer:
                meta_data = pd.DataFrame({
                    'اطلاعات': ['تاریخ گزارش', 'زمان گزارش', 'تعداد کل اختیارها', 
                               'تعداد اختيارخ', 'تعداد اختيارف', 'تاریخ ایجاد'],
                    'مقدار': [extracted_date, extracted_time, len(matching_rows),
                             len(matching_rows[matching_rows['نوع'] == 'اختيارخ']),
                             len(matching_rows[matching_rows['نوع'] == 'اختيارف']),
                             datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                })
                meta_data.to_excel(writer, sheet_name='اطلاعات فایل', index=False)
        except Exception as e:
            print(f"Error saving metadata: {e}")
        
        # Archive
        archive_folder = "archive optin tse"
        if not os.path.exists(archive_folder):
            os.makedirs(archive_folder)
        
        archive_path = os.path.join(archive_folder, main_filename)
        shutil.copy2(main_filename, archive_path)
        print(f" Saved to archive: {archive_path}")
        
        # Last Update
        last_update_filename = "last_update_option.xlsx"
        matching_rows['تاریخ دانلود'] = extracted_date
        matching_rows['زمان دانلود'] = extracted_time
        matching_rows['تاریخ-زمان پردازش'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        matching_rows.to_excel(last_update_filename, index=False)
        
        # Last Update Metadata
        try:
            with pd.ExcelWriter(last_update_filename, engine='openpyxl', mode='a') as writer:
                meta_data = pd.DataFrame({
                    'اطلاعات': ['تاریخ گزارش', 'زمان گزارش', 'تعداد کل اختیارها', 
                               'تعداد اختيارخ', 'تعداد اختيارف', 'آخرین بروزرسانی'],
                    'مقدار': [extracted_date, extracted_time, len(matching_rows),
                             len(matching_rows[matching_rows['نوع'] == 'اختيارخ']),
                             len(matching_rows[matching_rows['نوع'] == 'اختيارف']),
                             datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                })
                meta_data.to_excel(writer, sheet_name='اطلاعات فایل', index=False)
        except Exception as e:
            pass
        
        # Remove temporary file
        if os.path.exists(temp_file):
            os.remove(temp_file)
        
        return {
            'success': True,
            'main_file': main_filename,
            'archive_file': archive_path,
            'last_update_file': last_update_filename,
            'row_count': len(matching_rows),
            'option_types': option_types_found
        }
        
    except Exception as e:
        print(f" Processing error: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}