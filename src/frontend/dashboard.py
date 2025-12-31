# src/frontend/dashboard.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import sys
import config  # مطمئن شوید config را درست ایمپورت کرده‌اید
import json
import time
from datetime import datetime

# --- تنظیم مسیر برای پیدا کردن config.py ---
# این خطوط باید بعد از ایمپورت‌های اصلی باشند
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import config 

# --- Page Config ---
st.set_page_config(page_title="Comprehensive Options Dashboard", layout="wide", page_icon="📊")
def load_data():
    # تغییر مهم: خواندن از مسیر کانفیگ
    file_path = config.FINAL_FILE 
    if not os.path.exists(file_path):
        return None
    # ... بقیه کد مثل قبل
    
# --- Journal Section ---
def load_journal():
    # تغییر مهم: خواندن ژورنال از مسیر کانفیگ
    if not os.path.exists(config.JOURNAL_FILE):
        return pd.DataFrame(...)
    return pd.read_csv(config.JOURNAL_FILE)

def save_to_journal(entry):
    # تغییر مهم
    df = load_journal()
    # ...
    df.to_csv(config.JOURNAL_FILE, index=False)

def delete_journal_entry(index):
    # تغییر مهم
    df = load_journal()
    # ...
    df.to_csv(config.JOURNAL_FILE, index=False)
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
from datetime import datetime

# --- Page Config ---
st.set_page_config(page_title="Comprehensive Options Dashboard", layout="wide", page_icon="📊")

# --- Constants ---
JOURNAL_FILE = "trading_journal.csv"

# --- Helper Functions ---
@st.cache_data(ttl=180) 
def load_data():
    file_path = config.FINAL_FILE  # خواندن از کانفیگ
    if not os.path.exists(file_path):
        return None
    
    # استفاده از engine='openpyxl' برای اطمینان
    df = pd.read_excel(file_path, engine='openpyxl')
    # Clean column names
    df.columns = [c.strip() for c in df.columns]
    
    # Columns that must be numeric
    numeric_cols = ['قیمت اعمال', 'خرید - قیمت', 'فروش - قیمت', 'قیمت سهم', 
                    'خرید - حجم', 'فروش - حجم', 'آخرین معامله - مقدار',
                    'روزهای کاری تا سررسید']
    
    hv_cols = [c for c in df.columns if 'نوسان تا سررسید' in c]
    numeric_cols.extend(hv_cols)

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

def get_valid_price(row):
    """Returns valid price (Priority: Ask Price, then Last Price)"""
    ask = row.get('فروش - قیمت', 0)
    last = row.get('آخرین معامله - مقدار', 0)
    if ask > 0: return ask
    if last > 0: return last
    return 0

def calculate_payoff(strategy_type, strikes, premiums, spot_range):
    pnl = []
    for price in spot_range:
        profit = 0
        
        # --- Single Strike Strategies ---
        if strategy_type in ["Straddle", "Strangle", "Strap", "Strip"]:
            c_strike = strikes.get('call')
            p_strike = strikes.get('put')
            c_cost = premiums.get('call')
            p_cost = premiums.get('put')
            
            call_intrinsic = max(price - c_strike, 0)
            put_intrinsic = max(p_strike - price, 0)
            
            if strategy_type == "Straddle" or strategy_type == "Strangle":
                profit = (call_intrinsic - c_cost) + (put_intrinsic - p_cost)
            elif strategy_type == "Strap":
                profit = (2 * call_intrinsic - 2 * c_cost) + (put_intrinsic - p_cost)
            elif strategy_type == "Strip":
                profit = (call_intrinsic - c_cost) + (2 * put_intrinsic - 2 * p_cost)
        
        # --- Spread Strategies ---
        elif strategy_type == "Bull Call Spread":
            k_low = strikes['low_call']
            k_high = strikes['high_call']
            c_low = premiums['low_call']
            c_high = premiums['high_call']
            profit = (max(price - k_low, 0) - c_low) + (c_high - max(price - k_high, 0))

        elif strategy_type == "Bear Call Spread":
            k_low = strikes['low_call']
            k_high = strikes['high_call']
            c_low = premiums['low_call']
            c_high = premiums['high_call']
            profit = (c_low - max(price - k_low, 0)) + (max(price - k_high, 0) - c_high)
            
        pnl.append(profit)
    return pnl

