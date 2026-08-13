import copy
import queue
import threading
import uuid

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from .plc_client import (
    PlcCommError,
    open_serial,
    open_tcp,
    read_register,
    read_register_mc,
    write_register,
    write_register_mc,
)


class PlcWorker(QObject):
    connectionChanged = pyqtSignal(bool)
    commandSucceeded = pyqtSignal(str, str, object)
    commandFailed = pyqtSignal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._jobs = queue.Queue()
        self._stop_event = threading.Event()
        self._config_lock = threading.Lock()
        self._config = {}
        self._conn = None
        self._connected = False
        self._errors = 0

    @pyqtSlot(object)
    def apply_config(self, config):
        with self._config_lock:
            previous = self._config
            self._config = copy.deepcopy(config or {})
        # Bat ky truong nao anh huong toi VIEC MO KET NOI deu phai dong ket
        # noi cu di, khong chi rieng "port" nhu truoc (thieu se giu nguyen
        # socket TCP cu du IP/port vua doi trong luc dang mo cua so PLC).
        changed_keys = ("connection_type", "port", "host", "tcp_port", "enabled")
        if any(previous.get(k) != self._config.get(k) for k in changed_keys):
            self._close_connection()

    def _job(self, kind, payload=None, correlation_id=None):
        correlation_id = correlation_id or uuid.uuid4().hex
        self._jobs.put((kind, correlation_id, payload or {}))
        return correlation_id

    def enqueue_test_read(self, correlation_id=None, kind="test_read"):
        return self._job(kind, {}, correlation_id)

    def enqueue_test_write(self, value, correlation_id=None):
        return self._job("test_write", {"value": int(value)}, correlation_id)

    def send_ng_signal(self, correlation_id=None):
        return self._job("ng_signal", {"value_from_config": True}, correlation_id)

    def send_ok_reset(self, correlation_id=None):
        return self._job("ok_reset", {"value_from_config": False}, correlation_id)

    def send_pulse_reset(self, correlation_id=None):
        """Return the D register to zero after a pulse, independent of state mode."""
        return self._job("ok_reset", {"value": 0}, correlation_id)

    @property
    def is_connected(self):
        return self._connected

    def stop(self):
        self._stop_event.set()
        self._jobs.put(None)

    def _snapshot(self):
        with self._config_lock:
            return copy.deepcopy(self._config)

    def _set_connected(self, state):
        state = bool(state)
        if self._connected != state:
            self._connected = state
            self.connectionChanged.emit(state)

    def _close_connection(self):
        conn, self._conn = self._conn, None
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        self._errors = 0
        self._set_connected(False)

    def _ensure_connection(self, config):
        if not config.get("enabled"):
            self._close_connection()
            return None
        if config.get("connection_type") == "ethernet":
            if self._conn is not None:
                return self._conn
            try:
                self._conn = open_tcp(config.get("host", ""), int(config.get("tcp_port", 0) or 0))
            except Exception:
                self._set_connected(False)
                raise
            return self._conn
        if self._conn is not None and getattr(self._conn, "is_open", False):
            return self._conn
        if not config.get("port"):
            raise PlcCommError("Chưa chọn cổng COM cho PLC")
        try:
            self._conn = open_serial(config["port"], timeout=1.0)
        except Exception as exc:
            self._set_connected(False)
            raise PlcCommError(f"Không mở được {config['port']}: {exc}") from exc
        # KHONG goi _set_connected(True) o day (ca 2 nhanh serial/TCP o tren)
        # — mo cong COM/socket thanh cong chi co nghia he dieu hanh cho phep
        # truy cap, KHONG co nghia PLC that su dang phan hoi (bug that: PLC
        # khong ket noi/khong tra loi van hien "Da ket noi" vi mo cong luon
        # thanh cong). "Connected" chi duoc coi la dung sau khi 1 lenh giao
        # tiep THAT SU thanh cong — xem run(), goi _set_connected(True) o
        # nhanh commandSucceeded.
        return self._conn

    def _execute(self, kind, payload, config):
        if not config.get("enabled"):
            raise PlcCommError("PLC chưa được bật")
        conn = self._ensure_connection(config)
        d_register = int(config.get("d_register", 0))
        if config.get("connection_type") == "ethernet":
            read_fn, write_fn = read_register_mc, write_register_mc
        else:
            read_fn, write_fn = read_register, write_register
        if kind in ("test_read", "health_check"):
            return {"value": read_fn(conn, d_register)}
        if kind == "test_write":
            write_fn(conn, d_register, int(payload["value"]))
            return {"value": int(payload["value"])}
        if kind == "ng_signal":
            value = int(config.get("ng_value", 1))
            write_fn(conn, d_register, value)
            return {"value": value}
        if kind == "ok_reset":
            value = int(payload.get("value", config.get("ok_reset_value", 0)))
            write_fn(conn, d_register, value)
            return {"value": value}
        raise PlcCommError(f"Unknown PLC command: {kind}")

    @pyqtSlot()
    def run(self):
        while not self._stop_event.is_set():
            try:
                job = self._jobs.get(timeout=0.2)
            except queue.Empty:
                continue
            if job is None:
                break
            kind, correlation_id, payload = job
            try:
                result = self._execute(kind, payload, self._snapshot())
                self._errors = 0
                self._set_connected(True)
                self.commandSucceeded.emit(kind, correlation_id, result)
            except Exception as exc:
                self._errors += 1
                if self._errors >= 3:
                    self._close_connection()
                self.commandFailed.emit(kind, correlation_id, str(exc))
        self._close_connection()
