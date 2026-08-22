import streamlit as st
import gspread
import json
from datetime import datetime, timedelta
import pytz
import config as cfg


# KẾT NỐI TớI BẢNG SHEETS
SHEET_URL = "https://docs.google.com/spreadsheets/d/1XD3D4Gs3SI9aQB1aWfgZ_5wHsqNpjswDv_4EfTc708I/edit?usp=sharing"

@st.cache_resource
def get_spreadsheet():
    try:
        # Lấy creds từ secrets (khi deploy) hoặc file json (khi chạy local)
        if "google_credentials" in st.secrets:
            creds_dict = json.loads(st.secrets["google_credentials"])
            gc = gspread.service_account_from_dict(creds_dict) 
        else:
            # gc = gspread.service_account(filename="milkshop-506107-19ac...json") # Thay tên file json thực tế của bạn
            gc = gspread.service_account(filename='C:/Users/Bee/Desktop/ShopMilkPy/milkshop-506107-19ac8c82c7b0.json')
        
        # Sửa link Google Sheets của bạn ở đây
        SHEET_URL = cfg.SHEET_URL
        return gc.open_by_url(SHEET_URL)
    except Exception as e:
        st.error(f"Lỗi kết nối Sheets: {e}")
        return None


@st.cache_resource
def get_worksheet(sheet_name):
    spreadsheet = get_spreadsheet()
    if spreadsheet is None:
        return None
    return spreadsheet.worksheet(sheet_name)


@st.cache_data(ttl=120)
def get_sheet_data(sheet_name):
    worksheet = get_worksheet(sheet_name)
    if worksheet is None:
        return [], []
    values = worksheet.get_all_values()
    if not values:
        return [], []
    headers = values[0]
    records = [dict(zip(headers, row)) for row in values[1:]]
    return values, records


def clear_sheet_data_cache():
    get_sheet_data.clear()