def find_best_strategies(df, sort_col_hv):
    suggestions = []
    grouped = df.groupby(['نام سهم', 'تاریخ سررسید'])
    
    for (symbol, expiry), group in grouped:
        if group.empty: continue
        current_price = group['قیمت سهم'].iloc[0]
        if current_price == 0: continue
        
        move_rial = current_price * group[sort_col_hv].iloc[0]
        price_up = current_price + move_rial
        strikes = sorted(group['قیمت اعمال'].unique())
        if not strikes: continue
        
        atm_strike = min(strikes, key=lambda x: abs(x - current_price))
        
        c_atm = group[(group['نوع']=='اختيارخ') & (group['قیمت اعمال']==atm_strike)]
        p_atm = group[(group['نوع']=='اختيارف') & (group['قیمت اعمال']==atm_strike)]
        
        has_atm_call = not c_atm.empty and get_valid_price(c_atm.iloc[0]) > 0
        has_atm_put = not p_atm.empty and get_valid_price(p_atm.iloc[0]) > 0
        
        # 1. Straddle
        if has_atm_call and has_atm_put:
            cc = get_valid_price(c_atm.iloc[0])
            pc = get_valid_price(p_atm.iloc[0])
            cost = cc + pc
            suggestions.append({
                'Symbol': symbol, 'Expiry': expiry, 'Strategy': 'Straddle',
                'Cost': cost, 'Direction': 'Neutral (High Volatility)',
                'Potential': int(move_rial - cost)
            })

        # 2. Bull Call Spread
        higher_strikes = [s for s in strikes if s > atm_strike]
        if has_atm_call and higher_strikes:
            otm_strike = higher_strikes[0]
            c_otm = group[(group['نوع']=='اختيارخ') & (group['قیمت اعمال']==otm_strike)]
            if not c_otm.empty and get_valid_price(c_otm.iloc[0]) > 0:
                cost_buy = get_valid_price(c_atm.iloc[0])
                credit_sell = get_valid_price(c_otm.iloc[0])
                net_debit = cost_buy - credit_sell
                val_buy = max(price_up - atm_strike, 0)
                val_sell = max(price_up - otm_strike, 0)
                profit = (val_buy - cost_buy) + (credit_sell - val_sell)
                suggestions.append({
                    'Symbol': symbol, 'Expiry': expiry, 
                    'Strategy': f'Bull Call Spread ({atm_strike}/{otm_strike})',
                    'Cost': net_debit, 'Direction': 'Mildly Bullish ↗️',
                    'Potential': int(profit)
                })

        # 3. Bear Call Spread
        if has_atm_call and higher_strikes:
            otm_strike = higher_strikes[0]
            c_otm = group[(group['نوع']=='اختيارخ') & (group['قیمت اعمال']==otm_strike)]
            if not c_otm.empty and get_valid_price(c_otm.iloc[0]) > 0:
                credit_sell = get_valid_price(c_atm.iloc[0])
                cost_buy = get_valid_price(c_otm.iloc[0])
                net_credit = credit_sell - cost_buy
                suggestions.append({
                    'Symbol': symbol, 'Expiry': expiry, 
                    'Strategy': f'Bear Call Spread ({atm_strike}/{otm_strike})',
                    'Cost': -net_credit, 'Direction': 'Bearish/Neutral ↘️',
                    'Potential': int(net_credit)
                })

    return pd.DataFrame(suggestions)

# --- Journal Functions (New Feature) ---
def load_journal():
    if not os.path.exists(JOURNAL_FILE):
        return pd.DataFrame(columns=["Date", "Symbol", "Expiry", "Strategy", "Entry Price", "Notes"])
    return pd.read_csv(JOURNAL_FILE)

def save_to_journal(entry):
    df = load_journal()
    entry_df = pd.DataFrame([entry])
    df = pd.concat([df, entry_df], ignore_index=True)
    df.to_csv(JOURNAL_FILE, index=False)

def delete_journal_entry(index):
    df = load_journal()
    if index in df.index:
        df = df.drop(index).reset_index(drop=True)
        df.to_csv(JOURNAL_FILE, index=False)
        return True
    return False

# --- Main Body ---
st.title(" Comprehensive Options Dashboard")

# --- Smart Refresh Logic ---

# 1. Initialize session state for tracking update time
if 'last_mtime' not in st.session_state:
    st.session_state['last_mtime'] = 0

