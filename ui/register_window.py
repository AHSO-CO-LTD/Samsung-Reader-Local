import os
from datetime import datetime

from PyQt5 import uic
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QDialog

from db.local_db import add_local_notification, get_app_settings, update_app_settings
from machine.identity import ensure_machine_identity

UI_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "register_window.ui")

MAX_LOG_LINES = 500

STATUS_POLL_INTERVAL_MS = 12000

# Trạng thái hiển thị suy ra từ registration_status + license_activated_at —
# KHÔNG lưu trực tiếp khoá PENDING_LICENSE/PENDING_APPROVAL vào DB, cột
# registration_status trong schema chỉ có 5 giá trị (NOT_REQUESTED/PENDING/
# APPROVED/REJECTED/DUPLICATE), 2 khoá PENDING_* chỉ là view-state cục bộ.
STATUS_TEXT = {
    "NOT_REQUESTED": "No registration request sent",
    "PENDING_LICENSE": "Waiting for license",
    "PENDING_APPROVAL": "License activated — waiting for approval",
    "APPROVED": "Approved",
    "REJECTED": "Rejected",
    "DUPLICATE": "Duplicate data",
}

STATUS_STYLES = {
    "NOT_REQUESTED": "color: gray;",
    "PENDING_LICENSE": "color: darkorange;",
    "PENDING_APPROVAL": "color: darkorange;",
    "APPROVED": "color: green;",
    "REJECTED": "color: red;",
    "DUPLICATE": "color: red;",
}

# Cho phép chủ động bấm gửi lại yêu cầu ở các trạng thái này (không tự động
# gửi lại mù — luôn phải người dùng bấm nút).
_RESENDABLE_STATES = ("NOT_REQUESTED", "REJECTED", "DUPLICATE")


