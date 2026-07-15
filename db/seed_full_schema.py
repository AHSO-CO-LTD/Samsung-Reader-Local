"""
Sinh dữ liệu mẫu cho các bảng CHƯA được đồng bộ thật (local_scan_records,
sync_batches, command_inbox demo, local_notifications, api_request_logs,
app_event_logs) — dữ liệu TỰ BỊA (mock), không phải dữ liệu đã từng gọi
server thật.

profile_cache/profile_led_code_cache/vendor_cache/machine_cache/
server_settings_cache giờ là dữ liệu THẬT (đồng bộ qua GET /api/machines/config
— xem db/local_db.py:apply_machine_config) nên KHÔNG còn bị TRUNCATE ở đây —
script chỉ ĐẢM BẢO 4 profile mẫu (_MOCK_MAPPINGS) tồn tại (ON CONFLICT DO
NOTHING) để phần sinh local_scan_records mẫu bên dưới có profile_id hợp lệ để
tham chiếu, không ghi đè config thật nếu máy đã từng đồng bộ với server.

Luôn TRUNCATE các bảng còn lại trước khi sinh lại — chạy lại bao nhiêu lần
cũng ra kết quả giống nhau (trừ 5 bảng cache nói trên).

Cách dùng (chạy từ thư mục gốc project, dạng module vì import absolute):
    python -m db.seed_full_schema
"""

import json
import uuid
from datetime import datetime, timedelta

from data.duplicate_key import compute_duplicate_key
from db.local_db import get_connection, init_schema
from machine.hardware_id import get_hardware_id

MACHINE_CODE = "LOCAL01"

# Copy từ data/mapping_store.py trước khi module đó chuyển sang đọc DB thật
# (Bước 4: GET /api/machines/config) — script này không thể phụ thuộc vòng
# vào load_mappings() nữa vì hàm đó giờ đọc chính bảng profile_cache mà
# script cần đảm bảo tồn tại trước.
_MOCK_MAPPINGS = [
    {
        "profile_id": 1,
        "chassis_rear": "BN96-58285A",
        "led1": "BN96-60376A",
        "led2": "BN96-60377A",
        "length_led": 22,
        "length_bottom": 35,
        "no_led": 16,
        "no_bottom": 18,
        "factory_code": "DZLV",
    },
    {
        "profile_id": 2,
        "chassis_rear": "BN96-60875C",
        "led1": "BN96-60374A",
        "led2": "",
        "length_led": 22,
        "length_bottom": 35,
        "no_led": 16,
        "no_bottom": 18,
        "factory_code": "DZLV",
    },
    {
        "profile_id": 3,
        "chassis_rear": "BN96-58578A",
        "led1": "BN96-58291A",
        "led2": "BN96-58289A",
        "length_led": 22,
        "length_bottom": 35,
        "no_led": 16,
        "no_bottom": 18,
        "factory_code": "DZLV",
    },
    {
        "profile_id": 4,
        "chassis_rear": "BN96-60877C",
        "led1": "BN96-60376A",
        "led2": "BN96-60377A",
        "length_led": 22,
        "length_bottom": 35,
        "no_led": 16,
        "no_bottom": 18,
        "factory_code": "DZLV",
    },
]


def _strip_prefix(code_full):
    """'BN96-60376A' -> '60376A' (đúng ví dụ code_input trong doc 10)."""
    return code_full.split("-", 1)[1] if "-" in code_full else code_full


def _build_full_code(chassis_rear, vendor_char, led_suffix6, after_factory):
    prefix = "VN39"
    chassis_segment = chassis_rear.replace("-", "")
    before_vendor = "1A1"
    factory_code = "DZLV"
    return prefix + chassis_segment + before_vendor + vendor_char + led_suffix6 + factory_code + after_factory