if st.sidebar.button("🔄 Check for Updates"):
    
    # الف) چک کردن اینکه آیا دانلودر در حال کار است؟
    # (معمولاً دانلودر فایل temp_market_data.pkl را می‌سازد)
    # فرض می‌کنیم فایل تمپ در کنار فایل نهایی یا در ریشه است
    is_downloading = False
    possible_temp_files = [
        "temp_market_data.pkl", 
        os.path.join(os.path.dirname(config.FINAL_FILE), "temp_market_data.pkl")
    ]
    
    for t_file in possible_temp_files:
        if os.path.exists(t_file):
            is_downloading = True
            break
            
    if is_downloading:
        st.sidebar.warning("System is currently downloading data from TSETMC. Please wait 1-2 minutes...", icon="⏳")
    
    else:
        # ب) چک کردن اینکه آیا فایل جدید آمده است؟
        if os.path.exists(config.FINAL_FILE):
            file_mtime = os.path.getmtime(config.FINAL_FILE)
            
            # اگر زمان فایل اکسل جدیدتر از آخرین باری است که ما لود کردیم
            if file_mtime > st.session_state['last_mtime']:
                st.cache_data.clear()  # پاک کردن کش
                st.session_state['last_mtime'] = file_mtime # آپدیت زمان در حافظه
                st.toast("Data Updated Successfully! Reloading...", icon="✅")
                time.sleep(1)
                st.rerun()
            else:
                st.toast("Dashboard is already up to date.", icon="ℹ️")
        else:
            st.error("Data file not found yet.")
df = load_data()
if df is None:
    st.error(" Data file 'last_update_option.xlsx' not found.")
    st.stop()

# --- Last Update Info ---
last_date = df['تاریخ دانلود'].iloc[0] if 'تاریخ دانلود' in df.columns else "Unknown"
last_time = df['زمان دانلود'].iloc[0] if 'زمان دانلود' in df.columns else "Unknown"
st.sidebar.success(f"**Last Update:** {last_date}\n\n **Time:** {last_time}")

# --- Sidebar Filters ---
st.sidebar.header("General Filters")
all_assets = df['نام سهم'].unique()
selected_asset = st.sidebar.selectbox("Select Asset:", all_assets)
asset_df = df[df['نام سهم'] == selected_asset]
current_price = asset_df['قیمت سهم'].iloc[0] if not asset_df.empty else 0
st.sidebar.info(f"Price of {selected_asset}: {int(current_price):,} IRR")
expiry_dates = asset_df['تاریخ سررسید'].unique()
selected_expiry = st.sidebar.selectbox("Expiry Date:", expiry_dates)
final_df = asset_df[asset_df['تاریخ سررسید'] == selected_expiry]

# Pre-Filtering
valid_straddle_strikes = []
valid_call_strikes = []
valid_put_strikes = []

if not final_df.empty:
    for k in sorted(final_df['قیمت اعمال'].unique()):
        c_row = final_df[(final_df['نوع'] == 'اختيارخ') & (final_df['قیمت اعمال'] == k)]
        p_row = final_df[(final_df['نوع'] == 'اختيارف') & (final_df['قیمت اعمال'] == k)]
        
        has_call = False
        has_put = False
        
        if not c_row.empty and get_valid_price(c_row.iloc[0]) > 0:
            has_call = True
            valid_call_strikes.append(k)
        if not p_row.empty and get_valid_price(p_row.iloc[0]) > 0:
            has_put = True
            valid_put_strikes.append(k)
        if has_call and has_put:
            valid_straddle_strikes.append(k)

# --- Tabs ---
tabs = st.tabs([
    "Straddle", "Strangle", "Strap", "Strip", 
    "Bull Call Spread ", "Bear Call Spread ",
    " Smart Suggestions", "Trading Journal"
])