class RegisterWindow(QDialog):
    """Dialog đăng ký máy với server: gửi POST /api/machines/register-request,
    tự poll GET /api/machines/register-requests/:request_id/status tới khi
    APPROVED. Dùng chung server_worker (ServerWorker) với MainWindow — mỗi
    job_kind tự lọc theo tên, không đụng job "health" của MainWindow."""

    def __init__(self, server_worker, parent=None):
        super().__init__(parent)
        uic.loadUi(UI_PATH, self)

        self.server_worker = server_worker
        self.server_worker.callSucceeded.connect(self._on_call_succeeded)
        self.server_worker.callFailed.connect(self._on_call_failed)

        self.pushButtonSendRequest.clicked.connect(self.on_send_request_clicked)
        self.pushButtonRefreshStatus.clicked.connect(self.on_refresh_clicked)
        self.pushButtonClose.clicked.connect(self.close)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(STATUS_POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_status)

        self._serial = None
        self._uid = None
        # Baseline TRƯỚC lần _refresh_view() đầu tiên — tránh báo notification
        # ngay khi mở lại dialog ở 1 trạng thái đã có từ trước (không phải
        # transition thật xảy ra trong lúc dialog đang mở).
        self._last_view_state = self._view_state(get_app_settings())

        self._load_identity()
        view_state = self._refresh_view()
        if view_state in ("PENDING_LICENSE", "PENDING_APPROVAL"):
            self._poll_status()

    ######################################################################
    # Định danh máy (serial/uid/ip) — hiển thị read-only
    ######################################################################

    def _load_identity(self):
        serial, uid = ensure_machine_identity()
        self._serial = serial
        self._uid = uid
        self.lineEditSerial.setText(serial or "(unavailable)")
        self.lineEditUid.setText(uid or "(unavailable)")
        if not serial or not uid:
            self._append_log("Could not read hardware serial/UID for this machine — cannot send a registration request.")

    ######################################################################
    # Hiển thị trạng thái hiện tại (đọc lại từ local_app_settings)
    ######################################################################

    @staticmethod
    def _view_state(settings):
        status = settings.get("registration_status") or "NOT_REQUESTED"
        if status == "PENDING":
            return "PENDING_APPROVAL" if settings.get("license_activated_at") else "PENDING_LICENSE"
        return status

    def _refresh_view(self):
        settings = get_app_settings()
        view_state = self._view_state(settings)

        self.labelStatus.setText(STATUS_TEXT.get(view_state, view_state))
        self.labelStatus.setStyleSheet(STATUS_STYLES.get(view_state, ""))
        self.labelStatusDetail.setText(settings.get("local_status_message") or "")

        can_send = view_state in _RESENDABLE_STATES and bool(self._serial) and bool(self._uid)
        self.pushButtonSendRequest.setEnabled(can_send)

        has_request_id = bool(settings.get("registration_request_id"))
        self.pushButtonRefreshStatus.setEnabled(has_request_id and view_state != "APPROVED")

        if view_state in ("PENDING_LICENSE", "PENDING_APPROVAL"):
            if not self._poll_timer.isActive():
                self._poll_timer.start()
        else:
            self._poll_timer.stop()

        if view_state != self._last_view_state:
            self._notify_view_state_change(view_state, settings)
            self._last_view_state = view_state

        return view_state

    def _notify_view_state_change(self, view_state, settings):
        """Báo local_notifications đúng 1 lần mỗi lần trạng thái THẬT SỰ đổi
        (không báo lặp lại mỗi lần poll trạng thái không đổi)."""
        detail = settings.get("local_status_message") or ""
        if view_state == "PENDING_LICENSE":
            add_local_notification(
                "LOCAL_REGISTER_WAITING", "INFO",
                "Registration pending", detail or "Waiting for license.",
            )
        elif view_state == "PENDING_APPROVAL":
            add_local_notification(
                "LOCAL_REGISTER_WAITING", "INFO",
                "Registration pending", detail or "License activated, waiting for approval.",
            )
        elif view_state == "APPROVED":
            add_local_notification(
                "LOCAL_REGISTER_APPROVED", "INFO",
                "Registration approved", detail or "Machine registration approved.",
            )
        elif view_state == "REJECTED":
            add_local_notification(
                "LOCAL_REGISTER_REJECTED", "ERROR",
                "Registration rejected", detail or "Machine registration was rejected.",
            )
        elif view_state == "DUPLICATE":
            add_local_notification(
                "LOCAL_MACHINE_BLOCKED", "CRITICAL",
                "Duplicate registration data", detail or "Registration blocked due to duplicate data.",
            )

    ######################################################################
    # Gửi yêu cầu đăng ký
    ######################################################################

    def on_send_request_clicked(self):
        self._append_log(f"Sending registration request (serial={self._serial}, uid={self._uid})...")
        self.pushButtonSendRequest.setEnabled(False)
        self.server_worker.enqueue(
            "register_request", serial=self._serial, uid=self._uid, ip_address=None,
        )

    ######################################################################
    # Kiểm tra trạng thái (thủ công hoặc tự động qua QTimer)
    ######################################################################

    def on_refresh_clicked(self):
        self._poll_status()

    def _poll_status(self):
        settings = get_app_settings()
        request_id = settings.get("registration_request_id")
        if not request_id or not self._serial or not self._uid:
            return
        self.server_worker.enqueue(
            "register_status", request_id=str(request_id), serial=self._serial, uid=self._uid,
        )

    ######################################################################
    # Xử lý response từ ServerWorker (job_kind: register_request/register_status)
    ######################################################################

    def _on_call_succeeded(self, job_kind, correlation_id, data):
        if job_kind == "register_request":
            self._handle_register_request_result(data)
        elif job_kind == "register_status":
            self._handle_register_status_result(data)

    def _on_call_failed(self, job_kind, correlation_id, error_message, payload):
        if job_kind == "register_request":
            if payload.get("code"):
                self._handle_register_request_result(payload)
            else:
                self._append_log(f"Error sending registration request: {error_message}")
                self._refresh_view()
        elif job_kind == "register_status":
            if payload.get("code"):
                self._handle_register_status_result(payload)
            else:
                self._append_log(f"Error checking registration status: {error_message}")

    def _handle_register_request_result(self, response):
        code = response.get("code")
        data = response.get("data") or {}
        now = datetime.now().astimezone()

        if code == "MACHINE_REGISTER_REQUEST_SENT":
            update_app_settings(
                registration_request_id=data.get("request_id"),
                registration_status="PENDING",
                local_runtime_status="REGISTERING",
                local_status_message="Request sent, waiting for license.",
                local_status_updated_at=now,
            )
            self._append_log(f"Registration request sent — request_id={data.get('request_id')}.")
            add_local_notification(
                "LOCAL_REGISTER_REQUEST_SENT", "INFO",
                "Registration request sent", f"request_id={data.get('request_id')}",
            )
        elif code == "MACHINE_REGISTER_DUPLICATE":
            duplicates = data.get("duplicates") or []
            detail = "; ".join(
                f"{d.get('field')}={d.get('value')} (machine {d.get('machine_code')})" for d in duplicates
            ) or "(no detail available)"
            update_app_settings(
                registration_status="DUPLICATE",
                local_status_message=f"Duplicate data: {detail}",
                local_status_updated_at=now,
            )
            self._append_log(f"Duplicate data on registration: {detail}")
        else:
            self._append_log(f"Unrecognized response when sending registration request: {code} — {response.get('message')}")

        self._refresh_view()

    def _handle_register_status_result(self, response):
        code = response.get("code")
        data = response.get("data") or {}
        now = datetime.now().astimezone()

        if code == "MACHINE_REGISTER_PENDING":
            fields = {"registration_status": "PENDING", "local_status_updated_at": now}
            if data.get("license_activated_at"):
                fields["license_activated_at"] = data.get("license_activated_at")
                fields["local_status_message"] = "License activated, waiting for approval."
                self._append_log("License activated — waiting for approval.")
            else:
                fields["local_status_message"] = "Waiting for license."
                self._append_log("Still waiting for license.")
            update_app_settings(**fields)
        elif code == "MACHINE_REGISTER_APPROVED":
            machine_code = data.get("machine_code")
            update_app_settings(
                registration_status="APPROVED",
                machine_code=machine_code,
                license_activated_at=data.get("license_activated_at"),
                local_runtime_status="READY",
                local_status_message=f"Approved — machine_code={machine_code}.",
                local_status_updated_at=now,
            )
            self._append_log(f"Approved! machine_code={machine_code}")
        elif code == "MACHINE_REGISTER_REJECTED":
            reason = data.get("rejected_reason") or "(no reason given)"
            update_app_settings(
                registration_status="REJECTED",
                local_runtime_status="REJECTED",
                local_status_message=f"Rejected: {reason}",
                local_status_updated_at=now,
            )
            self._append_log(f"Request rejected: {reason}")
        else:
            self._append_log(f"Error response when checking registration status: {code} — {response.get('message')}")

        self._refresh_view()

    ######################################################################
    # Log dùng chung (cùng convention với ConfigWindow/MainWindow)
    ######################################################################

    def _append_log(self, line):
        self.textEditLog.append(f"[{self._now()}] {line}")
        doc = self.textEditLog.document()
        if doc.blockCount() > MAX_LOG_LINES:
            cursor = self.textEditLog.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.KeepAnchor, doc.blockCount() - MAX_LOG_LINES)
            cursor.removeSelectedText()

    @staticmethod
    def _now():
        return datetime.now().strftime("%H:%M:%S")
