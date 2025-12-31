# merge_volatility.py 
import pandas as pd
import os
import numpy as np 

def merge_hv_columns(
    target_file="last_update_option.xlsx",
    vol_folder="Underlying Asset symbol calculate",
    vol_file_name="0Market_Volatility_Report_last_update.xlsx"
):
    """
    Merge HV columns and calculate expected volatility until expiration.
    """
    print(f"Merging volatility data (HV) and performing calculations...")
    
    
    ANNUAL_TRADING_DAYS = 242 

    # Check files
    if not os.path.exists(target_file):
        print(f" Target file not found: {target_file}")
        return {'success': False, 'error': 'Target file not found'}

    vol_path = os.path.join(vol_folder, vol_file_name)
    if not os.path.exists(vol_path):
        print(f" Volatility file not found: {vol_path}")
        return {'success': False, 'error': 'Volatility file not found'}

    try:
        # 1. Read files
        df_target = pd.read_excel(target_file)
        df_vol = pd.read_excel(vol_path)
        
        # 2. Find key column (Stock Name)
        target_key = 'نام سهم' 
        days_column = 'روزهای کاری تا سررسید' 
        
        if target_key not in df_target.columns:
            return {'success': False, 'error': f"Column '{target_key}' not found."}

        
        vol_key = None
        possible_names = ['Nam', 'Symbol', 'نماد', 'Name', 'Ticker']
        for col in df_vol.columns:
            if str(col).strip() in possible_names:
                vol_key = col
                break
        
        if not vol_key:
            vol_key = df_vol.columns[0]
            print(f" Symbol column not found, using the first column: {vol_key}")

        # 3. Prepare for Merge
        df_target['join_key'] = df_target[target_key].astype(str).str.strip()
        df_vol['join_key'] = df_vol[vol_key].astype(str).str.strip()

        # 4. Identify HV columns
        hv_columns = [col for col in df_vol.columns if 'HV' in str(col)]
        
        if not hv_columns:
            print(" HV column not found.")
            return {'success': True, 'msg': 'No HV columns'}

        # Select columns
        cols_to_merge = ['join_key'] + hv_columns
        df_vol_subset = df_vol[cols_to_merge].copy().drop_duplicates(subset=['join_key'])

        # 5. Perform Merge
        merged_df = pd.merge(df_target, df_vol_subset, on='join_key', how='left')
        merged_df.drop(columns=['join_key'], inplace=True)

        # 6. --- Calculate Expected Volatility until Expiration ---
        if days_column in merged_df.columns:
            print("   🧮 Calculating expected volatility until expiration...")
            
            
            merged_df[days_column] = pd.to_numeric(merged_df[days_column], errors='coerce').fillna(0)
            
            for hv_col in hv_columns:
                
                new_col_name = f"نوسان تا سررسید ({hv_col})"
                
                # Formula: HV * Sqrt(Days / 242)
                # Note: Assumes HV is in decimal (e.g., 0.30) or percent (30). 
                # This formula works for both and provides proportional output.
                
                merged_df[new_col_name] = merged_df[hv_col] * np.sqrt(merged_df[days_column] / ANNUAL_TRADING_DAYS)
                
                # Round to 2 decimal places
                merged_df[new_col_name] = merged_df[new_col_name].round(2)
        else:
            print(f" Column '{days_column}' not found, calculations skipped.")

        # 7. Save
        merged_df.to_excel(target_file, index=False)
        print(f" Final file saved (with calculated volatility columns).")

        return {
            'success': True, 
            'hv_cols_count': len(hv_columns),
            'matched_rows': merged_df[hv_columns[0]].notna().sum() if hv_columns else 0
        }

    except Exception as e:
        print(f" Error: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}

if __name__ == "__main__":
    # Test execution
    merge_hv_columns()