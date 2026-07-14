# Đọc danh sách profile ĐANG ACTIVE từ profile_cache + profile_led_code_cache
# (đã đồng bộ qua GET /api/machines/config — xem db/local_db.py:apply_machine_config).
# Giữ NGUYÊN cấu trúc dict trả về như bản mock cũ (profile_id, chassis_rear,
# led1, led2, length_led, length_bottom, no_led, no_bottom, factory_code) để
# ui/main_window.py không cần sửa gì.

from db.local_db import get_connection


def load_mappings():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT profile_id, chassis_code_full, factory_code,
                       full_code_length, full_vendor_position,
                       led_scan_length, led_vendor_position
                FROM profile_cache WHERE is_active = true ORDER BY profile_id
                """
            )
            profile_rows = cur.fetchall()

            cur.execute(
                """
                SELECT profile_id, led_slot, code_full
                FROM profile_led_code_cache
                WHERE is_active = true ORDER BY profile_id, led_slot
                """
            )
            led_rows = cur.fetchall()
    finally:
        conn.close()

    led_by_profile = {}
    for profile_id, led_slot, code_full in led_rows:
        led_by_profile.setdefault(profile_id, {})[led_slot] = code_full

    return [
        {
            "profile_id": profile_id,
            "chassis_rear": chassis_code_full,
            "led1": led_by_profile.get(profile_id, {}).get(1, ""),
            "led2": led_by_profile.get(profile_id, {}).get(2, ""),
            "length_led": led_scan_length,
            "length_bottom": full_code_length,
            "no_led": led_vendor_position,
            "no_bottom": full_vendor_position,
            "factory_code": factory_code,
        }
        for profile_id, chassis_code_full, factory_code, full_code_length,
            full_vendor_position, led_scan_length, led_vendor_position in profile_rows
    ]
