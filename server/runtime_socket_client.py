"""
Socket.IO client kênh /machine-runtime — kênh PHỤ hiển thị "đang chạy gì
ngay lúc này" cho dashboard vận hành server (đang chạy chassis nào, tổng
OK/NG phiên hiện tại). KHÔNG phải hồ sơ QA chính thức (đó là scans/submit,
server/api_client.py) — lỗi/mất kết nối ở kênh này KHÔNG được phép ảnh
hưởng tới việc quét/chấm OK-NG của app (đúng tinh thần "kênh phụ" của
docs/10-huong-dan-api-may-local-python (2).md mục 12.1).

"Phiên" (session) ở đây = TRỌN 1 LẦN CHẠY APP (mở app -> emit runtime:start,
chuẩn bị đóng app -> emit runtime:stop) — KHÔNG gắn với khái niệm "operator
bấm nút Start/Stop 1 lượt chạy" mà tài liệu gốc mô tả (app này chưa có nút
đó, theo quyết định của user). Bộ đếm total/ok/ng chỉ reset đúng 1 lần lúc
start_session(), giữ nguyên tới khi đóng app — field
product_total_count/product_ok_count/product_ng_count TẠM THỜI lặp lại đúng
giá trị total/ok/ng (không tính riêng theo mã hàng, đơn giản hoá theo yêu
cầu user — có thể tách bộ đếm riêng sau nếu cần).

Không dùng chung server/server_worker.py:ServerWorker (REST, hàng đợi job
ngắn hạn) — đây là 1 kết nối bền vững (persistent), rập khuôn theo
reader/reader_bridge.py:_SocketWorker + reader/SRX_comm.py:SRXConnection
(1 QThread mỏng bọc ngoài 1 vòng lặp retry-connect có thể ngắt giữa chừng
qua threading.Event, .stop() chờ VÔ HẠN không timeout — lý do xem
_RuntimeConnectWorker.stop()).
"""

import threading
from datetime import datetime

import socketio
from PyQt5.QtCore import QObject, QThread, pyqtSignal

from app_logger import log_event

NAMESPACE = "/machine-runtime"
INITIAL_CONNECT_RETRY_INTERVAL_SEC = 5
RUNTIME_STOP_ACK_TIMEOUT_SEC = 3
RUNTIME_STOP_ACK_CODE = "RUNTIME_SESSION_STOPPED"


class _RuntimeConnectWorker(QThread):
    """Thread nền thử connect() ban đầu (retry vô hạn, ngắt được giữa
    chừng), rồi GIỮ SỐNG SUỐT PHIÊN kết nối — KHÔNG return ngay sau khi
    connect() thành công.

    ĐÃ TỰ VERIFY BẰNG TEST THẬT (3 script cô lập, không suy đoán): nếu
    run() return ngay sau connect() thành công — với giả định ban đầu là
    "engineio/socketio tự spawn thread nền riêng tiếp quản, không cần
    QThread này sống nữa" — thì sio.connected vẫn báo True, nhưng MỌI event
    nhận về sau đó (kể cả machine:accepted, tức PHẢN HỒI CHO CHÍNH
    machine:hello vừa gửi) KHÔNG BAO GIỜ được gọi tới handler nữa. Test cô
    lập bằng threading.Thread thường (không phải QThread) thì KHÔNG bị lỗi
    này — chỉ riêng QThread của Qt mới gây ra hiện tượng này khi thread đó
    tự thoát. Kết luận: phải coi QThread này như 1 kết nối bền vững, đúng
    kiểu reader/reader_bridge.py:_SocketWorker (sống suốt đời reader), KHÔNG
    phải chỉ lo mỗi lần connect() ban đầu như thiết kế lúc trước.

    KHÔNG dùng tham số retry=True sẵn có của Client.connect() cho vòng lặp
    retry ban đầu — tham số đó gọi _handle_reconnect() ĐỒNG BỘ bên trong,
    không đăng ký vào cơ chế shutdown() để ngắt giữa chừng được (đọc source
    socketio/client.py xác nhận) — tự làm vòng lặp riêng để luôn kiểm soát
    được việc dừng."""

    def __init__(self, sio, url, retry_interval_sec, parent=None):
        super().__init__(parent)
        self._sio = sio
        self._url = url
        self._retry_interval_sec = retry_interval_sec
        self._running = False
        self._stop_event = threading.Event()

    def run(self):
        self._running = True
        connected = False
        while self._running and not connected:
            try:
                self._sio.connect(self._url, namespaces=[NAMESPACE])
                connected = True
            except socketio.exceptions.ConnectionError as exc:
                log_event(
                    f"[machine-runtime] Chưa kết nối được ({exc}) — thử lại sau {self._retry_interval_sec}s."
                )
                self._stop_event.wait(self._retry_interval_sec)
        if connected:
            # Giữ thread sống tới khi stop() được gọi — xem lý do ở docstring
            # lớp. python-socketio tự lo reconnect (reconnection=True) hoàn
            # toàn nội bộ từ đây, không cần vòng lặp retry nào thêm ở đây.
            self._stop_event.wait()

    def stop(self):
        self._running = False
        self._stop_event.set()
        # KHÔNG timeout — giống hệt _SocketWorker.stop() (reader/reader_bridge.py).
        # Đã tự verify bằng crash thật trước đây: chờ có timeout rồi bỏ qua
        # trong khi thread vẫn sống -> nơi gọi xoá/deleteLater() lúc đó là
        # "QThread: Destroyed while thread is still running", crash cứng.
        self.wait()


