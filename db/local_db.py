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
    window_days=DUPLICATE_WINDOW_DAYS, local_scan_id=None,
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

    Trả về (final_is_ok, final_ng_reason, first_scan_at_neu_trung)."""
    if local_scan_id is None:
        local_scan_id = new_local_scan_id()
    machine_code = get_machine_code()
    duplicate_key = qr_data.get("duplicate_key") if is_ok else None

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
                    %s, %s, now()
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
                    "OK" if is_ok else "NG", ng_reason,
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

    return final_is_ok, final_ng_reason, first_scan_at


if __name__ == "__main__":
    init_schema()
    print("Schema local_qr da san sang.")
