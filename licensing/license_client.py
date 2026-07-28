"""
license_client.py — sinh Machine ID + verify license (offline).

Copy gần như nguyên vẹn từ E:\\License-Key-main\\python\\license_client.py —
KHÔNG sửa logic, để sau này xoay PUBLIC_KEY_HEX chỉ cần thay đúng file này.
Nhúng PUBLIC_KEY_HEX (lấy từ public key do bên giữ công cụ ký license cấp).
KHÔNG bao giờ nhúng private key.
"""
import base64
import hashlib
import json
import platform
import re
import subprocess
from datetime import date, datetime

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

# <<< Public key (hex) do bên giữ công cụ ký license cấp >>>
PUBLIC_KEY_HEX = "cbd069fde139494d9dd65b915db7084022120ab4cff4151ab213721656b5d1d3"

# Giá trị UUID rác/trùng phải loại bỏ (rơi về MachineGuid)
GARBAGE_UUIDS = {
    "",
    "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",
    "00000000-0000-0000-0000-000000000000",
    "03000200-0400-0500-0006-000700080009",   # default UUID trùng lặp nổi tiếng
    "NOT SETTINGS",
}


# ----------------------------- MACHINE ID -----------------------------

def _run(cmd: str) -> str:
    try:
        out = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL,
                                      timeout=10).decode(errors="ignore")
        return out
    except Exception:
        return ""


def _win_system_uuid() -> str:
    # Ưu tiên PowerShell (wmic bị gỡ ở Windows mới), fallback wmic.
    ps = _run('powershell -NoProfile -Command '
              '"(Get-CimInstance Win32_ComputerSystemProduct).UUID"')
    val = ps.strip().splitlines()[-1].strip() if ps.strip() else ""
    if not val:
        out = _run("wmic csproduct get UUID")
        lines = [l.strip() for l in out.splitlines() if l.strip() and "UUID" not in l]
        val = lines[0] if lines else ""
    return val.upper().strip()


def _win_machine_guid() -> str:
    out = _run('reg query "HKLM\\SOFTWARE\\Microsoft\\Cryptography" /v MachineGuid')
    for line in out.splitlines():
        if "MachineGuid" in line:
            return line.split()[-1].strip().upper()
    return ""


def _linux_machine_id() -> str:
    for p in ("/sys/class/dmi/id/product_uuid", "/etc/machine-id",
              "/var/lib/dbus/machine-id"):
        v = _run(f"cat {p}").strip()
        if v:
            return v.upper()
    return ""


def _mac_uuid() -> str:
    out = _run("ioreg -rd1 -c IOPlatformExpertDevice")
    for line in out.splitlines():
        if "IOPlatformUUID" in line:
            return line.split('"')[-2].upper()
    return ""


def get_machine_id() -> str:
    """
    Machine ID = SMBIOS System UUID (mainboard), fallback MachineGuid khi rác.
    Kết quả dạng XXXX-XXXX-XXXX-XXXX (16 hex).
    """
    system = platform.system()
    if system == "Windows":
        uuid = _win_system_uuid()
        if uuid in GARBAGE_UUIDS or not uuid:
            uuid = _win_machine_guid()
    elif system == "Darwin":
        uuid = _mac_uuid()
    else:
        uuid = _linux_machine_id()

    src = (uuid or "UNKNOWN-HARDWARE").upper().strip()
    h = hashlib.sha256(src.encode()).hexdigest()[:16].upper()
    return "-".join(h[i:i + 4] for i in range(0, 16, 4))


# ----------------------------- VERIFY -----------------------------

# base64url strict: chỉ nhận A-Z a-z 0-9 - _ (và '=' đệm nếu có).
# base64.urlsafe_b64decode() mặc định ÂM THẦM bỏ qua ký tự lạ thay vì báo lỗi
# (không có tham số validate=True như b64decode), nên phải tự kiểm tra bảng chữ
# cái trước khi decode để tránh chuỗi hỏng lọt qua — khớp electron/verifyLicense.js.
_B64URL_RE = re.compile(r"^[A-Za-z0-9_-]+=*$")


def _major(version: str) -> int:
    try:
        return int(str(version).split(".")[0])
    except Exception:
        return 0


def verify_license(lic_str: str, machine_id: str,
                   app_version: str = "1.0",
                   app_release_date: str | None = None,
                   app_product: str | None = None) -> dict:
    """
    Trả về {"ok": bool, "why": str|None, "lic": dict|None}.
    app_release_date: 'YYYY-MM-DD' ngày phát hành bản build (để check cửa sổ update).
    app_product: mã sản phẩm hiện tại — đối chiếu với lic["product"] nếu license có gắn product.
    """
    try:
        vk = VerifyKey(bytes.fromhex(PUBLIC_KEY_HEX))
    except Exception:
        return {"ok": False, "why": "public_key_chua_cau_hinh", "lic": None}

    lic_str = lic_str.strip()
    if not _B64URL_RE.match(lic_str):
        return {"ok": False, "why": "license_hong_dinh_dang", "lic": None}
    try:
        buf = base64.urlsafe_b64decode(lic_str.encode())
    except Exception:
        return {"ok": False, "why": "license_hong_dinh_dang", "lic": None}

    if len(buf) < 65:
        return {"ok": False, "why": "license_qua_ngan", "lic": None}

    raw, sig = buf[:-64], buf[-64:]

    # 1) Chữ ký — verify TRÊN KHỐI BYTE GỐC, không dựng lại JSON
    try:
        vk.verify(raw, sig)
    except BadSignatureError:
        return {"ok": False, "why": "chu_ky_sai", "lic": None}

    # 2) Parse payload
    try:
        lic = json.loads(raw.decode("utf-8"))
    except Exception:
        return {"ok": False, "why": "payload_hong", "lic": None}

    # 3) Đúng máy
    if lic.get("machine_id") != machine_id:
        return {"ok": False, "why": "sai_may", "lic": lic}

    # 3b) Đúng sản phẩm — fail-closed: nếu app có cấu hình app_product thì license
    # PHẢI có product trùng khớp; thiếu field product không được coi là "bỏ qua check".
    if app_product and lic.get("product") != app_product:
        return {"ok": False, "why": "sai_san_pham", "lic": lic}

    # 4) Hết hạn (trial) — bọc try/except như mọi bước khác: ngày sai định dạng
    # phải trả về lỗi có kiểm soát, không được để ValueError văng ra ngoài.
    if lic.get("expires_at"):
        try:
            expires_at = date.fromisoformat(lic["expires_at"])
        except (TypeError, ValueError):
            return {"ok": False, "why": "license_hong_dinh_dang", "lic": lic}
        if expires_at < date.today():
            return {"ok": False, "why": "het_han", "lic": lic}

    # 5) Quyền version — so theo NGÀY PHÁT HÀNH build, không theo hôm nay
    if lic.get("max_major") is not None and _major(app_version) > lic["max_major"]:
        return {"ok": False, "why": "can_nang_cap_license", "lic": lic}
    if lic.get("update_until") and app_release_date:
        try:
            release_date = datetime.fromisoformat(app_release_date).date()
            update_until = date.fromisoformat(lic["update_until"])
        except (TypeError, ValueError):
            return {"ok": False, "why": "license_hong_dinh_dang", "lic": lic}
        if release_date > update_until:
            return {"ok": False, "why": "can_gia_han_de_dung_ban_moi", "lic": lic}

    return {"ok": True, "why": None, "lic": lic}
