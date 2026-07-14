"""
Địa chỉ server API (host/port) đọc/ghi qua 1 file JSON cục bộ — KHÔNG lưu
trong database local, để đổi được ngay cả khi chưa/không kết nối được DB.
Cùng convention với db/local_db_config.json (file JSON cạnh module, đọc lại
mỗi lần mở app).
"""

import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_config.json")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 3979


def load_server_config():
    """Đọc host/port hiện tại. Trả về giá trị mặc định nếu file chưa tồn tại
    (lần đầu chạy trên 1 máy mới)."""
    if not os.path.exists(CONFIG_PATH):
        return {"host": DEFAULT_HOST, "port": DEFAULT_PORT}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        "host": data.get("host") or DEFAULT_HOST,
        "port": data.get("port") or DEFAULT_PORT,
    }


def save_server_config(host, port=DEFAULT_PORT):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"host": host, "port": port}, f, ensure_ascii=False, indent=2)
