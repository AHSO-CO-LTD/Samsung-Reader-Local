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

## Heartbeat → Machine/Line/Station

Đã hoàn tất (2026-07-28). MainWindow thật đã nhận
`HEARTBEAT_ACCEPTED` và hiển thị `data.machine.machine_name` ở góc trên trái;
user đã tự live-test tiếp với `line_name` và `station_name` thật khác `null`,
xác nhận Line/Station cập nhật đúng từ heartbeat. Không dùng dữ liệu giả hoặc
giá trị local DB để kết luận phần này.

## Chassis Rear → Keyboard-HID

Đã hoàn tất (2026-07-28). User đã live-test bằng máy quét HID vật lý qua toàn
bộ đường focus của `comboBoxChassisRear`: focus ô nhập, chọn từ popup
autocomplete, chọn từ dropdown, xác nhận bằng Enter và click ra ngoài. Chassis
được giữ/fallback đúng và HID tiếp tục nhận scan bình thường sau khi kết thúc
tìm kiếm.

## Socket.IO `/machine-runtime`

Đã verify với server thật (2026-07-21): connect+`machine:hello`+`machine:accepted`, `runtime:start` đúng 1 lần/phiên, đổi chassis → `runtime:update`, `runtime:error`, `runtime:snapshot` định kỳ 5s ổn định nhiều phút, **2 lần mất/khôi phục kết nối thật** (tắt/bật server dev giữa phiên) → `LOCAL_RUNTIME_DISCONNECTED`/`LOCAL_RUNTIME_RECONNECTED` đúng thứ tự, không gửi lại `runtime:start`, đóng app → `runtime:stop` + `LOCAL_RUNTIME_STOPPED` (kể cả sau khi đã reconnect), build PyInstaller `--onedir` thật.

Đã verify lại với server dev thật (2026-07-28): `runtime:stop` dùng `sio.call(..., timeout=3)`, server ACK ngay với `success=true`, `code="RUNTIME_SESSION_STOPPED"`; MainWindow chỉ ghi `LOCAL_RUNTIME_STOPPED` sau ACK rồi mới disconnect/thoát. Không còn sleep cố định; timeout/ACK sai được đánh dấu `LOCAL_RUNTIME_STOP_UNCONFIRMED`.

Trong shutdown thành công, callback transport disconnect có thể ghi
`LOCAL_RUNTIME_DISCONNECTED (client disconnect)` ngay trước
`LOCAL_RUNTIME_STOPPED`. Đây là disconnect chủ động sau khi đã nhận ACK, không
làm ACK stop mất hiệu lực. Nếu dashboard server đổi phiên từ STOPPED sang trạng
thái khác chỉ vì socket disconnect, cần sửa state handling phía server.

Còn 2 việc CHƯA verify qua đúng con đường thật 100% (đã verify gián tiếp/cô lập, coi như rủi ro thấp nhưng nên tự test lại khi có dịp):

- **`runtime:update` lúc chốt phiên quét**: chỉ mới verify qua gọi thẳng `MachineRuntimeClient.record_scan_result()` (tránh dùng DB/reader thật lúc test riêng phần Socket.IO) — CHƯA quét 1 mã thật qua `_finalize_scan_session()` thật để xác nhận `runtime:update` tự bắn đúng lúc đó. Cách test: quét 1 mã thật (OK hoặc NG) trong lúc runtime session đang active, xem dashboard server nhận đúng `runtime:update` với `last_result`/`last_code` khớp.
- **Mở app khi server ĐÃ OFFLINE SẴN từ đầu** (khác với mất kết nối giữa chừng — đã test ở trên): chỉ mới verify ở mức cô lập (`MachineRuntimeClient.start_session()` trỏ thẳng vào cổng đóng — xác nhận `_RuntimeConnectWorker` retry đúng, không crash, `.stop()` không hang) — CHƯA mở `MainWindow` thật trong lúc server dev tắt hẳn từ đầu để xác nhận app vẫn mở/quét bình thường và kênh tự kết nối khi server online lại, không cần khởi động lại app. Cách test: tắt server dev TRƯỚC khi mở app, mở app xác nhận không treo/crash, quét thử vẫn hoạt động bình thường, rồi bật server lên xem `LOCAL_RUNTIME_CONNECTED` tự xuất hiện trong vài giây.
