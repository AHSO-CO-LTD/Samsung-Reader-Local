"""
Kết nối PostgreSQL local + kiểm tra mã QRCODE BOTTOM độc nhất trong nhiều
ngày gần nhất (theo docs/11-sql-khoi-tao-db-may-local-python-postgres.md).

Schema đầy đủ 16 bảng (db/schema.sql). Cấu hình kết nối đọc từ
db/local_db_config.json.
"""

import json
import os
import uuid
from datetime import datetime, timedelta

import psycopg

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_db_config.json")
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")

# Số ngày lùi lại (ngoài hôm nay) khi kiểm tra độc nhất. 0 = chỉ hôm nay,
# 1 = hôm qua + hôm nay, 2 = 3 ngày gần nhất, ...
DUPLICATE_WINDOW_DAYS = 1

_config = None


def _load_config():
    global _config
    if _config is None:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            _config = json.load(f)
    return _config


def get_connection():
    cfg = _load_config()
    return psycopg.connect(
        host=cfg["host"],
        port=cfg["port"],
        dbname=cfg["dbname"],
        user=cfg["user"],
        password=cfg["password"],
        options=f"-c search_path={cfg['schema']},public",
    )


def init_schema():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    conn = get_connection()
    try:
        conn.execute(schema_sql)
        conn.commit()
    finally:
        conn.close()


def new_local_scan_id():
    return f"LOCAL-{datetime.now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}"


