import os
from datetime import datetime

from PyQt5 import uic
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QDialog, QInputDialog, QLabel, QListWidgetItem, QMainWindow, QMessageBox, QTableWidgetItem,
)

from data.duplicate_key import compute_duplicate_key
from data.mapping_store import load_mappings
from db.local_db import (
    add_local_notification, apply_machine_config, get_app_settings, record_full_scan, update_app_settings,
)
from machine.identity import ensure_machine_identity
from reader.reader_bridge import ReaderManager
from reader.reader_store import load_readers
from server.api_client import SamsungQrServerClient, ServerApiConfig
from server.server_config import load_server_config, save_server_config
from server.server_worker import ServerWorker
from ui.config_window import ConfigWindow
from ui.register_window import RegisterWindow

UI_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main_window.ui")
MAPPING_UI_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mapping_window.ui")

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

MAX_LOG_LINES = 500

SERVER_HEALTH_CHECK_INTERVAL_MS = 15000

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

IDENTITY_STATUS_POLL_INTERVAL_MS = 15000

# local_runtime_status coi là "được phép scan" — mọi giá trị khác đều chặn
# màn scan chính (xem _apply_runtime_status).
SCAN_ENABLED_STATUSES = {"READY", "SCANNING", "SYNCING"}

RUNTIME_BANNER_TEXT = {
    "BOOTING": "Đang kiểm tra trạng thái đăng ký máy...",
    "NOT_REGISTERED": "Máy chưa đăng ký — vào Register để gửi yêu cầu đăng ký.",
    "REGISTERING": "Đang gửi yêu cầu đăng ký...",
    "WAITING_LICENSE": "Đang chờ cấp license...",
    "WAITING_APPROVAL": "License đã kích hoạt — đang chờ duyệt...",
    "REJECTED": "Yêu cầu đăng ký đã bị từ chối.",
    "BLOCKED": "Máy bị khoá — liên hệ admin.",
    "SERVER_OFFLINE": "Mất kết nối server.",
    "ERROR": "Không đọc được định danh máy (serial/UID).",
}

RUNTIME_BANNER_STYLES = {
    "BOOTING": "background-color: #9e9e9e; color: white;",
    "SERVER_OFFLINE": "background-color: #9e9e9e; color: white;",
    "NOT_REGISTERED": "background-color: #f57c00; color: white;",
    "REGISTERING": "background-color: #f57c00; color: white;",
    "WAITING_LICENSE": "background-color: #f57c00; color: white;",
    "WAITING_APPROVAL": "background-color: #f57c00; color: white;",
    "REJECTED": "background-color: #c62828; color: white;",
    "BLOCKED": "background-color: #c62828; color: white;",
    "ERROR": "background-color: #c62828; color: white;",
    "_default": "background-color: #9e9e9e; color: white;",
}

RESULT_STYLE = {
    None: "background-color: palette(window); color: palette(window-text);",
    "ok": "background-color: #2e7d32; color: white;",
    "ng": "background-color: #c62828; color: white;",
}

# Tên reader cố định (chọn qua combobox ở Config Window) ứng với từng cột kết quả.
READER_COLUMN_MAP = {
    "LED BAR 1": "ledbar1",
    "LED BAR 2": "ledbar2",
    "QRCODE BOTTOM": "qrbottom",
}

# Mã reader trả về là 1 chuỗi liền không có khoảng trắng, nên word-wrap thường
# (ngắt theo từ) không tự xuống dòng được — chủ động chèn "\n" theo số ký tự
# cố định để đảm bảo luôn xuống dòng đúng chỗ, không phụ thuộc Qt word-wrap.
RESULT_WRAP_CHUNK = 22   # vừa đủ 1 hàng cho mã 22 ký tự (LED BAR 1/2)

# Nền từng khung mã trong 3 cột kết quả: True=đúng (xanh), False=sai (đỏ),
# None=chưa có logic kiểm tra (QRCODE BOTTOM hiện tại) — trung tính.
RESULT_ITEM_COLORS = {
    True: QColor("lightgreen"),
    False: QColor("lightcoral"),
    None: QColor("#eeeeee"),
}

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


def _wrap_for_display(text, chunk_size):
    if len(text) <= chunk_size:
        return text
    return "\n".join(text[i:i + chunk_size] for i in range(0, len(text), chunk_size))


