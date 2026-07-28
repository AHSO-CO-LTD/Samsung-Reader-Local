import os
import time
from datetime import datetime

from PyQt5 import uic
from PyQt5.QtCore import QEvent, Qt, QTimer, QUrl
from PyQt5.QtGui import QColor
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer, QMediaPlaylist
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QCompleter,
    QDialog,
    QInputDialog,
    QLabel,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QTableWidgetItem,
    QWidget,
)

from app_logger import log_event
from data.duplicate_key import compute_duplicate_key
from data.mapping_store import load_mappings
from db.local_db import (
    add_local_notification,
    apply_machine_config,
    apply_reconcile_pull,
    apply_scan_submit_result,
    apply_sync_batch_result,
    build_reconcile_payload,
    claim_pending_scans_for_batch,
    claim_specific_scans_for_batch,
    create_sync_batch,
    finish_command,
    get_app_settings,
    get_command_local_status,
    get_latest_unread_notification,
    get_scan_counts,
    get_server_settings,
    mark_notification_read,
    mark_scan_submit_failed,
    mark_sync_batch_failed,
    new_batch_code,
    record_full_scan,
    recover_stuck_syncing_scans,
    save_command_received,
    update_app_settings,
)
from machine.identity import ensure_machine_identity
from reader.reader_bridge import ReaderManager
from reader.reader_store import (
    ROLE_LED_BAR,
    ROLE_QR_BOTTOM,
    infer_role_from_name,
    load_hid_scanner_enabled,
    load_master_fill_timeout_seconds,
    load_readers,
)
from server.api_client import SamsungQrServerClient, ServerApiConfig
from server.runtime_socket_client import MachineRuntimeClient
from server.server_config import load_server_config, save_server_config
from server.server_worker import ServerWorker
from ui.config_window import ConfigWindow
from ui.reconcile_window import ReconcileWindow
from ui.register_window import RegisterWindow
from app_paths import get_bundle_dir

UI_PATH = os.path.join(get_bundle_dir(), "ui", "main_window.ui")
MAPPING_UI_PATH = os.path.join(get_bundle_dir(), "ui", "mapping_window.ui")
SOUND_DIR = os.path.join(get_bundle_dir(), "sound")

# Icon mũi tên spinbox/combobox nạp qua code (không phải QSS trong .ui) —
# url(data:...) base64 không được Qt QSS hỗ trợ, và đường dẫn tương đối
# trong QSS phụ thuộc thư mục làm việc lúc chạy app — dùng path tuyệt đối
# tính từ get_bundle_dir(), đúng pattern main.py:LOGO_PATH.
_ICONS_DIR = os.path.join(get_bundle_dir(), "ui", "icons").replace("\\", "/")
ARROW_ICONS_STYLESHEET = f"""
QSpinBox::up-arrow {{
    image: url({_ICONS_DIR}/arrow_up.png);
    width: 10px;
    height: 10px;
}}
QSpinBox::down-arrow {{
    image: url({_ICONS_DIR}/arrow_down.png);
    width: 10px;
    height: 10px;
}}
QComboBox::down-arrow {{
    image: url({_ICONS_DIR}/arrow_down.png);
    width: 12px;
    height: 12px;
}}
"""

STATUS_LABELS = {
    "connecting": "Đang kết nối...",
    "connected": "Đã kết nối",
    "disconnected": "Mất kết nối",
}

STATUS_COLORS = {
    "connecting": QColor("darkorange"),
    "connected": QColor("green"),
    "disconnected": QColor("red"),
}

SERVER_HEALTH_CHECK_INTERVAL_MS = 5000
IDENTITY_STATUS_POLL_INTERVAL_MS = 15000

SERVER_STATUS_LABELS = {
    True: "Server: Đã kết nối",
    False: "Server: Mất kết nối",
    None: "Server: -",
}

SERVER_STATUS_STYLES = {
    True: "color: green;",
    False: "color: red;",
    None: "color: gray;",
}

# Doc không cho số cụ thể cho commands/poll, chỉ nói "interval thưa hơn"
# health/identity — 30s là lựa chọn hợp lý, dễ chỉnh sau.
COMMANDS_POLL_INTERVAL_MS = 30000

# Doc mục 12.1: gửi runtime:snapshot định kỳ mỗi 3-10 giây trong lúc đang
# chạy — 5s nằm giữa khoảng đó.
RUNTIME_SNAPSHOT_INTERVAL_MS = 5000

# 4 command_type hợp lệ (đúng ENUM machine_command_type trong db/schema.sql) —
# command_type nào khác đều bị coi là không hỗ trợ, ack FAILED ngay, không
# ghi vào command_inbox (cột đó là ENUM, insert giá trị lạ sẽ lỗi).
KNOWN_COMMAND_TYPES = {
    "SYNC_PROFILE",
    "SYNC_SCAN_DATA",
    "RELOAD_CONFIG",
    "SHOW_MESSAGE",
}

# local_runtime_status coi là "được phép scan" — mọi giá trị khác đều chặn
# màn scan chính (xem _apply_runtime_status). SERVER_OFFLINE PHẢI nằm trong
# tập này — nguyên tắc local-first: mất kết nối server vẫn phải scan được,
# scan sẽ lưu pending (đúng doc mục 4.1.11), KHÔNG được khoá màn hình. Tình
# trạng mất kết nối vẫn hiển thị qua labelServerStatus (độc lập, đã có sẵn).
SCAN_ENABLED_STATUSES = {"READY", "SCANNING", "SYNCING", "SERVER_OFFLINE"}

# Không có entry "SERVER_OFFLINE" ở 2 map dưới — vì trạng thái đó nằm trong
# SCAN_ENABLED_STATUSES nên banner chặn không bao giờ hiện cho nó.
RUNTIME_BANNER_TEXT = {
    "BOOTING": "Đang kiểm tra trạng thái đăng ký máy...",
    "NOT_REGISTERED": "Máy chưa đăng ký — vào Register để gửi yêu cầu đăng ký.",
    "REGISTERING": "Đang gửi yêu cầu đăng ký...",
    "WAITING_LICENSE": "Đang chờ cấp license...",
    "WAITING_APPROVAL": "License đã kích hoạt — đang chờ duyệt...",
    "REJECTED": "Yêu cầu đăng ký đã bị từ chối.",
    "BLOCKED": "Máy bị khoá — liên hệ admin.",
    "ERROR": "Không đọc được định danh máy (serial/UID).",
}

RUNTIME_BANNER_STYLES = {
    "BOOTING": "background-color: #9e9e9e; color: white;",
    "NOT_REGISTERED": "background-color: #f57c00; color: white;",
    "REGISTERING": "background-color: #f57c00; color: white;",
    "WAITING_LICENSE": "background-color: #f57c00; color: white;",
    "WAITING_APPROVAL": "background-color: #f57c00; color: white;",
    "REJECTED": "background-color: #c62828; color: white;",
    "BLOCKED": "background-color: #c62828; color: white;",
    "ERROR": "background-color: #c62828; color: white;",
    "_default": "background-color: #9e9e9e; color: white;",
}

# Gộp lại vì bị lặp 5 chỗ literal tiếng Anh trước khi dịch.
MESSAGE_MACHINE_READY = "Máy đã sẵn sàng."

NOTIFICATION_POLL_INTERVAL_MS = 1500

# Nền GIỮ NGUYÊN màu đen giống textEditLog cũ (#071413) — chỉ đổi màu CHỮ
# theo severity, không đổi nền (yêu cầu rõ của user).
NOTIFICATION_BANNER_BASE_STYLE = "background-color: #071413; border: 1px solid #52736E; border-radius: 3px; padding: 8px;"
NOTIFICATION_SEVERITY_TEXT_COLORS = {
    "INFO": "#5FD68A",
    "WARNING": "#FFC107",
    "ERROR": "#FF6B5B",
    "CRITICAL": "#FF3B30",
    "_default": "#D8E9E4",  # màu chữ mặc định giống log cũ
}

APP_VERSION = "0.7.1"
# Ngày PHÁT HÀNH bản build này (không phải hôm nay) — dùng để check cửa sổ
# update_until của license (xem licensing/license_client.py:verify_license).
# Cập nhật thủ công mỗi lần release thật, không tự tính date.today().
APP_RELEASE_DATE = ""
# Mã sản phẩm đối chiếu với lic["product"] khi verify license (check
# "sai_san_pham") — để None để BỎ QUA check này. Cần thống nhất giá trị thật
# với bên giữ công cụ ký license nếu họ có gắn "product" vào license phát
# hành cho dự án này. Đặt cạnh APP_VERSION/APP_RELEASE_DATE cho dễ tìm — cả 3
# đều là cấu hình bắt buộc trước khi build (xem E:\License-Key-main\INTEGRATION.md mục 3).
APP_PRODUCT = "Samsung Reader Local"

# Mốc dùng lại từ reconcile_pull's take mặc định (server/api_client.py) — doc
# không cho số cụ thể riêng cho sync/batches/submit.
BATCH_SUBMIT_MAX_SIZE = 200

RESULT_STYLE = {
    # "" (không set gì) -> tự rơi về đúng style mặc định của
    # QLabel#labelResultStatus khai báo trong main_window.ui (nền tối + chữ
    # xanh dương theo theme hiện tại) — không hardcode lại màu ở đây để tránh
    # lệch mỗi khi theme trong .ui đổi mà quên sửa theo ở đây.
    None: "",
    "ok": "background-color: #2F8F5B; color: white;",
    "ng": "background-color: #c62828; color: white;",
    # Local đã pass nhưng CHƯA nhận SERVER_OK — theo đúng nguyên tắc "chỉ so
    # OK với OK" (doc mục 6.7/27: không hiển thị final OK khi final_status
    # còn PENDING_SERVER). Chỉ chuyển "ok" (xanh) sau khi server xác nhận.
    "pending": "background-color: #ffc107; color: black;",
}

RESULT_BLINK_OFF_STYLE = "background-color: #071413; color: white;"
RESULT_BLINK_INTERVAL_MS = 300
RESULT_SOUND_REPEAT_COUNT = 1
RESULT_SOUND_BASENAMES = {"ok": "OK", "ng": "NG"}
# .wav ưu tiên hơn .mp3 nếu cả 2 cùng tồn tại.


def _resolve_result_sound_paths():
    """Dò 1 LẦN DUY NHẤT lúc import — file âm thanh là asset tĩnh đóng gói
    sẵn, không đổi lúc app đang chạy, nên không cần os.path.isfile() lại mỗi
    lần phát (khác dữ liệu profile/config cần đọc lại theo thời gian thực)."""
    resolved = {}
    for result, basename in RESULT_SOUND_BASENAMES.items():
        for ext in (".wav", ".mp3"):
            path = os.path.join(SOUND_DIR, basename + ext)
            if os.path.isfile(path):
                resolved[result] = path
                break
        else:
            # Không có file nào — giữ đường dẫn .mp3 mặc định để log lỗi
            # "Không tìm thấy file" hiện đúng tên file đang mong đợi.
            resolved[result] = os.path.join(SOUND_DIR, basename + ".mp3")
    return resolved


RESULT_SOUND_PATHS = _resolve_result_sound_paths()

# Cảnh báo khi mã quét bị bỏ qua vì cột đã đủ số lượng — thường gặp nhất khi
# operator quét sản phẩm mới nhưng quên bấm Reset sau 1 kết quả NG (NG không
# tự xoá màn hình, xem _finalize_scan_session/_session_pending_clear), khiến
# mọi mã mới bị lặng lẽ bỏ qua (trước đây chỉ ghi log, dễ bị bỏ lỡ trên xưởng).
SCAN_IGNORED_WARNING_STYLE = "background-color: #ffc107; color: black;"

# Mã reader trả về là 1 chuỗi liền không có khoảng trắng, nên word-wrap thường
# (ngắt theo từ) không tự xuống dòng được — chủ động chèn "\n" theo số ký tự
# cố định để đảm bảo luôn xuống dòng đúng chỗ, không phụ thuộc Qt word-wrap.
RESULT_WRAP_CHUNK = 22  # vừa đủ 1 hàng cho mã 22 ký tự (LED BAR 1/2)

# Nền từng khung mã trong 3 cột kết quả: True=đúng (xanh), False=sai (đỏ),
# None=chưa có logic kiểm tra (QRCODE BOTTOM hiện tại) — trung tính.
RESULT_ITEM_COLORS = {
    True: QColor("lightgreen"),
    False: QColor("lightcoral"),
    None: QColor("#eeeeee"),
}

# Màu riêng cho item QRCODE BOTTOM lúc đang chờ server xác nhận — tách khỏi
# RESULT_ITEM_COLORS vì dict đó là kết quả so khớp LOCAL tức thời (True/
# False/None), còn đây là 1 trạng thái khác hẳn: đã pass local, chưa chốt final.
PENDING_ITEM_COLOR = QColor("#ffc107")

# Cả RESULT_ITEM_COLORS lẫn PENDING_ITEM_COLOR đều là nền sáng — chữ phải tối
# màu mới đủ tương phản (khác với nền tối mặc định của QListWidget, nơi chữ
# sáng theo theme mới lại đúng). Dùng chung 1 màu chữ tối cho mọi item đã đổi
# nền, không phụ thuộc theme sáng/tối của QListWidget.
RESULT_ITEM_TEXT_COLOR = QColor("#173A3A")


def _apply_item_result_color(item, color):
    """Đổi cả nền lẫn màu chữ cho 1 item — luôn gọi cặp đôi, không gọi
    setBackground() riêng lẻ, tránh lặp lại lỗi chữ trắng trên nền sáng khó
    đọc (đã gặp thật khi thêm theme QSS tối cho QListWidget)."""
    item.setBackground(color)
    item.setForeground(RESULT_ITEM_TEXT_COLOR)


# Mã NG cố định (khớp vocabulary docs/10-huong-dan-api-may-local-python.md) để
# lưu vào local_ng_reason/ng_reason — log hiển thị cho operator luôn dùng câu
# tiếng Việt tương ứng qua _describe_ng(), không bao giờ lộ mã ra log.
NG_NO_PROFILE_SELECTED = "NO_PROFILE_SELECTED"
NG_LED_SUFFIX_NOT_MATCH = "LED_SUFFIX_NOT_MATCH"
NG_FULL_CODE_INVALID_LENGTH = "FULL_CODE_INVALID_LENGTH"
NG_CHASSIS_NOT_MATCH = "CHASSIS_NOT_MATCH"
NG_FULL_VENDOR_NOT_MATCH = "FULL_VENDOR_NOT_MATCH"
NG_QR_BOTTOM_LED_NOT_MATCH = "QR_BOTTOM_LED_NOT_MATCH"
NG_FULL_FACTORY_NOT_MATCH = "FULL_FACTORY_NOT_MATCH"
NG_LOCAL_DUPLICATE = "LOCAL_DUPLICATE"
# Reader Keyence SR-X gửi đúng chuỗi "ERROR" (Read Error String mặc định,
# xem docs/srx_manual_dump.txt dòng ~3981-3984) khi không đọc được mã — coi
# đây là 1 lần đọc lỗi rõ ràng, KHÔNG chạy qua logic đối chiếu (độ dài/suffix/
# vendor...) vì "ERROR" chắc chắn không khớp bất kỳ điều kiện nào, chỉ tạo ra
# thông báo gây nhiễu (vd "Sai độ dài mã LED: 5 ký tự...").
NG_SCAN_FAILED = "SCAN_FAILED"
READER_SCAN_ERROR_TEXT = "ERROR"

# Máy quét mã vạch cầm tay (Keyboard-HID, giả lập gõ phím + Enter) — nguồn
# nhập liệu thứ 2 song song với reader TCP. Không có "reader nào gửi lên" cố
# định như socket TCP nên phải tự suy role từ NỘI DUNG mỗi lần quét — xem
# _detect_role_from_content()/eventFilter(). Cùng cơ chế này còn dùng cho
# reader TCP bật cờ Is Master (chế độ Master/Slave) — xem
# _is_master_mode_active().
HID_SCANNER_NAME = "HID Scanner"
QR_BOTTOM_PREFIX = "VN39"
HID_SCAN_MAX_GAP_SEC = (
    0.25  # khoảng cách tối đa giữa 2 phím liên tiếp để còn tính là "gõ từ máy quét"
)
HID_SCAN_MIN_LENGTH = (
    4  # độ dài tối thiểu để tính là 1 lần quét hợp lệ (tránh bắt nhầm Enter đơn lẻ)
)


def _wrap_for_display(text, chunk_size):
    if len(text) <= chunk_size:
        return text
    return "\n".join(text[i : i + chunk_size] for i in range(0, len(text), chunk_size))


