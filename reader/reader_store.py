import json
import os

from app_paths import get_writable_dir

DEFAULT_STORE_PATH = os.path.join(get_writable_dir(), "readers_config.json")

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
    return readers


def save_readers(readers, path=DEFAULT_STORE_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(readers, f, indent=2, ensure_ascii=False)


HID_SCANNER_CONFIG_PATH = os.path.join(get_writable_dir(), "hid_scanner_config.json")


def load_hid_scanner_enabled(path=HID_SCANNER_CONFIG_PATH):
    if not os.path.exists(path):
        return True  # mặc định BẬT
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("enabled", True)


def save_hid_scanner_enabled(enabled, path=HID_SCANNER_CONFIG_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"enabled": enabled}, f, indent=2)
