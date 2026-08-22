import streamlit as st
import json
from datetime import datetime
import pytz
import config as cfg
# Cấu hình trang
st.set_page_config(page_title="Tiệm Sữa Hạt", layout="centered")

# --- GIAO DIỆN CHÍNH ---
st.title("🥛 Tiệm Sữa Hạt")

# 1. Hiển thị thông tin tuần
menu_data, _ = cfg.get_sheet_data("NguoiDung")
st.write("### Bạn đã đăng ký sữa cho tuần này chưa?")
st.table(menu_data[1:]) # Hiển thị bảng menu từ hàng 2 trở đi

st.divider()

# 2. Đăng ký mới
st.subheader("📝 Đăng ký mới")
col1, col2 = st.columns(2)
with col1:
    ten = st.text_input("Tên")
with col2:
    sdt_moi = st.text_input("Số điện thoại")

if st.button("Đặt hàng ngay"):
    # Code xử lý lưu đơn vào tab DonHang...
    st.success("Đã ghi nhận đơn hàng của bạn!")

st.divider()

# 3. Kiểm tra đơn đã đặt
st.subheader("🔍 Đã đặt sữa rồi:")
col3, col4 = st.columns([2, 1])
with col3:
    sdt_kiemtra = st.text_input("Số điện thoại kiểm tra")
with col4:
    st.write("###") # Tạo khoảng cách cho đẹp
    if st.button("Kiểm tra đơn hàng"):
        # Code đọc tab DonHang và lọc theo SĐT...
        st.info("Đang tìm đơn hàng...")

st.divider()

# 4. Dành cho quản trị viên
if st.button("Dành cho quản trị viên"):
    password = st.text_input("Nhập mật khẩu Admin", type="password")
    if password == "Admin123":
        st.write("Chào Admin! Chuyển hướng đến bảng quản trị...")
        # Code điều hướng đến trang Admin...