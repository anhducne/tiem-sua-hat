import streamlit as st
import gspread
from datetime import datetime
import pytz
import json
# 1. KẾT NỐI VỚI GOOGLE SHEETS
# (Lưu ý: Bạn phải dán link file Sheets của bạn vào đây)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1XD3D4Gs3SI9aQB1aWfgZ_5wHsqNpjswDv_4EfTc708I/edit?usp=sharing"

def get_sheet():
    # Kéo chìa khóa từ "Két sắt bí mật" của máy chủ Streamlit
    creds_dict = json.loads(st.secrets["google_credentials"])
    gc = gspread.service_account_from_dict(creds_dict)
    sh = gc.open_by_url(SHEET_URL)
    return sh.worksheet("DonHang")

# 2. GIAO DIỆN WEB STREAMLIT
st.title("🥛 Tiệm Sữa Hạt - Đặt Hàng")
st.write("Vui lòng điền thông tin để đặt món cho ngày mai!")

# 3. LOGIC KIỂM TRA GIỜ (8H TỐI = 20:00)
# Luôn lấy giờ chuẩn Việt Nam, tránh lỗi khi đưa lên máy chủ nước ngoài
tz_vn = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(tz_vn)

# Nếu giờ hiện tại >= 20, khóa form
if now.hour >= 20:
    st.error("⏰ Đã qua 20:00! Hệ thống đã khóa đơn ngày hôm nay.")
else:
    # Mở form cho khách điền
    with st.form("form_dat_hang", clear_on_submit=True):
        sdt = st.text_input("Số điện thoại của bạn (Bắt buộc):")
        ten = st.text_input("Tên của bạn (Khách cũ có thể bỏ qua):")
        
        # Danh sách món (Sau này bạn có thể viết thêm code để Python tự kéo từ Sheets xuống)
        mon_an = st.selectbox(
            "Chọn món bạn muốn đặt:", 
            ["Thứ 2: Sữa Óc Chó", "Thứ 3: Sữa Hạnh Nhân", "Thứ 4: Sữa Hạt Điều"]
        )
        
        submit_btn = st.form_submit_button("Chốt Đơn")
        
        # 4. XỬ LÝ KHI KHÁCH BẤM NÚT
        if submit_btn:
            if not sdt.strip():
                st.warning("⚠️ Bạn quên nhập số điện thoại rồi!")
            else:
                with st.spinner("Đang gửi đơn hàng..."):
                    try:
                        sheet = get_sheet()
                        thoi_gian = now.strftime("%d/%m/%Y %H:%M:%S")
                        
                        # Ghi thẳng vào Google Sheets
                        sheet.append_row([thoi_gian, sdt, ten, mon_an])
                        
                        st.success(f"🎉 Chúc mừng! Đã đặt thành công món {mon_an}")
                    except Exception as e:
                        st.error(f"Có lỗi xảy ra: {e}")