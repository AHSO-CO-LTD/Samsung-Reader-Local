"""
Định danh máy local để gửi server (serial/uid).
Tách khỏi hardware_id.py: hardware_id.py chỉ lo đọc phần cứng thô, còn ở đây
lo đồng bộ giá trị đó vào local_app_settings (để không phải đọc lại phần
cứng mỗi lần).
"""

from db.local_db import get_app_settings, update_app_settings
from machine.hardware_id import get_hardware_id


def ensure_machine_identity():
    """Đảm bảo local_app_settings.machine_serial/machine_uid đã có giá trị.
    Nếu đã có sẵn (từ lần chạy trước) thì giữ nguyên, không đọc lại phần
    cứng. Nếu chưa có, tính qua get_hardware_id() (motherboard_serial ->
    serial, bios_uuid -> uid) rồi lưu lại.

    Trả về (serial, uid) hiện tại — có thể là (None, None) nếu mainboard
    không đọc được ID thật; nơi gọi (dialog đăng ký) tự quyết định chặn nút
    gửi khi gặp trường hợp này, không tự sinh ID giả để thay thế."""
    settings = get_app_settings()
    serial = settings.get("machine_serial")
    uid = settings.get("machine_uid")
    if serial and uid:
        return serial, uid

    info = get_hardware_id()
    new_serial = serial or info.get("motherboard_serial")
    new_uid = uid or info.get("bios_uuid")
    if new_serial != serial or new_uid != uid:
        update_app_settings(machine_serial=new_serial, machine_uid=new_uid)
    return new_serial, new_uid
