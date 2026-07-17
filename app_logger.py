"""
Logger dùng chung ghi VẾT TÍCH FILE cho local_notifications + log kỹ thuật
(_append_log của MainWindow/ConfigWindow/RegisterWindow). TÁCH BIỆT HOÀN
TOÀN khỏi crash logging (main.py: root logger + app_error.log) — propagate=False
để không bị ghi lặp vào app_error.log.

Ghi vào log/ CẠNH .exe (get_writable_dir(), đúng pattern app_paths.py), 1 file
xoay theo ngày, tự xoá sau 30 ngày.
"""
import logging
import os
from logging.handlers import TimedRotatingFileHandler

from app_paths import get_writable_dir

LOG_DIR = os.path.join(get_writable_dir(), "log")
LOG_FILE = os.path.join(LOG_DIR, "app_events.log")

os.makedirs(LOG_DIR, exist_ok=True)

_logger = logging.getLogger("app_events")
_logger.setLevel(logging.INFO)
_logger.propagate = False

if not _logger.handlers:
    _handler = TimedRotatingFileHandler(LOG_FILE, when="midnight", backupCount=30, encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    _logger.addHandler(_handler)


def log_event(line):
    _logger.info(line)
