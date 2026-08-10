import json
import os

from app_paths import get_config_dir

DEFAULT_STORE_PATH = os.path.join(get_config_dir(), "readers_config.json")

# Vai trò reader — tách khỏi tên (identity). LED_BAR: không giới hạn số
# lượng, cột hiển thị (ledbar1/ledbar2) xác định qua nội dung mã lúc chạy
# (xem ui/main_window.py:_classify_led_bar), không qua tên reader. QR_BOTTOM:
# đúng 1 reader tại 1 thời điểm, luôn map thẳng cột qrbottom.
ROLE_LED_BAR = "LED_BAR"
ROLE_QR_BOTTOM = "QR_BOTTOM"

LED_BAR_NAME_PREFIX = "LED BAR "
QR_BOTTOM_NAME = "QRCODE BOTTOM"

ROLE_DISPLAY_LABELS = {ROLE_LED_BAR: "LED BAR", ROLE_QR_BOTTOM: "QRCODE BOTTOM"}


def infer_role_from_name(name):
    """Suy role cho entry cũ (trước khi có field 'role' trong JSON, lúc hệ
    thống còn cố định đúng 3 tên reader) — tên đúng bằng QR_BOTTOM_NAME thì
    là QR_BOTTOM, còn lại (vd "LED BAR 1"/"LED BAR 2") là LED_BAR."""
    return ROLE_QR_BOTTOM if name == QR_BOTTOM_NAME else ROLE_LED_BAR


def load_readers(path=DEFAULT_STORE_PATH):
    """Trả về list[dict] các reader đã lưu, mỗi dict có
    name, ip, data_port, command_port (command_port có thể là None), role.
    Entry cũ thiếu field 'role' (file lưu trước refactor multi-reader) được
    tự suy role theo tên NGAY LÚC ĐỌC — không ghi đè lại file ở đây, chỉ
    ghi thật khi save_readers() được gọi lần kế tiếp (vd lúc add/remove
    reader qua Config Window)."""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        readers = json.load(f)
    for entry in readers:
        entry.setdefault("role", infer_role_from_name(entry.get("name", "")))
        # Entry cũ (trước khi có tính năng Master/Slave) mặc định KHÔNG phải
        # Master — xem ui/main_window.py: _is_master_mode_active()/
        # _detect_role_from_content().
        entry.setdefault("is_master", False)
    return readers


def save_readers(readers, path=DEFAULT_STORE_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(readers, f, indent=2, ensure_ascii=False)


HID_SCANNER_CONFIG_PATH = os.path.join(get_config_dir(), "hid_scanner_config.json")
DEFAULT_HID_SCAN_MAX_GAP_SEC = 0.25
DEFAULT_HID_SCAN_MIN_LENGTH = 4


def _read_hid_scanner_config(path=HID_SCANNER_CONFIG_PATH):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_hid_scanner_config_field(key, value, path=HID_SCANNER_CONFIG_PATH):
    # Đọc lại rồi chỉ cập nhật 1 field trước khi ghi — file này giờ giữ
    # chung nhiều field (enabled/max_gap_sec/min_length); ghi đè thẳng
    # {key: value} như bản cũ sẽ xoá mất các field khác đã lưu trước đó.
    data = _read_hid_scanner_config(path)
    data[key] = value
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_hid_scanner_enabled(path=HID_SCANNER_CONFIG_PATH):
    return _read_hid_scanner_config(path).get("enabled", True)  # mặc định BẬT


def save_hid_scanner_enabled(enabled, path=HID_SCANNER_CONFIG_PATH):
    _write_hid_scanner_config_field("enabled", enabled, path)


def load_hid_scan_max_gap_sec(path=HID_SCANNER_CONFIG_PATH):
    """Khoảng cách tối đa (giây) giữa 2 phím liên tiếp để còn tính là 1 lần
    quét từ máy quét HID — xem ui/main_window.py eventFilter(). Có thể cần
    chỉnh khác nhau tuỳ model máy quét vật lý gắn ở từng trạm."""
    return _read_hid_scanner_config(path).get("max_gap_sec", DEFAULT_HID_SCAN_MAX_GAP_SEC)


def save_hid_scan_max_gap_sec(seconds, path=HID_SCANNER_CONFIG_PATH):
    _write_hid_scanner_config_field("max_gap_sec", seconds, path)


def load_hid_scan_min_length(path=HID_SCANNER_CONFIG_PATH):
    """Độ dài tối thiểu để tính là 1 lần quét hợp lệ (tránh bắt nhầm Enter
    đơn lẻ) — xem ui/main_window.py eventFilter()."""
    return _read_hid_scanner_config(path).get("min_length", DEFAULT_HID_SCAN_MIN_LENGTH)


def save_hid_scan_min_length(length, path=HID_SCANNER_CONFIG_PATH):
    _write_hid_scanner_config_field("min_length", length, path)


# Chế độ Master relay im lặng (không gửi gì, không cả "ERROR") cho vị trí
# trạm vật lý đọc lỗi — khác TCP độc lập, nơi mỗi reader luôn tự gửi "ERROR"
# tường minh. Timeout này (tính từ mã ĐẦU TIÊN của phiên, không reset khi có
# mã mới tới) cho phép tự điền SCAN_FAILED cho vị trí còn thiếu sau khi hết
# giờ chờ — xem ui/main_window.py:_on_master_fill_timeout().
MASTER_FILL_TIMEOUT_CONFIG_PATH = os.path.join(get_config_dir(), "master_fill_timeout_config.json")
DEFAULT_MASTER_FILL_TIMEOUT_SECONDS = 3.0


def load_master_fill_timeout_seconds(path=MASTER_FILL_TIMEOUT_CONFIG_PATH):
    if not os.path.exists(path):
        return DEFAULT_MASTER_FILL_TIMEOUT_SECONDS
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("seconds", DEFAULT_MASTER_FILL_TIMEOUT_SECONDS)


def save_master_fill_timeout_seconds(seconds, path=MASTER_FILL_TIMEOUT_CONFIG_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"seconds": seconds}, f, indent=2)


