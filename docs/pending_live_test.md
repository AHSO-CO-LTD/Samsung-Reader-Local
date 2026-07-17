# Việc chưa test được với server thật

> File tạm. Xoá từng mục sau khi tự test xong với server thật (không tính test tĩnh/mock). Xoá cả file này nếu rỗng.

## Bước 5: `commands/poll` + `commands/:id/ack`

Đã verify với server thật (2026-07-15): poll hoạt động đúng (`MACHINE_COMMANDS_POLLED`, 200, nhiều lần), 3 dòng `command_inbox` cũ (id 101/102/103) xác nhận là rác test tĩnh ngày 2026-07-14 chứ không phải dữ liệu thật, không bị xử lý nhầm. `_commands_poll_timer` tự start đúng lúc.

Còn thiếu đúng 1 việc, cần admin tạo command thật trên server cho máy `Local02` mới test được:

- Chưa xác nhận command `SYNC_PROFILE`/`RELOAD_CONFIG`/`SHOW_MESSAGE` THẬT do server tạo có kích hoạt đúng luồng tự động (tải lại config + ack qua `correlation_id`) hay không — server hiện không có command nào đang chờ cho máy này để test.

**Cách test khi có command thật**: nhờ admin tạo 1 command (vd `SHOW_MESSAGE` — ít rủi ro nhất) cho `machine_code=Local02` trên server, sau đó mở app thật, đợi tối đa 30s (interval poll), xem `command_inbox`/`api_request_logs` (`request_type IN ('commands_poll','command_ack')`) qua Query Tool để xác nhận ack đúng.

## Bước 8: `POST /api/sync/batches/submit`

Đã verify với server thật (2026-07-16), qua trigger STARTUP tự động (10 bản ghi pending/failed_retryable tồn đọng thật từ trước): server trả đúng `BATCH_SUBMIT_PARTIAL_FAILED` với `data.results[]` trộn cả thành công (3× `SERVER_OK`, 2× `LOCAL_NG_SAVED`) và thất bại (5× `BATCH_MACHINE_CODE_MISMATCH` — mã lỗi mới, không có trong doc lúc viết code, nhưng xử lý generic theo `success:false` trong code đã bắt đúng, không cần biết trước tên mã lỗi cụ thể). Local xử lý đúng: 5 bản ghi thành công → `SYNCED` đúng `final_status`; 5 thất bại → `FAILED_BLOCKED`; `sync_batches.status='PARTIAL_FAILED'`, totals đúng (3 OK/2 NG/5 failed); notification `OFFLINE_SYNC_HAS_NG` bắn đúng; `local_runtime_status` revert `SYNCING→READY` đúng; `labelPendingSync` về đúng "0" sau khi xong.

Trigger MANUAL (nút Sync Now) dùng chung 100% code với STARTUP (chỉ khác chuỗi `trigger_type` truyền vào) nên coi như đã verify gián tiếp qua test trên.

Còn thiếu đúng 1 việc, cần admin tạo lệnh thật trên server mới test được:

- Chưa xác nhận lệnh `SYNC_SCAN_DATA` THẬT do server tạo có kích hoạt đúng `_maybe_start_sync_batch("MANUAL", command_id=...)` rồi ack lại đúng lúc qua `commands/:id/ack` hay không — chỉ mới test bằng cách gọi thẳng hàm với `command_id` giả (xem test dispatch), chưa qua đường `commands/poll` thật.

**Cách test khi có lệnh thật**: nhờ admin tạo command `SYNC_SCAN_DATA` cho `machine_code=Local02`, mở app thật, đợi tối đa 30s (interval poll), xem `labelPendingSync`/log/`api_request_logs` (`request_type IN ('commands_poll','batch_submit','command_ack')`) qua Query Tool để xác nhận batch chạy đúng rồi ack đúng.