class MainWindow(QMainWindow):
    """Cửa sổ chính — chỉ chứa các phần chung/tái sử dụng được: tiêu đề,
    nút Configure/Mapping/PLC, bảng trạng thái reader, log, khung kết quả
    OK/NG, và 3 cột hiển thị mã đọc được. Phần xử lý logic so sánh thật với
    server sẽ bổ sung sau — hiện dùng dữ liệu mapping mẫu (mapping_store.py)."""

    def __init__(self):
        super().__init__()
        uic.loadUi(UI_PATH, self)

        self.manager = ReaderManager()
        self._status = {}
        self._wired_readers = set()
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
        self._session_qr = None
        # True sau khi 1 phiên OK vừa chốt — chưa xoá màn hình ngay (để operator
        # kịp nhìn kết quả), chỉ xoá khi có mã MỚI của phiên tiếp theo tới.
        self._session_pending_clear = False
        self._last_duplicate_first_scan_at = None

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
        self.tableWidgetReaderStatus.setColumnWidth(0, 95)
        self.tableWidgetReaderStatus.setColumnWidth(1, 100)

        for widgets in self._column_widgets.values():
            widgets["list"].setSpacing(6)

        self.pushButtonConfigure.clicked.connect(self.on_configure_clicked)
        self.pushButtonMapping.clicked.connect(self.on_mapping_clicked)
        self.pushButtonRegister.clicked.connect(self.on_register_clicked)
        self.pushButtonChangeServerIp.clicked.connect(self.on_change_server_ip_clicked)
        self.pushButtonReset.clicked.connect(self.on_reset_clicked)
        self.comboBoxChassisRear.currentTextChanged.connect(self.on_chassis_rear_changed)

        for widgets in self._column_widgets.values():
            widgets["spin"].valueChanged.connect(self._update_progress)

        self.set_result_status(None)
        self._load_mappings()
        self._load_persisted_readers()
        self._update_progress()
        self._init_server_worker()

    ######################################################################
    # Kết nối server (REST) — bước 1: chỉ GET /api/health
    ######################################################################

    def _init_server_worker(self):
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

        settings = get_app_settings()
        initial_status = settings.get("local_runtime_status") or "BOOTING"
        # Baseline TRƯỚC lần apply đầu — tránh bắn notification cho trạng
        # thái đã có sẵn từ phiên trước (giống _last_view_state ở RegisterWindow).
        self._runtime_status = initial_status
        self._apply_runtime_status(initial_status, settings.get("local_status_message"))

        if self._serial and self._uid:
            self._check_identity_status()
        else:
            self._append_log(f"[{self._now()}] [Định danh máy] Không đọc được serial/UID phần cứng.")
            self._apply_runtime_status("ERROR", RUNTIME_BANNER_TEXT["ERROR"])

    def _check_server_health(self):
        self.server_worker.enqueue("health")

    def _check_identity_status(self):
        if self._serial and self._uid:
            self.server_worker.enqueue("identity_status", serial=self._serial, uid=self._uid)

    def _on_server_call_succeeded(self, job_kind, correlation_id, data):
        if job_kind == "health":
            update_app_settings(server_online=True, last_health_at=datetime.now().astimezone())
            self._apply_server_online(True)
        elif job_kind == "identity_status":
            self._handle_identity_status_result(data)
        elif job_kind == "config":
            self._handle_config_result(data)

    def _on_server_call_failed(self, job_kind, correlation_id, error_message, payload):
        if job_kind == "health":
            update_app_settings(server_online=False)
            self._apply_server_online(False)
        elif job_kind == "identity_status":
            if payload.get("code") == "MACHINE_IDENTITY_MISMATCH":
                matches = (payload.get("data") or {}).get("matches") or []
                detail = "; ".join(
                    f"{m.get('machine_code')}({m.get('serial')}/{m.get('uid')})" for m in matches
                ) or "(không có chi tiết)"
                message = f"Sai định danh — trùng với: {detail}"
                update_app_settings(
                    local_runtime_status="BLOCKED", local_status_message=message,
                    local_status_updated_at=datetime.now().astimezone(),
                )
                self._append_log(f"[{self._now()}] [Định danh máy] {message}")
                self._apply_runtime_status("BLOCKED", message)
            else:
                self._append_log(f"[{self._now()}] [Định danh máy] Lỗi mạng khi kiểm tra định danh: {error_message}")
        elif job_kind == "config":
            code = payload.get("code")
            if code in ("MACHINE_NOT_FOUND", "MACHINE_IDENTITY_MISMATCH"):
                message = f"Config load failed: {code}"
                update_app_settings(
                    local_runtime_status="BLOCKED", local_status_message=message,
                    local_status_updated_at=datetime.now().astimezone(),
                )
                self._append_log(f"[{self._now()}] [Config] {message}")
                self._apply_runtime_status("BLOCKED", message)
            else:
                self._append_log(f"[{self._now()}] [Config] Lỗi mạng khi tải cấu hình: {error_message}")

    def _handle_identity_status_result(self, response):
        code = response.get("code")
        data = response.get("data") or {}
        now = datetime.now().astimezone()

        if code == "MACHINE_IDENTITY_APPROVED":
            machine_code = data.get("machine_code")
            message = f"Approved — machine_code={machine_code}."
            update_app_settings(
                registration_status="APPROVED", machine_code=machine_code,
                local_runtime_status="READY", local_status_message=message,
                local_status_updated_at=now,
            )
            self._apply_runtime_status("READY", message)
            self._check_machine_config()
        elif code == "MACHINE_REGISTER_PENDING":
            waiting = "WAITING_APPROVAL" if data.get("license_activated_at") else "WAITING_LICENSE"
            message = (
                "License activated, waiting for approval." if waiting == "WAITING_APPROVAL"
                else "Waiting for license."
            )
            fields = {
                "registration_status": "PENDING", "local_runtime_status": waiting,
                "local_status_message": message, "local_status_updated_at": now,
            }
            if data.get("request_id"):
                fields["registration_request_id"] = data.get("request_id")
            if data.get("license_activated_at"):
                fields["license_activated_at"] = data.get("license_activated_at")
            update_app_settings(**fields)
            self._apply_runtime_status(waiting, message)
        elif code == "MACHINE_IDENTITY_NOT_REGISTERED":
            message = "Machine is not registered on the server yet."
            update_app_settings(
                registration_status="NOT_REQUESTED", registration_request_id=None,
                local_runtime_status="NOT_REGISTERED", local_status_message=message,
                local_status_updated_at=now,
            )
            self._apply_runtime_status("NOT_REGISTERED", message)
        elif code == "MACHINE_IDENTITY_DISABLED":
            message = "Machine has been disabled on the server. Contact admin."
            update_app_settings(
                local_runtime_status="BLOCKED", local_status_message=message,
                local_status_updated_at=now,
            )
            self._apply_runtime_status("BLOCKED", message)
        else:
            self._append_log(f"[{self._now()}] [Định danh máy] Phản hồi không xác định: {code} — {response.get('message')}")

    def _check_machine_config(self):
        self.server_worker.enqueue("config", serial=self._serial, uid=self._uid)

    def _handle_config_result(self, response):
        code = response.get("code")
        data = response.get("data") or {}
        now = datetime.now().astimezone()

        if code != "MACHINE_CONFIG_LOADED":
            self._append_log(f"[{self._now()}] [Config] Phản hồi không xác định: {code} — {response.get('message')}")
            return

        apply_machine_config(data, self._serial, self._uid)
        update_app_settings(last_config_sync_at=now)
        self._load_mappings()

        profiles = data.get("profiles") or []
        vendors = data.get("vendors") or []
        if not profiles:
            message = "No active profile assigned to this machine on the server."
            update_app_settings(
                local_runtime_status="BLOCKED", local_status_message=message,
                local_status_updated_at=now,
            )
            add_local_notification("LOCAL_PROFILE_EMPTY", "CRITICAL", "Thiếu profile", message)
            self._append_log(f"[{self._now()}] [Config] {message}")
            self._apply_runtime_status("BLOCKED", message)
        else:
            self._append_log(f"[{self._now()}] [Config] Đồng bộ thành công: {len(profiles)} profile, {len(vendors)} vendor.")
            add_local_notification(
                "LOCAL_CONFIG_SYNCED", "INFO", "Đã đồng bộ cấu hình",
                f"{len(profiles)} profile, {len(vendors)} vendor.",
            )
            self._apply_runtime_status("READY", "Machine is READY.")

    def _apply_runtime_status(self, status, message=None):
        """Điểm trung tâm gate màn scan chính theo local_runtime_status —
        cập nhật banner, disable/enable input, VÀ set self._scan_blocked
        (gate thật, xem on_data_received). Chỉ log/bắn notification khi
        trạng thái THẬT SỰ đổi so với lần trước (như _apply_server_online)."""
        changed = self._runtime_status != status
        self._runtime_status = status
        scan_enabled = status in SCAN_ENABLED_STATUSES
        self._scan_blocked = not scan_enabled

        for widget in (
            self.comboBoxChassisRear, self.spinBoxLedBar1Count,
            self.spinBoxLedBar2Count, self.spinBoxQrBottomCount, self.pushButtonReset,
        ):
            widget.setEnabled(scan_enabled)

        self.labelRuntimeBanner.setVisible(not scan_enabled)
        if not scan_enabled:
            self.labelRuntimeBanner.setText(message or RUNTIME_BANNER_TEXT.get(status, status))
            self.labelRuntimeBanner.setStyleSheet(
                RUNTIME_BANNER_STYLES.get(status, RUNTIME_BANNER_STYLES["_default"])
            )

        if scan_enabled:
            self._identity_status_timer.stop()
        elif self._serial and self._uid and not self._identity_status_timer.isActive():
            self._identity_status_timer.start()

        if not changed:
            return
        self._append_log(f"[{self._now()}] [Định danh máy] Trạng thái: {status}.")
        if status == "BLOCKED":
            add_local_notification(
                "LOCAL_MACHINE_BLOCKED", "CRITICAL",
                "Máy bị khoá", message or "Máy bị khoá bởi server.",
            )
        elif status in ("WAITING_LICENSE", "WAITING_APPROVAL"):
            add_local_notification(
                "LOCAL_REGISTER_WAITING", "INFO",
                "Đang chờ đăng ký", message or status,
            )
        elif status == "READY":
            add_local_notification(
                "LOCAL_REGISTER_APPROVED", "INFO",
                "Máy đã được duyệt", message or "Machine approved.",
            )

    def _apply_server_online(self, is_online):
        changed = self._server_online != is_online
        self._server_online = is_online
        self.labelServerStatus.setText(SERVER_STATUS_LABELS[is_online])
        self.labelServerStatus.setStyleSheet(SERVER_STATUS_STYLES[is_online])
        if changed:
            state = "Đã kết nối" if is_online else "Mất kết nối"
            self._append_log(f"[{self._now()}] [Server] {state}.")
            if is_online:
                add_local_notification(
                    "LOCAL_SERVER_RECONNECTED", "INFO",
                    "Server đã kết nối", "Health check thành công — server đang online.",
                )
            else:
                add_local_notification(
                    "LOCAL_SERVER_OFFLINE", "WARNING",
                    "Mất kết nối server", "Health check thất bại — chuyển sang chế độ local-only.",
                )

    ######################################################################
    # Configure
    ######################################################################

    def on_configure_clicked(self):
        dlg = ConfigWindow(self.manager, parent=self)
        dlg.exec_()
        self._sync_reader_panel()

    ######################################################################
    # Đăng ký máy với server
    ######################################################################

    def on_register_clicked(self):
        dlg = RegisterWindow(self.server_worker, parent=self)
        dlg.exec_()

    ######################################################################
    # Đổi địa chỉ server — lưu vào server/server_config.json, đọc lại mỗi
    # lần mở app (KHÔNG lưu trong database local)
    ######################################################################

    def on_change_server_ip_clicked(self):
        current = load_server_config()
        host, ok = QInputDialog.getText(
            self, "Change Server IP", "Server IP / host:", text=current["host"],
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
        self.server_worker.update_config(ServerApiConfig(host=host, port=current["port"]))
        self._append_log(f"[{self._now()}] [Server] Đổi địa chỉ server sang {host}:{current['port']} — đang kiểm tra kết nối...")
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
        table.setColumnWidth(5, 90)   # No Led

        dlg.exec_()

    ######################################################################
    # Chassis Rear — dữ liệu mẫu tạm (mapping_store), thay bằng server sau
    ######################################################################

    def _load_mappings(self):
        entries = load_mappings()
        self._mappings_by_chassis = {e["chassis_rear"]: e for e in entries}
        self.comboBoxChassisRear.clear()
        self.comboBoxChassisRear.addItems(list(self._mappings_by_chassis.keys()))

    def on_chassis_rear_changed(self, code):
        entry = self._mappings_by_chassis.get(code)
        if not entry:
            return
        self.labelLedBar1RefCode.setText(entry["led1"] or "-")
        self.labelLedBar2RefCode.setText(entry["led2"] or "-")
        self.labelQrBottomRefCode.setText(code)
        update_app_settings(active_profile_id=entry.get("profile_id"))

    ######################################################################
    # Nạp danh sách reader đã lưu (JSON) lúc khởi động
    ######################################################################

    def _load_persisted_readers(self):
        for entry in load_readers():
            try:
                reader = self.manager.add_reader(
                    entry["name"], entry["ip"], entry["data_port"],
                    command_port=entry.get("command_port"), parent=self,
                )
            except ValueError:
                continue
            self._wire_reader(reader)
            reader.start()
        self._rebuild_reader_table()

    ######################################################################
    # Đồng bộ bảng trạng thái reader sau khi đóng cửa sổ Configure
    ######################################################################

    def _sync_reader_panel(self):
        for name in self.manager.names():
            if name not in self._wired_readers:
                self._wire_reader(self.manager.get(name))
        self._rebuild_reader_table()

    def _wire_reader(self, reader):
        reader.dataReceived.connect(self.on_data_received)
        reader.statusChanged.connect(self.on_status_changed)
        self._status[reader.name] = {
            "data": "connected" if reader.is_data_connected() else "disconnected",
            "command": "connected" if reader.is_command_connected() else "disconnected",
        }
        self._wired_readers.add(reader.name)

    def _rebuild_reader_table(self):
        table = self.tableWidgetReaderStatus
        table.setRowCount(0)
        for name in self.manager.names():
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(name))
            status_item = QTableWidgetItem(self._status_label(name))
            status_item.setForeground(STATUS_COLORS.get(self._status.get(name, {}).get("data"), QColor("black")))
            table.setItem(row, 1, status_item)
            self._set_input_cell(row, self._last_input.get(name, ""))
            table.resizeRowToContents(row)

    ######################################################################
    # Nhận dữ liệu / trạng thái từ reader (chạy trên GUI thread nhờ signal)
    ######################################################################

    def on_data_received(self, name, text):
        if self._scan_blocked:
            return

        if self._session_pending_clear:
            self._clear_session()
            self._session_pending_clear = False
            self._append_log(f"[{self._now()}] Sản phẩm mới — tự động xoá kết quả phiên trước.")

        self._update_reader_input(name, text)

        is_ok = None
        code = None
        entry = self._current_entry()
        if name in ("LED BAR 1", "LED BAR 2"):
            column_key, is_ok, code = self._classify_led_bar(name, text)
            if is_ok:
                self._last_ok_led_text[column_key] = text
            else:
                self._append_log(f"[{self._now()}] [{name}] NG ({self._describe_ng(code, text, entry)}): {text}")
        else:
            column_key = READER_COLUMN_MAP.get(name)
        if column_key is None:
            return

        if column_key in ("ledbar1", "ledbar2") and len(text) >= 15:
            self.labelLotNo.setText(text[12:15])

        widgets = self._column_widgets[column_key]
        quota = widgets["spin"].value()

        if self._received_counts[column_key] >= quota:
            self._append_log(f"[{self._now()}] [{name}] Đã đủ số lượng ({quota}), bỏ qua mã dư: {text}")
            return

        # QRCODE BOTTOM luôn đọc đúng reader (không lẫn sang cột khác) nên hiển
        # thị mã lên danh sách NGAY, không chờ kiểm tra xong mới hiện — tránh
        # cảm giác "đọc được rồi mà màn hình chưa lên". Kiểm tra OK/NG (và đổi
        # màu) chạy đúng 1 lần lúc finalize — xem _finalize_scan_session().
        item = QListWidgetItem(_wrap_for_display(text, RESULT_WRAP_CHUNK))
        item.setTextAlignment(Qt.AlignCenter)
        item.setBackground(RESULT_ITEM_COLORS.get(is_ok, RESULT_ITEM_COLORS[None]))
        widgets["list"].addItem(item)
        self._received_counts[column_key] += 1
        if self._received_counts[column_key] >= quota:
            self._append_log(f"[{self._now()}] [{name}] Đã đủ số lượng ({quota}/{quota})")

        if column_key == "qrbottom":
            # Chưa kiểm tra ở đây — chỉ hiển thị trung tính ngay khi nhận
            # (item đã được tô RESULT_ITEM_COLORS[None] ở trên vì is_ok vẫn
            # là None). Kiểm tra thật + đổi màu chạy đúng 1 lần duy nhất lúc
            # finalize (đủ dữ liệu LED bar tham chiếu, không phụ thuộc thứ tự
            # reader nào về trước).
            self._session_qr = {"text": text, "item": item}
        else:
            self._session_led_items[column_key].append({"text": text, "is_ok": is_ok, "code": code})

        self._update_progress()

        total_expected = sum(w["spin"].value() for w in self._column_widgets.values())
        total_received = sum(self._received_counts.values())
        if total_received >= total_expected:
            self._finalize_scan_session()

    def _current_entry(self):
        return self._mappings_by_chassis.get(self.comboBoxChassisRear.currentText())

    def _describe_ng(self, code, text, entry):
        """Dựng câu tiếng Việt hiển thị trong log từ mã NG cố định — không bao
        giờ để mã (tiếng Anh) lộ thẳng ra log, luôn đi qua đây để đồng bộ."""
        entry = entry or {}
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
            led_ref_text = self._last_ok_led_text.get("ledbar1") or self._last_ok_led_text.get("ledbar2")
            if not led_ref_text:
                return "Chưa có mã LED bar đọc đúng để đối chiếu vendor"
            if not no_bottom or not no_led or no_bottom > len(text) or no_led > len(led_ref_text):
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
        return code

    def _classify_led_bar(self, name, text):
        """Xác định code này thuộc cột LED BAR 1 hay 2 (không cố định theo
        reader vật lý), và có hợp lệ hay không:
        1. Số ký tự phải bằng Length Code LED (theo Chassis Rear đang chọn).
        2. 5 ký tự cuối phải giống 5 ký tự cuối của Code LED 1 hoặc Code LED 2.
        Nếu không thỏa 1 trong 2 điều kiện trên với cả 2 code, xếp vào cột mặc
        định theo đúng reader vật lý (reader LED BAR 1 -> cột 1, reader LED
        BAR 2 -> cột 2) và đánh dấu NG."""
        default_column = READER_COLUMN_MAP[name]
        entry = self._current_entry()
        if not entry:
            return default_column, False, NG_NO_PROFILE_SELECTED

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

        return default_column, False, NG_LED_SUFFIX_NOT_MATCH

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

        led_ref_text = self._last_ok_led_text.get("ledbar1") or self._last_ok_led_text.get("ledbar2")
        if not led_ref_text:
            return False, NG_FULL_VENDOR_NOT_MATCH, None
        if not no_bottom or not no_led or no_bottom > len(text) or no_led > len(led_ref_text):
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
        self._append_log(f"[{self._now()}] [{name}] Trạng thái ({channel}): {STATUS_LABELS.get(status, status)}")
        self._update_reader_row_status(name)

    def _update_reader_row_status(self, name):
        table = self.tableWidgetReaderStatus
        for row in range(table.rowCount()):
            if table.item(row, 0).text() == name:
                item = table.item(row, 1)
                item.setText(self._status_label(name))
                item.setForeground(STATUS_COLORS.get(self._status.get(name, {}).get("data"), QColor("black")))
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

    def _finalize_scan_session(self):
        """Gọi khi tổng số mã đã nhận == tổng Quantity 3 cột (1 sản phẩm đã
        quét xong đủ mọi mảnh). Gộp toàn bộ item đã thu thập trong phiên
        thành 1 dòng local_scan_records + nhiều dòng local_scan_led_items."""
        qr = self._session_qr
        if qr is None:
            return

        entry = self._current_entry()

        # Kiểm tra QRCODE BOTTOM đúng 1 lần duy nhất tại đây — không kiểm tra
        # lúc vừa nhận, vì lúc đó LED bar tham chiếu (_last_ok_led_text) có
        # thể chưa đủ nếu QR bottom về trước LED bar. Tới đây, cả phiên đã đủ
        # dữ liệu (progress bar đầy) nên kết quả luôn đúng bất kể thứ tự về.
        own_is_ok, own_code, matched_led_code = self._classify_qr_bottom(qr["text"])
        qr["item"].setBackground(RESULT_ITEM_COLORS.get(own_is_ok, RESULT_ITEM_COLORS[None]))

        led_ledbar1 = self._session_led_items["ledbar1"]
        led_ledbar2 = self._session_led_items["ledbar2"]
        all_led_ok = all(it["is_ok"] for it in led_ledbar1 + led_ledbar2)

        is_ok = own_is_ok and all_led_ok
        if is_ok:
            ng_reason = None
        elif not own_is_ok:
            ng_reason = own_code
        else:
            ng_reason = next(it["code"] for it in led_ledbar1 + led_ledbar2 if not it["is_ok"])

        profile_id = entry.get("profile_id") if entry else None
        duplicate_key = compute_duplicate_key(qr["text"]) if is_ok else None
        qr_data = self._build_qr_data(qr["text"], entry, matched_led_code, duplicate_key)
        led_items_data = self._build_led_items_data(led_ledbar1, led_ledbar2, entry)

        try:
            final_is_ok, final_reason, first_scan_at = record_full_scan(
                profile_id, qr_data, led_items_data, is_ok, ng_reason,
            )
        except Exception as exc:
            self._append_log(f"[{self._now()}] Lỗi ghi local DB: {exc}")
            final_is_ok, final_reason, first_scan_at = is_ok, ng_reason, None

        if final_reason == NG_LOCAL_DUPLICATE:
            self._last_duplicate_first_scan_at = first_scan_at
            qr["item"].setBackground(RESULT_ITEM_COLORS[False])

        if not final_is_ok:
            detail = self._describe_ng(final_reason, qr["text"], entry)
            self._append_log(f"[{self._now()}] [QRCODE BOTTOM] Kết quả sản phẩm: NG ({detail})")

        self.set_result_status("ok" if final_is_ok else "ng")
        # OK: không xoá màn hình ngay, chờ mã mới của sản phẩm tiếp theo mới
        # xoá (xem đầu on_data_received) — để operator kịp nhìn kết quả.
        # NG: không set cờ, giữ nguyên hiển thị tới khi bấm Reset thủ công.
        self._session_pending_clear = final_is_ok
        self._session_led_items = {"ledbar1": [], "ledbar2": []}
        self._session_qr = None

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
                vendor_char = text[no_led - 1] if no_led and len(text) >= no_led else None
                result.append({
                    "led_slot": slot,
                    "led_index": index,
                    "led_scan_raw": text,
                    "led_lot_no": text[12:15] if len(text) >= 15 else None,
                    "vendor_char": vendor_char,
                    "led_suffix": text[-5:] if len(text) >= 5 else text,
                    "local_status": "OK" if it["is_ok"] else "NG",
                    "ng_reason": it["code"],
                })
        return result

    ######################################################################
    # Reset — dùng khi NG, xoá mã đã nhận để bắt đầu đợt kiểm mới
    ######################################################################

    def _clear_session(self):
        for key, widgets in self._column_widgets.items():
            widgets["list"].clear()
            self._received_counts[key] = 0
        self._last_input.clear()
        self._last_ok_led_text.clear()
        self._session_led_items = {"ledbar1": [], "ledbar2": []}
        self._session_qr = None
        self._rebuild_reader_table()
        self._update_progress()
        self.set_result_status(None)
        self.labelLotNo.setText("-")

    def on_reset_clicked(self):
        self._clear_session()
        self._session_pending_clear = False
        self._append_log(f"[{self._now()}] Reset — đã xoá mã đã nhận.")

    ######################################################################
    # Khung kết quả OK/NG (logic so sánh thật sẽ bổ sung sau)
    ######################################################################

    def set_result_status(self, result):
        """result: None ("-"), "ok", hoặc "ng"."""
        text = {"ok": "OK", "ng": "NG", None: "-"}.get(result, "-")
        self.labelResultStatus.setText(text)
        self.labelResultStatus.setStyleSheet(RESULT_STYLE.get(result, RESULT_STYLE[None]))

    ######################################################################
    # Log chung (dùng lại được cho thông báo ứng dụng)
    ######################################################################

    def _append_log(self, line):
        self.textEditLog.append(line)
        doc = self.textEditLog.document()
        if doc.blockCount() > MAX_LOG_LINES:
            cursor = self.textEditLog.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.KeepAnchor, doc.blockCount() - MAX_LOG_LINES)
            cursor.removeSelectedText()

    @staticmethod
    def _now():
        return datetime.now().strftime("%H:%M:%S")

    ######################################################################

    def closeEvent(self, event):
        self.manager.stop_all()
        self.server_worker.stop()
        self.server_worker.wait()
        super().closeEvent(event)
