import streamlit as st
import gspread
from datetime import datetime
import pytz
import json
import re
import unicodedata
import config as cfg
from pathlib import Path
from datetime import timedelta
from uuid import uuid4


def parse_date(value):
    for date_format in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value).strip(), date_format).date()
        except ValueError:
            continue
    return None


def get_order_week_start(current_time):
    week_start = current_time.date() - timedelta(days=current_time.weekday())
    if current_time.weekday() == 5 and current_time.hour >= 12:
        week_start += timedelta(days=7)
    elif current_time.weekday() == 6:
        week_start += timedelta(days=7)
    return week_start


def find_column(headers, names):
    for name in names:
        if name in headers:
            return headers.index(name)
    return None


def normalize_column_name(value):
    normalized = unicodedata.normalize("NFKD", str(value))
    normalized = normalized.replace("đ", "d").replace("Đ", "D")
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]", "", normalized.lower())


def get_normalized_value(row, names, default=""):
    normalized_names = {normalize_column_name(name) for name in names}
    for key, value in row.items():
        if normalize_column_name(key) in normalized_names and value not in (None, ""):
            return value
    return default


def get_value(row, names, default=""):
    for name in names:
        if row.get(name) not in (None, ""):
            return row.get(name)
    return default


def normalize_phone(value):
    phone = re.sub(r"[^0-9+]", "", str(value).strip())
    if phone.startswith("+84"):
        phone = "0" + phone[3:]
    elif phone.startswith("84"):
        phone = "0" + phone[2:]
    return phone


def is_valid_vietnamese_phone(value):
    return bool(re.fullmatch(r"0(?:3|5|7|8|9)\d{8}", value))


def is_account_locked(value):
    normalized_value = normalize_column_name(value)
    return normalized_value in {"1", "true", "yes", "khoa", "bikhoa", "dakhoa"}


def is_old_order(value):
    normalized_value = normalize_column_name(value)
    return normalized_value in {"1", "true", "yes", "cu", "doncu"}


def normalize_payment_status(value):
    normalized_value = normalize_column_name(value)
    if normalized_value in {"dathanhtoan", "thanhtoan", "paid"}:
        return "Đã thanh toán"
    return "Chưa thanh toán"


def build_order_items(selected_dates, menu_by_date):
    return " | ".join(
        f"{menu_by_date[menu_date]['day']} ({menu_date.strftime('%d/%m/%Y')}) - {menu_by_date[menu_date]['food']}"
        for menu_date in selected_dates
    )


def format_order_items(value, menu_dates=None):
    items = [item.strip() for item in str(value or "").split("|") if item.strip()]
    if not menu_dates:
        return items

    day_names = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]
    dated_items = []
    for item in items:
        if re.search(r"\(\d{2}/\d{2}(?:/\d{4})?\)", item):
            dated_items.append(item)
            continue
        dated_item = item
        for day_index, day_name in enumerate(day_names):
            if item.lower().startswith(f"{day_name.lower()} -") and day_index < len(menu_dates):
                dated_item = item.replace(
                    f"{day_name} -",
                    f"{day_name} ({menu_dates[day_index].strftime('%d/%m/%Y')}) -",
                    1,
                )
                break
        dated_items.append(dated_item)
    return dated_items


def get_order_item_date(item, reference_year):
    date_match = re.search(r"\((\d{2}/\d{2})(?:/(\d{4}))?\)", item)
    if not date_match:
        return None
    year = int(date_match.group(2) or reference_year)
    try:
        return datetime.strptime(f"{date_match.group(1)}/{year}", "%d/%m/%Y").date()
    except ValueError:
        return None


def split_current_and_history_items(value, week_dates):
    current_items = []
    history_items = []
    for item in format_order_items(value, week_dates):
        item_date = get_order_item_date(item, week_dates[0].year)
        if item_date in week_dates:
            current_items.append(item)
        else:
            history_items.append(item)
    return current_items, history_items


