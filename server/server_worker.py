"""
Worker nền gọi server (REST) — 1 QThread sống suốt vòng đời app, xử lý tuần
tự các job (health, và các loại job sẽ thêm ở các lần sau: identity, config,
heartbeat, submit_scan...) qua 1 hàng đợi, không chặn GUI thread.

Khác với reader/reader_bridge.py (1 QThread giữ 1 kết nối socket sống liên
tục), ở đây HTTP là request/response ngắn hạn nên dùng 1 thread xử lý nhiều
job tuần tự qua hàng đợi là hợp lý hơn là 1 thread/lần gọi.
"""

import queue

from PyQt5.QtCore import QThread, pyqtSignal

from server.api_client import ServerApiError

_STOP = object()


class ServerWorker(QThread):
    # (job_kind, correlation_id, response_dict)
    callSucceeded = pyqtSignal(str, str, dict)
    # (job_kind, correlation_id, error_message, response_payload — payload rỗng
    # {} nếu lỗi mạng/timeout thuần, hoặc chứa nguyên response body nếu server
    # trả HTTP lỗi kèm body (vd MACHINE_REGISTER_DUPLICATE) để nơi gọi vẫn đọc
    # được data.* chi tiết thay vì chỉ có 1 chuỗi message phẳng)
    callFailed = pyqtSignal(str, str, str, dict)

    def __init__(self, client, parent=None):
        super().__init__(parent)
        self._client = client
        self._queue = queue.Queue()

    def enqueue(self, job_kind, correlation_id="", **kwargs):
        self._queue.put((job_kind, correlation_id, kwargs))

    def update_config(self, config):
        """Đổi host/port đang dùng ngay lập tức — job đang chạy dở (nếu có)
        vẫn dùng config cũ, job kế tiếp trong hàng đợi dùng config mới."""
        self._client.config = config

    def stop(self):
        self._queue.put(_STOP)

    def run(self):
        while True:
            job = self._queue.get()
            if job is _STOP:
                break
            job_kind, correlation_id, kwargs = job
            try:
                result = self._dispatch(job_kind, kwargs)
                self.callSucceeded.emit(job_kind, correlation_id, result)
            except ServerApiError as exc:
                self.callFailed.emit(job_kind, correlation_id, str(exc), exc.payload)
            except Exception as exc:
                # Không để 1 job lỗi bất ngờ làm chết cả worker.
                self.callFailed.emit(job_kind, correlation_id, str(exc), {})

    def _dispatch(self, job_kind, kwargs):
        if job_kind == "health":
            return self._client.health()
        if job_kind == "register_request":
            return self._client.register_request(**kwargs)
        if job_kind == "register_status":
            return self._client.get_registration_status(**kwargs)
        if job_kind == "identity_status":
            return self._client.get_identity_status(**kwargs)
        raise ValueError(f"Không hỗ trợ job_kind: {job_kind}")
