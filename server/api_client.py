"""
Client HTTP gọi backend NestJS của Samsung QR Recorder Server, theo đúng
contract mô tả trong docs/10-huong-dan-api-may-local-python (2).md (mục 22).

Lần đầu triển khai (xem plan) chỉ gọi health(); các method còn lại được viết
sẵn đầy đủ để dùng dần ở các lần sau (identity/config/heartbeat/scan-submit/
register-request/batch-sync/reconcile) mà không cần sửa lại file này.

Mọi lần gọi (qua _request) đều tự động ghi 1 dòng vào api_request_logs (theo
docs/10-...: "Local nên ghi mọi lần gọi API vào api_request_logs") — chỉ cần
mỗi method truyền đúng request_type, không cần tự ghi log ở nơi gọi.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

from db.local_db import log_api_request


class ServerApiError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, payload: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


@dataclass(frozen=True)
class ServerApiConfig:
    host: str
    port: int = 3979
    timeout_seconds: float = 5.0

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/api"


def _safe_log_api_request(**kwargs: Any) -> None:
    """Ghi log không được làm hỏng luồng gọi API chính — lỗi ghi log (vd DB
    local tạm thời không kết nối được) chỉ bỏ qua, không raise lên trên."""
    try:
        log_api_request(**kwargs)
    except Exception:
        pass


class SamsungQrServerClient:
    def __init__(self, config: ServerApiConfig) -> None:
        self.config = config
        self.session = requests.Session()

    def health(self) -> Dict[str, Any]:
        return self._request("GET", "/health", "health")

    def get_identity_status(self, serial: str, uid: str) -> Dict[str, Any]:
        return self._request(
            "GET", "/machines/identity/status", "identity_status",
            params={"serial": serial, "uid": uid},
        )

    def register_request(
        self,
        serial: str,
        uid: str,
        ip_address: str,
    ) -> Dict[str, Any]:
        body = {
            "serial": serial,
            "uid": uid,
            "ip_address": ip_address,
        }
        return self._request("POST", "/machines/register-request", "register_request", json=body)

    def get_registration_status(self, request_id: str, serial: str, uid: str) -> Dict[str, Any]:
        return self._request(
            "GET",
            f"/machines/register-requests/{request_id}/status",
            "register_status",
            params={"serial": serial, "uid": uid},
        )

    def get_machine_config(self, serial: str, uid: str) -> Dict[str, Any]:
        return self._request(
            "GET", "/machines/config", "config",
            params={"serial": serial, "uid": uid},
        )

    def heartbeat(
        self,
        machine_code: str,
        serial: str,
        uid: str,
        ip_address: Optional[str],
        app_version: str,
        local_db_version: str,
        local_total_record: int,
        local_ok_record: int,
        local_ng_record: int,
        local_pending_sync: int,
        local_checksum: Optional[str],
    ) -> Dict[str, Any]:
        body = {
            "machine_code": machine_code,
            "serial": serial,
            "uid": uid,
            "ip_address": ip_address,
            "app_version": app_version,
            "local_db_version": local_db_version,
            "local_total_record": local_total_record,
            "local_ok_record": local_ok_record,
            "local_ng_record": local_ng_record,
            "local_pending_sync": local_pending_sync,
            "local_checksum": local_checksum,
        }
        return self._request("POST", "/machines/heartbeat", "heartbeat", json=body)

    def poll_commands(self, serial: str, uid: str, take: int = 20) -> Dict[str, Any]:
        return self._request(
            "GET", "/machines/commands/poll", "commands_poll",
            params={"serial": serial, "uid": uid, "take": take},
        )

    def ack_command(
        self,
        command_id: int,
        serial: str,
        uid: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        body = {
            "serial": serial,
            "uid": uid,
            "status": status,
            "error_message": error_message,
        }
        return self._request("POST", f"/machines/commands/{command_id}/ack", "command_ack", json=body)

    def submit_scan(self, scan_payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/scans/submit", "scan_submit", json=scan_payload)

    def submit_batch(
        self,
        batch_code: str,
        machine_code: str,
        serial: str,
        uid: str,
        trigger_type: str,
        scans: List[Dict[str, Any]],
        summary_json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body = {
            "batch_code": batch_code,
            "machine_code": machine_code,
            "serial": serial,
            "uid": uid,
            "trigger_type": trigger_type,
            "scans": scans,
            "summary_json": summary_json,
        }
        return self._request("POST", "/sync/batches/submit", "batch_submit", json=body)

    def reconcile_check(
        self,
        serial: str,
        uid: str,
        ip_address: str,
        records: Optional[List[Dict[str, Any]]] = None,
        from_scan_at: Optional[str] = None,
        to_scan_at: Optional[str] = None,
        local_total_record: Optional[int] = None,
        local_ok_record: Optional[int] = None,
        local_ng_record: Optional[int] = None,
        local_checksum: Optional[str] = None,
    ) -> Dict[str, Any]:
        body = {
            "serial": serial,
            "uid": uid,
            "ip_address": ip_address,
            "from_scan_at": from_scan_at,
            "to_scan_at": to_scan_at,
            "local_total_record": local_total_record,
            "local_ok_record": local_ok_record,
            "local_ng_record": local_ng_record,
            "local_checksum": local_checksum,
            "records": records,
        }
        return self._request("POST", "/sync/reconcile/check", "reconcile_check", json=body)

    def reconcile_pull(
        self,
        serial: str,
        uid: str,
        local_scan_ids: Optional[List[str]] = None,
        from_scan_at: Optional[str] = None,
        to_scan_at: Optional[str] = None,
        take: int = 200,
    ) -> Dict[str, Any]:
        body = {
            "serial": serial,
            "uid": uid,
            "local_scan_ids": local_scan_ids,
            "from_scan_at": from_scan_at,
            "to_scan_at": to_scan_at,
            "take": take,
        }
        return self._request("POST", "/sync/reconcile/pull", "reconcile_pull", json=body)

    def _request(
        self,
        method: str,
        path: str,
        request_type: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.config.base_url}{path}"
        started_at = time.monotonic()
        response_status_code: Optional[int] = None
        response_json: Optional[Dict[str, Any]] = None
        result_code: Optional[str] = None
        error_message: Optional[str] = None
        success = False
        try:
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    json=json,
                    params=params,
                    timeout=self.config.timeout_seconds,
                )
            except requests.Timeout as exc:
                raise ServerApiError(f"Server timeout: {url}") from exc
            except requests.ConnectionError as exc:
                raise ServerApiError(f"Cannot connect to server: {url}") from exc

            response_status_code = response.status_code
            try:
                payload = response.json()
            except ValueError as exc:
                raise ServerApiError(
                    message=f"Server returned non-JSON response: HTTP {response.status_code}",
                    status_code=response.status_code,
                    payload={"raw_text": response.text},
                ) from exc

            if isinstance(payload, dict):
                response_json = payload
                result_code = payload.get("code")

            if response.status_code < 200 or response.status_code >= 300:
                message = payload.get("message") if isinstance(payload, dict) else response.text
                raise ServerApiError(
                    message=str(message),
                    status_code=response.status_code,
                    payload=payload if isinstance(payload, dict) else {"response": payload},
                )

            if not isinstance(payload, dict):
                raise ServerApiError(
                    message="Server response is not an object.",
                    status_code=response.status_code,
                    payload={"response": payload},
                )

            success = True
            return payload
        except ServerApiError as exc:
            error_message = str(exc)
            if exc.status_code is not None:
                response_status_code = exc.status_code
            if exc.payload:
                response_json = exc.payload
                result_code = exc.payload.get("code")
            raise
        finally:
            duration_ms = int((time.monotonic() - started_at) * 1000)
            _safe_log_api_request(
                request_type=request_type,
                method=method,
                url=url,
                request_json=json,
                response_status_code=response_status_code,
                response_json=response_json,
                result_code=result_code,
                success=success,
                error_message=error_message,
                duration_ms=duration_ms,
            )