def get_app_settings():
    """Đọc toàn bộ local_app_settings (singleton, id=1), trả về dict theo tên cột."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM local_app_settings WHERE id = 1")
            row = cur.fetchone()
            columns = [desc[0] for desc in cur.description]
    finally:
        conn.close()
    return dict(zip(columns, row)) if row else {}


def update_app_settings(**fields):
    """Cập nhật local_app_settings (singleton, id=1) — chỉ set các cột được
    truyền vào qua keyword argument, ví dụ update_app_settings(server_online=True)."""
    if not fields:
        return
    columns = list(fields.keys())
    set_clause = ", ".join(f"{col} = %s" for col in columns)
    values = [fields[col] for col in columns]
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE local_app_settings SET {set_clause} WHERE id = 1", values)
        conn.commit()
    finally:
        conn.close()


def log_api_request(
    request_type, method, url, request_json=None, response_status_code=None,
    response_json=None, result_code=None, success=False, error_message=None,
    duration_ms=None, local_scan_id=None, batch_code=None, command_inbox_id=None,
):
    """Ghi 1 dòng vào api_request_logs — theo docs/10-huong-dan-api-may-local-
    python: local nên ghi lại MỌI lần gọi API lên server để tiện tra cứu/debug
    sau này. Gọi tại 1 điểm duy nhất (server/api_client.py._request) nên áp
    dụng tự động cho mọi endpoint, không cần thêm lại ở từng nơi gọi."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO api_request_logs (
                    request_type, method, url, local_scan_id, batch_code, command_inbox_id,
                    request_json, response_status_code, response_json, result_code,
                    success, error_message, duration_ms
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    request_type, method, url, local_scan_id, batch_code, command_inbox_id,
                    json.dumps(request_json) if request_json is not None else None,
                    response_status_code,
                    json.dumps(response_json) if response_json is not None else None,
                    result_code, success, error_message, duration_ms,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def add_local_notification(
    noti_code, severity, title, message, source="LOCAL",
    related_local_scan_id=None, related_batch_code=None, related_server_command_id=None,
    payload_json=None,
):
    """Ghi 1 dòng vào local_notifications (bảng cảnh báo cho màn hình local,
    theo docs/10-huong-dan-api-may-local-python mục 18)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO local_notifications (
                    noti_code, severity, title, message, source,
                    related_local_scan_id, related_batch_code, related_server_command_id,
                    payload_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    noti_code, severity, title, message, source,
                    related_local_scan_id, related_batch_code, related_server_command_id,
                    json.dumps(payload_json) if payload_json is not None else "{}",
                ),
            )
        conn.commit()
    finally:
        conn.close()


def apply_machine_config(data, serial, uid):
    """Ghi cache từ 1 response GET /api/machines/config (data.machine/settings/
    profiles/vendors/pending_commands) — coi server là nguồn chân lý.

    machine_cache/server_settings_cache: UPSERT 1 dòng (singleton/theo
    machine_code). profile_cache/profile_led_code_cache: UPSERT theo
    profile_id/(profile_id, led_slot) + soft-delete (is_active=false) cho
    dòng KHÔNG còn trong response — KHÔNG DELETE thật vì
    local_scan_records.profile_id có FK ON DELETE RESTRICT tới profile_cache,
    xoá thật sẽ vi phạm FK nếu profile đó đã từng có scan. vendor_cache:
    UPSERT theo vendor_char. command_inbox: chỉ INSERT command MỚI (ON
    CONFLICT DO NOTHING) — không đụng ack/local_status cục bộ của command đã
    có; xử lý/ack thật sự là việc của bước commands/poll sau."""
    machine = data.get("machine") or {}
    settings = data.get("settings") or {}
    profiles = data.get("profiles") or []
    vendors = data.get("vendors") or []
    pending_commands = data.get("pending_commands") or []
    now = datetime.now().astimezone()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO machine_cache (
                    machine_code, server_machine_id, machine_name, serial, uid,
                    line_name, station_name, ip_address, is_active, raw_json, synced_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (machine_code) DO UPDATE SET
                    server_machine_id = EXCLUDED.server_machine_id,
                    machine_name = EXCLUDED.machine_name,
                    serial = EXCLUDED.serial, uid = EXCLUDED.uid,
                    line_name = EXCLUDED.line_name, station_name = EXCLUDED.station_name,
                    ip_address = EXCLUDED.ip_address, is_active = EXCLUDED.is_active,
                    raw_json = EXCLUDED.raw_json, synced_at = EXCLUDED.synced_at,
                    updated_at = now()
                """,
                (
                    machine.get("machine_code"), machine.get("id"), machine.get("machine_name"),
                    serial, uid, machine.get("line_name"), machine.get("station_name"),
                    machine.get("ip_address"), machine.get("is_active", True),
                    json.dumps(machine), now,
                ),
            )

            cur.execute(
                """
                INSERT INTO server_settings_cache (
                    id, factory_code_default, full_code_length_default, full_vendor_position_default,
                    led_scan_length_default, led_vendor_position_default, duplicate_days,
                    heartbeat_timeout_seconds, raw_json, synced_at
                ) VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    factory_code_default = EXCLUDED.factory_code_default,
                    full_code_length_default = EXCLUDED.full_code_length_default,
                    full_vendor_position_default = EXCLUDED.full_vendor_position_default,
                    led_scan_length_default = EXCLUDED.led_scan_length_default,
                    led_vendor_position_default = EXCLUDED.led_vendor_position_default,
                    duplicate_days = EXCLUDED.duplicate_days,
                    heartbeat_timeout_seconds = EXCLUDED.heartbeat_timeout_seconds,
                    raw_json = EXCLUDED.raw_json, synced_at = EXCLUDED.synced_at,
                    updated_at = now()
                """,
                (
                    settings.get("factory_code_default"), settings.get("full_code_length_default"),
                    settings.get("full_vendor_position_default"), settings.get("led_scan_length_default"),
                    settings.get("led_vendor_position_default"), settings.get("duplicate_days"),
                    settings.get("heartbeat_timeout_seconds"), json.dumps(settings), now,
                ),
            )

            seen_profile_ids = []
            for p in profiles:
                profile_id = p.get("id")
                seen_profile_ids.append(profile_id)
                chassis = p.get("chassis_code") or {}
                cur.execute(
                    """
                    INSERT INTO profile_cache (
                        profile_id, version, chassis_code_id, chassis_code_full, chassis_code_input,
                        factory_code, full_code_length, full_vendor_position,
                        led_scan_length, led_vendor_position, is_active, raw_json, synced_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (profile_id) DO UPDATE SET
                        version = EXCLUDED.version, chassis_code_id = EXCLUDED.chassis_code_id,
                        chassis_code_full = EXCLUDED.chassis_code_full,
                        chassis_code_input = EXCLUDED.chassis_code_input,
                        factory_code = EXCLUDED.factory_code, full_code_length = EXCLUDED.full_code_length,
                        full_vendor_position = EXCLUDED.full_vendor_position,
                        led_scan_length = EXCLUDED.led_scan_length,
                        led_vendor_position = EXCLUDED.led_vendor_position,
                        is_active = EXCLUDED.is_active, raw_json = EXCLUDED.raw_json,
                        synced_at = EXCLUDED.synced_at, updated_at = now()
                    """,
                    (
                        profile_id, p.get("version"), p.get("chassis_code_id"),
                        chassis.get("code_full"), chassis.get("code_input"),
                        p.get("factory_code"), p.get("full_code_length"), p.get("full_vendor_position"),
                        p.get("led_scan_length"), p.get("led_vendor_position"),
                        p.get("is_active", True), json.dumps(p), now,
                    ),
                )

                seen_slots = []
                for plc in (p.get("profile_led_codes") or []):
                    led_slot = plc.get("led_slot")
                    seen_slots.append(led_slot)
                    led_code = plc.get("led_code") or {}
                    cur.execute(
                        """
                        INSERT INTO profile_led_code_cache (
                            profile_id, led_slot, led_code_id, code_full, code_input,
                            suffix_check, is_required, is_active, raw_json, synced_at
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (profile_id, led_slot) DO UPDATE SET
                            led_code_id = EXCLUDED.led_code_id, code_full = EXCLUDED.code_full,
                            code_input = EXCLUDED.code_input, suffix_check = EXCLUDED.suffix_check,
                            is_required = EXCLUDED.is_required, is_active = EXCLUDED.is_active,
                            raw_json = EXCLUDED.raw_json, synced_at = EXCLUDED.synced_at,
                            updated_at = now()
                        """,
                        (
                            profile_id, led_slot, led_code.get("id"), led_code.get("code_full"),
                            led_code.get("code_input"), led_code.get("suffix_check"),
                            plc.get("is_required", True), led_code.get("is_active", True),
                            json.dumps(plc), now,
                        ),
                    )

                if seen_slots:
                    cur.execute(
                        """
                        UPDATE profile_led_code_cache SET is_active = false, updated_at = now()
                        WHERE profile_id = %s AND NOT (led_slot = ANY(%s))
                        """,
                        (profile_id, seen_slots),
                    )
                else:
                    cur.execute(
                        "UPDATE profile_led_code_cache SET is_active = false, updated_at = now() WHERE profile_id = %s",
                        (profile_id,),
                    )

            if seen_profile_ids:
                cur.execute(
                    "UPDATE profile_cache SET is_active = false, updated_at = now() WHERE NOT (profile_id = ANY(%s))",
                    (seen_profile_ids,),
                )
            else:
                cur.execute("UPDATE profile_cache SET is_active = false, updated_at = now()")

            for v in vendors:
                cur.execute(
                    """
                    INSERT INTO vendor_cache (vendor_id, vendor_name, vendor_char, status, raw_json, synced_at)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (vendor_char) DO UPDATE SET
                        vendor_id = EXCLUDED.vendor_id, vendor_name = EXCLUDED.vendor_name,
                        status = EXCLUDED.status, raw_json = EXCLUDED.raw_json,
                        synced_at = EXCLUDED.synced_at, updated_at = now()
                    """,
                    (v.get("id"), v.get("vendor_name"), v.get("vendor_char"), v.get("status"),
                     json.dumps(v), now),
                )

            for c in pending_commands:
                cur.execute(
                    """
                    INSERT INTO command_inbox (
                        server_command_id, machine_code, command_type, payload_json,
                        local_status, received_at
                    ) VALUES (%s, %s, %s, %s, 'PENDING', %s)
                    ON CONFLICT (server_command_id) DO NOTHING
                    """,
                    (
                        c.get("id"), machine.get("machine_code"), c.get("command_type"),
                        json.dumps(c.get("payload_json") or {}), now,
                    ),
                )
        conn.commit()
    finally:
        conn.close()