# Trong lúc ô tìm Chassis Rear đang có focus, eventFilter() không bắt phím
# HID (xem docstring eventFilter trong main_window.py) — timer này tự đóng ô
# tìm kiếm sau 1 khoảng không tương tác để thu hẹp khoảng hở đó.
CHASSIS_SEARCH_CONFIG_PATH = os.path.join(get_config_dir(), "chassis_search_config.json")
DEFAULT_CHASSIS_SEARCH_IDLE_TIMEOUT_MS = 5000


def load_chassis_search_idle_timeout_ms(path=CHASSIS_SEARCH_CONFIG_PATH):
    if not os.path.exists(path):
        return DEFAULT_CHASSIS_SEARCH_IDLE_TIMEOUT_MS
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("idle_timeout_ms", DEFAULT_CHASSIS_SEARCH_IDLE_TIMEOUT_MS)


def save_chassis_search_idle_timeout_ms(ms, path=CHASSIS_SEARCH_CONFIG_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"idle_timeout_ms": ms}, f, indent=2)


# Thời gian giữ nguyên hiển thị/âm báo OK trước khi tự chuyển sang mã tiếp
# theo trong hàng đợi Rework — xem ui/main_window.py:_handle_rework_submit_result().
REWORK_CONFIG_PATH = os.path.join(get_config_dir(), "rework_config.json")
DEFAULT_REWORK_ADVANCE_DELAY_MS = 1500


def load_rework_advance_delay_ms(path=REWORK_CONFIG_PATH):
    if not os.path.exists(path):
        return DEFAULT_REWORK_ADVANCE_DELAY_MS
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("advance_delay_ms", DEFAULT_REWORK_ADVANCE_DELAY_MS)


def save_rework_advance_delay_ms(ms, path=REWORK_CONFIG_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"advance_delay_ms": ms}, f, indent=2)


# Số lượng scan tối đa gộp trong 1 batch submit lên server — xem
# ui/main_window.py:_maybe_start_sync_batch(). Site mạng yếu có thể cần
# batch nhỏ hơn để giảm rủi ro timeout.
SYNC_CONFIG_PATH = os.path.join(get_config_dir(), "sync_config.json")
DEFAULT_BATCH_SUBMIT_MAX_SIZE = 200


def load_batch_submit_max_size(path=SYNC_CONFIG_PATH):
    if not os.path.exists(path):
        return DEFAULT_BATCH_SUBMIT_MAX_SIZE
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("max_size", DEFAULT_BATCH_SUBMIT_MAX_SIZE)


def save_batch_submit_max_size(size, path=SYNC_CONFIG_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"max_size": size}, f, indent=2)