def main():
    init_schema()
    hw = get_hardware_id()
    machine_serial = hw["machine_guid"] or "SN-DEV-UNKNOWN"
    machine_uid = hw["bios_uuid"] or "UID-DEV-UNKNOWN"

    mappings = _MOCK_MAPPINGS

    now = datetime.now()
    yesterday_9am = (now - timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    today_9am = now.replace(hour=9, minute=0, second=0, microsecond=0)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Xoá sạch toàn bộ để sinh lại nhất quán (thứ tự theo FK con -> cha).
            # KHÔNG truncate profile_led_code_cache/profile_cache/vendor_cache/
            # machine_cache/server_settings_cache — giờ là dữ liệu THẬT đồng bộ
            # từ server (xem apply_machine_config), truncate sẽ xoá mất.
            cur.execute("""
                TRUNCATE
                    api_request_logs, app_event_logs, local_notifications,
                    sync_batch_items, sync_batches, command_inbox,
                    local_duplicate_keys, local_scan_led_items, local_scan_records,
                    local_app_settings, id_counters
            """)

            # ---------- local_app_settings (singleton, id=1) ----------
            cur.execute(
                """
                INSERT INTO local_app_settings (
                    id, server_host, api_port, machine_code, machine_serial, machine_uid,
                    machine_license_key, registration_status, active_profile_id,
                    app_version, local_db_version, duplicate_scope, server_online,
                    local_runtime_status, local_status_message, last_health_at
                ) VALUES (
                    1, '127.0.0.1', 3979, %s, %s, %s,
                    %s, 'NOT_REQUESTED', 1,
                    '1.0.0', '20260713.001', 'DAY', false,
                    'READY', 'Not connected to server yet - running in local-only mode.', NULL
                )
                """,
                (MACHINE_CODE, machine_serial, machine_uid, f"{machine_serial}|{machine_uid}"),
            )

            # ---------- server_settings_cache (singleton, id=1) ----------
            # ON CONFLICT DO NOTHING — nếu máy đã từng đồng bộ config thật
            # (apply_machine_config), giữ nguyên dữ liệu thật, không ghi đè.
            cur.execute(
                """
                INSERT INTO server_settings_cache (
                    id, factory_code_default, full_code_length_default, full_vendor_position_default,
                    led_scan_length_default, led_vendor_position_default, duplicate_days,
                    heartbeat_timeout_seconds, raw_json, synced_at
                ) VALUES (
                    1, 'DZLV', 35, 18, 22, 16, 30, 60, %s, NULL
                )
                ON CONFLICT (id) DO NOTHING
                """,
                (json.dumps({"note": "gia tri mac dinh local tu dat, chua tung sync tu server"}),),
            )

            # ---------- machine_cache ----------
            cur.execute(
                """
                INSERT INTO machine_cache (
                    machine_code, server_machine_id, machine_name, serial, uid,
                    line_name, station_name, ip_address, is_active, synced_at
                ) VALUES (
                    %s, NULL, 'LED/QR Scanner - Line A', %s, %s,
                    'LINE-A', 'ST-01', '127.0.0.1', true, NULL
                )
                ON CONFLICT (machine_code) DO NOTHING
                """,
                (MACHINE_CODE, machine_serial, machine_uid),
            )

            # ---------- vendor_cache ----------
            # Vendor không còn cố định trong profile (docs/11(2).md) — local lấy
            # ký tự vendor từ mã quét được rồi tra bảng này. Mock 1 vendor "L"
            # khớp với toàn bộ dữ liệu test hiện có.
            cur.execute(
                """
                INSERT INTO vendor_cache (vendor_id, vendor_name, vendor_char, status, synced_at)
                VALUES (1, 'Default LED Vendor', 'L', 'ACTIVE', NULL)
                ON CONFLICT (vendor_char) DO NOTHING
                """
            )

            # ---------- profile_cache + profile_led_code_cache ----------
            # ON CONFLICT DO NOTHING — chỉ đảm bảo 4 profile mẫu TỒN TẠI (để
            # phần sinh local_scan_records bên dưới có profile_id hợp lệ), KHÔNG
            # ghi đè nếu profile_id đó đã có dữ liệu thật từ config sync.
            for entry in mappings:
                profile_id = entry["profile_id"]
                chassis_full = entry["chassis_rear"]
                cur.execute(
                    """
                    INSERT INTO profile_cache (
                        profile_id, version, chassis_code_full, chassis_code_input,
                        factory_code, full_code_length, full_vendor_position,
                        led_scan_length, led_vendor_position, is_active, synced_at
                    ) VALUES (
                        %s, 1, %s, %s, %s, %s, %s, %s, %s, true, NULL
                    )
                    ON CONFLICT (profile_id) DO NOTHING
                    """,
                    (
                        profile_id, chassis_full, _strip_prefix(chassis_full),
                        entry["factory_code"], entry["length_bottom"], entry["no_bottom"],
                        entry["length_led"], entry["no_led"],
                    ),
                )
                for slot, led_key in ((1, "led1"), (2, "led2")):
                    code_full = entry.get(led_key)
                    if not code_full:
                        continue
                    cur.execute(
                        """
                        INSERT INTO profile_led_code_cache (
                            profile_id, led_slot, code_full, code_input, suffix_check, is_required, is_active
                        ) VALUES (%s, %s, %s, %s, %s, true, true)
                        ON CONFLICT (profile_id, led_slot) DO NOTHING
                        """,
                        (profile_id, slot, code_full, _strip_prefix(code_full), code_full[-5:]),
                    )

            # ---------- local_scan_records + local_scan_led_items ----------
            # profile 1 (BN96-58285A, led1+led2) dùng cho đa số scan; xen thêm
            # vài dòng profile 3 (BN96-58578A) để thấy dữ liệu nhiều profile.
            profile1 = mappings[0]
            profile3 = mappings[2]

            def _insert_scan(seq, day_base, profile, after_factory, local_status, ng_reason,
                              server_status, sync_status, final_status, is_synced):
                scan_id = f"{MACHINE_CODE}-{day_base:%Y%m%d}-{seq:06d}"
                chassis_full = profile["chassis_rear"]
                vendor_char = "L"
                led1_suffix6 = profile["led1"][-6:] if len(profile["led1"]) >= 6 else profile["led1"]
                full_code_raw = _build_full_code(chassis_full, vendor_char, led1_suffix6, after_factory)
                full_prefix = full_code_raw[0:4]
                full_chassis_segment = full_code_raw[4:14]
                full_before_vendor = full_code_raw[14:17]
                full_led_code_raw = full_code_raw[18:24]
                full_factory_code = full_code_raw[24:28]
                full_after_factory = full_code_raw[28:]
                duplicate_key = compute_duplicate_key(full_code_raw)
                scan_at = day_base + timedelta(minutes=seq * 6)

                full_code_json = {
                    "raw": full_code_raw, "prefix": full_prefix, "chassis_code": chassis_full,
                    "before_vendor": full_before_vendor, "vendor_char": vendor_char,
                    "led_code": profile["led1"], "factory_code": full_factory_code,
                    "after_factory": full_after_factory,
                }
                led_scans_json = [{
                    "slot": 1, "index": 1, "raw": f"ZB36L582465U528LD{led1_suffix6}",
                    "lot_no": "528", "vendor_char": vendor_char, "suffix": led1_suffix6[-5:],
                    "status": "OK", "ng_reason": None,
                }]

                server_code = {"OK": "SERVER_OK", "NG": "SERVER_DUPLICATE", None: None}.get(
                    "OK" if server_status == "OK" else "NG" if server_status == "NG" else None
                ) if is_synced else None
                server_scan_id = 1000 + seq if is_synced else None

                # chassis_scan_raw = chassis rear operator đang chọn ở comboBoxChassisRear
                # tại thời điểm scan — field guide ghi "insert ngay khi có scan", nên set
                # ngay bằng dữ liệu chassis đang có, dù không phải quét bằng reader riêng.
                cur.execute(
                    """
                    INSERT INTO local_scan_records (
                        local_scan_id, machine_code, profile_id, profile_version, duplicate_key,
                        full_code_raw, full_prefix, full_chassis_segment, full_chassis_code,
                        full_before_vendor, full_vendor_char, full_led_code, full_factory_code,
                        full_after_factory, chassis_scan_raw, full_code_json, led_scans_json,
                        local_status, local_ng_reason,
                        server_code, server_scan_id, server_status,
                        final_status, sync_status, last_sync_at, scan_at
                    ) VALUES (
                        %s, %s, %s, 1, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s
                    )
                    """,
                    (
                        scan_id, MACHINE_CODE, profile["profile_id"], duplicate_key,
                        full_code_raw, full_prefix, full_chassis_segment, chassis_full,
                        full_before_vendor, vendor_char, profile["led1"], full_factory_code,
                        full_after_factory, chassis_full, json.dumps(full_code_json), json.dumps(led_scans_json),
                        local_status, ng_reason,
                        server_code, server_scan_id, server_status,
                        final_status, sync_status, (scan_at if is_synced else None), scan_at,
                    ),
                )
                if local_status == "OK":
                    cur.execute(
                        """
                        INSERT INTO local_scan_led_items (
                            scan_id, local_scan_id, led_slot, led_index, led_scan_raw,
                            led_lot_no, vendor_char, led_suffix, local_status
                        )
                        SELECT id, local_scan_id, 1, 1, %s, '528', %s, %s, 'OK'
                        FROM local_scan_records WHERE local_scan_id = %s
                        """,
                        (f"ZB36L582465U528LD{led1_suffix6}", vendor_char, led1_suffix6[-5:], scan_id),
                    )
                return scan_id, duplicate_key, full_code_raw, scan_at

            scans = []
            seq = 1
            # Hôm qua: 4 scan OK đã "sync xong" (minh hoạ trạng thái sau khi có server).
            for after_factory in ["Y420001", "Y420002", "Y420003", "Y420004"]:
                info = _insert_scan(
                    seq, yesterday_9am, profile1, after_factory,
                    "OK", None, "OK", "SYNCED", "OK", is_synced=True,
                )
                scans.append(info + ("yesterday_ok_synced",))
                seq += 1

            # Hôm nay: 1 mã lặp lại hôm qua (Y420001) -> local NG do trùng.
            info = _insert_scan(
                seq, today_9am, profile1, "Y420001",
                "NG", "LOCAL_DUPLICATE", "SKIPPED", "SYNCED", "NG", is_synced=True,
            )
            scans.append(info + ("today_duplicate",))
            seq += 1

            # Hôm nay: 2 mã mới, local OK, ĐANG CHỜ sync (đúng thực tế hiện giờ).
            for after_factory in ["Y420005", "Y420006"]:
                info = _insert_scan(
                    seq, today_9am, profile1, after_factory,
                    "OK", None, "PENDING", "PENDING", "PENDING_SERVER", is_synced=False,
                )
                scans.append(info + ("today_pending",))
                seq += 1

            # Hôm nay: 1 mã lỗi mạng lúc submit -> FAILED_RETRYABLE (minh hoạ mất mạng).
            info = _insert_scan(
                seq, today_9am, profile1, "Y420007",
                "OK", None, "PENDING", "FAILED_RETRYABLE", "PENDING_SERVER", is_synced=False,
            )
            cur.execute(
                """
                UPDATE local_scan_records
                SET sync_attempt_count = 2, next_retry_at = now() + interval '30 seconds',
                    last_error_code = 'SERVER_DISCONNECTED', last_error_message = 'Cannot connect to server API'
                WHERE local_scan_id = %s
                """,
                (info[0],),
            )
            scans.append(info + ("today_failed_retryable",))
            seq += 1

            # Hôm nay: 1 mã dùng profile khác (profile 3) để thấy đa profile.
            info = _insert_scan(
                seq, today_9am, profile3, "Y430001",
                "OK", None, "PENDING", "PENDING", "PENDING_SERVER", is_synced=False,
            )
            scans.append(info + ("today_profile3",))
            seq += 1

            # ---------- local_duplicate_keys ----------
            # 1 dòng cho mỗi (profile_id, duplicate_key) lần đầu gặp — theo
            # đúng lần scan OK đầu tiên (không tạo cho scan bị trùng NG).
            first_seen = {}
            for scan_id, dup_key, _full_code, scan_at, tag in scans:
                if tag == "today_duplicate":
                    continue
                profile_id = profile1["profile_id"] if "profile3" not in tag else profile3["profile_id"]
                key = (profile_id, dup_key)
                if key not in first_seen:
                    first_seen[key] = (scan_id, scan_at)
            for (profile_id, dup_key), (scan_id, scan_at) in first_seen.items():
                cur.execute(
                    """
                    INSERT INTO local_duplicate_keys
                        (profile_id, duplicate_key, scope_key, first_local_scan_id, first_scan_at, machine_code)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (profile_id, dup_key, scan_at.strftime("%Y%m%d"), scan_id, scan_at, MACHINE_CODE),
                )

            # ---------- sync_batches + sync_batch_items ----------
            synced_scan_ids = [s[0] for s in scans if s[4] in ("yesterday_ok_synced", "today_duplicate")]
            cur.execute(
                """
                INSERT INTO sync_batches (
                    batch_code, trigger_type, total_sent, total_ok, total_ng, total_failed,
                    status, summary_json, started_at, finished_at
                ) VALUES (
                    %s, 'STARTUP', %s, %s, %s, 0, 'DONE', %s, %s, %s
                )
                """,
                (
                    f"{MACHINE_CODE}-{yesterday_9am:%Y%m%d}-STARTUP-0001", len(synced_scan_ids),
                    len(synced_scan_ids) - 1, 1,
                    json.dumps({"local_pending_before_batch": len(synced_scan_ids)}),
                    yesterday_9am, yesterday_9am + timedelta(seconds=2),
                ),
            )
            cur.execute("SELECT id FROM sync_batches WHERE batch_code = %s",
                        (f"{MACHINE_CODE}-{yesterday_9am:%Y%m%d}-STARTUP-0001",))
            batch_id = cur.fetchone()[0]
            for scan_id in synced_scan_ids:
                cur.execute(
                    """
                    INSERT INTO sync_batch_items (batch_id, local_scan_id, result_success, result_code, final_status)
                    VALUES (%s, %s, true, 'SERVER_OK', 'OK')
                    """,
                    (batch_id, scan_id),
                )

            # ---------- command_inbox ----------
            cur.execute(
                """
                INSERT INTO command_inbox (
                    server_command_id, machine_code, command_type, payload_json,
                    local_status, ack_status, received_at, finished_at, ack_sent_at
                ) VALUES
                    (101, %s, 'SYNC_PROFILE', %s, 'ACKED', 'ACK', %s, %s, %s),
                    (102, %s, 'SHOW_MESSAGE', %s, 'ACKED', 'ACK', %s, %s, %s),
                    (103, %s, 'RELOAD_CONFIG', %s, 'PENDING', NULL, %s, NULL, NULL)
                """,
                (
                    MACHINE_CODE, json.dumps({"reason": "Profile updated by engineer"}),
                    yesterday_9am, yesterday_9am, yesterday_9am,
                    MACHINE_CODE, json.dumps({"message": "Nhac kiem tra den bao LED tram 01"}),
                    today_9am, today_9am, today_9am,
                    MACHINE_CODE, json.dumps({"reason": "Chua thuc su xay ra, minh hoa PENDING"}),
                    today_9am,
                ),
            )

            # ---------- local_notifications ----------
            duplicate_scan_id = next(s[0] for s in scans if s[4] == "today_duplicate")
            cur.execute(
                """
                INSERT INTO local_notifications (
                    noti_code, severity, title, message, status, source, related_local_scan_id, created_at
                ) VALUES
                    ('LOCAL_DUPLICATE_DETECTED', 'WARNING', 'Phat hien ma trung',
                     'Ma QRCODE BOTTOM trung voi ban ghi da quet truoc do trong ngay.',
                     'NEW', 'LOCAL', %s, %s),
                    ('SYNC_BATCH_DONE', 'INFO', 'Dong bo thanh cong',
                     'Batch STARTUP da gui xong len server (mo phong).', 'READ', 'LOCAL', NULL, %s),
                    ('SERVER_OFFLINE', 'ERROR', 'Mat ket noi server',
                     'Khong goi duoc GET /api/health, du lieu se luu pending.', 'NEW', 'LOCAL', NULL, %s)
                """,
                (duplicate_scan_id, today_9am, yesterday_9am, today_9am),
            )

            # ---------- api_request_logs ----------
            cur.execute(
                """
                INSERT INTO api_request_logs (
                    request_type, method, url, local_scan_id, response_status_code,
                    result_code, success, duration_ms, created_at
                ) VALUES
                    ('HEALTH', 'GET', 'http://127.0.0.1:3979/api/health', NULL, 200, 'HEALTH_OK', true, 35, %s),
                    ('SCAN_SUBMIT', 'POST', 'http://127.0.0.1:3979/api/scans/submit', %s, 200, 'SERVER_OK', true, 120, %s),
                    ('HEALTH', 'GET', 'http://127.0.0.1:3979/api/health', NULL, NULL, NULL, false, 5000, %s)
                """,
                (yesterday_9am, synced_scan_ids[0], yesterday_9am, today_9am),
            )

            # ---------- app_event_logs ----------
            cur.execute(
                """
                INSERT INTO app_event_logs (level, event_code, message, payload_json, created_at)
                VALUES
                    ('INFO', 'APP_STARTED', 'Reader Monitor da khoi dong.', %s, %s),
                    ('INFO', 'HARDWARE_ID_DETECTED', 'Da doc duoc hardware id cua may local.', %s, %s),
                    ('WARNING', 'LOCAL_DUPLICATE', 'Phat hien 1 ma QRCODE BOTTOM trung trong ngay.', %s, %s)
                """,
                (
                    json.dumps({}), yesterday_9am,
                    json.dumps({
                        "machine_guid": hw["machine_guid"],
                        "bios_uuid": hw["bios_uuid"],
                        "motherboard_serial": hw["motherboard_serial"],
                    }), yesterday_9am,
                    json.dumps({"local_scan_id": duplicate_scan_id}), today_9am,
                ),
            )

        conn.commit()
    finally:
        conn.close()

    print("Da sinh du lieu mau cho du 16 bang.")
    print(f"machine_serial (MachineGuid)                     = {machine_serial}")
    print(f"machine_uid (that, tu machine/hardware_id.py)    = {machine_uid}")


if __name__ == "__main__":
    main()
