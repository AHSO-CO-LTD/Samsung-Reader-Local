"""
Đọc các ID ổn định của máy local: Windows MachineGuid, BIOS/Motherboard UUID
và Motherboard Serial Number. Flow định danh với server dùng MachineGuid làm
serial và BIOS UUID làm uid; Motherboard Serial vẫn được đọc/trả về để hiển
thị, chẩn đoán hoặc dùng cho mục đích khác.

Lấy qua PowerShell/CIM (Get-CimInstance) — không cần cài thêm package
`wmi`/`pywin32`, và không phụ thuộc `wmic` vì Microsoft đang loại bỏ dần công
cụ này khỏi các bản Windows mới.

Cách dùng:
    python machine/hardware_id.py
"""

import subprocess
import winreg

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


def _query_machine_guid():
    """Đọc Windows MachineGuid từ registry 64-bit, không cần PowerShell."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
    except OSError:
        return None

    value = str(value).strip()
    return None if _is_placeholder(value) else value


def get_hardware_id(force_refresh=False):
    """Trả về MachineGuid, BIOS UUID và Motherboard Serial độc lập.

    Không xoá hoặc thay thế Motherboard Serial bằng MachineGuid trong kết quả;
    nơi gọi tự chọn giá trị nào làm serial/uid. Nếu không đọc được một giá trị,
    field tương ứng là None và hàm không tự sinh ID giả để thay thế."""
    global _cache
    if _cache is not None and not force_refresh:
        return _cache

    _cache = {
        "machine_guid": _query_machine_guid(),
        "bios_uuid": _query_cim("Win32_ComputerSystemProduct", "UUID"),
        "motherboard_serial": _query_cim("Win32_BaseBoard", "SerialNumber"),
    }
    return _cache


if __name__ == "__main__":
    info = get_hardware_id()
    print(f"Windows MachineGuid   : {info['machine_guid']}")
    print(f"BIOS/Motherboard UUID : {info['bios_uuid']}")
    print(f"Motherboard Serial    : {info['motherboard_serial']}")
    if not any(info.values()):
        print("CANH BAO: khong doc duoc dinh danh may.")
