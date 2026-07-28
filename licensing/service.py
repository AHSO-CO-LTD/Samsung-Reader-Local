"""Lớp thay thế license_manager.py của E:\\License-Key-main — thay vì lưu
license.dat ra file %APPDATA%, lưu trực tiếp vào local_app_settings (đúng quy
ước của dự án: mọi state của máy sống trong Postgres local, không rải file)."""
from datetime import datetime

from db.local_db import get_app_settings, update_app_settings
from licensing.license_client import get_machine_id, verify_license


def evaluate_local_license(app_version, app_release_date, app_product=None):
    """Trạng thái hiện tại: {"state": "active"|"unactivated"|"invalid",
    "machine_id", "lic", "why"}. Tính machine_id MỚI mỗi lần gọi (rẻ, thuần
    cục bộ) — KHÔNG lưu vào DB (khác thiết kế trước) vì license giờ độc lập
    hoàn toàn với machine_code của luồng đăng ký cũ, tránh giẫm chân nhau."""
    lic_str = get_app_settings().get("machine_license_key")
    machine_id = get_machine_id()
    if not lic_str:
        return {"state": "unactivated", "machine_id": machine_id, "lic": None, "why": "chua_kich_hoat"}

    result = verify_license(lic_str, machine_id, app_version, app_release_date, app_product)
    if result["ok"]:
        return {"state": "active", "machine_id": machine_id, "lic": result["lic"], "why": None}
    return {"state": "invalid", "machine_id": machine_id, "lic": result["lic"], "why": result["why"]}


def activate_local_license(lic_str, app_version, app_release_date, app_product=None):
    """Operator dán license -> verify -> nếu OK thì lưu CHỈ machine_license_key
    (KHÔNG đụng machine_code/registration_status/license_activated_at — 3 cột
    đó thuộc về luồng đăng ký cũ, license không được phép ghi đè)."""
    machine_id = get_machine_id()
    result = verify_license(lic_str, machine_id, app_version, app_release_date, app_product)
    if not result["ok"]:
        return {"ok": False, "why": result["why"], "lic": None, "machine_id": machine_id}

    update_app_settings(machine_license_key=lic_str.strip())
    return {"ok": True, "why": None, "lic": result["lic"], "machine_id": machine_id}


def build_machine_info_export(app_version, app_release_date, app_product=None):
    """Gói thông tin bên cấp license cần để tự ký license đúng — operator chỉ
    cần gửi 1 file này, không cần trao đổi riêng thêm gì. local_db_version
    chỉ mang tính chẩn đoán, không ảnh hưởng verify_license().

    KHÔNG có field hostname — tạm bỏ theo yêu cầu (giá trị dễ đổi, không phải
    định danh ổn định như machine_id — không nên dùng để phân biệt máy)."""
    settings = get_app_settings()
    return {
        "machine_id": get_machine_id(),
        "app_version": app_version,
        "app_release_date": app_release_date,
        "app_product": app_product,
        "local_db_version": settings.get("local_db_version"),
        "exported_at": datetime.now().astimezone().isoformat(),
    }
