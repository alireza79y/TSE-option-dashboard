# run_app.py
import time
import threading
import sys
import os
import subprocess
import shutil

# --- 1. تنظیم مسیر پروژه ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config

# --- 2. ایمپورت توابع بک‌اند ---
try:
    from src.backend.downloader import download_marketwatch_excel
    from src.backend.processor import process_options_from_temp
    from src.backend.merger import merge_hv_columns
except ImportError as e:
    print(f"Critical Import Error: {e}")
    sys.exit(1)

def run_full_update_cycle(is_background=False):
    """
    یک دور کامل: دانلود -> پردازش -> مرج
    """
    prefix = "[Background]" if is_background else "[Startup]"
    print("\n" + "-" * 40)
    print(f"{prefix} Starting Update Cycle @ {time.strftime('%H:%M:%S')}...")

    # --- گام اول: دانلود ---
    try:
        dl_result = download_marketwatch_excel()
        if isinstance(dl_result, dict) and not dl_result.get('success', True):
            print(f"    Download Failed: {dl_result.get('error')}")
            return False
    except Exception as e:
        print(f"    Download Crash: {e}")
        return False

    # --- گام دوم: پردازش ---
    try:
        temp_file = "temp_market_data.pkl"
        if isinstance(dl_result, dict) and 'temp_file' in dl_result:
            temp_file = dl_result['temp_file']

        if not os.path.exists(temp_file):
            print(f"    Temp file missing.")
            return False

        process_res = process_options_from_temp(temp_file)
        if isinstance(process_res, dict) and not process_res.get('success', True):
            print(f"    Processing Failed.")
            return False
    except Exception as e:
        print(f"    Processing Crash: {e}")
        return False

    # --- گام سوم: مرج نوسان‌ذیری ---
    try:
        target_file = "last_update_option.xlsx"
        if isinstance(process_res, dict) and 'last_update_file' in process_res:
            target_file = process_res['last_update_file']
            
        merge_hv_columns(
            target_file=target_file,
            vol_folder=config.INPUT_DIR,
            vol_file_name="0Market_Volatility_Report_last_update.xlsx"
        )
    except Exception as e:
        print(f"    Merge Error (Skipping HV): {e}")

    # --- گام چهارم: ذخیره نهایی ---
    try:
        if os.path.exists("last_update_option.xlsx"):
            shutil.copy("last_update_option.xlsx", config.FINAL_FILE)
            print(f"{prefix}  Data Updated Successfully.")
            return True
        else:
            return False
    except Exception as e:
        print(f"    Copy Error: {e}")
        return False

def backend_loop():
    """حلقه آپدیت پس‌زمینه"""
    while True:
        # اول ۳ دقیقه صبر میکند، چون یک بار اول برنامه اجرا شده
        time.sleep(config.UPDATE_INTERVAL_SECONDS)
        run_full_update_cycle(is_background=True)

def main():
    print("="*60)
    print("  TSE Options System Initializing...")
    print("="*60)

    # --- تغییر مهم: همیشه اول کار آپدیت کن ---
    # قبلاً چک می‌کردیم if not os.path.exists. الان برش داشتیم.
    print(" Force Updating Data (Wait 2-3 mins)...")
    
    success = run_full_update_cycle(is_background=False)
    
    if success:
        print(" Startup Update Complete.")
    else:
        print(" Startup Update Failed (Using old data if available).")

    # --- شروع آپدیت‌کننده خودکار ---
    updater_thread = threading.Thread(target=backend_loop, daemon=True)
    updater_thread.start()
    print(f" Background updater active (Next run in {config.UPDATE_INTERVAL_SECONDS}s)")

    # --- اجرای داشبورد ---
    print("\n Launching Dashboard...")
    dashboard_path = os.path.join("src", "frontend", "dashboard.py")
    cmd = [sys.executable, "-m", "streamlit", "run", dashboard_path]
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n[System] Stopping application...")

if __name__ == "__main__":
    main()