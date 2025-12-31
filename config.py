# config.py
import os

# آدرس فولدر اصلی پروژه
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# مسیر فولدرهای دیتا
DATA_DIR = os.path.join(BASE_DIR, "data")
INPUT_DIR = os.path.join(DATA_DIR, "input")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")
ARCHIVE_DIR = os.path.join(DATA_DIR, "archive")

# اطمینان از اینکه فولدرها وجود دارند
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)

# فایل‌های ورودی و خروجی
VOLATILITY_FILE = os.path.join(INPUT_DIR, "0Market_Volatility_Report_last_update.xlsx")
TEMP_FILE = os.path.join(OUTPUT_DIR, "temp_market_data.pkl")
FINAL_FILE = os.path.join(OUTPUT_DIR, "last_update_option.xlsx")
JOURNAL_FILE = os.path.join(OUTPUT_DIR, "trading_journal.csv")

# تنظیمات زمان‌بندی
UPDATE_INTERVAL_SECONDS = 180  # هر 3 دقیقه