def get_server_settings():
    """Đọc server_settings_cache (singleton, id=1) — đã sync qua GET /api/
    machines/config (xem apply_machine_config), trả về dict theo tên cột."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM server_settings_cache WHERE id = 1")
            row = cur.fetchone()
            columns = [desc[0] for desc in cur.description]
    finally:
        conn.close()
    return dict(zip(columns, row)) if row else {}


def get_scan_counts():
    """Đếm local_scan_records cho heartbeat — TOÀN BỘ (không giới hạn hôm
    nay, đúng nghĩa "Tổng dữ liệu local đang có" của doc). pending_sync đếm
    sync_status IN ('PENDING','FAILED_RETRYABLE') — khớp định nghĩa
    v_pending_sync_scans/idx_local_scan_records_pending_sync đã có sẵn trong
    schema (không tính SYNCING — đang gửi dở, không phải đang chờ)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*),
                    COUNT(*) FILTER (WHERE local_status = 'OK'),
                    COUNT(*) FILTER (WHERE local_status = 'NG'),
                    COUNT(*) FILTER (WHERE sync_status IN ('PENDING', 'FAILED_RETRYABLE'))
                FROM local_scan_records
                """
            )
            total, ok, ng, pending = cur.fetchone()
    finally:
        conn.close()
    return {"total": total, "ok": ok, "ng": ng, "pending_sync": pending}


def get_command_local_status(server_command_id):
    """Đọc local_status hiện tại của 1 command đã lưu (None nếu chưa từng
    thấy) — dùng để dedupe khi commands/poll trả lại command cũ (poll không
    destructive, command chưa ack có thể xuất hiện lại nhiều lần)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT local_status FROM command_inbox WHERE server_command_id = %s",
                (server_command_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def save_command_received(server_command_id, machine_code, command_type, payload_json, server_status, raw_json):
    """Lưu/refresh 1 command vừa nhận từ commands/poll, set local_status
    'RUNNING' (bắt đầu xử lý). Chỉ gọi SAU KHI get_command_local_status() xác
    nhận command chưa ở trạng thái kết thúc (ACKED/FAILED)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO command_inbox (
                    server_command_id, machine_code, command_type, payload_json,
                    server_status, local_status, started_at, raw_json
                ) VALUES (%s, %s, %s, %s, %s, 'RUNNING', now(), %s)
                ON CONFLICT (server_command_id) DO UPDATE SET
                    payload_json = EXCLUDED.payload_json,
                    server_status = EXCLUDED.server_status,
                    local_status = 'RUNNING',
                    started_at = now(),
                    raw_json = EXCLUDED.raw_json,
                    updated_at = now()
                """,
                (
                    server_command_id, machine_code, command_type, json.dumps(payload_json),
                    server_status, json.dumps(raw_json),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def finish_command(server_command_id, local_status, ack_status=None, error_message=None):
    """Đóng 1 command sau khi SERVER đã xác nhận nhận ack (gọi từ
    _handle_command_ack_result, không gọi trước khi gửi ack — nếu lần gọi ack
    thất bại vì mạng, local_status phải giữ nguyên RUNNING để lần poll sau tự
    retry toàn bộ, an toàn hơn báo xong trong khi server chưa biết)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE command_inbox
                SET local_status = %s, ack_status = %s, error_message = %s,
                    finished_at = now(), ack_sent_at = now(), updated_at = now()
                WHERE server_command_id = %s
                """,
                (local_status, ack_status, error_message, server_command_id),
            )
        conn.commit()
    finally:
        conn.close()


def get_machine_code():
    """Đọc machine_code hiện tại từ local_app_settings (singleton, id=1).
    Trả về 'LOCAL01' nếu bảng chưa được seed (chưa chạy local_app_settings)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT machine_code FROM local_app_settings WHERE id = 1")
            row = cur.fetchone()
    finally:
        conn.close()
    return row[0] if row else "LOCAL01"


def record_full_scan(
    profile_id, qr_data, led_items, is_ok, ng_reason,
    window_days=DUPLICATE_WINDOW_DAYS, local_scan_id=None, scan_at=None,
):
    """Ghi 1 phiên quét ĐẦY ĐỦ — 1 sản phẩm = 1 dòng local_scan_records +
    nhiều dòng local_scan_led_items (mỗi item LED BAR 1/2 đã thu thập trong
    phiên). Thay cho check_and_record_scan cũ (chỉ ghi 1 tập cột tối thiểu,
    không có local_scan_led_items).

    qr_data: dict field parse từ mã QRCODE BOTTOM — full_code_raw, full_prefix,
        full_chassis_segment, full_chassis_code, full_before_vendor,
        full_vendor_char, full_led_code, full_factory_code, full_after_factory,
        chassis_scan_raw, duplicate_key.
    led_items: list[dict] — led_slot, led_index, led_scan_raw, led_lot_no,
        vendor_char, led_suffix, local_status ('OK'/'NG'), ng_reason.
    is_ok/ng_reason: kết quả tổng hợp ĐÃ TÍNH SẴN từ local parse (QR bottom +
        toàn bộ LED item). Hàm này CHỈ chạy kiểm tra trùng khi is_ok=True,
        đúng nguyên tắc "chỉ so OK với OK" — nếu is_ok=False vì lý do khác
        (sai định dạng...), không tra/không chiếm slot trong local_duplicate_keys.
    scan_at: thời điểm scan — truyền vào để nơi gọi (main_window.py) tái dùng
        ĐÚNG giá trị này khi build payload POST /api/scans/submit (idempotency
        yêu cầu không đổi scan_at giữa lần ghi local và lần submit/retry).
        Mặc định tự tính now() nếu không truyền (gọi độc lập/test).

    Trả về (final_is_ok, final_ng_reason, first_scan_at_neu_trung, local_scan_id)
    — local_scan_id trả ra để nơi gọi dùng làm khoá idempotency khi submit."""
    if local_scan_id is None:
        local_scan_id = new_local_scan_id()
    if scan_at is None:
        scan_at = datetime.now().astimezone()
    machine_code = get_machine_code()
    # Cột duplicate_key phải luôn khớp ĐÚNG giá trị đã (hoặc sẽ) gửi server
    # (qr_data["duplicate_key"], tính theo own_is_ok bên main_window.py) —
    # KHÔNG gate theo is_ok ở đây, chỉ gate is_ok cho việc có insert vào
    # local_duplicate_keys hay không (xem bên dưới). Trước đây gate nhầm
    # theo is_ok khiến cột này ra NULL cho case QR bottom hợp lệ nhưng NG vì
    # LED bar sai — lệch với payload thật đã gửi server, sẽ gây sai lệch khi
    # Bước 8 (retry/batch submit) đọc lại từ DB để gửi lại.
    duplicate_key = qr_data.get("duplicate_key")

    full_code_json = {
        "raw": qr_data.get("full_code_raw"),
        "prefix": qr_data.get("full_prefix"),
        "chassis_code": qr_data.get("full_chassis_code"),
        "before_vendor": qr_data.get("full_before_vendor"),
        "vendor_char": qr_data.get("full_vendor_char"),
        "led_code": qr_data.get("full_led_code"),
        "factory_code": qr_data.get("full_factory_code"),
        "after_factory": qr_data.get("full_after_factory"),
    }
    led_scans_json = [
        {
            "slot": item["led_slot"], "index": item["led_index"], "raw": item["led_scan_raw"],
            "lot_no": item.get("led_lot_no"), "vendor_char": item.get("vendor_char"),
            "suffix": item.get("led_suffix"), "status": item.get("local_status"),
            "ng_reason": item.get("ng_reason"),
        }
        for item in led_items
    ]

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO local_scan_records (
                    local_scan_id, machine_code, profile_id, duplicate_key,
                    full_code_raw, full_prefix, full_chassis_segment, full_chassis_code,
                    full_before_vendor, full_vendor_char, full_led_code, full_factory_code,
                    full_after_factory, chassis_scan_raw, full_code_json, led_scans_json,
                    local_status, local_ng_reason, scan_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s
                )
                ON CONFLICT (local_scan_id) DO NOTHING
                """,
                (
                    local_scan_id, machine_code, profile_id, duplicate_key,
                    qr_data.get("full_code_raw"), qr_data.get("full_prefix"),
                    qr_data.get("full_chassis_segment"), qr_data.get("full_chassis_code"),
                    qr_data.get("full_before_vendor"), qr_data.get("full_vendor_char"),
                    qr_data.get("full_led_code"), qr_data.get("full_factory_code"),
                    qr_data.get("full_after_factory"), qr_data.get("chassis_scan_raw"),
                    json.dumps(full_code_json), json.dumps(led_scans_json),
                    "OK" if is_ok else "NG", ng_reason, scan_at,
                ),
            )

            for item in led_items:
                cur.execute(
                    """
                    INSERT INTO local_scan_led_items (
                        scan_id, local_scan_id, led_slot, led_index, led_scan_raw,
                        led_lot_no, vendor_char, led_suffix, local_status, ng_reason
                    )
                    SELECT id, local_scan_id, %s, %s, %s, %s, %s, %s, %s, %s
                    FROM local_scan_records WHERE local_scan_id = %s
                    """,
                    (
                        item["led_slot"], item["led_index"], item["led_scan_raw"],
                        item.get("led_lot_no"), item.get("vendor_char"), item.get("led_suffix"),
                        item.get("local_status"), item.get("ng_reason"), local_scan_id,
                    ),
                )

            final_is_ok, final_ng_reason, first_scan_at = is_ok, ng_reason, None
            if is_ok and duplicate_key:
                today = datetime.now()
                scope_key = today.strftime("%Y%m%d")
                min_scope_key = (today - timedelta(days=window_days)).strftime("%Y%m%d")
                cur.execute(
                    """
                    SELECT first_local_scan_id, first_scan_at
                    FROM local_duplicate_keys
                    WHERE profile_id = %s AND duplicate_key = %s AND scope_key >= %s
                    ORDER BY first_scan_at ASC
                    LIMIT 1
                    """,
                    (profile_id, duplicate_key, min_scope_key),
                )
                row = cur.fetchone()
                if row is not None:
                    final_is_ok = False
                    final_ng_reason = "LOCAL_DUPLICATE"
                    first_scan_at = row[1]
                    cur.execute(
                        """
                        UPDATE local_scan_records
                        SET local_status = 'NG', local_ng_reason = 'LOCAL_DUPLICATE'
                        WHERE local_scan_id = %s
                        """,
                        (local_scan_id,),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO local_duplicate_keys
                            (profile_id, duplicate_key, scope_key, first_local_scan_id, first_scan_at, machine_code)
                        VALUES (%s, %s, %s, %s, now(), %s)
                        ON CONFLICT (profile_id, duplicate_key, scope_key) DO NOTHING
                        """,
                        (profile_id, duplicate_key, scope_key, local_scan_id, machine_code),
                    )
        conn.commit()
    finally:
        conn.close()

    return final_is_ok, final_ng_reason, first_scan_at, local_scan_id


def apply_scan_submit_result(local_scan_id, response):
    """Cập nhật local_scan_records sau khi nhận response POST /api/scans/submit.
    SERVER_OK/SERVER_DUPLICATE/LOCAL_NG_SAVED đều success:true — đều là kết
    quả NGHIỆP VỤ cuối cùng (không phải lỗi mạng), không retry lại."""
    code = response.get("code")
    data = response.get("data") or {}
    if code == "SERVER_OK":
        server_status, final_status, final_ng_reason = "OK", "OK", None
    elif code == "SERVER_DUPLICATE":
        server_status, final_status, final_ng_reason = "NG", "NG", "SERVER_DUPLICATE"
    elif code == "LOCAL_NG_SAVED":
        server_status, final_status, final_ng_reason = "SKIPPED", "NG", data.get("ng_reason")
    else:
        return
    now = datetime.now().astimezone()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE local_scan_records
                SET server_code = %s, server_message = %s, server_scan_id = %s,
                    server_first_scan_id = %s, server_status = %s,
                    final_status = %s, final_ng_reason = %s,
                    sync_status = 'SYNCED', last_sync_at = %s, updated_at = now()
                WHERE local_scan_id = %s
                """,
                (
                    code, response.get("message"), data.get("server_scan_id"),
                    data.get("first_scan_record_id"), server_status,
                    final_status, final_ng_reason, now, local_scan_id,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def mark_scan_submit_failed(local_scan_id, error_code, error_message, blocked=False):
    """Ghi nhận submit thất bại. blocked=True cho lỗi nghiệp vụ/payload
    không nên blind-retry (PROFILE_NOT_FOUND, payload bị server bác...) ->
    FAILED_BLOCKED. blocked=False cho lỗi mạng thuần (còn cơ hội retry ở
    bước sync/batches/submit sau) -> FAILED_RETRYABLE."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE local_scan_records
                SET sync_status = %s, sync_attempt_count = sync_attempt_count + 1,
                    last_error_code = %s, last_error_message = %s, updated_at = now()
                WHERE local_scan_id = %s
                """,
                ("FAILED_BLOCKED" if blocked else "FAILED_RETRYABLE", error_code, error_message, local_scan_id),
            )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_schema()
    print("Schema local_qr da san sang.")