def parse_prices(value):
    prices = []
    raw_value = str(value).strip()
    if re.search(r"[,;|/\n]", raw_value):
        price_items = re.split(r"[,;|/\n]+", raw_value)
    else:
        price_items = re.findall(r"\d[\d.]*\s*(?:đ|d|k)?", raw_value, re.IGNORECASE)

    for item in price_items:
        item = item.strip()
        if not item:
            continue
        try:
            numeric_value = re.sub(r"[^0-9]", "", item)
            if numeric_value and int(numeric_value) > 0:
                price_value = int(numeric_value)
                price_label = f"{price_value:,}".replace(",", ".")
                prices.append((price_label, price_value))
        except ValueError:
            continue
    return prices


# Giao diện web
logo_path = Path(__file__).parent / "suahat.jpg"
bank_image_path = Path(__file__).parent / "bank.jpg"
st.markdown(
    """
    <style>
    div[data-testid="stImage"] {
        display: flex;
        justify-content: center;
        align-items: center;
    }
    div[data-testid="stImage"] img {
        display: block;
        margin: 0 auto;
        max-width: 100%;
        height: auto;
    }
    h1 {
        text-align: center;
        margin: 0.3rem 0 0.8rem;
        font-size: clamp(1.2rem, 2.5vw, 2.2rem);
        line-height: 0.8;
    }
    .logo-header {
        width: min(100%, 520px);
        margin: 0 auto 0.5rem auto;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.image(str(logo_path), width=420, use_container_width=False)
st.markdown("<h1>Order Sữa ạt</h1>", unsafe_allow_html=True)
if not st.session_state.get("checked_phone") and not st.session_state.get("order_submitted"):
    st.write("Vui lòng nhập số điện thoại để kiểm tra hoặc tạo order")

if st.session_state.get("order_submitted"):
    order_result = st.session_state["order_result"]
    st.toast("Order đã được ghi nhận thành công!", icon="🎉")
    st.success(
        f"🎉 Order thành công! Mã order: {order_result['code']}\n\n"
        f"Món đã đặt: {order_result['items']}\n\n"
        f"Tổng số tiền: {order_result['total']:,}đ\n\n"
        f"Trạng thái thanh toán tiền: {order_result['payment']}".replace(",", ".")
    )
    if bank_image_path.exists():
        st.image(str(bank_image_path), caption="Thông tin chuyển khoản", width=320)
    st.stop()

tz_vn = pytz.timezone("Asia/Ho_Chi_Minh")
now = datetime.now(tz_vn)
today = now.date()
start_of_week = get_order_week_start(now)
week_dates = [start_of_week + timedelta(days=day) for day in range(7)]
day_names = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]

st.markdown(
    """
    <style>
    .order-intro, .order-day, .order-day * {
        font-size: 1.12rem;
    }
    .order-day {
        padding: 0.7rem 0.8rem;
        color: #ffffff;
        border-radius: 0.45rem;
        font-size: 1.15rem;
    }
    .order-product {
        padding: 0.75rem 0.8rem;
        color: #ffffff;
        border-radius: 0.45rem;
        font-size: 1.55rem;
        font-weight: 800;
    }
    .order-day-title {
        font-size: 1.25rem;
        font-weight: 700;
    }
    .stCheckbox label, .stRadio label {
        font-size: 1.12rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <style>
    div.stButton > button, div.stFormSubmitButton > button {
        width: 100%;
        min-height: 3rem;
        border-radius: 0.6rem;
        font-size: 1.08rem;
        font-weight: 700;
        border: 1px solid #147d92;
        background: #e4f6f8;
        color: #075766;
        transition: background 0.2s ease, transform 0.2s ease;
    }
    div.stButton > button:hover, div.stFormSubmitButton > button:hover {
        background: #bdeaf0;
        color: #064653;
        transform: translateY(-1px);
    }
    div.stButton > button[kind="primary"], div.stFormSubmitButton > button[kind="primary"] {
        background: #0f8b8d;
        border-color: #0f8b8d;
        color: white;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

try:
    workbook = cfg.get_spreadsheet()
    _, menu_rows = cfg.get_sheet_data("MenuTuan")
    _, food_rows = cfg.get_sheet_data("Menu")
    _, price_rows = cfg.get_sheet_data("GiaTien")
    food_details = {
        str(row.get("nguyenlieu")).strip(): row
        for row in food_rows
    }
    common_prices = []
    for row in price_rows:
        common_prices.extend(parse_prices(row.get("GiaSP") or ""))

    unique_prices = []
    seen_price_values = set()
    for price_label, price_value in common_prices:
        if price_value not in seen_price_values:
            unique_prices.append((price_label, price_value))
            seen_price_values.add(price_value)

    menu_by_date = {}
    for row in menu_rows:
        menu_date = parse_date(row.get("Ngay"))
        if menu_date in week_dates:
            food_name = row.get("MonAn") or "-- Không bán --"
            food_data = food_details.get(str(food_name).strip(), {})
            menu_by_date[menu_date] = {
                "day": row.get("Thu") or row.get("Thứ") or day_names[week_dates.index(menu_date)],
                "food": food_name,
                "image": food_data.get("hinhanh"),
                "description": food_data.get("MoTa")or "",
                "prices": unique_prices,
                "locked": str(row.get("TrangThai") or "").strip().lower() == "đóng",
            }
except Exception as error:
    st.error(f"Không thể đọc menu tuần: {error}")
    st.stop()

saved_phone = st.session_state.get("checked_phone", "")
saved_users = st.session_state.get("user_matches", [])
saved_user = saved_users[0]["data"] if saved_users else {}
has_verified_order = bool(
    saved_phone
    and saved_users
    and get_value(saved_user, ["maOrder"])
)

if has_verified_order:
    sdt = saved_phone
    ten = get_value(saved_user, ["ten"], "").strip()
else:
    phone_input = st.text_input("Số điện thoại (bắt buộc):", key="customer_phone").strip()
    sdt = normalize_phone(phone_input)
    has_checked_phone = bool(sdt and saved_phone == sdt)
    ten = ""
    if has_checked_phone:
        ten = st.text_input("Tên khách hàng:", key="customer_name").strip()

if has_verified_order:
    has_checked_phone = True

check_clicked = False
if not has_verified_order and not has_checked_phone:
    check_clicked = st.button("Kiểm tra", type="primary", use_container_width=True)
    st.page_link("pages/quan_tri.py", label="Quản trị", icon="🔐")

if not has_verified_order and not has_checked_phone and check_clicked:
    if not sdt:
        st.session_state.checked_phone = ""
        st.session_state.registration_confirmed = False
        st.error("Vui lòng nhập số điện thoại để kiểm tra.")
    elif not is_valid_vietnamese_phone(sdt):
        st.error("Số điện thoại không hợp lệ. Vui lòng nhập số điện thoại Việt Nam 10 số.")
    else:
        try:
            user_sheet = workbook.worksheet("NguoiDung")
            user_values, user_rows = cfg.get_sheet_data("NguoiDung")
            user_headers = user_values[0] if user_values else []
            user_phone_key = next(
                (key for key in user_headers if normalize_column_name(key) == "dienthoai"),
                None,
            )
            if user_phone_key is None:
                st.error(f"Sheet NguoiDung cần có cột dienthoai. Các cột hiện có: {', '.join(user_headers)}")
                st.stop()

            user_matches = [
                {"row_number": row_number, "data": row}
                for row_number, row in enumerate(user_rows, start=2)
                if normalize_phone(get_normalized_value(row, ["dienthoai"], "")) == sdt
            ]
            if user_matches:
                user_data = user_matches[0]["data"]
                account_locked = is_account_locked(
                    get_normalized_value(user_data, ["trangthaitaikhoan"], "0")
                )
                if account_locked:
                    st.session_state.account_locked = True
                    st.session_state.checked_phone = sdt
                    st.rerun()
                st.session_state.account_locked = False
            else:
                st.session_state.account_locked = False

            donhang_sheet = workbook.worksheet("DonHang")
            _, orders = cfg.get_sheet_data("DonHang")
            order_code = get_value(user_matches[0]["data"], ["maOrder"], "") if user_matches else ""
            matching_orders = [
                {"row_number": row_number, "data": row}
                for row_number, row in enumerate(orders, start=2)
                if order_code and str(row.get("maOrder", "")).strip() == str(order_code).strip()
            ]
            st.session_state.checked_phone = sdt
            st.session_state.customer_orders = matching_orders
            st.session_state.user_matches = user_matches
            st.session_state.registration_confirmed = bool(user_matches)
            st.rerun()
        except Exception as error:
            st.error(f"Không thể kiểm tra đơn hàng: {error}")

if st.session_state.get("account_locked") and st.session_state.get("checked_phone") == sdt:
    st.error("Tài khoản bị khóa, vui lòng liên hệ quản trị viên.")
    st.stop()

if st.session_state.get("checked_phone") == sdt and sdt:
    customer_orders = st.session_state.get("customer_orders", [])
    user_matches = st.session_state.get("user_matches", [])
    if customer_orders:
        first_order = customer_orders[0]["data"]
        order_code = get_value(first_order, ["maOrder"], "Chưa có mã order")
        customer_name = next(
            (first_order.get(name) for name in ["tennguoidung", "ten", "Tên", "Ten"] if first_order.get(name)),
            ten or "khách hàng",
        )
        st.success(f"Xin chào bạn: {customer_name} - Số điện thoại: {sdt}")
        st.success(f"Mã order: {order_code}")
        history_items = []
        seen_history_items = set()
        current_order_details = []
        history_order_details = []
        for order in customer_orders:
            order_current_items, order_history_items = split_current_and_history_items(
                get_normalized_value(order["data"], ["monandadat"], ""),
                week_dates,
            )
            if order_current_items:
                current_order_details.append((order["data"], order_current_items))
            if order_history_items:
                history_order_details.append((order["data"], order_history_items))
            for item in order_history_items:
                if item not in seen_history_items:
                    history_items.append(item)
                    seen_history_items.add(item)

        with st.expander("Lịch sử đặt món"):
            if history_order_details:
                for history_order, order_history_items in history_order_details:
                    st.markdown(f"**Mã order:** {get_value(history_order, ['maOrder'], 'Không rõ')}")
                    st.table({
                        "Món đã đặt": "\n".join(order_history_items),
                        "Thời gian chỉnh sửa": get_normalized_value(
                            history_order, ["thoigianchinhsuacuoi"]
                        ),
                        "Tổng số tiền": get_normalized_value(
                            history_order, ["tongsotien"]
                        ),
                        "Trạng thái thanh toán": get_normalized_value(
                                history_order, ["trangthai"], "Chưa thanh toán"
                        ),
                    })
            else:
                st.caption("Chưa có lịch sử")

        with st.expander("Xem chi tiết order"):
            if current_order_details:
                for order_data, current_items in current_order_details:
                    detail_order = {
                        "Thời gian chỉnh sửa": get_normalized_value(
                            order_data, ["thoigianchinhsuacuoi"]
                        ),
                        "Tổng số tiền": get_normalized_value(
                            order_data, ["tongsotien"]
                        ),
                        "Trạng thái thanh toán": get_normalized_value(
                            order_data, ["trangthai"], "Chưa thanh toán"
                        ),
                        "Trạng thái tài khoản": "Đã khóa" if is_account_locked(
                            get_normalized_value(saved_user, ["trangthaitaikhoan"], "0")
                        ) else "Không bị khóa",
                    }
                    st.table(detail_order)
                    st.markdown("**Món đã đặt trong tuần này**")
                    for item in current_items:
                        st.markdown(f"- {item}")
            else:
                st.caption("Chưa có món cho tuần này")
    else:
        registration_confirmed = st.session_state.get("registration_confirmed", False)
        if not registration_confirmed:
            st.info("Không có order với số điện thoại này. Vui lòng nhập tên để đăng ký.")
            if user_matches:
                st.info("Tài khoản đã tồn tại nhưng chưa có order. Bạn có thể chọn ngày bên dưới.")
            if not ten:
                st.warning("Vui lòng nhập tên khách hàng.")
            if st.button("Đăng ký", type="primary", use_container_width=True) and ten:
                try:
                    user_sheet = workbook.worksheet("NguoiDung")
                    user_values, user_rows = cfg.get_sheet_data("NguoiDung")
                    user_headers = user_values[0] if user_values else []
                    if not user_headers:
                        st.error("Sheet NguoiDung chưa có hàng tiêu đề.")
                        st.stop()
                    new_order_code = f"ORD-{uuid4().hex[:10].upper()}"
                    new_user_row = ["" for _ in user_headers]
                    user_column_values = {
                        "dienthoai": sdt,
                        "ten": ten,
                        "thoigiandathang": now.strftime("%d/%m/%Y %H:%M:%S"),
                        "maOrder": new_order_code,
                        "trangthaitaikhoan": 0,
                    }
                    for index, header in enumerate(user_headers):
                        normalized_header = normalize_column_name(header)
                        for column_name, column_value in user_column_values.items():
                            if normalize_column_name(column_name) == normalized_header:
                                new_user_row[index] = column_value
                                break
                    user_sheet.append_row(new_user_row)
                    st.session_state.user_matches = [{"row_number": len(user_rows) + 2, "data": user_column_values}]
                    cfg.clear_sheet_data_cache()
                    st.session_state.registration_confirmed = True
                except Exception as error:
                    st.error(f"Không thể đăng ký tài khoản: {error}")
                    st.stop()
                st.success("Đã xác nhận thông tin. Vui lòng chọn ngày và bấm Order.")
                st.rerun()

    if not customer_orders and not st.session_state.get("registration_confirmed", False):
        st.stop()

    st.markdown(
        f'<div class="order-intro">Order cho tuần {week_dates[0].strftime("%d/%m")} - {week_dates[-1].strftime("%d/%m/%Y")}</div>',
        unsafe_allow_html=True,
    )
    existing_order_text = " | ".join(str(order["data"].get("monandadat", "")) for order in customer_orders)
    selected_dates = []
    selected_prices = {}
    for day_name, menu_date in zip(day_names, week_dates):
        menu = menu_by_date.get(
            menu_date,
            {"day": day_name, "food": "-- Không bán --", "image": None, "description": "", "prices": [], "locked": False},
        )
        disabled = menu["locked"] or menu["food"] == "-- Không bán --"
        day_label = menu["day"]
        current_order_item = f"{day_label} ({menu_date.strftime('%d/%m/%Y')}) - {menu['food']}"
        previous_order_item = f"{day_label} ({menu_date.strftime('%d/%m')}) - {menu['food']}"
        old_order_item = f"{day_label} - {menu['food']}"
        existing_order_for_date = (
            current_order_item in existing_order_text
            or previous_order_item in existing_order_text
            or old_order_item in existing_order_text
        )
        with st.container(border=True):
            st.markdown(
                f'<div class="order-day-title">{day_label} - {menu_date.strftime("%d/%m/%Y")}</div>',
                unsafe_allow_html=True,
            )
            if menu["image"]:
                st.image(menu["image"], width=210)
            st.markdown(f'<div class="order-product">{menu["food"]}</div>', unsafe_allow_html=True)
            if menu["description"]:
                st.markdown(f'<div class="order-day">{menu["description"]}</div>', unsafe_allow_html=True)

            checked = st.checkbox(
                "Chọn ngày này",
                value=existing_order_for_date,
                disabled=disabled,
                key=f"order_day_{menu_date.isoformat()}",
            )
            if menu["locked"]:
                st.caption("Ngày này đã khóa")
            if checked:
                selected_dates.append(menu_date)

            price_labels = [f"{label}đ" for label, _ in menu["prices"]]
            if price_labels:
                selected_price = st.radio(
                    "Chọn mức giá",
                    price_labels,
                    index=None,
                    disabled=not checked,
                    key=f"price_{menu_date.isoformat()}",
                )
                if checked and selected_price:
                    selected_prices[menu_date] = dict(
                        zip(price_labels, [value for _, value in menu["prices"]])
                    )[selected_price]
            else:
                st.caption("Chưa có giá")
        st.divider()

    if st.button("Order", type="primary", use_container_width=True):
        if not selected_dates:
            st.warning("Vui lòng chọn ít nhất một ngày để order.")
        elif not customer_orders and not ten:
            st.error("Vui lòng nhập tên để tạo order mới.")
        elif any(menu_date not in selected_prices for menu_date in selected_dates):
            missing_price_days = ", ".join(
                menu_by_date[menu_date]["day"]
                for menu_date in selected_dates
                if menu_date not in selected_prices
            )
            st.warning(f"Vui lòng chọn giá tiền cho {missing_price_days}.")
        else:
            try:
                donhang_sheet = workbook.worksheet("DonHang")
                values, order_rows = cfg.get_sheet_data("DonHang")
                headers = values[0] if values else []
                required_columns = ["maOrder", "thoigianchinhsuacuoi", "dienthoai", "tennguoidung", "monandadat", "tongsotien", "trangthai"]
                missing_columns = [column for column in required_columns if column not in headers]
                if missing_columns:
                    st.error(f"DonHang thiếu cột: {', '.join(missing_columns)}")
                    st.stop()

                user_data = user_matches[0]["data"]
                order_code = get_value(user_data, ["maOrder"])
                if not order_code:
                    order_code = f"ORD-{uuid4().hex[:10].upper()}"
                order_items = build_order_items(selected_dates, menu_by_date)
                total_price = sum(
                    selected_prices.get(menu_date, 0)
                    for menu_date in selected_dates
                )
                existing_order = next(
                    (
                        order for order in customer_orders
                        if split_current_and_history_items(
                            get_normalized_value(order["data"], ["monandadat"], ""),
                            week_dates,
                        )[0]
                    ),
                    None,
                )
                order_values = {
                    "maOrder": order_code,
                    "thoigianchinhsuacuoi": now.strftime("%d/%m/%Y %H:%M:%S"),
                    "dienthoai": sdt,
                    "tennguoidung": ten or get_value(user_data, ["ten"]),
                    "monandadat": order_items,
                    "tongsotien": total_price,
                    "trangthai": normalize_payment_status(
                        get_value(
                            existing_order["data"] if existing_order else {},
                            ["trangthai"],
                            "Chưa thanh toán",
                        )
                    ),
                    "doncu": "Đơn mới",
                }
                doncu_column = next(
                    (index for index, header in enumerate(headers)
                     if normalize_column_name(header) == "doncu"),
                    None,
                )
                if doncu_column is None:
                    st.error("DonHang cần có cột doncu để phân biệt đơn mới và đơn cũ.")
                    st.stop()

                if existing_order is None:
                    for old_order in customer_orders:
                        old_row_number = old_order["row_number"]
                        donhang_sheet.update_cell(old_row_number, doncu_column + 1, "Đơn cũ")
                if existing_order:
                    row_number = existing_order["row_number"]
                    for index, header in enumerate(headers):
                        donhang_sheet.update_cell(row_number, index + 1, order_values[header])
                else:
                    donhang_sheet.append_row([order_values[header] for header in headers])

                user_match = user_matches[0]
                user_sheet = workbook.worksheet("NguoiDung")
                user_values, user_rows = cfg.get_sheet_data("NguoiDung")
                user_headers = user_values[0] if user_values else []
                for index, header in enumerate(user_headers):
                    if header == "thoigiandathang":
                        user_sheet.update_cell(user_match["row_number"], index + 1, now.strftime("%d/%m/%Y %H:%M:%S"))
                    elif header == "maOrder":
                        user_sheet.update_cell(user_match["row_number"], index + 1, order_code)
                cfg.clear_sheet_data_cache()
                if customer_orders:
                    st.success("🎉 Order của bạn đã được cập nhật thành công!")
                else:
                    st.success(f"🎉 Order của bạn đã được ghi nhận thành công! Mã order: {order_code}")
                st.write(f"**Món đã đặt:** {order_items}")
                st.write(f"**Tổng số tiền:** {total_price:,.0f}đ".replace(",", "."))
                st.session_state.order_submitted = True
                st.session_state.order_result = {
                    "code": order_code,
                    "items": order_items,
                    "total": total_price,
                    "payment": get_normalized_value(
                        order_values, ["trangthai"], "Chưa thanh toán"
                    ),
                }
                st.rerun()
            except Exception as error:
                st.error(f"Có lỗi khi lưu order: {error}")