# ---------------- Tab 1: Straddle ----------------
with tabs[0]:
    st.subheader("Straddle Strategy")
    if not valid_straddle_strikes:
        st.warning("No valid options found for Straddle.")
    else:
        default_idx = min(range(len(valid_straddle_strikes)), key=lambda i: abs(valid_straddle_strikes[i]-current_price))
        k = st.selectbox("Strike:", valid_straddle_strikes, index=default_idx, key='std_k')
        
        c_row = final_df[(final_df['نوع']=='اختيارخ') & (final_df['قیمت اعمال']==k)].iloc[0]
        p_row = final_df[(final_df['نوع']=='اختيارف') & (final_df['قیمت اعمال']==k)].iloc[0]
        cc = get_valid_price(c_row)
        pc = get_valid_price(p_row)
        total = cc + pc
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Call Cost", f"{int(cc):,}")
        c2.metric("Put Cost", f"{int(pc):,}")
        c3.metric("Total Cost", f"{int(total):,}", delta_color="inverse")
        
        rng = list(range(int(k*0.7), int(k*1.3), 100))
        pnl = calculate_payoff("Straddle", {'call':k, 'put':k}, {'call':cc, 'put':pc}, rng)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=rng, y=pnl, fill='tozeroy', name='P&L'))
        fig.add_vline(x=current_price, line_dash="dash", annotation_text="Current")
        st.plotly_chart(fig, use_container_width=True)

# ---------------- Tab 2: Strangle ----------------
with tabs[1]:
    st.subheader("Strangle Strategy")
    puts_otm = [s for s in valid_put_strikes if s < current_price]
    calls_otm = [s for s in valid_call_strikes if s > current_price]
    puts_list = puts_otm if puts_otm else valid_put_strikes
    calls_list = calls_otm if calls_otm else valid_call_strikes
    
    if not puts_list or not calls_list:
        st.warning("Not enough options available.")
    else:
        c1, c2 = st.columns(2)
        with c1: k_p = st.selectbox("Put Strike (Low):", puts_list, index=len(puts_list)-1, key='stg_kp')
        with c2: k_c = st.selectbox("Call Strike (High):", calls_list, index=0, key='stg_kc')
            
        c_row = final_df[(final_df['نوع']=='اختيارخ') & (final_df['قیمت اعمال']==k_c)].iloc[0]
        p_row = final_df[(final_df['نوع']=='اختيارف') & (final_df['قیمت اعمال']==k_p)].iloc[0]
        cc = get_valid_price(c_row)
        pc = get_valid_price(p_row)
        total = cc + pc
        
        st.metric("Total Cost", f"{int(total):,}")
        rng = list(range(int(min(k_p, k_c)*0.7), int(max(k_p, k_c)*1.3), 100))
        pnl = calculate_payoff("Strangle", {'call':k_c, 'put':k_p}, {'call':cc, 'put':pc}, rng)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=rng, y=pnl, fill='tozeroy', line_color='orange', name='P&L'))
        fig.add_vline(x=current_price, line_dash="dash", annotation_text="Current")
        st.plotly_chart(fig, use_container_width=True)

# ---------------- Tab 3: STRAP ----------------
with tabs[2]:
    st.subheader("Strap (Bullish)")
    if not valid_straddle_strikes:
        st.warning("No valid options found.")
    else:
        default_idx = min(range(len(valid_straddle_strikes)), key=lambda i: abs(valid_straddle_strikes[i]-current_price))
        k = st.selectbox("Strike:", valid_straddle_strikes, index=default_idx, key='strap_k')
        
        c_row = final_df[(final_df['نوع']=='اختيارخ') & (final_df['قیمت اعمال']==k)].iloc[0]
        p_row = final_df[(final_df['نوع']=='اختيارف') & (final_df['قیمت اعمال']==k)].iloc[0]
        cc = get_valid_price(c_row)
        pc = get_valid_price(p_row)
        total = (2 * cc) + pc
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Cost (2 Calls)", f"{int(2*cc):,}")
        c2.metric("Cost (1 Put)", f"{int(pc):,}")
        c3.metric("Total Cost", f"{int(total):,}", delta_color="inverse")
        
        rng = list(range(int(k*0.7), int(k*1.3), 100))
        pnl = calculate_payoff("Strap", {'call':k, 'put':k}, {'call':cc, 'put':pc}, rng)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=rng, y=pnl, fill='tozeroy', line_color='green', name='P&L'))
        fig.add_vline(x=current_price, line_dash="dash", annotation_text="Current")
        st.plotly_chart(fig, use_container_width=True)

