import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler

from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import QApplication

from app_paths import get_bundle_dir, get_writable_dir

LOGO_PATH = os.path.join(get_bundle_dir(), "ui", "logo", "VISION CENTER LOGOLOGO ICON.ico")
LOG_PATH = os.path.join(get_writable_dir(), "app_error.log")


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

    try:
        from ui.main_window import MainWindow  # sau _setup_crash_logging() để bắt được cả lỗi import

        app = QApplication(sys.argv)
        app.setApplicationName("Local Reader Monitor")
        app.setFont(QFont("Segoe UI", 10))
        app.setWindowIcon(QIcon(LOGO_PATH))
        window = MainWindow()
        window.showMaximized()
    except Exception:
        logging.critical("Uncaught exception during startup:\n%s", traceback.format_exc())
        sys.exit(1)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
