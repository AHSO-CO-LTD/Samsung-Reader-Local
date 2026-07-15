"""
2 hàm tính đường dẫn nền tảng cho toàn app — TẤT CẢ module cần đọc/ghi file
cạnh mình (thay vì tự tính os.path.dirname(os.path.abspath(__file__))) phải
dùng 1 trong 2 hàm dưới đây, KHÔNG tự tính riêng.

Lý do tách 2 hàm thay vì 1: khi đóng gói bằng PyInstaller (--onedir), 2 loại
file có ngữ nghĩa khác hẳn nhau và PHẢI trỏ tới 2 nơi khác nhau (đã tự verify
bằng build thật, không phải suy đoán):

- File CẦN ĐỌC/GHI được lúc chạy (3 config JSON, file log lỗi) → phải nằm
  NGAY CẠNH file .exe thật, dễ tìm/sửa/backup, không mất giữa các lần chạy.
  Dùng get_writable_dir().
- File CHỈ ĐỌC do PyInstaller bundle sẵn (.ui, icon, âm thanh, schema.sql)
  → nằm trong _internal/ (mặc định PyInstaller onedir) là đúng rồi, không
  cần dời ra ngoài. Dùng get_bundle_dir().

Nếu dùng lẫn — vd file cần ghi lại tính theo get_bundle_dir() — sẽ lặp lại
đúng lỗi đã verify với onefile: ghi vào chỗ không ổn định, mất dữ liệu giữa
các lần chạy (onedir đỡ hơn onefile nhưng _internal/ vẫn không phải chỗ
"tự nhiên" để người dùng tìm/sửa 1 file cấu hình).
"""

import os
import sys


def get_writable_dir():
    """Nơi chứa file CẦN ĐỌC/GHI được lúc chạy — 3 config JSON
    (local_db_config.json/server_config.json/readers_config.json), file
    log lỗi (app_error.log).

    Chạy từ .exe (PyInstaller --onedir, đã tự verify bằng build thật): đúng
    thư mục CHỨA file .exe, KHÔNG phải _internal/.
    Chạy từ source (python main.py): thư mục gốc project (giữ nguyên hành
    vi __file__-relative hiện tại — main.py nằm ở gốc)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def get_bundle_dir():
    """Nơi chứa file CHỈ ĐỌC được PyInstaller bundle sẵn — .ui, icon, âm
    thanh, schema.sql.

    Chạy từ .exe: sys._MEIPASS (nằm trong _internal/ ở chế độ --onedir —
    đã tự verify vẫn là file rời, sửa tay được sau khi build mà không cần
    rebuild, vì PyQt5 uic.loadUi()/open() đọc file này lúc chạy chứ không
    bị nén vào bytecode).
    Chạy từ source: thư mục gốc project."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))
