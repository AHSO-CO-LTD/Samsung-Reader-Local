# Việc chưa test được với server thật

> File tạm. Xoá từng mục sau khi tự test xong với server thật (không tính test tĩnh/mock). Xoá cả file này nếu rỗng.

## Bước 5: `commands/poll` + `commands/:id/ack` (2026-07-14, server down lúc code xong bước này)

Đã code + test tĩnh đầy đủ (`py_compile`, test cô lập các hàm DB, test dispatch với `enqueue` bị monkeypatch) nhưng CHƯA verify với server thật:

- Chưa gọi `GET /api/machines/commands/poll` với server thật — chỉ verify qua response giả.
- Chưa test round-trip `POST /api/machines/commands/:id/ack` thật (ACK lẫn FAILED).
- Chưa xác nhận command do `SYNC_PROFILE`/`RELOAD_CONFIG` kích hoạt tự động gọi lại `config` + ack đúng qua cơ chế `correlation_id`.
- Chưa xác nhận 3 dòng `command_inbox` mock cũ (`server_command_id` 101/102/103, từ `db/seed_full_schema.py`) không bị xử lý nhầm nếu server thật có command trùng id.
- Chưa xác nhận `_commands_poll_timer` (30s) thực sự bắt đầu đúng lúc (ngay sau `config` load thành công lần đầu) và không dừng khi máy chuyển sang `BLOCKED`.

**Cách test khi server up lại**: mở app thật, đợi máy lên `READY`, xem `command_inbox`/`api_request_logs` (`request_type IN ('commands_poll', 'command_ack')`) qua Query Tool hoặc script nhỏ đọc DB. Nếu có sẵn command test trên server (`SYNC_PROFILE`/`SHOW_MESSAGE`...), theo dõi log app + `local_notifications` để xác nhận đúng luồng.

## Bước 6: `heartbeat` (2026-07-14, server vẫn down lúc code xong bước này)

Đã code + test tĩnh đầy đủ (`py_compile`, test cô lập `get_server_settings`/`get_scan_counts`, test dispatch với `enqueue` bị monkeypatch, **đặc biệt đã test kỹ phần quan trọng nhất: `SERVER_OFFLINE` không khoá màn scan**) nhưng CHƯA verify với server thật:

- Chưa gọi `POST /api/machines/heartbeat` với server thật — chưa xác nhận nhận đúng `HEARTBEAT_ACCEPTED`.
- Chưa xem `data.sync_state` server trả về thực tế có hợp lý không (server tự tính `server_total_record`/`server_checksum`... dựa trên gì).
- Chưa test round-trip thật: tắt mạng/server giữa chừng khi app đang chạy → xác nhận chuyển đúng `SERVER_OFFLINE`, KHÔNG khoá màn scan, rồi bật lại server → xác nhận tự phục hồi về `READY` + `LOCAL_SERVER_RECONNECTED` (qua `_apply_server_online`, không phải qua heartbeat) đúng lúc.
- Chưa xác nhận interval heartbeat tính từ `heartbeat_timeout_seconds` thật của server (hiện đang tính `clamp(timeout//4, 5, 15)` giây, tự chọn vì doc không cho công thức) có hợp lý trong thực tế không.
- Chưa xác nhận `_heartbeat_timer` dừng đúng lúc máy chuyển `BLOCKED` và tự chạy lại khi hết `BLOCKED`.

**Cách test khi server up lại**: mở app thật, đợi máy `READY`, xem `local_app_settings.last_heartbeat_at` cập nhật đều đặn + `api_request_logs` (`request_type='heartbeat'`) qua Query Tool. Thử ngắt mạng cục bộ (rút cáp/tắt Wi-Fi) vài chục giây rồi bật lại để test nhánh `SERVER_OFFLINE` → phục hồi.

## Bước 7: `scans/submit` (2026-07-14, server vẫn down lúc code xong bước này)

Đã code + test tĩnh đầy đủ (`py_compile`, test cô lập `record_full_scan`/`apply_scan_submit_result`/`mark_scan_submit_failed`, test dispatch với `enqueue` bị monkeypatch — **đặc biệt đã test kỹ case operator chuyển sản phẩm mới TRƯỚC khi response submit của sản phẩm cũ về, qua `_session_generation`**) nhưng CHƯA verify với server thật — đây là API cốt lõi nhất, cần test kỹ khi có server:

- Chưa gọi `POST /api/scans/submit` thật — chưa xác nhận nhận đúng `SERVER_OK`/`SERVER_DUPLICATE`/`LOCAL_NG_SAVED` với payload thật (đặc biệt cấu trúc `full_code`/`led_scans` có đúng ý server không, dù đã map cẩn thận theo doc).
- Chưa test **màu vàng → xanh thật** trên máy thật (item QR bottom + `labelResultStatus`) với 1 scan OK thật, đo thời gian trễ giữa lúc hiện vàng và lúc server xác nhận.
- Chưa test `SERVER_DUPLICATE` thật (submit trùng `profile_id+duplicate_key` — có thể test bằng cách quét lại đúng 1 mã đã submit OK trước đó, tuỳ policy `duplicate_days` server đang cấu hình).
- Chưa test **idempotency thật**: kill app giữa lúc đang chờ response 1 scan (hoặc ngắt mạng đúng lúc submit), mở lại app, xác nhận server "replay" đúng kết quả cũ nếu retry cùng `local_scan_id` (retry thật chưa implement ở bước này — cần tự gọi tay hoặc đợi bước `sync/batches/submit`).
- Chưa xác nhận `PROFILE_NOT_FOUND` thật (vd tắt 1 profile bên server rồi quét lại) → có tự tải lại config đúng không.
- Chưa xác nhận `labelPendingSync` phản ánh đúng số liệu thật khi có nhiều scan pending cùng lúc (vd ngắt mạng rồi quét liên tục vài sản phẩm).

**Cách test khi server up lại**: mở app thật, quét vài sản phẩm OK — quan sát trực tiếp màu vàng→xanh + `labelResultStatus` "PENDING"→"OK". Kiểm `local_scan_records` (`server_code`, `final_status`, `sync_status`) qua Query Tool khớp với những gì thấy trên UI. Thử quét NG — xác nhận vẫn đỏ ngay và vẫn có dòng `api_request_logs` (`request_type='scan_submit'`) tương ứng.