class MainWindow(QMainWindow):
    """Cửa sổ chính — chỉ chứa các phần chung/tái sử dụng được: tiêu đề,
    nút Configure/Mapping/PLC, bảng trạng thái reader, log, khung kết quả
    OK/NG, và 3 cột hiển thị mã đọc được. Phần xử lý logic so sánh thật với
    server sẽ bổ sung sau — hiện dùng dữ liệu mapping mẫu (mapping_store.py)."""

    def __init__(self):
        super().__init__()
        uic.loadUi(UI_PATH, self)
        self.setStyleSheet(self.styleSheet() + ARROW_ICONS_STYLESHEET)

        # Giãn đều theo tỷ lệ khi cửa sổ lớn/nhỏ hơn 1920x1080 thiết kế gốc —
        # mặc định .ui KHÔNG có stretch factor nào nên Qt không biết phân
        # phối lại khoảng trống dư/thiếu, chỉ dựa vào sizePolicy/floor cứng
        # (nguyên nhân chính khiến panel phải bị đẩy khuất màn hình ở
        # 1366x768 — đã tự verify bằng màn hình thật). Tỷ lệ 4:1 xấp xỉ đúng
        # tỷ lệ hiện có ở 1920x1080 (~1520px:400px).
        self.horizontalLayoutBody.setStretch(
            0, 3
        )  # widgetResultContainer (3 cột LED/QR)
        self.horizontalLayoutBody.setStretch(1, 1)  # widgetRightPanel
        self.horizontalLayoutResultColumns.setStretch(0, 1)  # groupBoxLedBar1
        self.horizontalLayoutResultColumns.setStretch(1, 1)  # groupBoxLedBar2
        self.horizontalLayoutResultColumns.setStretch(2, 1)  # groupBoxQrBottom
        # Chassis Rear + Lot No gộp chung 1 hàng (trước đây 2 hàng riêng,
        # xếp chồng) để nhường chỗ dọc cho khung Result — bị khuất trên màn
        # phân giải thấp (1360x768, đã tự verify bằng màn hình thật). Chassis
        # Rear cần rộng hơn (hiển thị mã chassis dài, vd "BN96-58567A") so
        # với Lot No (chỉ 3 ký tự).
        self.horizontalLayoutChassisAndLotNo.setStretch(0, 2)  # groupBoxChassisRear
        self.horizontalLayoutChassisAndLotNo.setStretch(1, 1)  # groupBoxLotNo
        # groupBoxResult (chữ OK/NG) là mục DUY NHẤT trong verticalLayoutRight
        # có stretch > 0 — mọi khoảng trống dư (nếu có, vd màn 1920x1080 trở
        # lên) ưu tiên dồn hết vào đây thay vì bị chia đều/không đáng kể cho
        # các mục khác theo sizePolicy mặc định (đã tự verify: nếu không có
        # stretch này, chỉ giảm minimumSize của labelResultStatus để chống
        # tràn màn thấp sẽ khiến khung Result NHỎ ĐI ngay cả ở 1920x1080 —
        # 240px xuống còn 196px — dù màn có dư chỗ). labelResultStatus KHÔNG
        # đặt maximumSize (đã thử giới hạn 250px trước đó — gây khoảng trống
        # thừa trên/dưới chữ vì groupBoxResult vẫn giãn theo stretch trong khi
        # label bị chặn trần, user chọn bỏ hẳn trần để label luôn lấp đầy
        # đúng groupBoxResult, chấp nhận đánh đổi: màn rất lớn (4K...) khung
        # OK/NG có thể to hơn đáng kể so với 1920x1080).
        for i in range(self.verticalLayoutRight.count()):
            item = self.verticalLayoutRight.itemAt(i)
            widget = item.widget()
            self.verticalLayoutRight.setStretch(
                i, 1 if widget is self.groupBoxResult else 0
            )
        # Ngưỡng tối thiểu an toàn — phòng khi cửa sổ bị resize tay xuống
        # dưới phạm vi đã hỗ trợ (1366x768 trở lên); showMaximized() vẫn
        # luôn lấp đầy màn hình thật trước, đây chỉ là lưới an toàn.
        self.setMinimumSize(1280, 720)

        self.manager = ReaderManager()

        # Kênh Socket.IO /machine-runtime (dashboard vận hành server, KHÔNG
        # phải hồ sơ QA chính thức — đó là scans/submit) — khởi tạo SỚM
        # (trước dòng nối comboBoxChassisRear.currentTextChanged bên dưới)
        # vì _load_mappings() (gọi trong __init__, trước _init_server_worker)
        # tự bắn currentTextChanged ngay khi add item đầu tiên vào combobox
        # — on_chassis_rear_changed() cần self._runtime_client tồn tại sẵn
        # lúc đó, không thì AttributeError ngay lúc khởi động app. Xem
        # server/runtime_socket_client.py, _apply_runtime_status() (điểm
        # kích hoạt connect+hello+start), closeEvent() (điểm gửi stop).
        self._runtime_client = MachineRuntimeClient(parent=self)
        self._runtime_client.runtimeConnected.connect(self._on_runtime_connected)
        self._runtime_client.runtimeReconnected.connect(self._on_runtime_reconnected)
        self._runtime_client.runtimeDisconnected.connect(self._on_runtime_disconnected)
        self._runtime_client.runtimeBlocked.connect(self._on_runtime_blocked)
        self._runtime_session_started = False

        self._status = {}
        self._wired_readers = set()
        self._reader_roles = {}
        # Cờ "Is Master" (chế độ Master/Slave) — đọc TRỰC TIẾP từ thuộc tính
        # reader.is_master (reader/reader_bridge.py:SRXReaderQt), KHÔNG dùng
        # dict riêng ở đây — xem comment tại SRXReaderQt.__init__ lý do (dict
        # riêng từng gây bug thật: lệch pha đồng bộ giữa MainWindow/ConfigWindow).
        # Máy quét HID cầm tay — không tra self._reader_roles (dict đó bị
        # _sync_reader_panel() nạp lại hoàn toàn từ readers_config.json mỗi
        # lần đóng Config Window, sẽ xoá mất entry gán tay cho tên này).
        # self._hid_scan_role là biến TẠM, set ngay trước mỗi lời gọi
        # on_data_received(HID_SCANNER_NAME, ...) trong _handle_hid_scan().
        self._hid_scan_role = None
        self._hid_scan_buffer = ""
        self._hid_last_keypress_time = None
        self._hid_scanner_enabled = load_hid_scanner_enabled()
        self._ledbar2_locked = False
        self._received_counts = {"ledbar1": 0, "ledbar2": 0, "qrbottom": 0}
        self._last_input = {}
        self._mappings_by_chassis = {}
        # Mã LED bar gần nhất đã đọc ĐÚNG (is_ok=True), theo cột ledbar1/ledbar2
        # — dùng để đối chiếu ký tự vendor với QRCODE BOTTOM (mục 4 dưới đây).
        self._last_ok_led_text = {}

        # Buffer 1 "phiên quét" = 1 sản phẩm: Quantity của LED BAR 1/2/QRCODE
        # BOTTOM là số mảnh CỦA CÙNG 1 sản phẩm (không phải nhiều sản phẩm liên
        # tiếp) — khi progress bar đầy, toàn bộ item thu thập được hợp thành 1
        # dòng local_scan_records + nhiều dòng local_scan_led_items.
        self._session_led_items = {"ledbar1": [], "ledbar2": []}
        # Đếm thứ tự nhận thực tế trong phiên — dùng để xác định mã NG nào
        # "đến trước" khi cả ledbar1 lẫn ledbar2 đều có mã lỗi (xem
        # _finalize_scan_session): nối 2 list riêng rồi lấy phần tử đầu tiên
        # không đủ, vì mất thứ tự thời gian thật giữa 2 cột.
        self._session_led_seq = 0
        self._session_qr = None
        # True sau khi 1 phiên OK vừa chốt — chưa xoá màn hình ngay (để operator
        # kịp nhìn kết quả), chỉ xoá khi có mã MỚI của phiên tiếp theo tới.
        self._session_pending_clear = False
        # Đếm số mã bị bỏ qua vì cột đã đủ số lượng kể từ lần _clear_session()
        # gần nhất — xem SCAN_IGNORED_WARNING_STYLE/_show_scan_ignored_warning().
        self._ignored_scan_count = 0
        self._last_duplicate_first_scan_at = None
        # Tăng lên mỗi lần _clear_session() chạy — dùng để response submit
        # ASYNC (có thể về sau khi operator đã chuyển sang sản phẩm khác)
        # biết có còn an toàn để đụng vào QListWidgetItem/labelResultStatus
        # hiện tại hay không (xem _reflect_scan_submit_ui).
        self._session_generation = 0
        # local_scan_id -> (generation, item) — chỉ set khi final_is_ok=True
        # (case NG hiện kết quả ngay, không cần chờ/theo dõi thêm).
        self._pending_scan_ui = {}

        # True/False sau khi biết kết quả health-check gần nhất, None = chưa
        # kiểm tra lần nào — dùng để chỉ log lúc THAY ĐỔI trạng thái, tránh
        # log rác mỗi lần QTimer bắn lại (xem _apply_server_online).
        self._server_online = None

        # local_runtime_status hiện tại (None = chưa áp dụng lần nào) — dùng
        # để chỉ bắn notification lúc THẬT SỰ đổi trạng thái (xem
        # _apply_runtime_status), giống _server_online ở trên.
        self._runtime_status = None
        # Fail-closed: chặn scan cho tới khi có bằng chứng READY từ server —
        # đây là gate THẬT (xem on_data_received), disable widget chỉ là UX.
        self._scan_blocked = True
        self._serial = None
        self._uid = None
        # True sau khi heartbeat đã start lần đầu (ngay sau config thành
        # công) — dùng để _apply_runtime_status biết có nên tự bật lại
        # _heartbeat_timer khi thoát BLOCKED hay chưa (chưa từng bắt đầu thì
        # không tự bật, tránh gọi heartbeat trước khi có machine_code/config).
        self._heartbeat_started = False
        self._machine_location_identity = None

        # Bước 8 — sync/batches/submit. _batch_in_flight chặn 2 batch chạy
        # song song (trong 1 tiến trình — 2 tiến trình cùng máy đã bị QLockFile
        # chặn ở main.py). _batch_command_id: server_command_id nếu batch hiện
        # tại do lệnh SYNC_SCAN_DATA kích hoạt (cần ack đúng lúc xong), None
        # nếu do STARTUP/NETWORK_RESTORED/nút Sync Now tự kích hoạt.
        self._batch_in_flight = False
        self._batch_command_id = None
        self._startup_sync_done = False

        # Bước 9 — sync/reconcile/check + sync/reconcile/pull. _reconcile_manual
        # phân biệt lần check do nút "Check Data" bấm tay (mở ReconcileWindow
        # nếu có lệch) hay do auto-trigger STARTUP/NETWORK_RESTORED (chỉ log,
        # không tự mở dialog làm phiền operator đang thao tác).
        self._reconcile_in_flight = False
        self._reconcile_manual = False
        self._startup_reconcile_done = False

        self._column_widgets = {
            "ledbar1": {
                "list": self.listWidgetLedBar1Codes,
                "spin": self.spinBoxLedBar1Count,
                "ref_label": self.labelLedBar1RefCode,
            },
            "ledbar2": {
                "list": self.listWidgetLedBar2Codes,
                "spin": self.spinBoxLedBar2Count,
                "ref_label": self.labelLedBar2RefCode,
            },
            "qrbottom": {
                "list": self.listWidgetQrBottomCodes,
                "spin": self.spinBoxQrBottomCount,
                "ref_label": self.labelQrBottomRefCode,
            },
        }

        self.tableWidgetReaderStatus.horizontalHeader().setStretchLastSection(True)
        self.tableWidgetReaderStatus.setColumnWidth(0, 80)
        self.tableWidgetReaderStatus.setColumnWidth(1, 90)

        for widgets in self._column_widgets.values():
            widgets["list"].setSpacing(6)

        self.pushButtonConfigure.clicked.connect(self.on_configure_clicked)
        self.pushButtonMapping.clicked.connect(self.on_mapping_clicked)
        self.pushButtonRegister.clicked.connect(self.on_register_clicked)
        self.pushButtonChangeServerIp.clicked.connect(self.on_change_server_ip_clicked)
        self.pushButtonReset.clicked.connect(self.on_reset_clicked)
        self._configure_chassis_rear_search()
        self.comboBoxChassisRear.currentTextChanged.connect(
            self.on_chassis_rear_changed
        )

        for widgets in self._column_widgets.values():
            widgets["spin"].valueChanged.connect(self._update_progress)

        self._init_result_alerts()
        self._init_notification_banner()
        self.set_result_status(None)
        self._load_mappings()
        self._load_persisted_readers()
        self._update_progress()
        self._init_server_worker()

        # Cài SAU CÙNG — bắt phím toàn cục cho máy quét HID cầm tay (xem
        # eventFilter()). Cài ở tầng QApplication (không phải keyPressEvent
        # của riêng MainWindow) để nhận sự kiện SỚM NHẤT, trước khi 1 nút
        # bấm đang có focus kịp "nuốt" phím Enter kết thúc chuỗi quét.
        QApplication.instance().installEventFilter(self)

    ######################################################################
    # Kết nối server (REST) — bước 1: chỉ GET /api/health
    ######################################################################

    def _init_server_worker(self):
        recovered = recover_stuck_syncing_scans()
        if recovered:
            self._append_log(
                f"[{self._now()}] [Đồng bộ] Phục hồi {recovered} bản ghi kẹt ở SYNCING "
                "(app đóng/crash giữa lúc đang đồng bộ lần trước) về PENDING."
            )

        self._serial, self._uid = ensure_machine_identity()
        server_config = load_server_config()
        config = ServerApiConfig(host=server_config["host"], port=server_config["port"])
        client = SamsungQrServerClient(config)
        self.server_worker = ServerWorker(client, parent=self)
        self.server_worker.callSucceeded.connect(self._on_server_call_succeeded)
        self.server_worker.callFailed.connect(self._on_server_call_failed)
        self.server_worker.start()

        self._server_health_timer = QTimer(self)
        self._server_health_timer.setInterval(SERVER_HEALTH_CHECK_INTERVAL_MS)
        self._server_health_timer.timeout.connect(self._check_server_health)
        self._server_health_timer.start()
        self._check_server_health()

        # Timer riêng cho identity-status — tách khỏi health vì health chạy
        # mãi mãi (theo dõi kết nối), còn identity-status chỉ cần chạy tới
        # khi READY (xem _apply_runtime_status dừng/bật lại timer này).
        self._identity_status_timer = QTimer(self)
        self._identity_status_timer.setInterval(IDENTITY_STATUS_POLL_INTERVAL_MS)
        self._identity_status_timer.timeout.connect(self._check_identity_status)

        # Timer commands/poll — khác _identity_status_timer, timer này KHÔNG
        # dừng khi BLOCKED (command vẫn có thể tới bất cứ lúc nào, vd
        # SHOW_MESSAGE giải thích lý do bị khoá) — chỉ bắt đầu 1 lần đầu tiên
        # ngay sau khi config load thành công (xem _ensure_commands_polling_started).
        self._commands_poll_timer = QTimer(self)
        self._commands_poll_timer.setInterval(COMMANDS_POLL_INTERVAL_MS)
        self._commands_poll_timer.timeout.connect(self._check_commands)

        # Timer heartbeat — interval tính động lúc bắt đầu (xem
        # _ensure_heartbeat_started), không cố định như các timer trên. Dừng
        # hẳn khi BLOCKED (đúng doc: "Khi BLOCKED, local phải dừng submit/
        # heartbeat runtime"), tự bật lại khi thoát BLOCKED — xem _apply_runtime_status.
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.timeout.connect(self._send_heartbeat)

        # Timer runtime:snapshot — .start() ở _start_machine_runtime_session
        # (đúng 1 lần lúc phiên bắt đầu), .stop() ở closeEvent. emit_snapshot()
        # tự no-op nếu phiên chưa/không còn active, an toàn dù timer lỡ chạy
        # ngoài khoảng đó.
        self._runtime_snapshot_timer = QTimer(self)
        self._runtime_snapshot_timer.setInterval(RUNTIME_SNAPSHOT_INTERVAL_MS)
        self._runtime_snapshot_timer.timeout.connect(self._runtime_client.emit_snapshot)

        # Timer 1 lần (singleShot) điền lỗi "SCAN_FAILED" cho vị trí Master
        # relay im lặng (không gửi cả ERROR lẫn dữ liệu thật) khi 1 trạm vật
        # lý dưới Master đọc lỗi — xem _on_master_fill_timeout()/
        # on_data_received(). Chỉ có ý nghĩa ở chế độ Master
        # (_is_master_mode_active()); TCP độc lập mỗi reader đã tự gửi
        # "ERROR" tường minh nên không cần cơ chế này.
        self._master_fill_timeout_timer = QTimer(self)
        self._master_fill_timeout_timer.setSingleShot(True)
        self._master_fill_timeout_timer.timeout.connect(self._on_master_fill_timeout)

        settings = get_app_settings()
        initial_status = settings.get("local_runtime_status") or "BOOTING"
        # Baseline TRƯỚC lần apply đầu — tránh bắn notification cho trạng
        # thái đã có sẵn từ phiên trước (giống _last_view_state ở RegisterWindow).
        self._runtime_status = initial_status
        self._apply_runtime_status(initial_status, settings.get("local_status_message"))

        if self._serial and self._uid:
            self._check_identity_status()
        else:
            self._append_log(
                f"[{self._now()}] [Định danh máy] Không đọc được serial/UID phần cứng."
            )
            self._apply_runtime_status("ERROR", RUNTIME_BANNER_TEXT["ERROR"])

    def _check_server_health(self):
        self.server_worker.enqueue("health")

    def _check_identity_status(self):
        if self._serial and self._uid:
            self.server_worker.enqueue(
                "identity_status", serial=self._serial, uid=self._uid
            )

    def _check_commands(self):
        self.server_worker.enqueue(
            "commands_poll", serial=self._serial, uid=self._uid, take=20
        )

    def _ack_command(self, server_command_id, status, error_message=None):
        self.server_worker.enqueue(
            "command_ack",
            correlation_id=str(server_command_id),
            command_id=server_command_id,
            serial=self._serial,
            uid=self._uid,
            status=status,
            error_message=error_message,
        )

    def _send_heartbeat(self):
        settings = get_app_settings()
        counts = get_scan_counts()
        self.server_worker.enqueue(
            "heartbeat",
            machine_code=settings.get("machine_code"),
            serial=self._serial,
            uid=self._uid,
            ip_address=None,
            app_version=APP_VERSION,
            local_db_version=settings.get("local_db_version"),
            local_total_record=counts["total"],
            local_ok_record=counts["ok"],
            local_ng_record=counts["ng"],
            local_pending_sync=counts["pending_sync"],
            local_checksum=None,
        )

    def _on_server_call_succeeded(self, job_kind, correlation_id, data):
        if job_kind == "health":
            update_app_settings(
                server_online=True, last_health_at=datetime.now().astimezone()
            )
            self._apply_server_online(True)
        elif job_kind == "identity_status":
            self._handle_identity_status_result(data)
        elif job_kind == "config":
            self._handle_config_result(data, correlation_id)
        elif job_kind == "commands_poll":
            self._handle_commands_poll_result(data)
        elif job_kind == "command_ack":
            self._handle_command_ack_result(data)
        elif job_kind == "heartbeat":
            self._handle_heartbeat_result(data)
        elif job_kind == "scan_submit":
            self._handle_scan_submit_result(correlation_id, data)
        elif job_kind == "batch_submit":
            self._handle_batch_submit_response(correlation_id, data)
        elif job_kind == "reconcile_check":
            self._handle_reconcile_check_response(data)
        elif job_kind == "reconcile_pull":
            self._handle_reconcile_pull_response(data)

    def _on_server_call_failed(self, job_kind, correlation_id, error_message, payload):
        if job_kind == "health":
            update_app_settings(server_online=False)
            self._apply_server_online(False)
        elif job_kind == "identity_status":
            if payload.get("code") == "MACHINE_IDENTITY_MISMATCH":
                matches = (payload.get("data") or {}).get("matches") or []
                detail = (
                    "; ".join(
                        f"{m.get('machine_code')}({m.get('serial')}/{m.get('uid')})"
                        for m in matches
                    )
                    or "(không có chi tiết)"
                )
                message = f"Sai định danh — trùng với: {detail}"
                update_app_settings(
                    local_runtime_status="BLOCKED",
                    local_status_message=message,
                    local_status_updated_at=datetime.now().astimezone(),
                )
                self._append_log(f"[{self._now()}] [Định danh máy] {message}")
                self._apply_runtime_status("BLOCKED", message)
            else:
                self._append_log(
                    f"[{self._now()}] [Định danh máy] Lỗi mạng khi kiểm tra định danh: {error_message}"
                )
        elif job_kind == "config":
            code = payload.get("code")
            if code in ("MACHINE_NOT_FOUND", "MACHINE_IDENTITY_MISMATCH"):
                message = f"Tải cấu hình thất bại: {code}"
                update_app_settings(
                    local_runtime_status="BLOCKED",
                    local_status_message=message,
                    local_status_updated_at=datetime.now().astimezone(),
                )
                self._append_log(f"[{self._now()}] [Config] {message}")
                self._apply_runtime_status("BLOCKED", message)
                if correlation_id:
                    self._complete_config_triggered_command(
                        correlation_id, False, message
                    )
            else:
                self._append_log(
                    f"[{self._now()}] [Config] Lỗi mạng khi tải cấu hình: {error_message}"
                )
                if correlation_id:
                    self._complete_config_triggered_command(
                        correlation_id, False, f"Network error: {error_message}"
                    )
        elif job_kind == "commands_poll":
            self._append_log(
                f"[{self._now()}] [Command] Lỗi mạng khi poll command: {error_message}"
            )
        elif job_kind == "command_ack":
            if payload.get("code") == "MACHINE_COMMAND_NOT_FOUND" and correlation_id:
                finish_command(
                    int(correlation_id), "FAILED", "FAILED", "MACHINE_COMMAND_NOT_FOUND"
                )
                self._append_log(
                    f"[{self._now()}] [Command] Command không thuộc máy này (id={correlation_id}) — đánh dấu xong cục bộ."
                )
            else:
                self._append_log(
                    f"[{self._now()}] [Command] Lỗi mạng khi ack command (id={correlation_id}): {error_message}"
                )
        elif job_kind == "heartbeat":
            code = payload.get("code")
            now = datetime.now().astimezone()
            if code in ("MACHINE_NOT_FOUND", "MACHINE_IDENTITY_MISMATCH"):
                message = f"Heartbeat thất bại: {code}"
                update_app_settings(
                    local_runtime_status="BLOCKED",
                    local_status_message=message,
                    local_status_updated_at=now,
                )
                self._append_log(f"[{self._now()}] [Heartbeat] {message}")
                self._apply_runtime_status("BLOCKED", message)
            else:
                # Timeout/mất kết nối — theo doc mục 4.1.11: "Set server offline,
                # tiếp tục lưu local. Không xóa machine_code." KHÔNG khoá màn
                # scan (SERVER_OFFLINE nằm trong SCAN_ENABLED_STATUSES).
                message = "Không kết nối được server — dữ liệu quét được lưu cục bộ và sẽ đồng bộ sau."
                update_app_settings(
                    local_runtime_status="SERVER_OFFLINE", local_status_updated_at=now
                )
                self._append_log(
                    f"[{self._now()}] [Heartbeat] Server không phản hồi: {error_message}"
                )
                self._apply_runtime_status("SERVER_OFFLINE", message)
        elif job_kind == "scan_submit":
            local_scan_id = correlation_id
            code = payload.get("code")
            if code == "PROFILE_NOT_FOUND":
                mark_scan_submit_failed(
                    local_scan_id, code, payload.get("message"), blocked=True
                )
                message = f"Profile không còn hợp lệ trên server (id={local_scan_id}) — đang tải lại config."
                add_local_notification(
                    "PROFILE_NOT_FOUND", "ERROR", "Profile không hợp lệ", message
                )
                self._check_machine_config()
            elif code in ("MACHINE_NOT_FOUND", "MACHINE_IDENTITY_MISMATCH"):
                mark_scan_submit_failed(
                    local_scan_id, code, payload.get("message"), blocked=True
                )
                message = f"Gửi kết quả scan thất bại: {code}"
                update_app_settings(
                    local_runtime_status="BLOCKED",
                    local_status_message=message,
                    local_status_updated_at=datetime.now().astimezone(),
                )
                self._append_log(f"[{self._now()}] [Scan] {message}")
                self._apply_runtime_status("BLOCKED", message)
            elif code:
                # Họ mã FULL_CODE_INVALID/DUPLICATE_KEY_INVALID/... — server bác
                # cấu trúc payload, hiếm gặp, nghĩa là parser local sai lệch.
                mark_scan_submit_failed(
                    local_scan_id, code, payload.get("message"), blocked=True
                )
                message = f"Server từ chối payload (id={local_scan_id}): {code} — {payload.get('message')}"
                add_local_notification(
                    "LOCAL_SCAN_PAYLOAD_INVALID",
                    "ERROR",
                    "Server từ chối dữ liệu quét",
                    f"Dữ liệu gửi lên không hợp lệ (mã lỗi: {code}).",
                )
                self._append_log(f"[{self._now()}] [Scan] {message}")
            else:
                # Lỗi mạng thuần — giữ FAILED_RETRYABLE, retry thật là việc của
                # bước sync/batches/submit sau. Không notification riêng —
                # LOCAL_SERVER_OFFLINE từ health/heartbeat đã lo, tránh spam
                # theo từng scan.
                mark_scan_submit_failed(
                    local_scan_id, "NETWORK_ERROR", error_message, blocked=False
                )
                self._append_log(
                    f"[{self._now()}] [Scan] Lỗi mạng khi gửi scan (id={local_scan_id}): {error_message}"
                )
        elif job_kind == "batch_submit":
            # Cùng lý do defensive-dual-path như scan_submit ở trên —
            # BATCH_SUBMIT_PARTIAL_FAILED có success:false trong sample doc,
            # chưa rõ HTTP status, nên có thể tới qua callFailed dù không
            # phải lỗi mạng thật.
            if payload.get("code"):
                self._handle_batch_submit_response(correlation_id, payload)
            else:
                self._handle_batch_submit_network_error(correlation_id, error_message)
        elif job_kind == "reconcile_check":
            # Cả 3 code thành công của reconcile/check đều success:true (xác
            # nhận qua toàn bộ sample doc) — callFailed ở đây luôn là lỗi
            # THẬT (mạng/MACHINE_NOT_FOUND...), không cần dual-path như
            # batch_submit. Không notification riêng cho lỗi mạng thuần —
            # health/heartbeat đã lo, tránh spam.
            self._reconcile_in_flight = False
            self._append_log(
                f"[{self._now()}] [Đối soát] Lỗi khi kiểm tra dữ liệu: {error_message}"
            )
        elif job_kind == "reconcile_pull":
            message = f"Kéo dữ liệu từ server thất bại: {error_message}"
            add_local_notification(
                "LOCAL_DB_SYNC_FAILED",
                "CRITICAL",
                "Đồng bộ từ server thất bại",
                message,
            )

    def _handle_identity_status_result(self, response):
        code = response.get("code")
        data = response.get("data") or {}
        now = datetime.now().astimezone()

        if code == "MACHINE_IDENTITY_APPROVED":
            machine_code = data.get("machine_code")
            message = f"Đã được duyệt — machine_code={machine_code}."
            update_app_settings(
                registration_status="APPROVED",
                machine_code=machine_code,
                local_runtime_status="READY",
                local_status_message=message,
                local_status_updated_at=now,
            )
            self._apply_runtime_status("READY", message)
            self._check_machine_config()
        elif code == "MACHINE_REGISTER_PENDING":
            waiting = (
                "WAITING_APPROVAL"
                if data.get("license_activated_at")
                else "WAITING_LICENSE"
            )
            message = (
                "License đã kích hoạt, đang chờ duyệt."
                if waiting == "WAITING_APPROVAL"
                else "Đang chờ cấp license."
            )
            fields = {
                "registration_status": "PENDING",
                "local_runtime_status": waiting,
                "local_status_message": message,
                "local_status_updated_at": now,
            }
            if data.get("request_id"):
                fields["registration_request_id"] = data.get("request_id")
            if data.get("license_activated_at"):
                fields["license_activated_at"] = data.get("license_activated_at")
            update_app_settings(**fields)
            self._apply_runtime_status(waiting, message)
        elif code == "MACHINE_IDENTITY_NOT_REGISTERED":
            message = "Máy chưa được đăng ký trên server."
            update_app_settings(
                registration_status="NOT_REQUESTED",
                registration_request_id=None,
                local_runtime_status="NOT_REGISTERED",
                local_status_message=message,
                local_status_updated_at=now,
            )
            self._apply_runtime_status("NOT_REGISTERED", message)
        elif code == "MACHINE_IDENTITY_DISABLED":
            message = "Máy đã bị vô hiệu hoá trên server. Liên hệ admin."
            update_app_settings(
                local_runtime_status="BLOCKED",
                local_status_message=message,
                local_status_updated_at=now,
            )
            self._apply_runtime_status("BLOCKED", message)
        else:
            self._append_log(
                f"[{self._now()}] [Định danh máy] Phản hồi không xác định: {code} — {response.get('message')}"
            )

    def _check_machine_config(self, correlation_id=""):
        self.server_worker.enqueue(
            "config",
            correlation_id=correlation_id,
            serial=self._serial,
            uid=self._uid,
        )

    def _handle_config_result(self, response, correlation_id=""):
        code = response.get("code")
        data = response.get("data") or {}
        now = datetime.now().astimezone()

        if code != "MACHINE_CONFIG_LOADED":
            self._append_log(
                f"[{self._now()}] [Config] Phản hồi không xác định: {code} — {response.get('message')}"
            )
            if correlation_id:
                self._complete_config_triggered_command(
                    correlation_id, False, f"Unexpected response: {code}"
                )
            return

        apply_machine_config(data, self._serial, self._uid)
        update_app_settings(last_config_sync_at=now)
        self._load_mappings()

        profiles = data.get("profiles") or []
        vendors = data.get("vendors") or []
        if not profiles:
            message = "Chưa có profile nào được gán cho máy này trên server."
            update_app_settings(
                local_runtime_status="BLOCKED",
                local_status_message=message,
                local_status_updated_at=now,
            )
            add_local_notification(
                "LOCAL_PROFILE_EMPTY", "CRITICAL", "Thiếu profile", message
            )
            self._apply_runtime_status("BLOCKED", message)
            if correlation_id:
                self._complete_config_triggered_command(correlation_id, False, message)
        else:
            add_local_notification(
                "LOCAL_CONFIG_SYNCED",
                "INFO",
                "Đã đồng bộ cấu hình",
                f"{len(profiles)} profile, {len(vendors)} vendor.",
            )
            message = MESSAGE_MACHINE_READY
            update_app_settings(
                local_runtime_status="READY",
                local_status_message=message,
                local_status_updated_at=now,
            )
            self._apply_runtime_status("READY", message)
            self._ensure_commands_polling_started()
            self._ensure_heartbeat_started()
            self._ensure_startup_sync_triggered()
            self._ensure_startup_reconcile_triggered()
            if correlation_id:
                self._complete_config_triggered_command(correlation_id, True, None)

    def _ensure_commands_polling_started(self):
        if not self._commands_poll_timer.isActive():
            self._commands_poll_timer.start()
            self._check_commands()

    def _ensure_heartbeat_started(self):
        if self._heartbeat_started:
            return
        self._heartbeat_started = True
        timeout_seconds = get_server_settings().get("heartbeat_timeout_seconds") or 60
        interval_seconds = max(5, min(15, timeout_seconds // 4))
        self._heartbeat_timer.setInterval(interval_seconds * 1000)
        self._heartbeat_timer.start()
        self._send_heartbeat()

    def _ensure_startup_sync_triggered(self):
        """Trigger STARTUP — chỉ 1 lần cho cả vòng đời app (config có thể
        reload nhiều lần qua lệnh SYNC_PROFILE/RELOAD_CONFIG, không phải mỗi
        lần reload đều coi là "khởi động lại")."""
        if self._startup_sync_done:
            return
        self._startup_sync_done = True
        self._maybe_start_sync_batch("STARTUP")

    def _ensure_startup_reconcile_triggered(self):
        """Trigger STARTUP cho reconcile/check — độc lập với
        _ensure_startup_sync_triggered (chạy dù batch có pending hay không,
        đúng flow doc: app mở -> ... -> tuỳ policy reconcile/check)."""
        if self._startup_reconcile_done:
            return
        self._startup_reconcile_done = True
        self._start_reconcile_check(manual=False)

    def _handle_heartbeat_result(self, response):
        if response.get("code") != "HEARTBEAT_ACCEPTED":
            self._append_log(
                f"[{self._now()}] [Heartbeat] Phản hồi không xác định: {response.get('code')} — {response.get('message')}"
            )
            return
        machine = (response.get("data") or {}).get("machine")
        if isinstance(machine, dict):
            self._update_machine_location_display(machine)
        now = datetime.now().astimezone()
        update_app_settings(last_heartbeat_at=now)
        if self._runtime_status == "SERVER_OFFLINE":
            self._append_log(f"[{self._now()}] [Heartbeat] Server đã kết nối lại.")
            message = MESSAGE_MACHINE_READY
            update_app_settings(
                local_runtime_status="READY",
                local_status_message=message,
                local_status_updated_at=now,
            )
            self._apply_runtime_status("READY", message)

    @staticmethod
    def _machine_location_value(value):
        text = str(value).strip() if value is not None else ""
        return text or "-"

    def _update_machine_location_display(self, machine):
        identity = tuple(
            self._machine_location_value(machine.get(field))
            for field in ("machine_name", "line_name", "station_name")
        )
        if identity == self._machine_location_identity:
            return

        self._machine_location_identity = identity
        machine_name, line_name, station_name = identity
        self.labelMachineLocation.setText(
            f"Machine: {machine_name}\n"
            f"Line: {line_name}  |  Station: {station_name}"
        )

    def _complete_config_triggered_command(self, correlation_id, ok, message):
        """config được gọi vì command SYNC_PROFILE/RELOAD_CONFIG
        (correlation_id = server_command_id dạng chuỗi) — ack lại command đó
        theo đúng kết quả tải config vừa xong."""
        self._ack_command(
            int(correlation_id), "ACK" if ok else "FAILED", None if ok else message
        )

    ######################################################################
    # Command server (commands/poll + commands/:id/ack)
    ######################################################################

    def _handle_commands_poll_result(self, response):
        if response.get("code") != "MACHINE_COMMANDS_POLLED":
            self._append_log(
                f"[{self._now()}] [Command] Phản hồi không xác định: {response.get('code')} — {response.get('message')}"
            )
            return
        machine_code = get_app_settings().get("machine_code")
        for cmd in response.get("data") or []:
            self._process_command(cmd, machine_code)

    def _process_command(self, cmd, machine_code):
        server_command_id = cmd.get("id")
        command_type = cmd.get("command_type")
        payload = cmd.get("payload_json") or {}

        if command_type not in KNOWN_COMMAND_TYPES:
            message = f"Loại lệnh không được hỗ trợ: {command_type}"
            add_local_notification(
                "LOCAL_COMMAND_FAILED", "WARNING", "Lệnh không hỗ trợ", message
            )
            self._ack_command(server_command_id, "FAILED", message)
            return

        existing_status = get_command_local_status(server_command_id)
        if existing_status in ("ACKED", "FAILED"):
            return

        save_command_received(
            server_command_id,
            machine_code,
            command_type,
            payload,
            cmd.get("status"),
            cmd,
        )
        add_local_notification(
            "LOCAL_COMMAND_RECEIVED",
            "INFO",
            "Nhận lệnh mới từ server",
            f"Đã nhận lệnh: {command_type}",
        )

        if command_type in ("SYNC_PROFILE", "RELOAD_CONFIG"):
            self._check_machine_config(correlation_id=str(server_command_id))
        elif command_type == "SHOW_MESSAGE":
            message = payload.get("message") or "(không có nội dung)"
            add_local_notification(
                "LOCAL_SERVER_MESSAGE", "INFO", "Thông báo từ server", message
            )
            self._ack_command(server_command_id, "ACK")
        elif command_type == "SYNC_SCAN_DATA":
            self._maybe_start_sync_batch("MANUAL", command_id=server_command_id)

    def _handle_command_ack_result(self, response):
        code = response.get("code")
        data = response.get("data") or {}
        server_command_id = data.get("id")
        if code in ("MACHINE_COMMAND_ACKED", "MACHINE_COMMAND_FAILED"):
            local_status = "ACKED" if code == "MACHINE_COMMAND_ACKED" else "FAILED"
            finish_command(
                server_command_id,
                local_status,
                data.get("status"),
                data.get("error_message"),
            )
            self._append_log(
                f"[{self._now()}] [Command] Đã ack: id={server_command_id}, status={data.get('status')}"
            )
        else:
            self._append_log(
                f"[{self._now()}] [Command] Ack không xác định: {code} — {response.get('message')}"
            )

    ######################################################################
    # Đồng bộ batch (POST /api/sync/batches/submit) — Bước 8
    ######################################################################

    def _maybe_start_sync_batch(self, trigger_type, command_id=None):
        """Điểm vào chung cho cả 4 trigger (STARTUP/NETWORK_RESTORED/lệnh
        SYNC_SCAN_DATA/nút Sync Now). command_id khác None nghĩa là trigger
        này đến từ 1 command server cần ack lại khi xong (xem
        _finish_sync_batch)."""
        if self._batch_in_flight:
            if command_id is not None:
                self._ack_command(
                    command_id, "FAILED", "A sync batch is already in progress."
                )
            return

        if get_scan_counts()["pending_sync"] == 0:
            if command_id is not None:
                # Đúng doc: "Nếu không có pending vẫn có thể ack kèm message local."
                self._ack_command(command_id, "ACK", "No pending scans to sync.")
            return

        self._batch_command_id = command_id
        self._start_sync_batch(trigger_type)

    def _start_sync_batch(self, trigger_type, scan_ids=None):
        """scan_ids khác None (Bước 9 — nút "Push to Server" trong
        ReconcileWindow): gửi ĐÚNG danh sách id cụ thể server báo đang thiếu,
        bất kể sync_status hiện tại. scan_ids=None (mặc định, Bước 8): lấy
        oldest-N theo sync_status PENDING/FAILED_RETRYABLE như cũ — 100%
        tương thích ngược."""
        self._batch_in_flight = True
        scans_rows = (
            claim_specific_scans_for_batch(scan_ids)
            if scan_ids
            else claim_pending_scans_for_batch(BATCH_SUBMIT_MAX_SIZE)
        )
        batch_code = new_batch_code(trigger_type)
        machine_code = get_app_settings().get("machine_code")

        # Field giống hệt shape scans/submit (Bước 7, xem _submit_scan) —
        # full_code_json/led_scans_json đọc thẳng từ DB đã đúng shape sẵn.
        scans_payload = [
            {
                "local_scan_id": row["local_scan_id"],
                # machine_code LẤY TỪ DÒNG ĐÃ CLAIM (không phải máy hiện tại)
                # — để server tự phát hiện BATCH_MACHINE_CODE_MISMATCH nếu có.
                "machine_code": row["machine_code"],
                "serial": self._serial,
                "uid": self._uid,
                "profile_id": row["profile_id"],
                "duplicate_key": row["duplicate_key"],
                "full_code": row["full_code_json"],
                "chassis_scan_raw": row["chassis_scan_raw"],
                "led_scans": row["led_scans_json"],
                "local_status": row["local_status"],
                "local_ng_reason": row["local_ng_reason"],
                "scan_at": row["scan_at"].isoformat(),
            }
            for row in scans_rows
        ]

        request_json = {
            "batch_code": batch_code,
            "machine_code": machine_code,
            "serial": self._serial,
            "uid": self._uid,
            "trigger_type": trigger_type,
            "scans": scans_payload,
        }
        create_sync_batch(batch_code, trigger_type, len(scans_payload), request_json)

        message = f"Đang đồng bộ {len(scans_payload)} bản ghi (batch={batch_code})..."
        update_app_settings(
            local_runtime_status="SYNCING",
            local_status_message=message,
            local_status_updated_at=datetime.now().astimezone(),
        )
        self._apply_runtime_status("SYNCING", message)
        self._append_log(f"[{self._now()}] [Đồng bộ] {message}")

        self.server_worker.enqueue(
            "batch_submit",
            correlation_id=batch_code,
            batch_code=batch_code,
            machine_code=machine_code,
            serial=self._serial,
            uid=self._uid,
            trigger_type=trigger_type,
            scans=scans_payload,
        )

    def _handle_batch_submit_response(self, batch_code, response):
        """response tới qua callSucceeded (BATCH_SUBMIT_DONE, HTTP 2xx chắc
        chắn) HOẶC qua callFailed (BATCH_SUBMIT_PARTIAL_FAILED — sample doc
        có success:false, chưa rõ HTTP status) — cả 2 đường đều gọi hàm này,
        chỉ cần thấy data.results là xử lý per-item giống nhau."""
        data = response.get("data") or {}
        if not data.get("results"):
            self._handle_batch_submit_blocked(batch_code, response)
            return

        result = apply_sync_batch_result(batch_code, response)
        if result["total_failed"] == 0:
            add_local_notification(
                "OFFLINE_SYNC_DONE_OK",
                "INFO",
                "Đồng bộ hoàn tất",
                f"Đã đồng bộ xong: {result['total_ok']} OK, {result['total_ng']} NG.",
            )
        else:
            add_local_notification(
                "OFFLINE_SYNC_HAS_NG",
                "WARNING",
                "Đồng bộ có bản ghi lỗi",
                f"Có {result['total_failed']} bản ghi đồng bộ thất bại.",
            )
        if any(
            item.get("code") == "PROFILE_NOT_FOUND" for item in result["failed_items"]
        ):
            self._check_machine_config()

        self._append_log(
            f"[{self._now()}] [Đồng bộ] Batch {batch_code} xong: "
            f"{result['total_ok']} OK, {result['total_ng']} NG, {result['total_failed']} thất bại."
        )
        if self._runtime_status == "SYNCING":
            message = MESSAGE_MACHINE_READY
            update_app_settings(
                local_runtime_status="READY",
                local_status_message=message,
                local_status_updated_at=datetime.now().astimezone(),
            )
            self._apply_runtime_status("READY", message)
        self._finish_sync_batch(True, None)

    def _handle_batch_submit_blocked(self, batch_code, response):
        """response KHÔNG có data.results — lỗi cấp batch (MACHINE_NOT_FOUND/
        MACHINE_IDENTITY_MISMATCH/lỗi nghiệp vụ khác server bác trước khi kịp
        xử lý từng item). Revert toàn bộ scan đã claim trong batch này."""
        code = response.get("code")
        message = response.get("message") or f"Batch submit failed: {code}"
        identity_error = code in ("MACHINE_NOT_FOUND", "MACHINE_IDENTITY_MISMATCH")
        mark_sync_batch_failed(batch_code, code, message, blocked=identity_error)
        self._append_log(
            f"[{self._now()}] [Đồng bộ] Batch {batch_code} thất bại: {code} — {message}"
        )

        if identity_error:
            update_app_settings(
                local_runtime_status="BLOCKED",
                local_status_message=message,
                local_status_updated_at=datetime.now().astimezone(),
            )
            self._apply_runtime_status("BLOCKED", message)
        elif self._runtime_status == "SYNCING":
            ready_message = MESSAGE_MACHINE_READY
            update_app_settings(
                local_runtime_status="READY",
                local_status_message=ready_message,
                local_status_updated_at=datetime.now().astimezone(),
            )
            self._apply_runtime_status("READY", ready_message)

        self._finish_sync_batch(False, message)

    def _handle_batch_submit_network_error(self, batch_code, error_message):
        # Lỗi mạng thuần — giữ FAILED_RETRYABLE (blocked=False), trigger sau
        # tự nhặt lại. Không notification riêng, giống scan_submit đơn lẻ:
        # LOCAL_SERVER_OFFLINE từ health/heartbeat đã lo, tránh spam.
        mark_sync_batch_failed(
            batch_code, "NETWORK_ERROR", error_message, blocked=False
        )
        self._append_log(
            f"[{self._now()}] [Đồng bộ] Lỗi mạng khi gửi batch {batch_code}: {error_message}"
        )
        if self._runtime_status == "SYNCING":
            message = MESSAGE_MACHINE_READY
            update_app_settings(
                local_runtime_status="READY",
                local_status_message=message,
                local_status_updated_at=datetime.now().astimezone(),
            )
            self._apply_runtime_status("READY", message)
        self._finish_sync_batch(False, error_message)

    def _finish_sync_batch(self, ok, message):
        self._batch_in_flight = False
        if self._batch_command_id is not None:
            self._ack_command(
                self._batch_command_id,
                "ACK" if ok else "FAILED",
                None if ok else message,
            )
            self._batch_command_id = None

    ######################################################################
    # Đối soát dữ liệu (POST /api/sync/reconcile/check + .../pull) — Bước 9
    ######################################################################

    def _start_reconcile_check(self, manual):
        """manual=True: do nút "Check Data" (Register window) kích hoạt —
        nếu có lệch thì mở ReconcileWindow. manual=False: auto-trigger
        (STARTUP/NETWORK_RESTORED) — chỉ log/notification, không tự mở
        dialog làm phiền operator đang thao tác."""
        if self._reconcile_in_flight:
            return
        self._reconcile_in_flight = True
        self._reconcile_manual = manual
        payload = build_reconcile_payload()
        self.server_worker.enqueue(
            "reconcile_check",
            correlation_id="reconcile",
            serial=self._serial,
            uid=self._uid,
            ip_address=None,
            **payload,
        )

    def _handle_reconcile_check_response(self, response):
        self._reconcile_in_flight = False
        code = response.get("code")
        data = response.get("data") or {}

        if code == "SYNC_RECONCILE_CHECK_READY":
            add_local_notification(
                "LOCAL_RECONCILE_SNAPSHOT_READY",
                "INFO",
                "Đối soát dữ liệu",
                "Server chưa đủ dữ liệu để so sánh — cần gửi thêm heartbeat/manifest.",
            )
        elif code == "SYNC_RECONCILE_MATCHED":
            add_local_notification(
                "LOCAL_RECONCILE_MATCHED",
                "INFO",
                "Đối soát dữ liệu",
                "Dữ liệu local và server khớp nhau.",
            )
        elif code == "SYNC_RECONCILE_DIFF_FOUND":
            diff = data.get("diff") or {}
            missing_server = len(diff.get("missing_on_server") or [])
            missing_local = len(diff.get("missing_on_local") or [])
            changed = len(diff.get("changed_records") or [])
            add_local_notification(
                "LOCAL_RECONCILE_DIFF_FOUND",
                "WARNING",
                "Đối soát dữ liệu — có lệch",
                f"Thiếu trên server: {missing_server}, thiếu trên local: {missing_local}, lệch: {changed}.",
            )
            if self._reconcile_manual:
                dlg = ReconcileWindow(
                    diff,
                    on_push=self._handle_reconcile_push,
                    on_pull=self._handle_reconcile_pull,
                    parent=self,
                )
                dlg.exec_()
        else:
            self._append_log(
                f"[{self._now()}] [Đối soát] Phản hồi không xác định: {code} — {response.get('message')}"
            )

    def _handle_reconcile_push(self, local_scan_ids):
        """Callback từ ReconcileWindow, nút "Push to Server" (Sync theo
        Local) — tái dùng nguyên hạ tầng batch-submit Bước 8, chỉ khác nguồn
        claim (theo id cụ thể thay vì oldest-N-pending)."""
        self._start_sync_batch("MANUAL", scan_ids=local_scan_ids)

    def _handle_reconcile_pull(self, local_scan_ids):
        """Callback từ ReconcileWindow, nút "Pull from Server" (Sync theo
        Server, đã gộp cả Review theo quyết định chốt trước khi làm bước
        này)."""
        self.server_worker.enqueue(
            "reconcile_pull",
            correlation_id="reconcile_pull",
            serial=self._serial,
            uid=self._uid,
            local_scan_ids=local_scan_ids,
        )

    def _handle_reconcile_pull_response(self, response):
        records = (response.get("data") or {}).get("records") or []
        count = apply_reconcile_pull(records)
        add_local_notification(
            "LOCAL_SYNC_FROM_SERVER_DONE",
            "INFO",
            "Đã đồng bộ từ server",
            f"{count} bản ghi đã cập nhật theo dữ liệu server.",
        )
        # "check lại" đúng theo doc sau khi sync xong — manual=False vì đây là
        # check XÁC NHẬN, không cần mở lại dialog.
        self._start_reconcile_check(manual=False)

    def _apply_runtime_status(self, status, message=None):
        """Điểm trung tâm gate màn scan chính theo local_runtime_status —
        cập nhật banner, disable/enable input, VÀ set self._scan_blocked
        (gate thật, xem on_data_received). Chỉ log/bắn notification khi
        trạng thái THẬT SỰ đổi so với lần trước (như _apply_server_online)."""
        changed = self._runtime_status != status
        self._runtime_status = status
        scan_enabled = status in SCAN_ENABLED_STATUSES
        self._scan_blocked = not scan_enabled

        # Kích hoạt kênh Socket.IO /machine-runtime ĐÚNG 1 LẦN/lần chạy app
        # — cố ý đặt TRƯỚC "if not changed: return" bên dưới, KHÔNG dựa vào
        # changed: máy đã APPROVED từ lần chạy trước (trường hợp phổ biến
        # nhất thực tế) có self._runtime_status được set TRÙNG initial_status
        # NGAY TRƯỚC lệnh gọi _apply_runtime_status() đầu tiên của cả app
        # run (xem _init_server_worker) — nghĩa là changed=False ngay ở lần
        # gọi ĐẦU TIÊN cho đúng trường hợp này, 1 guard dựa theo "đổi sang
        # READY" sẽ không bao giờ kích hoạt được. self._runtime_session_started
        # không phụ thuộc changed nên luôn đúng bất kể lệnh gọi READY nào
        # (có 7 chỗ gọi READY trong file) xảy ra trước.
        if status == "READY" and not self._runtime_session_started:
            self._runtime_session_started = True
            self._start_machine_runtime_session()

        for widget in (
            self.comboBoxChassisRear,
            self.spinBoxLedBar1Count,
            self.spinBoxLedBar2Count,
            self.spinBoxQrBottomCount,
            self.pushButtonReset,
        ):
            widget.setEnabled(scan_enabled)

        # Vòng lặp trên vừa mở khoá spinBoxLedBar2Count vô điều kiện — nếu
        # profile hiện tại không có Code LED 2, phải khoá lại ngay, không thì
        # BLOCKED -> READY sẽ mở nhầm cột 2 dù profile không cần nó.
        if scan_enabled:
            self._apply_ledbar2_lock(self._current_entry())

        self.labelRuntimeBanner.setVisible(not scan_enabled)
        if not scan_enabled:
            self.labelRuntimeBanner.setText(
                message or RUNTIME_BANNER_TEXT.get(status, status)
            )
            self.labelRuntimeBanner.setStyleSheet(
                RUNTIME_BANNER_STYLES.get(status, RUNTIME_BANNER_STYLES["_default"])
            )

        if scan_enabled:
            self._identity_status_timer.stop()
        elif self._serial and self._uid and not self._identity_status_timer.isActive():
            self._identity_status_timer.start()

        # Heartbeat PHẢI dừng khi BLOCKED (đúng doc), tự chạy lại khi thoát
        # BLOCKED — chỉ nếu đã từng bắt đầu (tránh gọi heartbeat trước khi
        # có machine_code, vd lúc NOT_REGISTERED/WAITING_*).
        if status == "BLOCKED":
            self._heartbeat_timer.stop()
        elif self._heartbeat_started and not self._heartbeat_timer.isActive():
            self._heartbeat_timer.start()

        if not changed:
            return
        self._append_log(f"[{self._now()}] [Định danh máy] Trạng thái: {status}.")
        if status == "BLOCKED":
            add_local_notification(
                "LOCAL_MACHINE_BLOCKED",
                "CRITICAL",
                "Máy bị khoá",
                message or "Máy bị khoá bởi server.",
            )
        elif status in ("WAITING_LICENSE", "WAITING_APPROVAL"):
            add_local_notification(
                "LOCAL_REGISTER_WAITING",
                "INFO",
                "Đang chờ đăng ký",
                message or "Vui lòng chờ, quá trình đăng ký đang được xử lý.",
            )
        elif status == "READY":
            add_local_notification(
                "LOCAL_REGISTER_APPROVED",
                "INFO",
                "Máy đã được duyệt",
                message or "Máy đã sẵn sàng hoạt động.",
            )

    def _start_machine_runtime_session(self):
        """Gọi đúng 1 lần (xem điểm gọi ở _apply_runtime_status) — kích hoạt
        kết nối Socket.IO /machine-runtime + gửi machine:hello/runtime:start
        khi đã có machine_code. self._serial/self._uid chắc chắn khác None
        tại đây (mọi đường tới READY đều đã qua kiểm tra đó trước)."""
        settings = get_app_settings()
        server_config = load_server_config()
        self._runtime_client.start_session(
            machine_code=settings.get("machine_code"),
            serial=self._serial,
            uid=self._uid,
            app_version=APP_VERSION,
            local_db_version=settings.get("local_db_version"),
            host=server_config["host"],
            port=server_config["port"],
        )
        self._runtime_snapshot_timer.start()

    def _on_runtime_connected(self):
        self._append_log(
            f"[{self._now()}] [Machine Runtime] Đã kết nối và được server chấp nhận."
        )
        add_local_notification(
            "LOCAL_RUNTIME_CONNECTED",
            "INFO",
            "Runtime đã kết nối",
            "Socket.IO machine-runtime đã kết nối và được server chấp nhận.",
        )

    def _on_runtime_reconnected(self):
        self._append_log(f"[{self._now()}] [Machine Runtime] Reconnect thành công.")
        add_local_notification(
            "LOCAL_RUNTIME_RECONNECTED",
            "INFO",
            "Runtime đã kết nối lại",
            "Socket.IO machine-runtime vừa reconnect và được server chấp nhận lại.",
        )

    def _on_runtime_disconnected(self, reason):
        self._append_log(f"[{self._now()}] [Machine Runtime] Mất kết nối: {reason}")
        add_local_notification(
            "LOCAL_RUNTIME_DISCONNECTED",
            "WARNING",
            "Runtime mất kết nối",
            f"Socket.IO machine-runtime mất kết nối — sẽ tự reconnect. ({reason})",
        )

    def _on_runtime_blocked(self, message):
        add_local_notification(
            "LOCAL_RUNTIME_BLOCKED", "CRITICAL", "Runtime bị chặn", message
        )
        self._append_log(f"[{self._now()}] [Machine Runtime] Bị chặn: {message}")
        self._apply_runtime_status("BLOCKED", message)

    def _apply_server_online(self, is_online):
        was_online = self._server_online
        changed = was_online != is_online
        self._server_online = is_online
        self.labelServerStatus.setText(SERVER_STATUS_LABELS[is_online])
        self.labelServerStatus.setStyleSheet(SERVER_STATUS_STYLES[is_online])
        if changed:
            state = "Đã kết nối" if is_online else "Mất kết nối"
            self._append_log(f"[{self._now()}] [Server] {state}.")
            if is_online:
                add_local_notification(
                    "LOCAL_SERVER_RECONNECTED",
                    "INFO",
                    "Server đã kết nối",
                    "Health check thành công — server đang online.",
                )
            else:
                add_local_notification(
                    "LOCAL_SERVER_OFFLINE",
                    "WARNING",
                    "Mất kết nối server",
                    "Health check thất bại — chuyển sang chế độ local-only.",
                )

        # Trigger NETWORK_RESTORED — bắt buộc so was_online is False (không
        # phải changed): self._server_online khởi tạo None, lần health-check
        # đầu tiên None->True cũng làm changed=True nhưng KHÔNG phải "vừa mất
        # mạng xong có lại", sẽ bắn nhầm trigger ngay lúc cold-boot (đua với
        # STARTUP, trước khi config/profile sẵn sàng). was_online is False chỉ
        # đúng lúc offline THẬT SỰ chuyển sang online.
        if is_online and was_online is False:
            self._maybe_start_sync_batch("NETWORK_RESTORED")
            # Gọi độc lập, không chờ batch xong mới check — đơn giản hơn phải
            # track chính xác "batch này có phải NETWORK_RESTORED không" để
            # chain đúng thứ tự. Nếu batch chưa xong lúc reconcile chạy, lần
            # check tiếp theo (auto hoặc bấm "Check Data") sẽ thấy đã khớp.
            self._start_reconcile_check(manual=False)

    ######################################################################
    # Configure
    ######################################################################

    def on_configure_clicked(self):
        dlg = ConfigWindow(self.manager, parent=self)
        dlg.exec_()
        # Đọc lại trạng thái bật/tắt HID scanner — có thể vừa đổi qua
        # checkbox trong dialog vừa đóng. _sync_reader_panel() bên dưới tự
        # gọi _rebuild_reader_table() (sẽ vẽ lại dòng "HID Scanner" đúng
        # trạng thái mới).
        self._hid_scanner_enabled = load_hid_scanner_enabled()
        self._sync_reader_panel()

    ######################################################################
    # Đăng ký máy với server
    ######################################################################

    def on_register_clicked(self):
        dlg = RegisterWindow(
            self.server_worker,
            app_version=APP_VERSION,
            app_release_date=APP_RELEASE_DATE,
            app_product=APP_PRODUCT,
            on_sync_now=lambda: self._maybe_start_sync_batch("MANUAL"),
            on_check_data=lambda: self._start_reconcile_check(manual=True),
            on_sync_profile=lambda: self._check_machine_config(),
            parent=self,
        )
        dlg.exec_()

    ######################################################################
    # Đổi địa chỉ server — lưu vào server/server_config.json, đọc lại mỗi
    # lần mở app (KHÔNG lưu trong database local)
    ######################################################################

    def on_change_server_ip_clicked(self):
        current = load_server_config()
        host, ok = QInputDialog.getText(
            self,
            "Change Server IP",
            "Server IP / host:",
            text=current["host"],
        )
        if not ok:
            return
        host = host.strip()
        if not host:
            QMessageBox.warning(self, "Invalid IP", "Server IP cannot be empty.")
            return
        if host == current["host"]:
            return
        save_server_config(host, current["port"])
        self.server_worker.update_config(
            ServerApiConfig(host=host, port=current["port"])
        )
        self._append_log(
            f"[{self._now()}] [Server] Đổi địa chỉ server sang {host}:{current['port']} — đang kiểm tra kết nối..."
        )
        self._check_server_health()

    ######################################################################
    # Mapping — chỉ hiển thị, dùng chung nguồn dữ liệu mẫu (mapping_store)
    ######################################################################

    def on_mapping_clicked(self):
        dlg = QDialog(self)
        uic.loadUi(MAPPING_UI_PATH, dlg)

        table = dlg.tableWidgetMapping
        entries = load_mappings()
        table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            table.setItem(row, 0, QTableWidgetItem(entry["chassis_rear"]))
            table.setItem(row, 1, QTableWidgetItem(entry["led1"]))
            table.setItem(row, 2, QTableWidgetItem(entry["led2"]))
            table.setItem(row, 3, QTableWidgetItem(str(entry["length_led"])))
            table.setItem(row, 4, QTableWidgetItem(str(entry["length_bottom"])))
            table.setItem(row, 5, QTableWidgetItem(str(entry["no_led"])))
            table.setItem(row, 6, QTableWidgetItem(str(entry["no_bottom"])))

        # Độ rộng cột theo nội dung thực tế: cột mã (Chassis Rear/LED1/LED2) cần
        # rộng hơn để chứa mã dài, cột Length/No chỉ cần đủ chỗ cho tiêu đề.
        table.setColumnWidth(0, 160)  # Code Chassis Rear
        table.setColumnWidth(1, 140)  # Code LED 1
        table.setColumnWidth(2, 140)  # Code LED 2
        table.setColumnWidth(3, 150)  # Length Code LED
        table.setColumnWidth(4, 170)  # Length Code Bottom
        table.setColumnWidth(5, 90)  # No Led

        dlg.exec_()

    ######################################################################
    # Chassis Rear — dữ liệu mẫu tạm (mapping_store), thay bằng server sau
    ######################################################################

    def _configure_chassis_rear_search(self):
        """Cho nhập để lọc mã chassis theo chuỗi con, không thêm text tự do."""
        combo = self.comboBoxChassisRear
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        line_edit = combo.lineEdit()
        line_edit.setFont(combo.font())
        line_edit.setPlaceholderText("Nhập để tìm mã Chassis Rear")
        line_edit.editingFinished.connect(self._finish_chassis_rear_search)
        self._last_valid_chassis_code = None
        self._finishing_chassis_rear_search = False

        completer = combo.completer()
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setMaxVisibleItems(12)
        completer.popup().setFont(combo.font())
        completer.activated[str].connect(self._finish_chassis_rear_search)
        combo.activated[str].connect(self._finish_chassis_rear_search)

    def _load_mappings(self):
        entries = load_mappings()
        self._mappings_by_chassis = {e["chassis_rear"]: e for e in entries}
        self._chassis_codes_casefold = {
            code.casefold(): code for code in self._mappings_by_chassis
        }
        self.comboBoxChassisRear.clear()
        self.comboBoxChassisRear.addItems(list(self._mappings_by_chassis.keys()))

    def _canonical_chassis_code(self, code):
        return self._chassis_codes_casefold.get((code or "").strip().casefold())

    def _finish_chassis_rear_search(self, selected_code=None):
        """Kết thúc nhập Chassis và trả keyboard events lại cho HID scanner."""
        if self._finishing_chassis_rear_search:
            return

        self._finishing_chassis_rear_search = True
        try:
            canonical_code = self._canonical_chassis_code(selected_code)
            if canonical_code:
                self.comboBoxChassisRear.setCurrentText(canonical_code)
            self._restore_last_valid_chassis_code()
            self.comboBoxChassisRear.completer().popup().hide()
            self.comboBoxChassisRear.lineEdit().clearFocus()
        finally:
            self._finishing_chassis_rear_search = False

    def _restore_last_valid_chassis_code(self):
        """Khôi phục lựa chọn trước nếu người dùng rời ô với text chưa hợp lệ."""
        combo = self.comboBoxChassisRear
        if self._canonical_chassis_code(combo.currentText()):
            return

        fallback_code = self._last_valid_chassis_code
        entry = self._mappings_by_chassis.get(fallback_code)
        if not entry:
            return

        combo.blockSignals(True)
        combo.setCurrentText(fallback_code)
        combo.blockSignals(False)
        self._show_chassis_rear_entry(fallback_code, entry)

    def _show_chassis_rear_entry(self, code, entry):
        self.labelLedBar1RefCode.setText(entry["led1"] or "-")
        self.labelLedBar2RefCode.setText(entry["led2"] or "-")
        self.labelQrBottomRefCode.setText(code)
        self._apply_ledbar2_lock(entry)

    def on_chassis_rear_changed(self, code):
        canonical_code = self._canonical_chassis_code(code)
        entry = self._mappings_by_chassis.get(canonical_code)
        if not entry:
            self.labelLedBar1RefCode.setText("-")
            self.labelLedBar2RefCode.setText("-")
            self.labelQrBottomRefCode.setText("-")
            return

        if code != canonical_code:
            self.comboBoxChassisRear.blockSignals(True)
            self.comboBoxChassisRear.setEditText(canonical_code)
            self.comboBoxChassisRear.blockSignals(False)

        self._last_valid_chassis_code = canonical_code
        self._show_chassis_rear_entry(canonical_code, entry)
        update_app_settings(active_profile_id=entry.get("profile_id"))
        self._runtime_client.set_current_product(
            canonical_code, entry.get("profile_id")
        )

    def _apply_ledbar2_lock(self, entry):
        """Khoá cột LED BAR 2 (quota=0, disable spin+list+ref_label) khi
        profile hiện tại không có Code LED 2 — cột vẫn hiện, không ẩn. Mở lại
        (quota về 2, đúng default thiết kế trong .ui) CHỈ khi chuyển từ khoá
        -> mở, không ghi đè quota operator đã tự chỉnh khi đổi qua lại giữa
        các profile đều có Code LED 2 (theo dõi qua self._ledbar2_locked)."""
        widgets = self._column_widgets["ledbar2"]
        has_led2 = bool((entry or {}).get("led2"))
        if not has_led2:
            widgets["spin"].setValue(0)
            widgets["spin"].setEnabled(False)
            widgets["list"].setEnabled(False)
            widgets["ref_label"].setEnabled(False)
            self._ledbar2_locked = True
        else:
            if self._ledbar2_locked:
                widgets["spin"].setValue(2)
            widgets["spin"].setEnabled(True)
            widgets["list"].setEnabled(True)
            widgets["ref_label"].setEnabled(True)
            self._ledbar2_locked = False

    ######################################################################
    # Nạp danh sách reader đã lưu (JSON) lúc khởi động
    ######################################################################

    def _load_persisted_readers(self):
        for entry in load_readers():
            try:
                reader = self.manager.add_reader(
                    entry["name"],
                    entry["ip"],
                    entry["data_port"],
                    command_port=entry.get("command_port"),
                    parent=self,
                )
            except ValueError:
                continue
            self._reader_roles[entry["name"]] = entry.get(
                "role"
            ) or infer_role_from_name(entry["name"])
            reader.is_master = entry.get("is_master", False)
            self._wire_reader(reader)
            reader.start()
        self._rebuild_reader_table()

    ######################################################################
    # Đồng bộ bảng trạng thái reader sau khi đóng cửa sổ Configure
    ######################################################################

    def _sync_reader_panel(self):
        # _wired_readers theo dõi theo OBJECT (không phải theo tên) — reader
        # bị remove (qua Config Window) rồi add lại CÙNG TÊN là 1 object
        # SRXReaderQt hoàn toàn mới (ReaderManager.add_reader luôn tạo mới).
        # Nếu theo dõi bằng tên, tên đó vẫn "còn hợp lệ" ngay khi add lại
        # (không kịp bị coi là stale ở bước dọn), khiến vòng lặp dưới tưởng
        # nhầm object mới đã được wire rồi và bỏ qua — dataReceived/
        # statusChanged của object mới không bao giờ nối tới MainWindow
        # (Config Window vẫn báo kết nối được vì nó tự nối signal riêng cho
        # chính nó, độc lập với MainWindow).
        current_names = set(self.manager.names())
        current_readers = {self.manager.get(name) for name in current_names}
        self._wired_readers &= current_readers  # bỏ object đã bị remove khỏi manager

        # Role có thể đã đổi qua Config Window (thêm/xoá reader) — nạp lại từ
        # file (đã được ConfigWindow._persist() ghi mới nhất trước khi dialog
        # đóng modal), lọc theo reader còn tồn tại.
        self._reader_roles = {
            e["name"]: e.get("role") or infer_role_from_name(e["name"])
            for e in load_readers()
            if e["name"] in current_names
        }
        # KHÔNG cần nạp lại is_master ở đây — cờ này sống TRÊN object reader
        # (reader.is_master), ConfigWindow sửa trực tiếp lên cùng object chia
        # sẻ qua self.manager nên luôn tức thời, không cần đồng bộ qua JSON.

        for stale_name in set(self._status) - current_names:
            self._status.pop(stale_name, None)
            self._last_input.pop(stale_name, None)

        for name in current_names:
            reader = self.manager.get(name)
            if reader not in self._wired_readers:
                self._wire_reader(reader)
        self._rebuild_reader_table()

    def _wire_reader(self, reader):
        reader.dataReceived.connect(self.on_data_received)
        reader.statusChanged.connect(self.on_status_changed)
        self._status[reader.name] = {
            "data": "connected" if reader.is_data_connected() else "disconnected",
            "command": "connected" if reader.is_command_connected() else "disconnected",
        }
        self._wired_readers.add(reader)

    def _rebuild_reader_table(self):
        table = self.tableWidgetReaderStatus
        table.setRowCount(0)
        for name in self.manager.names():
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(name))
            status_item = QTableWidgetItem(self._status_label(name))
            status_item.setForeground(
                STATUS_COLORS.get(
                    self._status.get(name, {}).get("data"), QColor("black")
                )
            )
            table.setItem(row, 1, status_item)
            self._set_input_cell(row, self._last_input.get(name, ""))
            table.resizeRowToContents(row)

        # Máy quét HID cầm tay — không phải reader TCP thật (ReaderManager
        # không biết gì về nó), thêm 1 dòng cố định riêng để operator luôn
        # thấy trạng thái/mã vừa quét, nhất quán với các reader thật.
        row = table.rowCount()
        table.insertRow(row)
        table.setItem(row, 0, QTableWidgetItem(HID_SCANNER_NAME))
        status_item = QTableWidgetItem(
            "Đã bật" if self._hid_scanner_enabled else "Đã tắt"
        )
        status_item.setForeground(
            QColor("green" if self._hid_scanner_enabled else "red")
        )
        table.setItem(row, 1, status_item)
        self._set_input_cell(row, self._last_input.get(HID_SCANNER_NAME, ""))
        table.resizeRowToContents(row)

    ######################################################################
    # Máy quét mã vạch cầm tay (Keyboard-HID) — nguồn nhập liệu thứ 2
    ######################################################################

    def eventFilter(self, obj, event):
        """Khôi phục Chassis Rear khi click ngoài và bắt phím máy quét HID.

        Click vào vùng nền không làm QLineEdit mất focus nên không phát
        editingFinished; xử lý MouseButtonPress toàn cục để vẫn fallback.

        Bắt phím toàn cục để phát hiện chuỗi gõ từ máy quét HID (giả lập
        gõ phím + Enter). Phân biệt với người gõ phím thật bằng TỐC ĐỘ: máy
        quét gõ rất nhanh, người gõ tay chậm hơn nhiều — dùng time.monotonic()
        (đồng hồ đơn điệu, không bị ảnh hưởng chỉnh giờ hệ thống) đo khoảng
        cách giữa các lần nhấn phím liên tiếp. Chỉ hoạt động khi MainWindow
        là cửa sổ đang active (ConfigWindow/RegisterWindow mở modal sẽ tự
        làm QApplication.activeWindow() khác self, không cần điều kiện riêng).

        QUAN TRỌNG — đã tự verify bằng bug thật: nếu widget đang focus (vd 1
        QPushButton) không tiêu thụ 1 phím, Qt PHÁT LẠI CÙNG 1 event object
        lên từng widget cha (propagate), gọi lại eventFilter() 1 lần nữa cho
        MỖI cấp cha — khiến buffer bị nhân bản từng ký tự (vd "ZB36..." thành
        "ZZZZZBBBBB33333..."). Từng thử dedupe bằng id(event) cho CẢ ký tự
        thường LẪN Enter nhưng KHÔNG an toàn: CPython tái sử dụng đúng địa
        chỉ bộ nhớ cho các QKeyEvent ngắn hạn (đã tự verify bằng test thật
        theo 2 hướng riêng — ký tự bị mất do đè lẫn nhau trong 1 chuỗi, VÀ
        Enter của lượt quét SAU bị nhận nhầm trùng Enter của lượt TRƯỚC do
        object cũ vừa huỷ được cấp lại đúng địa chỉ). Giải pháp đúng — LUÔN
        NUỐT (return True) mọi phím (ký tự thường lẫn Enter) ngay khi tính
        năng đang bật, không cần dò trùng gì cả — chặn đứng Qt phát lại từ
        gốc. Riêng ô tìm Chassis Rear được loại trừ để người dùng vẫn nhập
        và xác nhận nội dung autocomplete bình thường."""
        if (
            event.type() == QEvent.MouseButtonPress
            and self.comboBoxChassisRear.lineEdit().hasFocus()
        ):
            combo = self.comboBoxChassisRear
            popup = combo.completer().popup()
            clicked_inside_search = isinstance(obj, QWidget) and (
                obj is combo
                or combo.isAncestorOf(obj)
                or obj is popup
                or popup.isAncestorOf(obj)
            )
            if not clicked_inside_search:
                self._finish_chassis_rear_search()

        if (
            event.type() == QEvent.KeyPress
            and self._hid_scanner_enabled
            and QApplication.activeWindow() is self
            and not self.comboBoxChassisRear.lineEdit().hasFocus()
        ):
            now = time.monotonic()
            gap = (
                None
                if self._hid_last_keypress_time is None
                else now - self._hid_last_keypress_time
            )
            self._hid_last_keypress_time = now

            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                buffer, self._hid_scan_buffer = self._hid_scan_buffer, ""
                if (
                    gap is not None
                    and gap <= HID_SCAN_MAX_GAP_SEC
                    and len(buffer) >= HID_SCAN_MIN_LENGTH
                ):
                    self._handle_hid_scan(buffer)
                return True

            text = event.text()
            if text.isprintable():
                if gap is None or gap > HID_SCAN_MAX_GAP_SEC:
                    self._hid_scan_buffer = text  # bắt đầu chuỗi mới
                else:
                    self._hid_scan_buffer += text
                return True
            return False
        return super().eventFilter(obj, event)

    def _detect_role_from_content(self, text):
        """Dùng chung cho 2 nguồn KHÔNG có 'vai trò cố định theo reader' —
        máy quét HID (1 nguồn duy nhất, quét lẫn lộn mọi loại mã) VÀ reader
        TCP bật cờ Is Master (gộp dữ liệu của chính nó lẫn mọi Slave qua UDP
        nội bộ Master/Slave của phần cứng, trả về qua 1 luồng TCP duy nhất —
        xem _is_master_mode_active()). Tự suy vai trò từ NỘI DUNG mỗi lần
        nhận: QRCODE BOTTOM luôn có tiền tố VN39; MỌI mã khác đều coi là LED
        BAR (kể cả không khớp độ dài/suffix nào — để _classify_led_bar tự
        đánh dấu NG qua _pick_fallback_led_column(), VẪN hiển thị lên màn
        hình, không âm thầm bỏ qua)."""
        return ROLE_QR_BOTTOM if text.startswith(QR_BOTTOM_PREFIX) else ROLE_LED_BAR

    def _handle_hid_scan(self, text):
        self._hid_scan_role = self._detect_role_from_content(text)
        self.on_data_received(HID_SCANNER_NAME, text)

    ######################################################################
    # Nhận dữ liệu / trạng thái từ reader (chạy trên GUI thread nhờ signal)
    ######################################################################

    def _reader_is_master(self, name):
        """Đọc cờ Is Master TRỰC TIẾP từ object reader (reader.is_master) —
        KHÔNG qua dict riêng (đã bỏ, từng gây bug thật: lệch pha đồng bộ
        giữa MainWindow/ConfigWindow khi tick Master lúc dialog đang mở)."""
        reader = self.manager.get(name)
        return bool(reader and reader.is_master)

    def _is_master_mode_active(self):
        """True nếu có ÍT NHẤT 1 reader đang bật cờ Is Master — khi đó toàn
        bộ app chuyển sang chế độ Master: CHỈ xử lý dữ liệu từ (các) reader
        Master, bỏ qua dữ liệu từ mọi reader KHÔNG bật cờ này (Slave) để
        tránh đếm trùng (Master đã relay đủ dữ liệu Slave qua UDP nội bộ
        Master/Slave phần cứng rồi). KHÔNG cache — tính lại mỗi lần gọi (rẻ,
        luôn đọc trực tiếp từ object reader, không lo lệch pha sau khi
        Config Window thêm/xoá/đổi cấu hình reader)."""
        return any(self._reader_is_master(n) for n in self.manager.names())

    def on_data_received(self, name, text):
        if self._scan_blocked:
            return

        if (
            name != HID_SCANNER_NAME
            and self._is_master_mode_active()
            and not self._reader_is_master(name)
        ):
            # Đang ở chế độ Master (có >=1 reader bật Is Master) — HOÀN TOÀN
            # không quan tâm dữ liệu từ reader KHÔNG phải Master (Slave):
            # dừng NGAY dòng đầu tiên của hàm, TRƯỚC MỌI xử lý khác (kể cả
            # _update_reader_input hiển thị chẩn đoán bên dưới — Slave vẫn
            # còn kết nối TCP thật, nhưng cột Input trên bảng Reader sẽ
            # KHÔNG cập nhật nữa trong lúc đang chế độ Master, đúng nghĩa
            # "không quan tâm slave"). Đặt thành điều kiện ĐẦU TIÊN (chỉ sau
            # _scan_blocked) thay vì chỉ "return sớm hơn 1 khối khác" — để
            # sau này có thêm bao nhiêu bước xử lý mới trong hàm này cũng
            # không thể vô tình chèn TRƯỚC khối này nữa (không còn "thứ tự"
            # nào để mà sai). Trước đây từng có bug thật: khối
            # `_session_pending_clear` ("có mã mới thì xoá kết quả phiên
            # trước") nằm trước khối này, khiến bản dữ liệu trùng từ Slave
            # (tới sau Master do đi qua nhiều chặng UDP/TCP hơn) vẫn kịp xoá
            # mất kết quả OK vừa chốt xong dù chính nó bị lọc bỏ.
            self._append_log(
                f"[{self._now()}] [{name}] Bỏ qua (đang ở chế độ Master, tránh trùng dữ liệu)"
            )
            return

        self._update_reader_input(name, text)

        if self._session_pending_clear:
            self._clear_session()
            self._session_pending_clear = False
            self._append_log(
                f"[{self._now()}] Sản phẩm mới — tự động xoá kết quả phiên trước."
            )

        is_ok = None
        code = None
        entry = self._current_entry()
        if name == HID_SCANNER_NAME:
            # HID Scanner không tra self._reader_roles — role đã được
            # _handle_hid_scan() tự suy từ nội dung ngay trước lời gọi này.
            role = self._hid_scan_role
        elif self._reader_is_master(name):
            # Reader bật Is Master relay CẢ dữ liệu của chính nó lẫn mọi
            # Slave qua 1 luồng TCP duy nhất — không còn tin được vào
            # self._reader_roles cố định nữa, tự suy như máy quét HID.
            role = self._detect_role_from_content(text)
        else:
            role = self._reader_roles.get(name)
        if role == ROLE_LED_BAR:
            if text == READER_SCAN_ERROR_TEXT:
                # Reader báo lỗi đọc rõ ràng — không chạy qua so khớp độ dài/
                # suffix (chắc chắn NG, dễ ra thông báo gây nhiễu như "Sai độ
                # dài mã LED: 5 ký tự...").
                column_key = self._pick_fallback_led_column()
                is_ok, code = False, NG_SCAN_FAILED
                self._append_log(f"[{self._now()}] [{name}] Không quét được mã (ERROR)")
            else:
                column_key, is_ok, code = self._classify_led_bar(text)
                if is_ok:
                    self._last_ok_led_text[column_key] = text
                else:
                    self._append_log(
                        f"[{self._now()}] [{name}] NG ({self._describe_ng(code, text, entry)}): {text}"
                    )
        elif role == ROLE_QR_BOTTOM:
            column_key = "qrbottom"
        else:
            column_key = None
        if column_key is None:
            return

        if column_key in ("ledbar1", "ledbar2") and len(text) >= 15:
            self.labelLotNo.setText(text[12:15])

        widgets = self._column_widgets[column_key]
        quota = widgets["spin"].value()

        if self._received_counts[column_key] >= quota:
            self._append_log(
                f"[{self._now()}] [{name}] Đã đủ số lượng ({quota}), bỏ qua mã dư: {text}"
            )
            self._ignored_scan_count += 1
            self._show_scan_ignored_warning()
            return

        # QRCODE BOTTOM luôn đọc đúng reader (không lẫn sang cột khác) nên hiển
        # thị mã lên danh sách NGAY, không chờ kiểm tra xong mới hiện — tránh
        # cảm giác "đọc được rồi mà màn hình chưa lên". Kiểm tra OK/NG (và đổi
        # màu) chạy đúng 1 lần lúc finalize — xem _finalize_scan_session().
        item = QListWidgetItem(_wrap_for_display(text, RESULT_WRAP_CHUNK))
        item.setTextAlignment(Qt.AlignCenter)
        _apply_item_result_color(
            item, RESULT_ITEM_COLORS.get(is_ok, RESULT_ITEM_COLORS[None])
        )
        widgets["list"].addItem(item)
        self._received_counts[column_key] += 1
        if self._received_counts[column_key] >= quota:
            self._append_log(
                f"[{self._now()}] [{name}] Đã đủ số lượng ({quota}/{quota})"
            )

        if (
            name != HID_SCANNER_NAME
            and self._is_master_mode_active()
            and sum(self._received_counts.values()) == 1
        ):
            # Vừa nhận mã ĐẦU TIÊN của 1 phiên MỚI ở chế độ Master — bắt đầu
            # đếm ngược 1 lần duy nhất (không reset khi có thêm mã tới trong
            # lúc đếm, xem _on_master_fill_timeout()). HID Scanner luôn loại
            # trừ (thao tác tay, tốc độ tuỳ ý).
            self._master_fill_timeout_timer.stop()
            timeout_seconds = load_master_fill_timeout_seconds()
            self._master_fill_timeout_timer.start(int(timeout_seconds * 1000))

        if column_key == "qrbottom":
            # Chưa kiểm tra ở đây — chỉ hiển thị trung tính ngay khi nhận
            # (item đã được tô RESULT_ITEM_COLORS[None] ở trên vì is_ok vẫn
            # là None). Kiểm tra thật + đổi màu chạy đúng 1 lần duy nhất lúc
            # finalize (đủ dữ liệu LED bar tham chiếu, không phụ thuộc thứ tự
            # reader nào về trước).
            self._session_qr = {"text": text, "item": item}
        else:
            self._session_led_seq += 1
            self._session_led_items[column_key].append(
                {
                    "text": text,
                    "is_ok": is_ok,
                    "code": code,
                    "seq": self._session_led_seq,
                }
            )

        self._update_progress()

        total_expected = sum(w["spin"].value() for w in self._column_widgets.values())
        total_received = sum(self._received_counts.values())
        if total_received >= total_expected:
            self._finalize_scan_session()

    def _current_entry(self):
        code = self._canonical_chassis_code(self.comboBoxChassisRear.currentText())
        return self._mappings_by_chassis.get(code)

    def _describe_ng(self, code, text, entry):
        """Dựng câu tiếng Việt hiển thị trong log từ mã NG cố định — không bao
        giờ để mã (tiếng Anh) lộ thẳng ra log, luôn đi qua đây để đồng bộ."""
        entry = entry or {}
        if code == NG_SCAN_FAILED:
            return "Không quét được mã"
        if code == NG_NO_PROFILE_SELECTED:
            return "Chưa chọn Chassis Rear"
        if code == NG_LED_SUFFIX_NOT_MATCH:
            length_led = entry.get("length_led")
            if length_led is not None and len(text) != length_led:
                return f"Sai độ dài mã LED: {len(text)} ký tự, cần {length_led} ký tự"
            return "5 ký tự cuối không khớp Code LED 1 hoặc Code LED 2"
        if code == NG_FULL_CODE_INVALID_LENGTH:
            return f"Sai độ dài mã QRCODE BOTTOM: {len(text)} ký tự, cần {entry.get('length_bottom')} ký tự"
        if code == NG_CHASSIS_NOT_MATCH:
            chassis_expected = (entry.get("chassis_rear") or "").replace("-", "")
            return f"Đoạn mã chassis không khớp: {text[4:14]} (cần {chassis_expected})"
        if code == NG_FULL_VENDOR_NOT_MATCH:
            no_bottom = entry.get("no_bottom")
            no_led = entry.get("no_led")
            led_ref_text = self._last_ok_led_text.get(
                "ledbar1"
            ) or self._last_ok_led_text.get("ledbar2")
            if not led_ref_text:
                return "Chưa có mã LED bar đọc đúng để đối chiếu vendor"
            if (
                not no_bottom
                or not no_led
                or no_bottom > len(text)
                or no_led > len(led_ref_text)
            ):
                return "Thiếu vị trí No Bottom/No Led để đối chiếu vendor"
            return (
                f"Vendor không khớp: ký tự {no_bottom}='{text[no_bottom - 1]}' "
                f"so với mã LED bar ký tự {no_led}='{led_ref_text[no_led - 1]}'"
            )
        if code == NG_QR_BOTTOM_LED_NOT_MATCH:
            return f"Đoạn mã LED trong QRCODE BOTTOM không khớp: {text[19:24]}"
        if code == NG_FULL_FACTORY_NOT_MATCH:
            return f"Mã factory không khớp: {text[24:28]} (cần {entry.get('factory_code')})"
        if code == NG_LOCAL_DUPLICATE:
            first_scan_at = self._last_duplicate_first_scan_at
            if first_scan_at is not None:
                return f"Trùng mã trong ngày (lần đầu lúc {first_scan_at:%H:%M:%S})"
            return "Trùng mã trong ngày"
        return f"Lỗi không xác định ({code})"

    def _pick_fallback_led_column(self):
        """Chọn cột LED BAR để gán tạm cho mã không xác định được cột qua nội
        dung (chưa chọn profile, hoặc không khớp cả led1/led2) — ưu tiên
        ledbar1 nếu còn thiếu số lượng, rồi mới xét ledbar2 (chỉ nếu đang mở
        khoá, quota > 0). Cả 2 đã đủ/khoá -> trả ledbar1, on_data_received tự
        phát hiện đã đủ và bỏ qua mã dư (logic sẵn có)."""
        w1, w2 = self._column_widgets["ledbar1"], self._column_widgets["ledbar2"]
        if self._received_counts["ledbar1"] < w1["spin"].value():
            return "ledbar1"
        if (
            w2["spin"].value() > 0
            and self._received_counts["ledbar2"] < w2["spin"].value()
        ):
            return "ledbar2"
        return "ledbar1"

    def _append_scan_failed_item(self, column_key):
        """Tạo 1 item NG (SCAN_FAILED) cho column_key và cập nhật state
        phiên — dùng cho _on_master_fill_timeout() điền vị trí Master relay
        im lặng. KHÔNG kiểm tra quota (caller đảm bảo còn chỗ trống), KHÔNG
        gọi _update_progress()/_finalize_scan_session() (caller tự làm sau
        khi điền xong toàn bộ vị trí thiếu). Cố ý KHÔNG dùng chung với nhánh
        "ERROR" tường minh ở on_data_received: nhánh đó còn phải chạy qua
        kiểm tra quota/log/lot-no/điều kiện chốt phiên riêng, gộp chung sẽ
        phải thêm nhiều nhánh rẽ mới cho 1 đoạn code vốn đã chạy đúng."""
        widgets = self._column_widgets[column_key]
        item = QListWidgetItem(
            _wrap_for_display(READER_SCAN_ERROR_TEXT, RESULT_WRAP_CHUNK)
        )
        item.setTextAlignment(Qt.AlignCenter)
        _apply_item_result_color(item, RESULT_ITEM_COLORS[False])
        widgets["list"].addItem(item)
        self._received_counts[column_key] += 1
        if column_key == "qrbottom":
            self._session_qr = {"text": READER_SCAN_ERROR_TEXT, "item": item}
        else:
            self._session_led_seq += 1
            self._session_led_items[column_key].append(
                {
                    "text": READER_SCAN_ERROR_TEXT,
                    "is_ok": False,
                    "code": NG_SCAN_FAILED,
                    "seq": self._session_led_seq,
                }
            )

    def _classify_led_bar(self, text):
        """Xác định code này thuộc cột LED BAR 1 hay 2 — theo NỘI DUNG mã,
        không phụ thuộc reader vật lý nào gửi lên (mọi reader vai trò LED BAR
        đều gọi qua đây):
        1. Số ký tự phải bằng Length Code LED (theo Chassis Rear đang chọn).
        2. 5 ký tự cuối phải giống 5 ký tự cuối của Code LED 1 hoặc Code LED 2.
        Nếu không thỏa 1 trong 2 điều kiện trên với cả 2 code (hoặc chưa chọn
        profile), không thể xác định cột qua nội dung -> gán tạm qua
        _pick_fallback_led_column() và đánh dấu NG."""
        entry = self._current_entry()
        if not entry:
            return self._pick_fallback_led_column(), False, NG_NO_PROFILE_SELECTED

        length_led = entry.get("length_led")
        code_led1 = entry.get("led1") or ""
        code_led2 = entry.get("led2") or ""

        length_ok = length_led is not None and len(text) == length_led
        match1 = length_ok and len(code_led1) >= 5 and text[-5:] == code_led1[-5:]
        match2 = length_ok and len(code_led2) >= 5 and text[-5:] == code_led2[-5:]

        if match1:
            return "ledbar1", True, None
        if match2:
            return "ledbar2", True, None

        return self._pick_fallback_led_column(), False, NG_LED_SUFFIX_NOT_MATCH

    def _classify_qr_bottom(self, text):
        """Kiểm tra mã QRCODE BOTTOM (reader này luôn đọc đúng cột, không cần
        định tuyến như LED BAR). Kiểm tra trùng trong ngày KHÔNG chạy ở đây
        nữa — chuyển sang _finalize_scan_session() (chỉ chạy khi cả phiên đã
        OK, đúng nguyên tắc "chỉ so OK với OK").
        1. Số ký tự phải bằng Length Code Bottom.
        2. Ký tự thứ 5-14 phải giống Code Chassis Rear (bỏ dấu "-").
        3. Ký tự thứ "No Bottom" phải giống ký tự thứ "No Led" của 1 mã LED
           BAR bất kỳ ĐÃ đọc đúng (mã led bar thật, không phải code led).
        4. Ký tự 20-24 phải khớp 5 ký tự cuối Code LED 1 hoặc Code LED 2 —
           trả thêm code LED nào đã khớp (để ghi full_led_code).
        5. Ký tự 25-28 phải khớp Factory Code đang cấu hình.

        Trả về (is_ok, ng_code, matched_led_code)."""
        entry = self._current_entry()
        if not entry:
            return False, NG_NO_PROFILE_SELECTED, None

        length_bottom = entry.get("length_bottom")
        chassis_rear = entry.get("chassis_rear") or ""
        no_bottom = entry.get("no_bottom")
        no_led = entry.get("no_led")
        code_led1 = entry.get("led1") or ""
        code_led2 = entry.get("led2") or ""
        factory_code = entry.get("factory_code") or ""

        if length_bottom is None or len(text) != length_bottom:
            return False, NG_FULL_CODE_INVALID_LENGTH, None

        chassis_in_qr = text[4:14]
        chassis_expected = chassis_rear.replace("-", "")
        if chassis_in_qr != chassis_expected:
            return False, NG_CHASSIS_NOT_MATCH, None

        led_ref_text = self._last_ok_led_text.get(
            "ledbar1"
        ) or self._last_ok_led_text.get("ledbar2")
        if not led_ref_text:
            return False, NG_FULL_VENDOR_NOT_MATCH, None
        if (
            not no_bottom
            or not no_led
            or no_bottom > len(text)
            or no_led > len(led_ref_text)
        ):
            return False, NG_FULL_VENDOR_NOT_MATCH, None
        if text[no_bottom - 1] != led_ref_text[no_led - 1]:
            return False, NG_FULL_VENDOR_NOT_MATCH, None

        led_in_qr = text[19:24]
        match1 = len(code_led1) >= 5 and led_in_qr == code_led1[-5:]
        match2 = len(code_led2) >= 5 and led_in_qr == code_led2[-5:]
        if not (match1 or match2):
            return False, NG_QR_BOTTOM_LED_NOT_MATCH, None
        matched_led_code = code_led1 if match1 else code_led2

        factory_in_qr = text[24:28]
        if factory_code and factory_in_qr != factory_code:
            return False, NG_FULL_FACTORY_NOT_MATCH, None

        return True, None, matched_led_code

    def on_status_changed(self, name, channel, status):
        self._status.setdefault(name, {})[channel] = status
        self._append_log(
            f"[{self._now()}] [{name}] Trạng thái ({channel}): {STATUS_LABELS.get(status, status)}"
        )
        self._update_reader_row_status(name)

    def _update_reader_row_status(self, name):
        table = self.tableWidgetReaderStatus
        for row in range(table.rowCount()):
            if table.item(row, 0).text() == name:
                item = table.item(row, 1)
                item.setText(self._status_label(name))
                item.setForeground(
                    STATUS_COLORS.get(
                        self._status.get(name, {}).get("data"), QColor("black")
                    )
                )
                return

    def _update_reader_input(self, name, text):
        self._last_input[name] = text
        table = self.tableWidgetReaderStatus
        for row in range(table.rowCount()):
            if table.item(row, 0).text() == name:
                self._set_input_cell(row, text)
                table.resizeRowToContents(row)
                return

    def _set_input_cell(self, row, text):
        # Chèn "\n" thủ công theo số ký tự vừa khít độ rộng cột THỰC TẾ (cột
        # Input tự giãn theo stretchLastSection nên không có 1 số cố định) —
        # tránh vừa dư khoảng trắng vừa tránh bị cắt "..." như QTableWidgetItem.
        label = QLabel()
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        col_width = self.tableWidgetReaderStatus.columnWidth(2)
        char_width = max(label.fontMetrics().averageCharWidth(), 1)
        chars_per_line = max(8, (col_width - 12) // char_width)
        label.setText(_wrap_for_display(text, chars_per_line))
        self.tableWidgetReaderStatus.setCellWidget(row, 2, label)

    def _status_label(self, name):
        status = self._status.get(name, {}).get("data")
        return STATUS_LABELS.get(status, "-")

    ######################################################################
    # Progress — tổng số mã đã nhận / tổng số mã cần (theo 3 ô Quantity)
    ######################################################################

    def _update_progress(self):
        total_expected = sum(w["spin"].value() for w in self._column_widgets.values())
        total_received = sum(self._received_counts.values())
        self.progressBarScan.setMaximum(max(total_expected, 1))
        self.progressBarScan.setValue(min(total_received, total_expected))

    ######################################################################
    # Gộp 3 reader thành 1 bản ghi scan khi đủ số lượng (progress bar đầy)
    ######################################################################

    def _on_master_fill_timeout(self):
        """Hết thời gian chờ (chế độ Master) mà phiên vẫn chưa đủ mã — Master
        relay không gửi gì cho (các) vị trí trạm vật lý đọc lỗi (khác hẳn TCP
        độc lập, nơi mỗi reader luôn tự gửi "ERROR" tường minh). Điền
        SCAN_FAILED cho MỌI vị trí còn thiếu rồi tự chốt phiên, không chờ
        on_data_received (đường total_received>=total_expected ở đó sẽ không
        bao giờ tới vì im lặng vĩnh viễn, không phải "tới trễ")."""
        total_expected = sum(w["spin"].value() for w in self._column_widgets.values())
        total_received = sum(self._received_counts.values())
        if total_received >= total_expected:
            # Phiên đã hoàn tất bằng dữ liệu thật ngay trước khi timer kịp
            # bắn (đua thời gian) — _finalize_scan_session() lẽ ra đã
            # stop() timer này, nhưng phòng hờ trường hợp không kịp: không
            # làm gì thêm, tránh điền chồng lên phiên đã chốt.
            return

        filled_columns = []
        for column_key in ("ledbar1", "ledbar2", "qrbottom"):
            widgets = self._column_widgets[column_key]
            missing = widgets["spin"].value() - self._received_counts[column_key]
            for _ in range(missing):
                self._append_scan_failed_item(column_key)
                filled_columns.append(column_key)

        if not filled_columns:
            return

        timeout_seconds = load_master_fill_timeout_seconds()
        self._append_log(
            f"[{self._now()}] Hết thời gian chờ ({timeout_seconds}s) ở chế độ Master — "
            f"tự động đánh dấu lỗi cho vị trí chưa nhận được mã: {', '.join(filled_columns)}"
        )
        self._update_progress()
        self._finalize_scan_session()

    def _finalize_scan_session(self):
        """Gọi khi tổng số mã đã nhận == tổng Quantity 3 cột (1 sản phẩm đã
        quét xong đủ mọi mảnh). Gộp toàn bộ item đã thu thập trong phiên
        thành 1 dòng local_scan_records + nhiều dòng local_scan_led_items."""
        # Dừng timer điền lỗi Master (nếu còn đang đếm) — che cả 2 trường
        # hợp: chốt phiên bình thường (đủ quota thật), VÀ chính
        # _on_master_fill_timeout() gọi hàm này ở cuối (.stop() trên 1
        # singleShot QTimer đã bắn rồi là no-op an toàn).
        self._master_fill_timeout_timer.stop()

        qr = self._session_qr
        if qr is None:
            return

        entry = self._current_entry()

        # Kiểm tra QRCODE BOTTOM đúng 1 lần duy nhất tại đây — không kiểm tra
        # lúc vừa nhận, vì lúc đó LED bar tham chiếu (_last_ok_led_text) có
        # thể chưa đủ nếu QR bottom về trước LED bar. Tới đây, cả phiên đã đủ
        # dữ liệu (progress bar đầy) nên kết quả luôn đúng bất kể thứ tự về.
        if qr["text"] == READER_SCAN_ERROR_TEXT:
            # Xem chú thích tương tự ở on_data_received (LED bar) — reader
            # báo lỗi đọc rõ ràng, không chạy qua 5 bước đối chiếu của
            # _classify_qr_bottom (chắc chắn NG, tránh thông báo gây nhiễu
            # như "Sai độ dài mã QRCODE BOTTOM: 5 ký tự...").
            own_is_ok, own_code, matched_led_code = False, NG_SCAN_FAILED, None
        else:
            own_is_ok, own_code, matched_led_code = self._classify_qr_bottom(qr["text"])
        # own_code=NG_FULL_VENDOR_NOT_MATCH nhưng KHÔNG có bất kỳ mã LED OK
        # nào trong phiên (led_ref_text rỗng ở _classify_qr_bottom) — nghĩa
        # là QR bottom KHÔNG THỂ xác minh được (thiếu tham chiếu), không
        # phải "chắc chắn sai". Không nên tô đỏ như 1 lỗi thật sự của chính
        # QR bottom — dùng màu trung tính (None/xám) để phản ánh đúng "chưa
        # xác định được", tránh đánh lừa operator giống bug LED-lây-QR đã sửa.
        own_unverifiable = own_code == NG_FULL_VENDOR_NOT_MATCH and not (
            self._last_ok_led_text.get("ledbar1")
            or self._last_ok_led_text.get("ledbar2")
        )
        if own_unverifiable:
            _apply_item_result_color(qr["item"], RESULT_ITEM_COLORS[None])
        else:
            _apply_item_result_color(
                qr["item"], RESULT_ITEM_COLORS.get(own_is_ok, RESULT_ITEM_COLORS[None])
            )

        led_ledbar1 = self._session_led_items["ledbar1"]
        led_ledbar2 = self._session_led_items["ledbar2"]
        all_led_ok = all(it["is_ok"] for it in led_ledbar1 + led_ledbar2)

        is_ok = own_is_ok and all_led_ok
        if is_ok:
            ng_reason = None
            ng_text = None
        elif not all_led_ok:
            # LED bar sai là nguyên nhân gốc rất có thể khiến QR bottom không
            # đối chiếu được vendor (NG_FULL_VENDOR_NOT_MATCH do thiếu tham
            # chiếu — _classify_qr_bottom không có mã LED OK nào để so) — ưu
            # tiên báo đúng lỗi LED bar, tránh đánh lừa operator nghĩ QR
            # bottom sai trong khi QR bottom có thể vẫn đúng (LED sai lây
            # sang QR bottom, không phải ngược lại).
            # min(..., key=seq) chứ không phải next() trên list nối — next()
            # sẽ luôn ưu tiên hết ledbar1 rồi mới xét ledbar2 (mất thứ tự
            # thời gian NHẬN THẬT giữa 2 cột nếu cả 2 đều có mã NG); seq gán
            # lúc on_data_received nhận mã mới phản ánh đúng mã nào lỗi TRƯỚC.
            ng_item = min(
                (it for it in led_ledbar1 + led_ledbar2 if not it["is_ok"]),
                key=lambda it: it["seq"],
            )
            ng_reason = ng_item["code"]
            # _describe_ng cần đúng TEXT của item đang bị NG để dựng câu (vd
            # độ dài mã) — dùng qr["text"] (35 ký tự QR bottom) ở đây sẽ ra
            # câu sai hoàn toàn ("Sai độ dài mã LED: 35 ký tự...") vì lẫn văn
            # bản của QR bottom vào lỗi của LED bar.
            ng_text = ng_item["text"]
        else:
            # LED bar đều OK — QR bottom sai là lỗi thật của chính nó.
            ng_reason = own_code
            ng_text = qr["text"]

        profile_id = entry.get("profile_id") if entry else None
        # own_is_ok (không phải is_ok tổng hợp) — theo doc: "duplicate_key vẫn
        # nên gửi nếu parse được", kể cả khi final NG do LED bar lỗi (QR bottom
        # tự nó vẫn hợp lệ, chỉ NG vì LED bar), không chỉ khi final OK hẳn.
        duplicate_key = compute_duplicate_key(qr["text"]) if own_is_ok else None
        qr_data = self._build_qr_data(
            qr["text"], entry, matched_led_code, duplicate_key
        )
        led_items_data = self._build_led_items_data(led_ledbar1, led_ledbar2, entry)
        scan_at = datetime.now().astimezone()

        try:
            final_is_ok, final_reason, first_scan_at, local_scan_id = record_full_scan(
                profile_id,
                qr_data,
                led_items_data,
                is_ok,
                ng_reason,
                scan_at=scan_at,
            )
        except Exception as exc:
            self._append_log(f"[{self._now()}] Lỗi ghi local DB: {exc}")
            self._runtime_client.emit_runtime_error("LOCAL_DB_WRITE_FAILED", str(exc))
            final_is_ok, final_reason, first_scan_at, local_scan_id = (
                is_ok,
                ng_reason,
                None,
                None,
            )

        self._runtime_client.record_scan_result(
            product_code=(entry or {}).get("chassis_rear"),
            profile_id=profile_id,
            is_ok=final_is_ok,
            last_code=qr["text"],
            local_scan_id=local_scan_id or "",
            pending_sync=get_scan_counts().get("pending_sync", 0),
        )

        if final_reason == NG_LOCAL_DUPLICATE:
            self._last_duplicate_first_scan_at = first_scan_at

        if final_is_ok:
            # Đã pass local nhưng CHƯA chốt final OK — chờ server xác nhận
            # SERVER_OK (nguyên tắc "chỉ so OK với OK", doc mục 6.7/27: không
            # hiển thị final OK khi final_status còn PENDING_SERVER). Hiện
            # VÀNG, label CHƯA hiện "OK" — xem _reflect_scan_submit_ui.
            _apply_item_result_color(qr["item"], PENDING_ITEM_COLOR)
            self.set_result_status("pending")
            if local_scan_id is not None:
                self._pending_scan_ui[local_scan_id] = (
                    self._session_generation,
                    qr["item"],
                )
        else:
            # Chỉ tô đỏ khung QR bottom khi CHÍNH QR bottom là nguyên nhân NG
            # (own_is_ok=False VÀ xác định được thật — không phải chỉ vì
            # thiếu tham chiếu LED, xem own_unverifiable ở trên), hoặc trùng
            # mã (trùng mã cũng gắn với chính mã QR bottom này). Nếu NG do
            # LED bar sai (own_is_ok=True) hoặc không xác minh được
            # (own_unverifiable), GIỮ màu đã set ở trên (xanh/xám) — trước
            # đây tô đè đỏ vô điều kiện ở đây khiến khung QR bottom báo sai
            # dù bản thân nó đúng/chưa rõ, mâu thuẫn với lý do NG thật đã
            # hiển thị trên banner (LED bar).
            qr_is_culprit = (
                not own_is_ok and not own_unverifiable
            ) or final_reason == NG_LOCAL_DUPLICATE
            if qr_is_culprit:
                _apply_item_result_color(qr["item"], RESULT_ITEM_COLORS[False])
            # ng_text rỗng khi final_reason bị record_full_scan ghi đè thành
            # NG_LOCAL_DUPLICATE (phát hiện trùng phía DB, không phải nhánh
            # ng_reason đã tính ở trên) — _describe_ng không cần text cho
            # trường hợp đó nên fallback qr["text"] chỉ để không truyền None.
            detail = self._describe_ng(final_reason, ng_text or qr["text"], entry)
            add_local_notification("LOCAL_SCAN_NG", "ERROR", "Kết quả: NG", detail)
            # Bấm ngay 1 lần thay vì chờ _notification_poll_timer (tối đa
            # NOTIFICATION_POLL_INTERVAL_MS sau) — labelResultStatus đổi tức
            # thì ngay dòng dưới, để banner đổi TRỄ hơn dễ gây cảm giác lệch/
            # giật cho operator dù cùng 1 kết quả.
            self._poll_latest_notification()
            self.set_result_status("ng")

        # OK/pending: không xoá màn hình ngay, chờ mã mới của sản phẩm tiếp
        # theo mới xoá (xem đầu on_data_received) — để operator kịp nhìn kết
        # quả nhưng không bị chặn chờ server. NG: không set cờ, giữ nguyên
        # hiển thị tới khi bấm Reset thủ công.
        self._session_pending_clear = final_is_ok
        self._session_led_items = {"ledbar1": [], "ledbar2": []}
        self._session_led_seq = 0
        self._session_qr = None

        # Submit lên server — CẢ OK LẪN NG (doc: "Local NG vẫn gửi server để
        # lưu trace"), kể cả khi QR bottom không tự parse được (duplicate_key/
        # full_code.led_code = None) — server đã bỏ validate bắt buộc 2 field
        # này (xác nhận thật 2026-07-15, trả LOCAL_NG_SAVED bình thường kể cả
        # payload rỗng gần hết). Chỉ bỏ qua khi thiếu profile_id (bắt buộc —
        # chưa chọn Chassis Rear thì không đủ dữ liệu hợp lệ để gửi).
        if profile_id is None:
            self._append_log(
                f"[{self._now()}] [Scan] Bỏ qua submit — chưa chọn Chassis Rear."
            )
        elif local_scan_id is not None:
            self._submit_scan(
                local_scan_id,
                qr_data,
                led_items_data,
                profile_id,
                final_is_ok,
                final_reason,
                scan_at,
            )

    def _build_qr_data(self, text, entry, matched_led_code, duplicate_key):
        entry = entry or {}
        return {
            "full_code_raw": text,
            "full_prefix": text[0:4] if len(text) >= 4 else None,
            "full_chassis_segment": text[4:14] if len(text) >= 14 else None,
            "full_chassis_code": entry.get("chassis_rear"),
            "full_before_vendor": text[14:17] if len(text) >= 17 else None,
            "full_vendor_char": text[17:18] if len(text) >= 18 else None,
            "full_led_code": matched_led_code,
            "full_factory_code": text[24:28] if len(text) >= 28 else None,
            "full_after_factory": text[28:] if len(text) >= 28 else None,
            "chassis_scan_raw": self.comboBoxChassisRear.currentText() or None,
            "duplicate_key": duplicate_key,
        }

    @staticmethod
    def _build_led_items_data(ledbar1_items, ledbar2_items, entry):
        entry = entry or {}
        no_led = entry.get("no_led")
        result = []
        for slot, items in ((1, ledbar1_items), (2, ledbar2_items)):
            for index, it in enumerate(items, start=1):
                text = it["text"]
                vendor_char = (
                    text[no_led - 1] if no_led and len(text) >= no_led else None
                )
                result.append(
                    {
                        "led_slot": slot,
                        "led_index": index,
                        "led_scan_raw": text,
                        "led_lot_no": text[12:15] if len(text) >= 15 else None,
                        "vendor_char": vendor_char,
                        "led_suffix": text[-5:] if len(text) >= 5 else text,
                        "local_status": "OK" if it["is_ok"] else "NG",
                        "ng_reason": it["code"],
                    }
                )
        return result

    ######################################################################
    # Submit scan lên server (POST /api/scans/submit)
    ######################################################################

    def _submit_scan(
        self,
        local_scan_id,
        qr_data,
        led_items_data,
        profile_id,
        is_ok,
        ng_reason,
        scan_at,
    ):
        payload = {
            "local_scan_id": local_scan_id,
            "machine_code": get_app_settings().get("machine_code"),
            "serial": self._serial,
            "uid": self._uid,
            "profile_id": profile_id,
            "duplicate_key": qr_data.get("duplicate_key"),
            "full_code": {
                "raw": qr_data.get("full_code_raw"),
                "prefix": qr_data.get("full_prefix"),
                "chassis_code": qr_data.get("full_chassis_code"),
                "before_vendor": qr_data.get("full_before_vendor"),
                "vendor_char": qr_data.get("full_vendor_char"),
                "led_code": qr_data.get("full_led_code"),
                "factory_code": qr_data.get("full_factory_code"),
                "after_factory": qr_data.get("full_after_factory"),
            },
            "chassis_scan_raw": qr_data.get("chassis_scan_raw"),
            "led_scans": [
                {
                    "slot": item["led_slot"],
                    "index": item["led_index"],
                    "raw": item["led_scan_raw"],
                    "lot_no": item.get("led_lot_no"),
                    "vendor_char": item.get("vendor_char"),
                    "suffix": item.get("led_suffix"),
                    "status": item.get("local_status"),
                    "ng_reason": item.get("ng_reason"),
                }
                for item in led_items_data
            ],
            "local_status": "OK" if is_ok else "NG",
            "local_ng_reason": ng_reason,
            "scan_at": scan_at.isoformat(),
        }
        self.server_worker.enqueue(
            "scan_submit", correlation_id=local_scan_id, scan_payload=payload
        )

    def _handle_scan_submit_result(self, local_scan_id, response):
        code = response.get("code")
        if code not in ("SERVER_OK", "SERVER_DUPLICATE", "LOCAL_NG_SAVED"):
            self._append_log(
                f"[{self._now()}] [Scan] Phản hồi không xác định (id={local_scan_id}): {code} — {response.get('message')}"
            )
            return
        apply_scan_submit_result(local_scan_id, response)
        self._reflect_scan_submit_ui(local_scan_id, code)
        if code == "SERVER_DUPLICATE":
            add_local_notification(
                "SERVER_DUPLICATE",
                "ERROR",
                "Server phát hiện trùng",
                f"Server phát hiện mã quét bị trùng lặp (mã: {local_scan_id}).",
            )
            self._poll_latest_notification()

    def _reflect_scan_submit_ui(self, local_scan_id, code):
        """Chỉ đụng UI nếu operator CHƯA chuyển sang sản phẩm khác từ lúc
        submit này được gửi đi (so generation) — response về sau khi đã
        chuyển phiên thì chỉ có DB được cập nhật (đã làm ở nơi gọi), bỏ qua
        UI để tránh hiện sai/đụng vào QListWidgetItem đã bị Qt xoá."""
        pending = self._pending_scan_ui.pop(local_scan_id, None)
        if pending is None:
            return
        generation, item = pending
        if generation != self._session_generation:
            return
        if code == "SERVER_OK":
            _apply_item_result_color(item, RESULT_ITEM_COLORS[True])
            self.set_result_status("ok")
            add_local_notification(
                "LOCAL_SCAN_OK", "INFO", "Kết quả: OK", "Sản phẩm đạt yêu cầu."
            )
            self._poll_latest_notification()  # xem ghi chú ở _finalize_scan_session — tránh banner đổi trễ hơn label
        else:
            _apply_item_result_color(item, RESULT_ITEM_COLORS[False])
            self.set_result_status("ng")
            if (
                code != "SERVER_DUPLICATE"
            ):  # SERVER_DUPLICATE đã có notification riêng, tránh trùng
                add_local_notification(
                    "LOCAL_SCAN_NG",
                    "ERROR",
                    "Kết quả: NG",
                    "Server ghi nhận kết quả không đạt.",
                )
                self._poll_latest_notification()

    ######################################################################
    # Reset — dùng khi NG, xoá mã đã nhận để bắt đầu đợt kiểm mới
    ######################################################################

    def _clear_session(self):
        # Dừng timer điền lỗi Master nếu còn đang đếm dở — tránh bắn muộn
        # vào phiên MỚI sau khi màn hình đã xoá (vd bấm Reset thủ công giữa
        # lúc đang chờ), không phải phiên cũ đã bị xoá này.
        self._master_fill_timeout_timer.stop()

        # Tăng generation TRƯỚC khi xoá widget — mọi response submit đang chờ
        # (đã lưu generation cũ trong _pending_scan_ui) sẽ tự biết item của nó
        # không còn an toàn để đụng vào nữa (xem _reflect_scan_submit_ui).
        self._session_generation += 1
        for key, widgets in self._column_widgets.items():
            widgets["list"].clear()
            self._received_counts[key] = 0
        self._last_input.clear()
        self._last_ok_led_text.clear()
        self._session_led_items = {"ledbar1": [], "ledbar2": []}
        self._session_led_seq = 0
        self._session_qr = None
        self._rebuild_reader_table()
        self._update_progress()
        self.set_result_status(None)
        self.labelLotNo.setText("-")
        self._ignored_scan_count = 0
        self.labelScanIgnoredWarning.setVisible(False)

    def on_reset_clicked(self):
        self._clear_session()
        self._session_pending_clear = False
        self._reset_notification_banner()
        self._append_log(f"[{self._now()}] Reset — đã xoá mã đã nhận.")

    def _show_scan_ignored_warning(self):
        """Hiện banner vàng khi 1 mã bị bỏ qua vì cột đã đủ số lượng — trước
        đây chỉ ghi log, dễ bị bỏ lỡ trên xưởng. Banner tự ẩn khi Reset hoặc
        sản phẩm mới thật sự bắt đầu (xem _clear_session), không tự ẩn theo
        thời gian — để operator chắc chắn nhìn thấy dù không đứng cạnh máy
        đúng lúc mã bị bỏ qua."""
        self.labelScanIgnoredWarning.setStyleSheet(SCAN_IGNORED_WARNING_STYLE)
        self.labelScanIgnoredWarning.setText(
            f"{self._ignored_scan_count} mã đã bị bỏ qua (đã đủ số lượng) — "
            "nếu vừa có kết quả NG, bấm Reset trước khi quét sản phẩm mới."
        )
        self.labelScanIgnoredWarning.setVisible(True)

    ######################################################################
    # Khung kết quả OK/NG + cảnh báo hình ảnh/âm thanh
    ######################################################################

    def _init_result_alerts(self):
        # object() làm sentinel để lần set_result_status(None) đầu tiên vẫn áp
        # text/style, còn các lần gọi lặp cùng trạng thái sau đó bị bỏ qua.
        self._result_status = object()
        self._result_blink_visible = True

        self._result_blink_timer = QTimer(self)
        self._result_blink_timer.setInterval(RESULT_BLINK_INTERVAL_MS)
        self._result_blink_timer.timeout.connect(self._toggle_result_blink)

        # Dùng playlist 2 item giống nhau thay vì tự canh duration MP3 bằng
        # timer — Qt tự chuyển bài đúng lúc file thứ nhất kết thúc.
        self._result_audio_playlist = QMediaPlaylist(self)
        self._result_audio_playlist.setPlaybackMode(QMediaPlaylist.Sequential)
        self._result_audio_player = QMediaPlayer(self)
        self._result_audio_player.setPlaylist(self._result_audio_playlist)
        self._reported_result_audio_errors = set()
        self._reported_missing_sound_paths = set()
        self._result_audio_player.error.connect(self._on_result_audio_error)

    def set_result_status(self, result):
        """result: None ("-"), "ok", "ng", hoặc "pending" (đã pass local,
        đang chờ server xác nhận SERVER_OK — xem _finalize_scan_session).

        Hiệu ứng chỉ chạy khi trạng thái THẬT SỰ đổi sang OK/NG. Vì vậy lần
        server ack gọi lại "ng" cho một kết quả đã NG local sẽ không phát âm
        thanh hay khởi động lại nhấp nháy. Nền tiếp tục nhấp nháy cho tới khi
        phiên mới/reset đổi label sang trạng thái khác."""
        if result not in ("ok", "ng", "pending", None):
            result = None
        if result == self._result_status:
            return

        self._stop_result_alerts()
        self._result_status = result
        text = {"ok": "OK", "ng": "NG", "pending": "PENDING", None: "-"}.get(
            result, "-"
        )
        self.labelResultStatus.setText(text)
        self.labelResultStatus.setStyleSheet(
            RESULT_STYLE.get(result, RESULT_STYLE[None])
        )

        if result in ("ok", "ng"):
            self._start_result_alerts(result)

    def _start_result_alerts(self, result):
        self._result_blink_visible = True
        self._result_blink_timer.start()
        self._play_result_sound(result)

    def _toggle_result_blink(self):
        if self._result_status not in ("ok", "ng"):
            self._stop_result_alerts()
            return
        self._result_blink_visible = not self._result_blink_visible
        style = (
            RESULT_STYLE[self._result_status]
            if self._result_blink_visible
            else RESULT_BLINK_OFF_STYLE
        )
        self.labelResultStatus.setStyleSheet(style)

    def _play_result_sound(self, result):
        path = RESULT_SOUND_PATHS.get(result)
        if not path or not os.path.isfile(path):
            if path not in self._reported_missing_sound_paths:
                self._reported_missing_sound_paths.add(path)
                self._append_log(
                    f"[{self._now()}] [Âm thanh] Không tìm thấy file: {path}"
                )
            return

        media = QMediaContent(QUrl.fromLocalFile(os.path.abspath(path)))
        self._result_audio_playlist.clear()
        for _ in range(RESULT_SOUND_REPEAT_COUNT):
            self._result_audio_playlist.addMedia(media)
        self._result_audio_playlist.setCurrentIndex(0)
        self._result_audio_player.play()

    def _stop_result_alerts(self):
        self._result_blink_timer.stop()
        self._result_audio_player.stop()
        self._result_audio_playlist.clear()
        self._result_blink_visible = True

    def _on_result_audio_error(self, error):
        if error == QMediaPlayer.NoError:
            return
        message = (
            self._result_audio_player.errorString()
            or f"QMediaPlayer error {int(error)}"
        )
        key = (int(error), message)
        if key in self._reported_result_audio_errors:
            return
        self._reported_result_audio_errors.add(key)
        self._append_log(f"[{self._now()}] [Âm thanh] {message}")

    ######################################################################
    # Banner notification (thay chỗ Log cũ) — đọc lại local_notifications,
    # mỗi lần chỉ hiện 1 thông báo mới nhất, giữ nguyên tới khi có cái mới.
    ######################################################################

    def _init_notification_banner(self):
        self.labelNotificationBanner.setText("Chưa có thông báo.")
        self._apply_notification_style("_default")
        self._notification_poll_timer = QTimer(self)
        self._notification_poll_timer.setInterval(NOTIFICATION_POLL_INTERVAL_MS)
        self._notification_poll_timer.timeout.connect(self._poll_latest_notification)
        self._notification_poll_timer.start()
        self._poll_latest_notification()

    def _apply_notification_style(self, severity):
        color = NOTIFICATION_SEVERITY_TEXT_COLORS.get(
            severity, NOTIFICATION_SEVERITY_TEXT_COLORS["_default"]
        )
        self.labelNotificationBanner.setStyleSheet(
            NOTIFICATION_BANNER_BASE_STYLE + f" color: {color};"
        )

    def _reset_notification_banner(self):
        # Chỉ đổi hiển thị — không cần đụng DB: bản NEW gần nhất (nếu có) đã
        # được _poll_latest_notification() đánh dấu READ ngay khi hiện lên
        # banner từ trước, nên vòng poll tiếp theo sẽ không tự ghi đè lại.
        self.labelNotificationBanner.setText("Chưa có thông báo.")
        self._apply_notification_style("_default")

    def _poll_latest_notification(self):
        noti = get_latest_unread_notification()
        if noti is None:
            return
        self.labelNotificationBanner.setText(f"{noti['title']}\n{noti['message']}")
        self._apply_notification_style(noti["severity"])
        mark_notification_read(noti["id"])

    ######################################################################
    # Log chung (dùng lại được cho thông báo ứng dụng)
    ######################################################################

    def _append_log(self, line):
        log_event(line)

    @staticmethod
    def _now():
        return datetime.now().strftime("%H:%M:%S")

    ######################################################################

    def closeEvent(self, event):
        self._stop_result_alerts()
        self.manager.stop_all()
        self._runtime_snapshot_timer.stop()
        if self._runtime_client.stop():
            add_local_notification(
                "LOCAL_RUNTIME_STOPPED",
                "INFO",
                "Đã dừng runtime",
                "Server đã xác nhận runtime:stop trước khi đóng ứng dụng.",
            )
        elif self._runtime_client.was_last_stop_unconfirmed():
            add_local_notification(
                "LOCAL_RUNTIME_STOP_UNCONFIRMED",
                "WARNING",
                "Chưa xác nhận dừng runtime",
                "Không nhận được ACK runtime:stop từ server trước khi đóng ứng dụng.",
            )
        self.server_worker.stop()
        self.server_worker.wait()
        super().closeEvent(event)
