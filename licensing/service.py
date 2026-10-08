"""Lớp thay thế license_manager.py của E:\\License-Key-main — thay vì lưu
license-<product>.dat ra file %APPDATA%, lưu trực tiếp vào local_app_settings
(đúng quy ước của dự án: mọi state của máy sống trong Postgres local, không
rải file). Thông tin version/release date/product lấy từ app_info.py."""
from app_info import APP_NAME, APP_PRODUCT, APP_RELEASE_DATE, APP_VERSION
from db.local_db import get_app_settings, update_app_settings
from licensing.license_client import get_machine_id, verify_license
from licensing.license_request import build_license_request

_machine_id_cache = None


def get_cached_machine_id():
    """Machine ID tính 1 lần/tiến trình — get_machine_id() gọi PowerShell
    (~1s) và phần cứng không đổi khi app đang chạy, nên các lần re-check
    định kỳ không được phép chạy lại PowerShell trên UI thread."""
    global _machine_id_cache
    if _machine_id_cache is None:
        _machine_id_cache = get_machine_id()
    return _machine_id_cache


def _verify(lic_str, machine_id):
    return verify_license(lic_str, machine_id, APP_VERSION, APP_RELEASE_DATE, APP_PRODUCT)


def evaluate_local_license():
    """Trạng thái hiện tại: {"state": "active"|"unactivated"|"invalid",
    "machine_id", "lic", "why"}. Verify lại từ chuỗi đã lưu mỗi lần gọi (rẻ,
    thuần cục bộ) để bắt được license hết hạn trong lúc app đang chạy.
    KHÔNG lưu machine_id/trạng thái vào DB — license độc lập hoàn toàn với
    machine_code của luồng đăng ký server."""
    lic_str = get_app_settings().get("machine_license_key")
    machine_id = get_cached_machine_id()
    if not lic_str:
        return {"state": "unactivated", "machine_id": machine_id, "lic": None, "why": "chua_kich_hoat"}

    result = _verify(lic_str, machine_id)
    if result["ok"]:
        return {"state": "active", "machine_id": machine_id, "lic": result["lic"], "why": None}
    return {"state": "invalid", "machine_id": machine_id, "lic": result["lic"], "why": result["why"]}


def activate_local_license(lic_str):
    """Operator dán license -> verify -> nếu OK thì lưu CHỈ machine_license_key
    (KHÔNG đụng machine_code/registration_status/license_activated_at — 3 cột
    đó thuộc về luồng đăng ký server, license không được phép ghi đè)."""
    machine_id = get_cached_machine_id()
    result = _verify(lic_str, machine_id)
    if not result["ok"]:
        return {"ok": False, "why": result["why"], "lic": None, "machine_id": machine_id}

    update_app_settings(machine_license_key=lic_str.strip())
    return {"ok": True, "why": None, "lic": result["lic"], "machine_id": machine_id}


def build_machine_license_request():
    """Nội dung file yêu cầu cấp license (chuẩn AHSO_LICENSE_REQUEST_V1) —
    operator chỉ cần gửi file này, tool cấp license tự nạp vào form."""
    return build_license_request(
        machine_id=get_cached_machine_id(),
        product=APP_PRODUCT,
        app_version=APP_VERSION,
        app_name=APP_NAME,
        release_date=APP_RELEASE_DATE,
    )
