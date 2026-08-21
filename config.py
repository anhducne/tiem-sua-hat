import streamlit as st
import gspread
import json
from datetime import datetime, timedelta
import pytz
import config as cfg


# KẾT NỐI TớI BẢNG SHEETS
gc = gspread.service_account(filename='C:/Users/Bee/Desktop/ShopMilkPy/milkshop-506107-19ac8c82c7b0.json')
SHEET_URL = "https://docs.google.com/spreadsheets/d/1XD3D4Gs3SI9aQB1aWfgZ_5wHsqNpjswDv_4EfTc708I/edit?usp=sharing"

@st.cache_resource
def get_spreadsheet():
    try:
        # Lấy creds từ secrets (khi deploy) hoặc file json (khi chạy local)
        if "google_credentials" in st.secrets:
            creds_dict = json.loads(st.secrets["google_credentials"])
            # gc = gspread.service_account_from_dict(creds_dict) 
            gc = cfg.gc
        else:
            # gc = gspread.service_account(filename="milkshop-506107-19ac...json") # Thay tên file json thực tế của bạn
            gc = cfg.gc
        
        # Sửa link Google Sheets của bạn ở đây
        SHEET_URL = cfg.SHEET_URL
        return gc.open_by_url(SHEET_URL)
    except Exception as e:
        st.error(f"Lỗi kết nối Sheets: {e}")
        return None


@st.cache_data(ttl=30)
def get_sheet_data(sheet_name):
    spreadsheet = get_spreadsheet()
    if spreadsheet is None:
        return [], []
    worksheet = spreadsheet.worksheet(sheet_name)
    values = worksheet.get_all_values()
    if not values:
        return [], []
    headers = values[0]
    records = [dict(zip(headers, row)) for row in values[1:]]
    return values, records


def clear_sheet_data_cache():
    get_sheet_data.clear()

# dành cho món ăn 
# monan_sheet = sh.worksheet("MonAn")
# list_mon_an = [row["TenMon"] for row in monan_sheet.get_all_records() if row.get("TenMon")]