class MachineRuntimeClient(QObject):
    """Wrapper socketio.Client cho kênh /machine-runtime. KHÔNG tự connect
    lúc khởi tạo — gọi start_session() khi máy đạt READY (có machine_code)."""

    runtimeConnected = pyqtSignal()  # lần connect+accept ĐẦU TIÊN trong phiên
    runtimeReconnected = pyqtSignal()  # bất kỳ lần connect+accept nào SAU đó
    runtimeDisconnected = pyqtSignal(str)  # reason
    runtimeBlocked = pyqtSignal(str)  # message — machine:hello bị từ chối

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sio = socketio.Client(
            reconnection=True,
            reconnection_attempts=0,
            reconnection_delay=1,
            reconnection_delay_max=5,
            # Mặc định True sẽ tự signal.signal(SIGINT, ...) ngay lúc khởi
            # tạo, ghi đè signal handler của CẢ process (đọc source
            # socketio/base_client.py xác nhận) — app này đóng qua
            # closeEvent, không có lý do gì 1 widget con tự đổi SIGINT
            # handler toàn process.
            handle_sigint=False,
        )
        self._sio.on("connect", self._on_connect, namespace=NAMESPACE)
        self._sio.on("disconnect", self._on_disconnect, namespace=NAMESPACE)
        self._sio.on("machine:accepted", self._on_machine_accepted, namespace=NAMESPACE)

        self._lock = threading.Lock()
        self._identity = None
        self._session_active = False
        self._ever_accepted = False
        self._connect_worker = None
        self._last_stop_confirmed = None

        self._current_product_code = None
        self._current_profile_id = None
        self._counters = {"total": 0, "ok": 0, "ng": 0}
        self._last_result = None
        self._last_code = ""
        self._last_local_scan_id = ""
        self._last_pending_sync = 0

    ######################################################################
    # API công khai — gọi từ MainWindow (GUI thread)
    ######################################################################

    def start_session(
        self, *, machine_code, serial, uid, app_version, local_db_version, host, port
    ):
        """Gọi đúng 1 lần/lần chạy app — lúc máy đạt READY (có machine_code).
        KHÔNG tự gọi lại giữa chừng dù trạng thái READY tự đổi qua lại — đó
        là trách nhiệm của caller (xem MainWindow._runtime_session_started)."""
        with self._lock:
            self._identity = {
                "machine_code": machine_code,
                "serial": serial,
                "uid": uid,
                "ip_address": None,
                "app_version": app_version,
                "local_db_version": local_db_version,
            }
            self._counters = {"total": 0, "ok": 0, "ng": 0}
            self._current_product_code = None
            self._current_profile_id = None
            self._session_active = True

        url = f"http://{host}:{port}"
        self._connect_worker = _RuntimeConnectWorker(
            self._sio, url, INITIAL_CONNECT_RETRY_INTERVAL_SEC, parent=self
        )
        self._connect_worker.start()

    def set_current_product(self, product_code, profile_id):
        """Gọi khi operator đổi Chassis Rear. KHÔNG reset bộ đếm gì (đơn
        giản hoá theo yêu cầu user) — chỉ cập nhật product_code/profile_id
        đang theo dõi rồi báo server ngay qua runtime:update (nếu phiên
        đang chạy), đúng quy tắc tài liệu "đổi mã hàng thì gửi product_code
        mới". An toàn gọi cả khi phiên chưa bắt đầu (chỉ cập nhật state)."""
        with self._lock:
            self._current_product_code = product_code
            self._current_profile_id = profile_id
            if not self._session_active:
                return
            payload = self._build_update_payload_locked()
        self._emit("runtime:update", payload)

    def record_scan_result(
        self, *, product_code, profile_id, is_ok, last_code, local_scan_id, pending_sync
    ):
        """Gọi mỗi khi 1 phiên quét (LED bar + QR bottom) chốt xong OK/NG."""
        with self._lock:
            # Đường dự phòng: nếu Chassis Rear đã đúng sẵn từ đầu (vd mặc
            # định index 0 đúng luôn), currentTextChanged không bắn lại sau
            # __init__ nên set_current_product() không có cơ hội chạy —
            # product_code sẽ kẹt ở None mãi nếu không tự cập nhật ở đây.
            self._current_product_code = product_code
            self._current_profile_id = profile_id

            self._counters["total"] += 1
            self._counters["ok" if is_ok else "ng"] += 1
            self._last_result = "OK" if is_ok else "NG"
            self._last_code = last_code or ""
            self._last_local_scan_id = local_scan_id or ""
            self._last_pending_sync = pending_sync

            if not self._session_active:
                return
            payload = self._build_update_payload_locked()
        self._emit("runtime:update", payload)

    def emit_snapshot(self):
        """Nối thẳng QTimer.timeout — không tham số. KHÔNG đổi bộ đếm."""
        with self._lock:
            if not self._session_active:
                return
            payload = self._build_update_payload_locked()
        self._emit("runtime:snapshot", payload)

    def emit_runtime_error(self, error_code, message):
        """App local lỗi (vd ghi DB thất bại) nhưng socket còn sống."""
        with self._lock:
            if not self._session_active:
                return
            payload = {
                "profile_id": self._current_profile_id,
                "product_code": self._current_product_code,
                "total_count": self._counters["total"],
                "ok_count": self._counters["ok"],
                "ng_count": self._counters["ng"],
                "last_result": "ERROR",
                "error_code": error_code,
                "message": message,
            }
        self._emit("runtime:error", payload)

    def stop(self, reason="APP_CLOSING"):
        """Gọi đúng 1 lần từ closeEvent — AN TOÀN gọi cả khi start_session()
        chưa từng chạy. ĐỒNG BỘ hoàn toàn (đã gồm chờ thread nền xong bên
        trong, không cần .wait() riêng ở nơi gọi). Trả True chỉ khi server
        ACK runtime:stop bằng code RUNTIME_SESSION_STOPPED."""
        with self._lock:
            was_active = self._session_active
            payload = None
            self._last_stop_confirmed = None
            if was_active:
                payload = self._build_update_payload_locked()
                payload["stopped_at"] = datetime.now().astimezone().isoformat()
                payload["reason"] = reason
            self._session_active = False

        confirmed = self._call_runtime_stop(payload) if was_active else False
        if was_active:
            with self._lock:
                self._last_stop_confirmed = confirmed

        if self._connect_worker is not None:
            self._connect_worker.stop()

        if self._sio.connected:
            try:
                self._sio.disconnect()
            except Exception as exc:
                log_event(f"[machine-runtime] Lỗi khi disconnect: {exc}")

        return confirmed

    def is_session_active(self):
        return self._session_active

    def was_last_stop_unconfirmed(self):
        return self._last_stop_confirmed is False

    ######################################################################
    # Nội bộ
    ######################################################################

    def _build_update_payload_locked(self):
        """PHẢI gọi trong lúc đang giữ self._lock. Dùng chung cho
        runtime:update/runtime:snapshot/phần đầu runtime:stop (cùng 12
        field — runtime:stop nối thêm stopped_at/reason ở nơi gọi)."""
        total = self._counters["total"]
        ok = self._counters["ok"]
        ng = self._counters["ng"]
        return {
            "profile_id": self._current_profile_id,
            "product_code": self._current_product_code,
            "total_count": total,
            "ok_count": ok,
            "ng_count": ng,
            # Chưa tách bộ đếm riêng theo product_code (đơn giản hoá theo
            # yêu cầu user) — lặp lại đúng số tổng.
            "product_total_count": total,
            "product_ok_count": ok,
            "product_ng_count": ng,
            "last_result": self._last_result,
            "last_code": self._last_code,
            "local_scan_id": self._last_local_scan_id,
            "pending_sync": self._last_pending_sync,
        }

    def _build_start_payload_locked(self):
        """PHẢI gọi trong lúc đang giữ self._lock."""
        return {
            "profile_id": self._current_profile_id,
            "product_code": self._current_product_code,
            "started_at": datetime.now().astimezone().isoformat(),
            "total_count": 0,
            "ok_count": 0,
            "ng_count": 0,
            "product_total_count": 0,
            "product_ok_count": 0,
            "product_ng_count": 0,
        }

    def _emit(self, event, payload, require_connected=True):
        """Điểm CHỐT DUY NHẤT chạm vào self._sio.emit() — khoá riêng cho lời
        gọi này (KHÔNG giữ chung khoá với lúc tính payload, để không giữ
        self._lock suốt thời gian I/O mạng — nếu không, việc ghi nhận 1 kết
        quả quét mới từ GUI thread có thể bị chặn lại phía sau 1 lần emit()
        chậm/kẹt mạng). self._sio.emit() được chính thư viện ghi rõ trong
        docstring là KHÔNG thread-safe — lời gọi này có thể tới từ 3 thread
        khác nhau (GUI; _RuntimeConnectWorker lúc machine:hello đầu tiên vì
        _on_connect chạy đồng bộ ngay trong lúc .connect() đang blocking;
        thread nền riêng của chính socketio lúc machine:hello sau mỗi lần
        reconnect) nên bắt buộc phải khoá. Trả True nếu đã gửi thành công.

        require_connected=False (chỉ _on_connect dùng): đọc source
        socketio/client.py xác nhận self.connected=True được set TRONG
        connect() SAU KHI _connect_event.wait() trả về, mà _connect_event
        chỉ được .set() TRONG _handle_connect() SAU DÒNG gọi
        _trigger_event('connect', ...) (chính là _on_connect ở đây) — tức
        self._sio.connected LUÔN CÒN False (không phải thỉnh thoảng) tại
        đúng thời điểm _on_connect chạy. Đã tự verify bằng trace thật trên
        instance sống (sio.connected=False mọi lần). Bỏ qua check này an
        toàn vì emit() tự kiểm tra namespace trong self.namespaces — dòng
        đó đã được gán TRƯỚC _trigger_event trong cùng _handle_connect()."""
        if payload is None:
            return False
        with self._lock:
            if require_connected and not self._sio.connected:
                return False
            try:
                self._sio.emit(event, payload, namespace=NAMESPACE)
                return True
            except Exception as exc:
                log_event(f"[machine-runtime] Lỗi khi emit {event}: {exc}")
                return False

    def _call_runtime_stop(self, payload):
        """Gửi runtime:stop và chờ ACK thật từ server trước khi disconnect."""
        if payload is None:
            return False
        with self._lock:
            if not self._sio.connected:
                log_event(
                    "[machine-runtime] Không thể xác nhận runtime:stop: socket đã ngắt."
                )
                return False
            try:
                response = self._sio.call(
                    "runtime:stop",
                    payload,
                    timeout=RUNTIME_STOP_ACK_TIMEOUT_SEC,
                    namespace=NAMESPACE,
                )
            except socketio.exceptions.TimeoutError:
                log_event(
                    "[machine-runtime] Không nhận ACK runtime:stop trong "
                    f"{RUNTIME_STOP_ACK_TIMEOUT_SEC} giây."
                )
                return False
            except Exception as exc:
                log_event(f"[machine-runtime] Lỗi khi chờ ACK runtime:stop: {exc}")
                return False

        ack_code = response.get("code") if isinstance(response, dict) else None
        if ack_code != RUNTIME_STOP_ACK_CODE:
            log_event(
                "[machine-runtime] ACK runtime:stop không hợp lệ: "
                f"code={ack_code!r}."
            )
            return False

        log_event(
            f"[machine-runtime] Server ACK runtime:stop: {RUNTIME_STOP_ACK_CODE}."
        )
        return True

    def _on_connect(self):
        with self._lock:
            identity = self._identity
        if identity is not None:
            self._emit("machine:hello", identity, require_connected=False)

    def _on_disconnect(self, reason=None):
        self.runtimeDisconnected.emit(reason or "")

    def _on_machine_accepted(self, data):
        if data.get("success") and data.get("code") == "RUNTIME_SOCKET_ACCEPTED":
            with self._lock:
                first_time = not self._ever_accepted
                self._ever_accepted = True
                start_payload = (
                    self._build_start_payload_locked() if first_time else None
                )
            if first_time:
                self.runtimeConnected.emit()
                self._emit("runtime:start", start_payload)
            else:
                self.runtimeReconnected.emit()
                self.emit_snapshot()
        else:
            message = (
                data.get("message") or "Machine runtime bị server từ chối định danh."
            )
            self.runtimeBlocked.emit(message)
