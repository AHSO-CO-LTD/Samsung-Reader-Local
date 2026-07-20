import logging
import os
import shutil
import sys
import traceback
from logging.handlers import RotatingFileHandler

from PyQt5.QtCore import QLockFile, Qt
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import QApplication, QMessageBox

from app_paths import get_bundle_dir, get_config_dir, get_writable_dir

LOGO_PATH = os.path.join(get_bundle_dir(), "ui", "logo", "VISION CENTER LOGOLOGO ICON.ico")
LOG_PATH = os.path.join(get_writable_dir(), "app_error.log")
LOCK_PATH = os.path.join(get_writable_dir(), "app.lock")

# Tên file cấu hình từng nằm rải rác ở gốc/cạnh .exe (bản cũ) — nay gộp
# chung vào thư mục config/ (xem app_paths.get_config_dir()). Máy đã chạy
# bản cũ cần được tự động di chuyển sang vị trí mới — xem
# _migrate_legacy_config_files().
_LEGACY_CONFIG_FILENAMES = (
    "local_db_config.json",
    "server_config.json",
    "readers_config.json",
    "hid_scanner_config.json",
    "master_fill_timeout_config.json",
)


def _migrate_legacy_config_files():
    """Di chuyển file cấu hình từng nằm rải rác ở gốc/cạnh .exe (bản cũ)
    sang thư mục config/ mới. Idempotent — gọi lại nhiều lần vô hại: bỏ qua
    file không tồn tại ở vị trí cũ, KHÔNG ghi đè nếu vị trí mới đã có file
    (không mất cấu hình mới hơn nếu lỡ chạy lại bản cũ sau khi đã migrate)."""
    old_dir = get_writable_dir()
    new_dir = get_config_dir()
    for filename in _LEGACY_CONFIG_FILENAMES:
        old_path = os.path.join(old_dir, filename)
        new_path = os.path.join(new_dir, filename)
        if os.path.exists(old_path) and not os.path.exists(new_path):
            shutil.move(old_path, new_path)


def _setup_crash_logging():
    """Bắt mọi exception chưa xử lý, ghi ra app_error.log cạnh .exe — app
    đóng gói chạy --windowed (không có terminal), lỗi không bắt được sẽ
    biến mất hoàn toàn nếu không có hook này.

    2 lớp, vì 2 loại exception đi theo 2 đường khác nhau:
    - sys.excepthook: bắt exception xảy ra TRONG 1 Qt slot lúc event loop
      (app.exec_()) đang chạy — từ PyQt5 5.5, PyQt tự gọi sys.excepthook rồi
      Qt abort tiến trình ngay, không có cách nào ngăn vụ abort, chỉ kịp ghi
      log trước khi tắt.
    - try/except quanh phần khởi động trong main(): bắt exception xảy ra
      TRƯỚC khi event loop chạy (import lỗi, MainWindow() lỗi do thiếu
      config...). Nếu để lọt ra khỏi main() — kể cả khi sys.excepthook đã
      log xong — bootloader PyInstaller bản --windowed (runw.exe) tự hiện
      thêm hộp thoại "Unhandled exception in script" của riêng nó, bất kể
      sys.excepthook đã làm gì (verify bằng build thật). gọi sys.exit()
      tường minh trong except tránh được hộp thoại đó vì SystemExit không
      bị bootloader coi là "unhandled exception"."""
    handler = RotatingFileHandler(LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)

    def _hook(exc_type, exc_value, exc_tb):
        logging.critical(
            "Uncaught exception:\n%s",
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
        )

    sys.excepthook = _hook


def main():
    _setup_crash_logging()

    # Qt >=5.14 (đang dùng PyQt5 5.15.11) đã tự bật AA_EnableHighDpiScaling
    # mặc định — không cần set lại. 2 dòng dưới đây chỉ giảm mờ/lệch khi màn
    # hình dùng tỷ lệ scale lẻ (125%/150% phổ biến trên laptop) — PHẢI đặt
    # TRƯỚC khi tạo QApplication.
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setApplicationName("Local Reader Monitor")
    app.setFont(QFont("Segoe UI", 10))
    app.setWindowIcon(QIcon(LOGO_PATH))

    # Chặn mở 2 instance cùng lúc trên 1 máy — mở 2 lần sẽ khiến 2 tiến trình
    # cùng giành kết nối TCP tới 3 đầu đọc thật, cùng ghi đè local_app_settings
    # (bảng chỉ 1 dòng), và cùng gửi heartbeat/identity-status lên server với
    # cùng machine_code. Dùng QLockFile (PyQt5, không cần thêm dependency như
    # pywin32) thay vì Mutex kiểu Windows — QLockFile tự phát hiện lock cũ do
    # tiến trình trước bị crash để lại (PID trong lock file không còn sống) và
    # tự dọn, không cần code thêm.
    lock_file = QLockFile(LOCK_PATH)
    if not lock_file.tryLock(100):
        QMessageBox.warning(
            None, "Local Reader Monitor",
            "Ứng dụng đã đang chạy trên máy này — chỉ được mở 1 cửa sổ cùng lúc.",
        )
        sys.exit(0)

    try:
        _migrate_legacy_config_files()

        from ui.main_window import MainWindow  # sau _setup_crash_logging() để bắt được cả lỗi import

        window = MainWindow()
        window.showMaximized()
    except Exception:
        logging.critical("Uncaught exception during startup:\n%s", traceback.format_exc())
        sys.exit(1)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
