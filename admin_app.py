import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime, timedelta
import pytz
import config as cfg


def is_locked_account_status(value):
    normalized_value = str(value or "").strip().lower()
    normalized_value = normalized_value.replace("đ", "d").replace("á", "a").replace("ó", "o")
    return normalized_value in {"1", "true", "yes", "khoa", "bi khoa", "da khoa"}


def format_admin_order_items(value):
    return [item.strip() for item in str(value or "").split("|") if item.strip()]
from auth_utils import get_cookie_manager, read_admin_auth_state, save_admin_auth_state, clear_admin_auth_state

# --- BẢO MẬT ĐĂNG NHẬP ---
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False
if "admin_username" not in st.session_state:
    st.session_state.admin_username = ""

cookie_manager = get_cookie_manager()
read_admin_auth_state(st.session_state, cookie_manager)

# --- Phần Login ---
st.title("🔑 Trang Quản Trị Tiệm Sữa Hạt")
sh = cfg.get_spreadsheet()
if not sh:
    st.stop()

if not st.session_state.admin_logged_in:
    st.image("https://i.pinimg.com/1200x/4d/cb/43/4dcb438b80c4b6224d6c3c8d834a0786.jpg", width=400)
    username = st.text_input("Tên đăng nhập:")
    password = st.text_input("Mật khẩu:", type="password")
    if st.button("Đăng nhập"):
        try:
            @st.cache_data(ttl=300)
            def load_admin_rows():
                return sh.worksheet("QuanTriVien").get_all_records()

            admin_rows = load_admin_rows()
            valid_login = any(
                str(row.get("tendangnhap", "")).strip() == username.strip()
                and str(row.get("matkhau", "")).strip() == password
                for row in admin_rows
            )
        except Exception as e:
            valid_login = False
            st.error(f"Không thể đọc bảng QuanTriVien: {e}")

        if valid_login:
            save_admin_auth_state(st.session_state, cookie_manager, username)
            st.rerun()
        else:
            st.error("Sai tên đăng nhập hoặc mật khẩu!")
    st.stop() # Dừng lại nếu chưa đăng nhập thành công

# SAU KHI ĐĂNG NHẬP XONG SẼ VÀO TRANG QUẢN TRỊ

