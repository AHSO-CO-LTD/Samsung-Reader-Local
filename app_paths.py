"""
3 hàm tính đường dẫn nền tảng cho toàn app — TẤT CẢ module cần đọc/ghi file
cạnh mình (thay vì tự tính os.path.dirname(os.path.abspath(__file__))) phải
dùng 1 trong 3 hàm dưới đây, KHÔNG tự tính riêng.

Lý do tách get_writable_dir()/get_bundle_dir() thay vì 1 hàm: khi đóng gói
bằng PyInstaller (--onedir), 2 loại file có ngữ nghĩa khác hẳn nhau và PHẢI
trỏ tới 2 nơi khác nhau (đã tự verify bằng build thật, không phải suy đoán):

- File CẦN ĐỌC/GHI được lúc chạy (file cấu hình JSON, file log lỗi) → phải
  nằm NGAY CẠNH file .exe thật, dễ tìm/sửa/backup, không mất giữa các lần
  chạy. Dùng get_writable_dir().
- File CHỈ ĐỌC do PyInstaller bundle sẵn (.ui, icon, âm thanh, schema.sql)
  → nằm trong _internal/ (mặc định PyInstaller onedir) là đúng rồi, không
  cần dời ra ngoài. Dùng get_bundle_dir().

Nếu dùng lẫn — vd file cần ghi lại tính theo get_bundle_dir() — sẽ lặp lại
đúng lỗi đã verify với onefile: ghi vào chỗ không ổn định, mất dữ liệu giữa
các lần chạy (onedir đỡ hơn onefile nhưng _internal/ vẫn không phải chỗ
"tự nhiên" để người dùng tìm/sửa 1 file cấu hình).

get_config_dir() là 1 thư mục con của get_writable_dir() — gộp CHUNG 1 chỗ
mọi file cấu hình JSON riêng từng máy (trước đây rải rác từng file rời ở
gốc, mỗi module tự tính path riêng) để dễ backup/di chuyển cả cụm khi đổi
máy. File cũ ở vị trí rải rác được tự động di chuyển sang đây 1 lần lúc
khởi động — xem main.py:_migrate_legacy_config_files().
"""

import os
import sys


def get_writable_dir():
    """Nơi chứa file CẦN ĐỌC/GHI được lúc chạy — thư mục con config/ (xem
    get_config_dir()), file log lỗi (app_error.log), file khoá (app.lock).

    Chạy từ .exe (PyInstaller --onedir, đã tự verify bằng build thật): đúng
    thư mục CHỨA file .exe, KHÔNG phải _internal/.
    Chạy từ source (python main.py): thư mục gốc project (giữ nguyên hành
    vi __file__-relative hiện tại — main.py nằm ở gốc)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def get_config_dir():
    """Thư mục con "config" chứa MỌI file cấu hình JSON riêng từng máy —
    local_db_config.json/server_config.json/readers_config.json/
    hid_scanner_config.json/master_fill_timeout_config.json — gộp chung 1
    chỗ (trước đây rải rác từng file rời ở gốc) để dễ backup/di chuyển cả
    cụm khi đổi máy. Tự tạo thư mục nếu chưa có, gọi lại nhiều lần vô hại
    (os.makedirs(exist_ok=True))."""
    path = os.path.join(get_writable_dir(), "config")
    os.makedirs(path, exist_ok=True)
    return path


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
