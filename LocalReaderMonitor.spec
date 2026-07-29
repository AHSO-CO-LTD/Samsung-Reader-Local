# -*- mode: python ; coding: utf-8 -*-
#
# Build: pyinstaller LocalReaderMonitor.spec --noconfirm
# (Không gọi "pyinstaller main.py ..." trực tiếp bằng tham số dòng lệnh —
# mọi tuỳ chọn đóng gói (icon, datas, onedir/--windowed) đã cố định trong
# file này để build ra kết quả giống nhau giữa các máy và CI.)
#
# --onedir (không phải --onefile): xem app_paths.py — onefile giải nén lại
# vào 1 thư mục tạm ngẫu nhiên mỗi lần chạy, làm mất hết config/DB đã lưu
# giữa các lần mở app.
#
# datas: liệt kê đúng những gì app_paths.get_bundle_dir() + ui/main_window.py,
# ui/config_window.py, ui/register_window.py, main.py cần đọc lúc chạy (.ui,
# icon mũi tên combobox, icon logo .exe/cửa sổ, âm thanh OK/NG, schema.sql).
# KHÔNG bundle 4 file config JSON thật (local_db_config.json/server_config.json/
# readers_config.json/hid_scanner_config.json) — các file đó do setup.ps1/app tự
# sinh cạnh .exe lúc cài đặt/chạy thật, đưa vào đây sẽ rò rỉ cấu hình riêng máy
# và mật khẩu DB của máy dev vào bản build.
#
# PyNaCl 1.5.0 nạp _cffi_backend gián tiếp từ nacl._sodium. hook-nacl của
# _pyinstaller_hooks_contrib chỉ gom file nacl, không khai báo extension này là
# hidden import. Phải liệt kê tường minh để build trên runner CI sạch không lỗi
# ModuleNotFoundError lúc app import licensing/license_client.py.

datas = [
    ("ui/main_window.ui", "ui"),
    ("ui/config_window.ui", "ui"),
    ("ui/register_window.ui", "ui"),
    ("ui/mapping_window.ui", "ui"),
    ("ui/reconcile_window.ui", "ui"),
    ("ui/icons", "ui/icons"),
    ("ui/logo", "ui/logo"),
    ("sound", "sound"),
    ("db/schema.sql", "db"),
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=["_cffi_backend"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LocalReaderMonitor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="ui/logo/VISION CENTER LOGOLOGO ICON.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="LocalReaderMonitor",
)
