"""
Đọc hardware ID gắn với phần cứng vật lý của máy local (BIOS/Motherboard UUID
+ Motherboard Serial Number), dùng để định danh máy với server thay vì IP
(IP có thể đổi mà không được khai báo lại, gây lẫn dữ liệu giữa các máy).

Lấy qua PowerShell/CIM (Get-CimInstance) — không cần cài thêm package
`wmi`/`pywin32`, và không phụ thuộc `wmic` vì Microsoft đang loại bỏ dần công
cụ này khỏi các bản Windows mới.

Cách dùng:
    python machine/hardware_id.py
"""

import subprocess

_PLACEHOLDER_STRINGS = {
    "to be filled by o.e.m.",
    "default string",
    "system serial number",
    "not specified",
    "none",
    "n/a",
}

_cache = None


def _is_placeholder(value):
    if not value:
        return True
    value = value.strip()
    if not value:
        return True
    lowered = value.lower()
    if lowered in _PLACEHOLDER_STRINGS:
        return True
    stripped = value.replace("-", "")
    if stripped == "0" * len(stripped):
        return True
    if stripped.upper() == "F" * len(stripped):
        return True
    return False


def _query_cim(class_name, property_name):
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-CimInstance {class_name}).{property_name}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return None if _is_placeholder(value) else value


def get_hardware_id(force_refresh=False):
    """Trả về {"bios_uuid": str | None, "motherboard_serial": str | None}.

    Mỗi giá trị được đọc và kiểm tra độc lập — không suy ra hay thay thế
    bằng giá trị kia. Nếu cả 2 đều None (mainboard không rõ thương hiệu,
    không trả UUID/serial thật), hàm này vẫn trả về bình thường, KHÔNG tự
    sinh ID giả để thay thế — nơi gọi (flow đăng ký/license sau này) tự
    quyết định chặn lại khi gặp trường hợp này."""
    global _cache
    if _cache is not None and not force_refresh:
        return _cache

    _cache = {
        "bios_uuid": _query_cim("Win32_ComputerSystemProduct", "UUID"),
        "motherboard_serial": _query_cim("Win32_BaseBoard", "SerialNumber"),
    }
    return _cache


if __name__ == "__main__":
    info = get_hardware_id()
    print(f"BIOS/Motherboard UUID : {info['bios_uuid']}")
    print(f"Motherboard Serial    : {info['motherboard_serial']}")
    if not info["bios_uuid"] and not info["motherboard_serial"]:
        print("CANH BAO: khong doc duoc hardware ID that tu mainboard nay.")