# ---------------- Tab 4: STRIP ----------------
with tabs[3]:
    st.subheader("Strip (Bearish)")
    if not valid_straddle_strikes:
        st.warning("No valid options found.")
    else:
        default_idx = min(range(len(valid_straddle_strikes)), key=lambda i: abs(valid_straddle_strikes[i]-current_price))
        k = st.selectbox("Strike:", valid_straddle_strikes, index=default_idx, key='strip_k')
        
        c_row = final_df[(final_df['نوع']=='اختيارخ') & (final_df['قیمت اعمال']==k)].iloc[0]
        p_row = final_df[(final_df['نوع']=='اختيارف') & (final_df['قیمت اعمال']==k)].iloc[0]
        cc = get_valid_price(c_row)
        pc = get_valid_price(p_row)
        total = cc + (2 * pc)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Cost (1 Call)", f"{int(cc):,}")
        c2.metric("Cost (2 Puts)", f"{int(2*pc):,}")
        c3.metric("Total Cost", f"{int(total):,}", delta_color="inverse")
        
        rng = list(range(int(k*0.7), int(k*1.3), 100))
        pnl = calculate_payoff("Strip", {'call':k, 'put':k}, {'call':cc, 'put':pc}, rng)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=rng, y=pnl, fill='tozeroy', line_color='red', name='P&L'))
        fig.add_vline(x=current_price, line_dash="dash", annotation_text="Current")
        st.plotly_chart(fig, use_container_width=True)

# ---------------- Tab 5: Bull Call Spread ----------------
with tabs[4]:
    st.subheader("Bull Call Spread (Mildly Bullish)")
    if len(valid_call_strikes) < 2:
        st.warning("At least 2 valid Call strikes are required.")
    else:
        c1, c2 = st.columns(2)
        with c1: k_low = st.selectbox("Buy Call (Low):", valid_call_strikes, index=0, key='bull_k1')
        with c2:
            available_high = [k for k in valid_call_strikes if k > k_low]
            if not available_high:
                k_high = None
                st.error("No higher strikes available.")
            else:
                k_high = st.selectbox("Sell Call (High):", available_high, index=0, key='bull_k2')
        
        if k_high:
            row_low = final_df[(final_df['نوع']=='اختيارخ') & (final_df['قیمت اعمال']==k_low)].iloc[0]
            row_high = final_df[(final_df['نوع']=='اختيارخ') & (final_df['قیمت اعمال']==k_high)].iloc[0]
            cost_low = get_valid_price(row_low)
            credit_high = get_valid_price(row_high)
            net_debit = cost_low - credit_high
            max_profit = (k_high - k_low) - net_debit
            breakeven = k_low + net_debit
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Net Cost", f"{int(net_debit):,}")
            c2.metric("Max Profit", f"{int(max_profit):,}")
            c3.metric("Breakeven Point", f"{int(breakeven):,}")
            
            rng = list(range(int(k_low*0.8), int(k_high*1.2), 100))
            pnl = calculate_payoff("Bull Call Spread", {'low_call': k_low, 'high_call': k_high}, {'low_call': cost_low, 'high_call': credit_high}, rng)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=rng, y=pnl, fill='tozeroy', line_color='green', name='P&L'))
            fig.add_vline(x=current_price, line_dash="dash", annotation_text="Current")
            st.plotly_chart(fig, use_container_width=True)

# ---------------- Tab 6: Bear Call Spread ----------------
with tabs[5]:
    st.subheader("Bear Call Spread (Mildly Bearish)")
    if len(valid_call_strikes) < 2:
        st.warning("Not enough options available.")
    else:
        c1, c2 = st.columns(2)
        with c1: k_low = st.selectbox("Sell Call (Low):", valid_call_strikes, index=0, key='bear_k1')
        with c2:
            available_high = [k for k in valid_call_strikes if k > k_low]
            if not available_high:
                k_high = None
                st.error("No higher strikes available.")
            else:
                k_high = st.selectbox("Buy Call (High):", available_high, index=0, key='bear_k2')
                
        if k_high:
            row_low = final_df[(final_df['نوع']=='اختيارخ') & (final_df['قیمت اعمال']==k_low)].iloc[0]
            row_high = final_df[(final_df['نوع']=='اختيارخ') & (final_df['قیمت اعمال']==k_high)].iloc[0]
            credit_low = get_valid_price(row_low)
            cost_high = get_valid_price(row_high)
            net_credit = credit_low - cost_high
            max_loss = (k_high - k_low) - net_credit
            breakeven = k_low + net_credit
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Net Credit", f"{int(net_credit):,}")
            c2.metric("Max Profit", f"{int(net_credit):,}")
            c3.metric("Breakeven Point", f"{int(breakeven):,}")
            
            rng = list(range(int(k_low*0.8), int(k_high*1.2), 100))
            pnl = calculate_payoff("Bear Call Spread", {'low_call': k_low, 'high_call': k_high}, {'low_call': credit_low, 'high_call': cost_high}, rng)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=rng, y=pnl, fill='tozeroy', line_color='red', name='P&L'))
            fig.add_vline(x=current_price, line_dash="dash", annotation_text="Current")
            st.plotly_chart(fig, use_container_width=True)