admin_display_name = st.session_state.get("admin_username", "Admin") or "Admin"
# Nút đăng xuất ở sidebar
st.sidebar.header(f"Xin chào {admin_display_name}! Ba chúc em thật đắt hàng! 🎉")
st.sidebar.info("Lưu ý: Chỉ Admin mới có quyền truy cập trang này.", icon="ℹ️")
st.sidebar.info("Hôm nay là ngày: " + datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')).strftime("%d/%m/%Y %H:%M:%S") , icon="📅")
st.sidebar.markdown("---")


if st.sidebar.button("Đăng xuất"):
    clear_admin_auth_state(st.session_state, cookie_manager)
    st.rerun()


# TẠO TABS CHỨC NĂNG QUẢN TRỊ
tab1, tab2, tab3 = st.tabs(["📅 Cấu Hình Menu Tuần", "🛒 Quản Lý Đơn Hàng (Orders)", "🥛 Danh Mục Món Ăn"])

# ==============================================================================
# TAB 1: CẤU HÌNH MENU THEO THỨ NGÀY (THỨ 2 -> CHỦ NHẬT & KHÓA NGÀY)
# ==============================================================================
with tab1:
    st.header("Cấu hình Menu & Khóa Ngày Order")
    
    # 1. Tính toán ngày Thứ 2 đến Chủ Nhật của tuần hiện tại
    tz_vn = pytz.timezone('Asia/Ho_Chi_Minh')
    today = datetime.now(tz_vn).date()
    start_of_week = today - timedelta(days=today.weekday()) # Lấy ngày Thứ 2 tuần này
    
    days_of_week = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]
    week_dates = [start_of_week + timedelta(days=i) for i in range(7)]

    # 2. Đọc MenuTuan để khôi phục cấu hình của tuần hiện tại nếu có
    try:
        order_sheet = sh.worksheet("MenuTuan")
        menu_tuan_rows = order_sheet.get_all_records()
    except Exception:
        order_sheet = None
        menu_tuan_rows = []

    current_week_menu = {}
    for row in menu_tuan_rows:
        raw_date = row.get("Ngay") or row.get("Ngày")
        try:
            menu_date = datetime.strptime(str(raw_date), "%d/%m/%Y").date()
        except (TypeError, ValueError):
            continue

        if menu_date in week_dates:
            current_week_menu[menu_date] = row

    # 3. Lấy danh sách món ăn từ Tab Menu để làm Dropdownlist
    try:
        monan_sheet = sh.worksheet("Menu")
        list_mon_an = [row["nguyenlieu"] for row in monan_sheet.get_all_records() if row.get("nguyenlieu")]
    except Exception:
        list_mon_an = ["Sữa Óc Chó", "Sữa Hạnh Nhân", "Sữa Hạt Điều", "Sữa Đậu Đen"]
        st.warning("Chưa có dữ liệu món ăn trên Sheets, đang dùng danh sách mặc định.")
    
    st.subheader(f"📅 Bảng phân công tuần: {start_of_week.strftime('%d/%m/%Y')} - {week_dates[-1].strftime('%d/%m/%Y')}")
    
    with st.form("form_update_menu"):
        menu_updates = []
        for idx, (thu, date_obj) in enumerate(zip(days_of_week, week_dates)):
            col_day, col_select, col_lock = st.columns([2, 3, 2])
            saved_row = current_week_menu.get(date_obj, {})
            saved_food = saved_row.get("MonAn")
            saved_status = saved_row.get("TrangThai")
            food_options = ["-- Không bán --"] + list_mon_an
            selected_index = food_options.index(saved_food) if saved_food in food_options else 0
            
            with col_day:
                st.markdown(f"**{thu}** `({date_obj.strftime('%d/%m')})`")
            
            with col_select:
                mon_selected = st.selectbox(
                    f"Chọn món cho {thu}",
                    options=food_options,
                    index=selected_index,
                    key=f"select_{idx}"
                )
            
            with col_lock:
                is_locked = st.toggle("Khóa Order", value=saved_status == "Đóng", key=f"lock_{idx}")
                status = "Đóng" if is_locked else "Mở"
            
            menu_updates.append([thu, date_obj.strftime('%d/%m/%Y'), mon_selected, status])
            st.divider()
        if st.form_submit_button("💾 Lưu Cấu Hình Menu Tuần"):
            try:
                if order_sheet is None:
                    st.error("Chưa có tab 'MenuTuan' trên Sheets.")
                    st.stop()
                # Ghi đè vào Tab Menu (Cột A: Thứ, B: Ngày, C: Món, D: Trạng thái)
                order_sheet.clear()
                order_sheet.append_row(["Thu", "Ngay", "MonAn", "TrangThai"])
                for row in menu_updates:
                    order_sheet.append_row(row)
                cfg.clear_sheet_data_cache()
                st.success("Đã cập nhật Menu tuần thành công!")
            except Exception as e:
                st.error(f"Lỗi khi lưu Menu: {e}")

