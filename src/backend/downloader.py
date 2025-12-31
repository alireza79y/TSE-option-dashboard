
# download_excel.py
import requests
from io import BytesIO
import os
import pickle
import re
import pandas as pd

def download_marketwatch_excel():
    """
    Download Excel from TSE
    """
    url = "https://old.tsetmc.com/tsev2/excel/MarketWatchPlus.aspx?d=0"
    
    try:
        print("downloading from TSE")
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        
        # Get content
        excel_content = response.content
        
        # Initial read to find date and time
        df_raw = pd.read_excel(BytesIO(excel_content), header=None)
        
        # Search for date and time pattern
        extracted_date = "1400/01/01"
        extracted_time = "00:00:00"
        
        # Regex to match Persian text in the file: "Market Watch : Date - Last Trade Time : Time"
        full_pattern = r'دیده بان بازار\s*:\s*(\d{4}/\d{2}/\d{2})\s*-\s*زمان آخرین معامله\s*:\s*(\d{2}:\d{2}:\d{2})'
        
        for row_idx in range(min(20, len(df_raw))):
            for col_idx in range(min(20, len(df_raw.columns))):
                cell_value = str(df_raw.iat[row_idx, col_idx])
                full_match = re.search(full_pattern, cell_value)
                
                if full_match:
                    extracted_date = full_match.group(1)
                    extracted_time = full_match.group(2)
                    break
            if extracted_date != "1400/01/01":
                break
        
        # Find Persian header row
        header_row = None
        for row_idx in range(min(10, len(df_raw))):
            row_values = df_raw.iloc[row_idx].dropna().astype(str).tolist()
            # Check if any cell contains Persian characters
            has_persian = any(re.search('[\u0600-\u06FF]', cell) for cell in row_values)
            
            if has_persian and len(row_values) >= 5:
                header_row = row_idx
                break
        
        if header_row is None:
            header_row = 0
        
        # Save data to a temporary dictionary
        temp_data = {
            'excel_content': excel_content,
            'header_row': header_row,
            'extracted_date': extracted_date,
            'extracted_time': extracted_time,
            'download_time': pd.Timestamp.now()
        }
        
        # Save to pickle file
        temp_filename = "temp_market_data.pkl"
        with open(temp_filename, 'wb') as f:
            pickle.dump(temp_data, f)
        
        print(" File successfully downloaded and temporarily saved.")
        print(f" Report Date: {extracted_date}")
        print(f" Report Time: {extracted_time}")
        
        return {
            'success': True,
            'temp_file': temp_filename,
            'date': extracted_date,
            'time': extracted_time,
            'header_row': header_row
        }
        
    except Exception as e:
        print(f" Error downloading file: {e}")
        return {
            'success': False,
            'error': str(e)
        }

if __name__ == "__main__":
    result = download_marketwatch_excel()