# ---------------- Tab 7: Smart Suggestions ----------------
with tabs[6]:
    st.markdown("###  Smart Suggestions")
    hv_cols = [c for c in df.columns if 'نوسان تا سررسید' in c]
    if hv_cols:
        selected_hv = st.selectbox("Volatility Basis (HV):", hv_cols)
        if st.button("Analyze Market"):
            res_df = find_best_strategies(df, selected_hv)
            if not res_df.empty:
                profitable = res_df[res_df['Potential'] > 0].sort_values('Potential', ascending=False)
                st.dataframe(profitable, use_container_width=True)
            else:
                st.warning("No profitable strategies found based on expected volatility.")
    else:
        st.error("Volatility columns not found.")

import json # برای ذخیره دیکشنری‌ها در CSV

# ---------------- Tab 8: Trading Journal (Advanced) ----------------
with tabs[7]:
    st.subheader(" Professional Trading Journal")
    
    # بارگذاری فایل ژورنال
    journal_df = load_journal()

    # تقسیم صفحه به دو بخش: ثبت (چپ) و نمایش/تحلیل (راست)
    col_input, col_view = st.columns([1, 2])
    
    # --- Left Column: New Trade Entry ---
    with col_input:
        st.markdown("### ➕ New Trade")
        
        # 1. Asset Selection (From Excel)
        available_assets = sorted(df['نام سهم'].unique())
        j_symbol = st.selectbox("Select Asset", available_assets, key='j_asset_select')
        
        # 2. Expiry Selection (Dependent on Asset)
        asset_specific_dates = sorted(df[df['نام سهم'] == j_symbol]['تاریخ سررسید'].unique())
        j_expiry = st.selectbox("Select Expiry", asset_specific_dates, key='j_expiry_select')
        
        # 3. Strategy Selection
        j_strategy = st.selectbox("Strategy Type", 
                                  ["Straddle", "Strangle", "Bull Call Spread", "Bear Call Spread", "Strap", "Strip"],
                                  key='j_strat_select')
        
        st.markdown("---")
        st.write(f"**Strategy Details:** {j_strategy}")
        
        # 4. Dynamic Inputs based on Strategy
        input_strikes = {}
        input_premiums = {}
        entry_cost = 0
        
        # --- Logic for Inputs ---
        if j_strategy in ["Straddle", "Strap", "Strip"]:
            k = st.number_input("Strike Price", step=1000, format="%d", key='j_k')
            c1, c2 = st.columns(2)
            c_price = c1.number_input("Call Price", min_value=0, step=100, key='j_cp')
            p_price = c2.number_input("Put Price", min_value=0, step=100, key='j_pp')
            
            input_strikes = {'call': k, 'put': k}
            input_premiums = {'call': c_price, 'put': p_price}
            
            if j_strategy == "Straddle": entry_cost = c_price + p_price
            elif j_strategy == "Strap": entry_cost = (2 * c_price) + p_price
            elif j_strategy == "Strip": entry_cost = c_price + (2 * p_price)

        elif j_strategy == "Strangle":
            c1, c2 = st.columns(2)
            k_put = c1.number_input("Put Strike (Low)", step=1000, format="%d", key='j_kp')
            k_call = c2.number_input("Call Strike (High)", step=1000, format="%d", key='j_kc')
            
            c3, c4 = st.columns(2)
            p_price = c3.number_input("Put Price", min_value=0, step=100, key='j_pp_s')
            c_price = c4.number_input("Call Price", min_value=0, step=100, key='j_cp_s')
            
            input_strikes = {'call': k_call, 'put': k_put}
            input_premiums = {'call': c_price, 'put': p_price}
            entry_cost = c_price + p_price

        elif "Call Spread" in j_strategy:
            c1, c2 = st.columns(2)
            k_low = c1.number_input("Low Strike", step=1000, format="%d", key='j_kl')
            k_high = c2.number_input("High Strike", step=1000, format="%d", key='j_kh')
            
            c3, c4 = st.columns(2)
            p_low = c3.number_input("Low Strike Premium", min_value=0, step=100, key='j_pl') 
            p_high = c4.number_input("High Strike Premium", min_value=0, step=100, key='j_ph') 
            
            input_strikes = {'low_call': k_low, 'high_call': k_high}
            input_premiums = {'low_call': p_low, 'high_call': p_high}
            
            if "Bull" in j_strategy:
                entry_cost = p_low - p_high 
            else:
                entry_cost = p_low - p_high 

        # Notes
        j_notes = st.text_area("Notes", placeholder="Reason for trade...", key='j_notes')

        # Save Button
        if st.button("💾 Save Trade to Journal", type="primary", key='j_save_btn'):
            new_entry = {
                "Date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Symbol": j_symbol,
                "Expiry": j_expiry,
                "Strategy": j_strategy,
                "Entry Cost": entry_cost,
                "Strikes_Data": json.dumps(input_strikes),
                "Premiums_Data": json.dumps(input_premiums),
                "Notes": j_notes
            }
            save_to_journal(new_entry)
            st.success("Trade Saved Successfully!")
            st.rerun()

    # --- Right Column: Visualization & List ---
    with col_view:
        st.markdown("### 📊 Active Trades Analysis")
        
        if journal_df.empty:
            st.info("No trades found. Please add a trade from the left panel.")
        else:
            # 1. Select a trade to visualize
            # FIX: Use dot notation (row.Symbol) instead of brackets
            trade_options = [f"{row.Index}: {row.Symbol} - {row.Strategy} ({row.Date})" for row in journal_df.itertuples()]
            selected_trade_str = st.selectbox("Select a Trade to Analyze:", trade_options, key='j_view_select')
            selected_index = int(selected_trade_str.split(":")[0])
            
            # دریافت داده‌های ردیف انتخاب شده
            trade_data = journal_df.loc[selected_index]
            
            # تبدیل رشته‌های JSON برگشتی به دیکشنری
            try:
                t_strikes = json.loads(trade_data['Strikes_Data'])
                t_premiums = json.loads(trade_data['Premiums_Data'])
            except:
                t_strikes = {}
                t_premiums = {}

            # FIX: Handle NaN cost
            raw_cost = trade_data.get('Entry Cost', 0)
            if pd.isna(raw_cost) or raw_cost == "":
                safe_cost = 0
            else:
                try:
                    safe_cost = int(float(raw_cost))
                except:
                    safe_cost = 0

            # نمایش خلاصه
            m1, m2, m3 = st.columns(3)
            m1.metric("Symbol", trade_data['Symbol'])
            m2.metric("Strategy", trade_data['Strategy'])
            m3.metric("Entry Cost/Credit", f"{safe_cost:,}")
            
            # 2. Draw Chart
            st.markdown("#### P&L Diagram")
            
            current_spot = 0
            if not df.empty:
                spot_row = df[df['نام سهم'] == trade_data['Symbol']]
                if not spot_row.empty:
                    current_spot = spot_row['قیمت سهم'].iloc[0]
            
            if t_strikes:
                base_price = current_spot if current_spot > 0 else list(t_strikes.values())[0]
                if base_price == 0: base_price = 1000
                rng = list(range(int(base_price*0.7), int(base_price*1.3), 100))
                
                pnl = calculate_payoff(trade_data['Strategy'], t_strikes, t_premiums, rng)
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=rng, y=pnl, fill='tozeroy', 
                                         line=dict(color='purple', width=2), name='P&L'))
                
                if current_spot > 0:
                    fig.add_vline(x=current_spot, line_dash="dash", line_color="blue", annotation_text="Current Market Price")
                
                fig.add_hline(y=0, line_color="black", line_width=1)
                
                # FIX: Unique Key Added
                st.plotly_chart(fig, use_container_width=True, key="journal_chart_unique")
            else:
                st.warning("Could not load strike data for chart.")
            
            st.info(f"📝 Notes: {trade_data['Notes']}")

            # دکمه حذف
            st.markdown("---")
            # FIX: Unique Key Added
            if st.button("Delete This Trade", key="del_btn_journal_unique"):
                delete_journal_entry(selected_index)
                st.success("Trade Deleted.")
                st.rerun()