# ==============================================================================
# TAB 2: CRUD QUẢN LÝ ĐƠN HÀNG (READ, UPDATE, DELETE)
# ==============================================================================
with tab2:
    st.header("🛒 Danh Sách Đơn Đặt Hàng")
    try:
        donhang_sheet = sh.worksheet("DonHang")
        nguoidung_sheet = sh.worksheet("NguoiDung")
        try:
            thuchi_sheet = sh.worksheet("ThuChi")
        except Exception:
            thuchi_sheet = None

        @st.cache_data(ttl=30)
        def load_admin_order_cache():
            orders = donhang_sheet.get_all_records()
            users = nguoidung_sheet.get_all_records()
            thuchi_rows = thuchi_sheet.get_all_records() if thuchi_sheet is not None else []
            return orders, users, thuchi_rows

        def clear_admin_order_cache():
            load_admin_order_cache.clear()
            cfg.clear_sheet_data_cache()

        orders, nguoidung_rows, thuchi_rows = load_admin_order_cache()

        def normalize_header_name(value):
            return str(value or "").strip().lower()

        def get_sheet_row_number(rows, key_name, value):
            for index, row in enumerate(rows, start=2):
                if str(row.get(key_name, "")).strip() == str(value).strip():
                    return index
            return None

        def get_field_value(row, *names):
            for name in names:
                if row.get(name) not in (None, ""):
                    return row.get(name)
            return ""

        def render_order_edit_dialog(order_row):
            if not hasattr(st, "dialog"):
                return

            @st.dialog(f"Chỉnh sửa đơn: {order_row.get('maOrder', 'Không rõ')}")
            def _dialog():
                with st.form("form_edit_order"):
                    st.markdown("### Thông tin đơn hàng")
                    ten_nguoi_dung = st.text_input(
                        "Tên người dùng:",
                        value=str(order_row.get("tennguoidung", "") or ""),
                    )
                    so_dien_thoai = st.text_input(
                        "Số điện thoại:",
                        value=str(order_row.get("dienthoai", "") or ""),
                    )
                    mon_da_dat = st.text_area(
                        "Món ăn đã đặt:",
                        value=str(order_row.get("monandadat", "") or ""),
                        height=180,
                    )

                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        save_clicked = st.form_submit_button("💾 Lưu")
                    with col_cancel:
                        cancel_clicked = st.form_submit_button("❌ Hủy")

                    if cancel_clicked:
                        st.session_state["editing_order_code"] = None
                        st.rerun()

                    if save_clicked:
                        ten_moi = ten_nguoi_dung.strip()
                        if not ten_moi:
                            st.warning("Vui lòng nhập tên người dùng!")
                            return

                        order_code = str(order_row.get("maOrder", "")).strip()
                        row_number = get_sheet_row_number(orders, "maOrder", order_code)
                        if row_number is None:
                            st.error("Không tìm thấy đơn hàng cần sửa.")
                            return

                        donhang_headers = donhang_sheet.row_values(1)
                        for column_name, new_value in {
                            "tennguoidung": ten_moi,
                            "dienthoai": so_dien_thoai.strip(),
                            "monandadat": mon_da_dat,
                        }.items():
                            column_index = next(
                                (idx for idx, name in enumerate(donhang_headers, start=1)
                                 if normalize_header_name(name) == normalize_header_name(column_name)),
                                None,
                            )
                            if column_index is not None:
                                donhang_sheet.update_cell(row_number, column_index, new_value)

                        user_row = get_sheet_row_number(nguoidung_rows, "maOrder", order_code)
                        if user_row is not None:
                            nguoidung_headers = nguoidung_sheet.row_values(1)
                            for key, value in {
                                "ten": ten_moi,
                                "dienthoai": so_dien_thoai.strip(),
                            }.items():
                                user_col = next(
                                    (idx for idx, name in enumerate(nguoidung_headers, start=1)
                                     if normalize_header_name(name) == normalize_header_name(key)),
                                    None,
                                )
                                if user_col is not None:
                                    nguoidung_sheet.update_cell(user_row, user_col, value)

                        clear_admin_order_cache()
                        st.session_state["editing_order_code"] = None
                        st.success(f"Chỉnh sửa {ten_moi} thành công. Hãy bấm làm mới trang thủ công để xem dữ liệu mới.")

            _dialog()

        def format_money(value):
            amount = parse_money(value)
            return f"{amount:,.0f}".replace(",", ".") + " đ"

        def render_batch_confirm_dialog():
            if not hasattr(st, "dialog"):
                return

            @st.dialog("Chọn đơn để xác nhận")
            def _dialog():
                st.markdown("Chọn những đơn cần xác nhận, sau đó bấm **Lưu xác nhận**.")
                with st.form("form_batch_confirm_orders"):
                    selected_codes = []
                    for order in orders:
                        order_code = str(get_field_value(order, "maOrder", "MaOrder", "mã đơn")).strip()
                        if not order_code:
                            continue
                        order_status = str(order.get("trangthai", "") or "").strip().lower()
                        is_confirmed = order_status in {"đã xác nhận", "da xac nhan", "đã nhận đơn", "da nhan don"}
                        order_name = str(get_field_value(order, "tennguoidung", "TenNguoiDung", "Tên người dùng")).strip()
                        phone = str(get_field_value(order, "dienthoai", "DienThoai", "SĐT")).strip()
                        checked = st.checkbox(
                            f"{order_code} | {order_name or 'Không có tên'} | {phone or 'Không có SĐT'} | {format_money(order.get('tongsotien'))}",
                            value=is_confirmed,
                            key=f"batch_confirm_{order_code}",
                        )
                        if checked:
                            selected_codes.append(order_code)

                    save_batch = st.form_submit_button("💾 Lưu xác nhận", use_container_width=True)
                    cancel_batch = st.form_submit_button("❌ Hủy", use_container_width=True)

                if cancel_batch:
                    st.session_state["batch_confirm_dialog"] = False
                    st.rerun()

                if save_batch:
                    donhang_headers = donhang_sheet.row_values(1)
                    donhang_status_col = next(
                        (idx for idx, name in enumerate(donhang_headers, start=1)
                         if normalize_header_name(name) == "trangthai"),
                        None,
                    )
                    nguoidung_headers = nguoidung_sheet.row_values(1)
                    payment_col = next(
                        (idx for idx, name in enumerate(nguoidung_headers, start=1)
                         if normalize_header_name(name) == "thanhtoantien"),
                        None,
                    )

                    order_updates = []
                    user_updates = []
                    for order_code in selected_codes:
                        order_row = get_sheet_row_number(orders, "maOrder", order_code)
                        if order_row is not None and donhang_status_col is not None:
                            order_updates.append({
                                "range": f"{gspread.utils.rowcol_to_a1(order_row, donhang_status_col)}",
                                "values": [["Đã xác nhận"]],
                            })
                        user_row = get_sheet_row_number(nguoidung_rows, "maOrder", order_code)
                        if user_row is not None and payment_col is not None:
                            user_updates.append({
                                "range": f"{gspread.utils.rowcol_to_a1(user_row, payment_col)}",
                                "values": [["Đã thanh toán"]],
                            })

                    if order_updates:
                        for update in order_updates:
                            row_number, column_number = gspread.utils.a1_to_rowcol(update["range"])
                            donhang_sheet.update_cell(row_number, column_number, update["values"][0][0])
                    if user_updates:
                        for update in user_updates:
                            row_number, column_number = gspread.utils.a1_to_rowcol(update["range"])
                            nguoidung_sheet.update_cell(row_number, column_number, update["values"][0][0])

                    clear_admin_order_cache()
                    st.session_state["batch_confirm_dialog"] = False
                    st.rerun()

            _dialog()

        if not orders:
            st.info("Chưa có đơn hàng nào.")
        else:
            def parse_money(value):
                if value in (None, ""):
                    return 0
                try:
                    if isinstance(value, (int, float)):
                        return float(value)
                    cleaned = str(value).replace(".", "").replace(",", "").replace("đ", "").replace(" ", "")
                    return float(cleaned)
                except Exception:
                    return 0

            def parse_datetime_value(value):
                if value in (None, ""):
                    return None
                for fmt in (
                    "%d/%m/%Y %H:%M:%S",
                    "%Y-%m-%d %H:%M:%S",
                    "%d/%m/%Y",
                    "%Y-%m-%d",
                    "%Y/%m/%d %H:%M:%S",
                    "%Y/%m/%d",
                ):
                    try:
                        return datetime.strptime(str(value), fmt)
                    except ValueError:
                        continue
                return None

            def get_order_date(order):
                for key in ["thoigianchinhsuacuoi", "thoigiandathang", "thoigian", "created_at", "ngaydat"]:
                    parsed = parse_datetime_value(order.get(key))
                    if parsed is not None:
                        return parsed.date()
                return None

            def get_order_day_labels(order):
                raw_value = str(order.get("monandadat", "") or "")
                if raw_value.strip():
                    weekday_names = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]
                    matched = []
                    seen = set()
                    for part in raw_value.split("|"):
                        part_text = part.strip()
                        for weekday in weekday_names:
                            if weekday.lower() in part_text.lower() and weekday.lower() not in seen:
                                matched.append(weekday)
                                seen.add(weekday.lower())
                    if matched:
                        return ", ".join(matched)

                registered_date = get_order_date(order)
                if registered_date is not None:
                    return date_to_weekday_label(registered_date)
                return "Không rõ"

            def date_to_weekday_label(date_value):
                if date_value is None:
                    return "Không rõ"
                weekday_names = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]
                return weekday_names[date_value.weekday()]

            today = datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")).date()
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)

            current_week_orders = []
            for order in orders:
                order_date = get_order_date(order)
                if order_date is not None and week_start <= order_date <= week_end:
                    current_week_orders.append(order)

            total_week_orders = len(current_week_orders)
            total_due = sum(parse_money(order.get("tongsotien")) for order in current_week_orders)
            confirmed_orders = [
                order for order in current_week_orders
                if str(order.get("trangthai", "")).strip().lower() in {"đã xác nhận", "da xac nhan", "đã nhận đơn", "da nhan don"}
            ]
            total_collected = sum(parse_money(order.get("tongsotien")) for order in confirmed_orders)

            current_year = today.year
            current_month = today.month
            month_revenue_total = 0
            if thuchi_sheet is not None:
                for row in thuchi_rows:
                    if str(row.get("Nam", "")).strip() == str(current_year) and str(row.get("Thang", "")).strip() == str(current_month):
                        month_revenue_total += parse_money(row.get("TongSoTienThu"))
            if month_revenue_total == 0:
                month_revenue_total = sum(parse_money(order.get("tongsotien")) for order in orders if get_order_date(order) and get_order_date(order).year == current_year and get_order_date(order).month == current_month)

            st.success(
                f"**Tổng số tiền thu được trong 1 tháng (4 tuần):** {format_money(month_revenue_total)}"
            )
            st.markdown(
                f"**Tổng số đơn của tuần ({week_start.strftime('%d/%m/%Y')} đến {week_end.strftime('%d/%m/%Y')}):** {total_week_orders} đơn\n"
            )
            st.markdown(
                f"**Tổng số tiền phải thu trong tuần:** {format_money(total_due)}\n"
            )
            st.markdown(
                f"**Tổng số tiền đã có trong tuần:** {format_money(total_collected)}"
            )

            account_status_map = {}
            for user in nguoidung_rows:
                order_code = str(user.get("maOrder", "") or "").strip()
                status_value = str(user.get("trangthaitaikhoan", "Hoạt động") or "Hoạt động").strip()
                if order_code:
                    account_status_map[order_code] = status_value if status_value else "Hoạt động"

            display_orders = []
            for order in orders:
                order_code = str(get_field_value(order, "maOrder", "MaOrder", "mã đơn")).strip()
                phone = str(get_field_value(order, "dienthoai", "DienThoai", "SĐT")).strip()
                customer_name = str(get_field_value(order, "tennguoidung", "TenNguoiDung", "Tên người dùng")).strip()
                order_status = str(order.get("trangthai", "") or "").strip()
                registered_date = get_order_date(order)
                display_orders.append({
                    "Mã Order": order_code or "UNKNOWN",
                    "Xác nhận đơn": "Đã xác nhận" if order_status.lower() in {"đã xác nhận", "da xac nhan", "đã nhận đơn", "da nhan don"} else "Chưa xác nhận",
                    "Điện thoại": phone or "Không có SĐT",
                    "Tên": customer_name or "Không có tên",
                    "Ngày đăng ký": get_order_day_labels(order),
                    "Tiền": format_money(order.get("tongsotien")),
                    "Chỉnh sửa cuối": str(order.get("thoigianchinhsuacuoi", "") or ""),
                    "Trạng thái Tài khoản": account_status_map.get(order_code, "Hoạt động"),
                })

            column_order = [
                "Mã Order",
                "Xác nhận đơn",
                "Điện thoại",
                "Tên",
                "Ngày đăng ký",
                "Tiền",
                "Chỉnh sửa cuối",
                "Trạng thái Tài khoản",
            ]
            st.dataframe(pd.DataFrame(display_orders)[column_order], use_container_width=True)

            order_options = []
            order_map = {}
            for order in orders:
                order_code = str(get_field_value(order, "maOrder", "MaOrder", "mã đơn")).strip()
                phone = str(get_field_value(order, "dienthoai", "DienThoai", "SĐT")).strip()
                customer_name = str(get_field_value(order, "tennguoidung", "TenNguoiDung", "Tên người dùng")).strip()
                if not order_code:
                    order_code = "UNKNOWN"
                label = f"{order_code} • {phone or 'Không có SĐT'} • {customer_name or 'Không có tên'}"
                order_options.append(label)
                order_map[label] = order

            if "selected_order_code" not in st.session_state:
                st.session_state["selected_order_code"] = order_options[0]

            selected_label = st.selectbox(
                "Chọn đơn hàng cần xem / thao tác",
                options=order_options,
                index=order_options.index(st.session_state["selected_order_code"]) if st.session_state["selected_order_code"] in order_options else 0,
                key="order_selector",
            )
            st.session_state["selected_order_code"] = selected_label
            selected_order = order_map.get(selected_label, orders[0])

            st.subheader("📄 Chi tiết đơn hàng")
            with st.container(border=True):
                st.markdown(f"**Mã đơn:** {selected_order.get('maOrder', '')}")
                st.markdown(f"**Tên người dùng:** {selected_order.get('tennguoidung', '')}")
                st.markdown(f"**Số điện thoại:** {selected_order.get('dienthoai', '')}")
                st.markdown("**Món ăn đã đặt:**")
                for order_item in format_admin_order_items(selected_order.get("monandadat", "")):
                    st.markdown(f"- {order_item}")
                st.markdown(f"**Tổng số tiền:** {format_money(selected_order.get('tongsotien'))}")
                st.markdown(f"**Trạng thái:** {selected_order.get('trangthai', '')}")
                st.markdown(f"**Thời gian chỉnh sửa cuối:** {selected_order.get('thoigianchinhsuacuoi', '')}")

            if st.session_state.get("editing_order_code"):
                render_order_edit_dialog(order_map.get(st.session_state["editing_order_code"], selected_order))
            if st.session_state.get("batch_confirm_dialog"):
                render_batch_confirm_dialog()

            left_col, right_col = st.columns([1.3, 1])
            with left_col:
                st.markdown("### ⚙️ Cập nhật trạng thái")
                with st.container(border=True):
                    user_match = next(
                        (user for user in nguoidung_rows if str(user.get("maOrder", "")).strip() == str(selected_order.get("maOrder", "")).strip()),
                        None,
                    )
                    locked_value = user_match.get("trangthaitaikhoan", "Hoạt động") if user_match else "Hoạt động"
                    is_locked = is_locked_account_status(locked_value)
                    current_status = str(selected_order.get("trangthai", "")).strip().lower()
                    is_confirmed = current_status in {"đã xác nhận", "da xac nhan", "đã nhận đơn", "da nhan don"}

                    st.markdown("**Khóa tài khoản**")
                    account_status_options = ["Hoạt động", "Bị khóa"]
                    account_status_value = "Bị khóa" if is_locked else "Hoạt động"
                    selected_account_status = st.selectbox(
                        "",
                        options=account_status_options,
                        index=account_status_options.index(account_status_value),
                        key=f"account_status_select_{selected_order.get('maOrder', 'unknown')}",
                        label_visibility="collapsed",
                    )

                    st.markdown("**Xác nhận đơn hàng**")
                    order_status_options = ["Chưa xác nhận", "Đã xác nhận"]
                    selected_order_status = st.selectbox(
                        "",
                        options=order_status_options,
                        index=0 if not is_confirmed else 1,
                        key=f"order_status_select_{selected_order.get('maOrder', 'unknown')}",
                        label_visibility="collapsed",
                    )

                    if st.button("💾 Lưu", use_container_width=True):
                        account_status = selected_account_status
                        new_status = selected_order_status

                        user_row = get_sheet_row_number(nguoidung_rows, "maOrder", str(selected_order.get("maOrder", "")).strip())
                        if user_row is not None:
                            nguoidung_headers = nguoidung_sheet.row_values(1)
                            user_updates = []
                            status_col = next(
                                (idx for idx, name in enumerate(nguoidung_headers, start=1)
                                 if normalize_header_name(name) == "trangthaitaikhoan"),
                                None,
                            )
                            if status_col is not None:
                                user_updates.append({
                                    "range": gspread.utils.rowcol_to_a1(user_row, status_col),
                                    "values": [[account_status]],
                                })

                            payment_col = next(
                                (idx for idx, name in enumerate(nguoidung_headers, start=1)
                                 if normalize_header_name(name) == "thanhtoantien"),
                                None,
                            )
                            if payment_col is not None:
                                user_updates.append({
                                    "range": gspread.utils.rowcol_to_a1(user_row, payment_col),
                                    "values": [["Đã thanh toán" if new_status == "Đã xác nhận" else "Chưa thanh toán"]],
                                })
                            if user_updates:
                                nguoidung_sheet.batch_update(user_updates)

                        row_number = get_sheet_row_number(orders, "maOrder", str(selected_order.get("maOrder", "")).strip())
                        if row_number is not None:
                            donhang_headers = donhang_sheet.row_values(1)
                            status_col = next(
                                (idx for idx, name in enumerate(donhang_headers, start=1)
                                 if normalize_header_name(name) == "trangthai"),
                                None,
                            )
                            if status_col is not None:
                                donhang_sheet.batch_update([{
                                    "range": gspread.utils.rowcol_to_a1(row_number, status_col),
                                    "values": [[new_status]],
                                }])

                        if thuchi_sheet is not None:
                            week_index = ((today.day - 1) // 7) + 1
                            week_label = f"{week_start.strftime('%d/%m/%Y')} - {week_end.strftime('%d/%m/%Y')}"
                            revenue_for_week = sum(
                                parse_money(order.get("tongsotien"))
                                for order in orders
                                if str(order.get("trangthai", "")).strip().lower() in {"đã xác nhận", "da xac nhan", "đã nhận đơn", "da nhan don"}
                                and get_order_date(order) is not None
                                and week_start <= get_order_date(order) <= week_end
                            )
                            thuchi_rows = thuchi_sheet.get_all_records()
                            match_row = next(
                                (row for row in thuchi_rows if str(row.get("Nam", "")).strip() == str(today.year) and str(row.get("Thang", "")).strip() == str(today.month) and str(row.get("Tuan", "")).strip() == str(week_index) and str(row.get("Ngay", "")).strip() == week_label),
                                None,
                            )
                            if match_row is not None:
                                row_idx = thuchi_rows.index(match_row) + 2
                                thuchi_sheet.batch_update([{
                                    "range": f"A{row_idx}:E{row_idx}",
                                    "values": [[today.year, today.month, week_index, week_label, revenue_for_week]],
                                }])
                            else:
                                thuchi_sheet.append_row([today.year, today.month, week_index, week_label, revenue_for_week])

                        clear_admin_order_cache()
                        st.rerun()

            with right_col:
                st.markdown("### 🧰 Thao tác đơn hàng")
                with st.container(border=True):
                    action_row = st.columns([1, 1, 1])
                    with action_row[0]:
                        if st.button("🗑️ Xóa đơn hàng", use_container_width=True):
                            order_code = str(selected_order.get("maOrder", "")).strip()
                            if order_code:
                                row_number = get_sheet_row_number(orders, "maOrder", order_code)
                                if row_number is not None:
                                    donhang_sheet.delete_rows(row_number)
                                    clear_admin_order_cache()
                                    st.success(f"Đã xóa đơn {order_code}. Hãy bấm làm mới trang thủ công để cập nhật bảng.")
                    with action_row[1]:
                        if st.button("✏️ Chỉnh sửa đơn hàng", use_container_width=True):
                            st.session_state["editing_order_code"] = str(selected_order.get("maOrder", "")).strip()
                            st.rerun()
                    with action_row[2]:
                        if st.button("✅ Chọn đơn để xác nhận", use_container_width=True):
                            st.session_state["batch_confirm_dialog"] = True
                            st.rerun()
    except Exception as e:
        st.error(f"Lỗi tải danh sách đơn: {e}")

# ==============================================================================
# TAB 3: CRUD DANH MỤC MÓN ĂN & HÌNH ẢNH
# ==============================================================================
with tab3:
    st.header("🥛 Quản Lý Danh Mục Món Ăn")
    try:
        monan_sheet = sh.worksheet("Menu")
        ds_mon = monan_sheet.get_all_records()

        if "editing_food_idx" not in st.session_state:
            st.session_state["editing_food_idx"] = None

        def render_edit_dialog(food_row, row_index):
            if hasattr(st, "dialog"):
                @st.dialog(f"Chỉnh sửa món: {food_row.get('nguyenlieu', 'Món ăn')}")
                def _dialog():
                    with st.form(f"form_edit_mon_{row_index}"):
                        ten_mon_cap_nhat = st.text_input(
                            "Tên món sữa hạt:",
                            value=str(food_row.get("nguyenlieu", "") or ""),
                        )
                        mota_mon_cap_nhat = st.text_area(
                            "Mô tả:",
                            value=str(food_row.get("MoTa", "") or ""),
                        )
                        link_anh_cap_nhat = st.text_input(
                            "Link hình ảnh (URL):",
                            value=str(food_row.get("hinhanh", "") or ""),
                        )

                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            save_clicked = st.form_submit_button("💾 Lưu")
                        with col_cancel:
                            cancel_clicked = st.form_submit_button("❌ Hủy")

                        if cancel_clicked:
                            st.session_state["editing_food_idx"] = None
                            st.rerun()

                        if save_clicked:
                            ten_moi = ten_mon_cap_nhat.strip()
                            if ten_moi:
                                row_number = row_index + 2
                                monan_sheet.update_cell(row_number, 1, ten_moi)
                                monan_sheet.update_cell(row_number, 2, link_anh_cap_nhat)
                                monan_sheet.update_cell(row_number, 3, mota_mon_cap_nhat)
                                st.session_state["editing_food_idx"] = None
                                st.success(f"Chỉnh sửa {ten_moi} thành công")
                                st.rerun()
                            else:
                                st.warning("Vui lòng nhập tên món!")

                _dialog()
            else:
                with st.expander("✏️ Chỉnh sửa món"):
                    with st.form(f"fallback_form_edit_mon_{row_index}"):
                        ten_mon_cap_nhat = st.text_input(
                            "Tên món sữa hạt:",
                            value=str(food_row.get("nguyenlieu", "") or ""),
                        )
                        mota_mon_cap_nhat = st.text_area(
                            "Mô tả:",
                            value=str(food_row.get("MoTa", "") or ""),
                        )
                        link_anh_cap_nhat = st.text_input(
                            "Link hình ảnh (URL):",
                            value=str(food_row.get("hinhanh", "") or ""),
                        )
                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            save_clicked = st.form_submit_button("💾 Lưu")
                        with col_cancel:
                            cancel_clicked = st.form_submit_button("❌ Hủy")

                        if cancel_clicked:
                            st.session_state["editing_food_idx"] = None
                            st.rerun()

                        if save_clicked:
                            ten_moi = ten_mon_cap_nhat.strip()
                            if ten_moi:
                                row_number = row_index + 2
                                monan_sheet.update_cell(row_number, 1, ten_moi)
                                monan_sheet.update_cell(row_number, 2, link_anh_cap_nhat)
                                monan_sheet.update_cell(row_number, 3, mota_mon_cap_nhat)
                                st.session_state["editing_food_idx"] = None
                                st.success(f"Chỉnh sửa {ten_moi} thành công")
                                st.rerun()
                            else:
                                st.warning("Vui lòng nhập tên món!")

        # 1. CREATE (Thêm món mới)
        with st.expander("➕ Thêm Món Ăn Mới"):
            with st.form("form_add_mon"):
                ten_mon_moi = st.text_input("Tên món sữa hạt:")
                mota_mon = st.text_area("Mô tả:")
                link_anh = st.text_input("Link hình ảnh (URL):")

                if st.form_submit_button("Thêm Món"):
                    if ten_mon_moi:
                        monan_sheet.append_row([ten_mon_moi, link_anh, mota_mon])
                        st.success("Đã thêm món mới thành công!")
                        st.rerun()
                    else:
                        st.warning("Vui lòng nhập tên món!")

        # 2. READ, EDIT & DELETE (Xem danh sách món, chỉnh sửa, xóa)
        st.subheader("📋 Danh sách các món hiện có")
        if ds_mon:
            current_edit_idx = st.session_state.get("editing_food_idx")
            if current_edit_idx is not None and 0 <= current_edit_idx < len(ds_mon):
                render_edit_dialog(ds_mon[current_edit_idx], current_edit_idx)

            for idx, mon in enumerate(ds_mon):
                c1, c2, c3 = st.columns([2, 4, 2])
                with c1:
                    if mon.get("hinhanh"):
                        st.image(mon["hinhanh"], width=100)
                    else:
                        st.write("🖼️ (Chưa có ảnh)")
                with c2:
                    st.markdown(f"**{mon.get('nguyenlieu')}**")
                    st.caption(mon.get("MoTa", ""))
                with c3:
                    if st.button("🗑️ Xóa", key=f"del_mon_{idx}"):
                        monan_sheet.delete_rows(idx + 2)
                        st.success("Đã xóa món!")
                        st.rerun()

                    if st.button("✏️ Chỉnh sửa", key=f"edit_btn_{idx}"):
                        st.session_state["editing_food_idx"] = idx
                        st.rerun()

                st.divider()
    except Exception as e:
        st.error(f"Lỗi quản lý món ăn: {e}")