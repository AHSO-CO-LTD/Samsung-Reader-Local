"""
license_request.py — sinh file JSON yêu cầu cấp license theo chuẩn
AHSO_LICENSE_REQUEST_V1 (E:\\License-Key-main\\CHUAN-JSON-REQUEST.md).

Port từ E:\\License-Key-main\\python\\license_request.py, chỉ khác: nhận
machine_id từ nơi gọi (đã cache ở licensing/service.py) thay vì tự gọi lại
get_machine_id() — tránh chạy PowerShell thêm lần nữa trên UI thread.
"""
import json
from datetime import datetime, timezone

REQUEST_FORMAT = "AHSO_LICENSE_REQUEST_V1"


def build_license_request(machine_id: str, product: str, app_version: str,
                          app_name: str = "", release_date: str = "",
                          customer_hint: str = "") -> dict:
    return {
        "format": REQUEST_FORMAT,
        "machine_id": machine_id,
        "product": product,
        "app_version": app_version,
        "app_name": app_name or None,
        "release_date": release_date or None,
        "customer_hint": customer_hint or None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def save_license_request(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
