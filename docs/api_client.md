# API client — mục đích & contract từng endpoint

> Tài liệu tham khảo sâu cho tầng tích hợp server (`server/api_client.py`, `server/server_worker.py`, và phần xử lý trong `ui/main_window.py`/`ui/register_window.py`). Bổ sung cho `docs/dev.md` (giữ `dev.md` gọn để định hướng nhanh toàn project; file này đi sâu riêng từng API — vì sao project cần nó, không phải chỉ dịch lại doc chung chung).
>
> Nguồn contract chuẩn: `docs/10-huong-dan-api-may-local-python (2).md`. Khi contract ở đây và doc lệch nhau, doc là đúng — cập nhật lại file này.

## Đã làm

### `GET /api/health`

- **Trạng thái**: ✅ Bước 1.
- **Mục đích trong project**: kiểm tra server có đang chạy không, tách biệt hoàn toàn khỏi việc máy này đã đăng ký hay chưa. Đây là điều kiện tiên quyết cho MỌI lệnh gọi khác — nếu server sập, không có lý do gì gọi các API còn lại. Cũng là nền tảng cho cơ chế local-first: khi `server_online=False`, app biết phải chuyển sang chế độ chỉ ghi local, không cố gắng gửi lên server.
- **Contract**: `GET /api/health`, không tham số. Thành công: `HEALTH_OK`.
- **File**: `server/api_client.py:health()`, `ui/main_window.py:_check_server_health/_apply_server_online`. `QTimer` 15s, chạy suốt vòng đời app, không phụ thuộc trạng thái đăng ký.
- **Ghi chú**: đây là API DUY NHẤT không cần `serial`/`uid` — không định danh, chỉ hỏi "server có sống không".

### `POST /api/machines/register-request` + `GET /api/machines/register-requests/:id/status`

- **Trạng thái**: ✅ Bước 2.
- **Mục đích trong project**: máy này (định danh bằng `serial`+`uid` phần cứng qua `machine/hardware_id.py`) chưa có `machine_code` chính thức — server không biết trạm QA này tồn tại. Đây là bước "khai sinh" 1 trạm mới trên dây chuyền, cần admin duyệt tay bên server (import license + approve). Không có bước này, không API nào khác chấp nhận dữ liệu từ máy này.
- **Contract**: `POST .../register-request` body `{serial, uid, ip_address}` (từ Bước "đổi IP", `ip_address` luôn gửi `null` — không còn gửi IP máy local lên server). Trả `MACHINE_REGISTER_REQUEST_SENT` (kèm `request_id`) hoặc `MACHINE_REGISTER_DUPLICATE`. `GET .../register-requests/:request_id/status` poll bằng `request_id`, trả `MACHINE_REGISTER_PENDING` (chờ license/duyệt) → `MACHINE_REGISTER_APPROVED` (kèm `machine_code`) hoặc `MACHINE_REGISTER_REJECTED`.
- **File**: `ui/register_window.py` — dialog riêng, tự poll khi `PENDING` (12s), không tự động mở lúc khởi động app.
- **Ghi chú**: hành động HIẾM — chỉ làm khi setup máy mới hoặc khi dữ liệu đăng ký trên server bị mất/reset (đã gặp nhiều lần trong quá trình dev — xem `docs/dev.md` mục 7). Vì hiếm và cần người duyệt tay, tách hẳn thành dialog thay vì chạy ngầm.

### `GET /api/machines/identity/status`

- **Trạng thái**: ✅ Bước 3.
- **Mục đích trong project**: `machine_code` được cấp 1 lần nhưng không có nguồn xác thực nào khác ngoài server — mỗi lần mở app phải hỏi lại "tôi còn được phép hoạt động không". Đây là **cổng chặn quan trọng nhất về nghiệp vụ**: máy chưa đăng ký / bị từ chối / bị admin khoá (`is_active=false`) đều không được phép tạo dữ liệu QA, vì server sẽ không bao giờ chấp nhận dữ liệu đó — cho scan chạy trong tình huống này chỉ tạo dữ liệu vô nghĩa.
- **Contract**: `GET .../identity/status?serial=...&uid=...`. 5 code: `MACHINE_IDENTITY_APPROVED` (có `machine_code`), `MACHINE_REGISTER_PENDING` (dùng chung với luồng đăng ký), `MACHINE_IDENTITY_NOT_REGISTERED`, `MACHINE_IDENTITY_DISABLED` (đã duyệt nhưng admin tắt), `MACHINE_IDENTITY_MISMATCH` (`success:false` — serial/uid trùng máy khác).
- **File**: `ui/main_window.py:_handle_identity_status_result`, `_apply_runtime_status`. Gọi ngay lúc mở app + định kỳ 15s **chỉ khi chưa READY** (dừng hẳn khi đã READY — không cần hỏi lại liên tục khi đã ổn).
- **Ghi chú**: điều khiển trực tiếp `local_runtime_status` → banner `labelRuntimeBanner` + khoá input scan + **chặn dữ liệu thật** ở `on_data_received` (không chỉ disable widget, vì disable không ngăn được reader gửi data qua signal).

### `GET /api/machines/config`

- **Trạng thái**: ✅ Bước 4, đã verify với server thật.
- **Mục đích trong project**: máy đã hợp lệ rồi thì cần biết đang được giao chạy chassis/LED profile nào, factory code gì, ngưỡng kiểm tra (độ dài, vị trí vendor) — những thứ đổi theo thời gian trên dây chuyền thật (thêm sản phẩm mới, đổi mã tham chiếu) và không thể hardcode trong code Python. Đây là API **quan trọng nhất cho tính đúng đắn của việc chấm OK/NG** — biến `data/mapping_store.py` từ list hardcode thành nguồn dữ liệu thật từ server.
- **Contract**: `GET .../config?serial=...&uid=...`. Thành công `MACHINE_CONFIG_LOADED`, `data` gồm `machine{}`/`settings{}`/`profiles[]` (lồng `chassis_code{}`+`profile_led_codes[]`)/`vendors[]`/`pending_commands[]`. Lỗi: `MACHINE_NOT_FOUND`, `MACHINE_IDENTITY_MISMATCH`.
- **File**: `ui/main_window.py:_handle_config_result`, `db/local_db.py:apply_machine_config` (UPSERT + soft-delete cho `profile_cache`/`profile_led_code_cache`, tránh vi phạm FK `local_scan_records.profile_id RESTRICT`), `data/mapping_store.py:load_mappings()` (đọc lại từ cache này).
- **Ghi chú**: gọi lại **mọi lần** `identity/status` xác nhận APPROVED (không chỉ lần đầu) — vì local có thể miss thay đổi server trong lúc app đóng. Không có polling định kỳ riêng — chỉ re-sync khi có command `SYNC_PROFILE`/`RELOAD_CONFIG` (Bước 5) hoặc lỗi `PROFILE_NOT_FOUND` lúc submit scan.

### `GET /api/machines/commands/poll` + `POST /api/machines/commands/:id/ack`

- **Trạng thái**: ✅ Bước 5, đã verify với server thật (2026-07-15) — xem `docs/pending_live_test.md` cho phần còn thiếu (cần admin tạo 1 command thật để test luồng tự động tải lại config).
- **Mục đích trong project**: kênh để **server chủ động ra lệnh cho máy này** mà không cần đến tận nơi — server không gọi ngược được vào local qua LAN, local phải chủ động hỏi. 4 loại lệnh: `SYNC_PROFILE`/`RELOAD_CONFIG` (tải lại config — vd kỹ sư vừa đổi profile), `SYNC_SCAN_DATA` (đẩy dữ liệu pending ngay), `SHOW_MESSAGE` (hiện thông báo cho operator, vd cảnh báo an toàn). Trong project: quản lý tập trung nhiều trạm scan mà không cần đi từng máy.
- **Contract**: xem chi tiết trong `docs/dev.md` mục 4 (cookbook). Poll không destructive — command chưa ack sẽ xuất hiện lại ở lần poll sau.
- **File**: `ui/main_window.py:_check_commands/_handle_commands_poll_result/_process_command/_ack_command`, `db/local_db.py:save_command_received/finish_command`. `QTimer` 30s, tự start sau khi config load thành công lần đầu, không dừng khi `BLOCKED`.

### `POST /api/machines/heartbeat`

- **Trạng thái**: ✅ Bước 6, đã verify với server thật (2026-07-15), kể cả round-trip mất kết nối/phục hồi thật.
- **Mục đích trong project**: khác `health` (hỏi server còn sống không), đây là báo cho server biết **MÁY NÀY** còn sống + số liệu local hiện tại (tổng/OK/NG/pending). Cho phép dashboard trung tâm biết trạm nào đang online/offline gần thời gian thực — quản lý line phát hiện 1 trạm bị treo/mất mạng ngay, không phải đợi hàng giờ mới nhận ra không có dữ liệu về. Cũng là điều kiện để mở kênh Socket.IO runtime.
- **Vị trí trong flow**: sau `config`, trước khi poll command lần đầu (theo doc mục 6.1).
- **File**: `ui/main_window.py:_send_heartbeat/_handle_heartbeat_result/_ensure_heartbeat_started`, `db/local_db.py:get_server_settings/get_scan_counts`. `local_runtime_status=SERVER_OFFLINE` khi mất kết nối (nằm trong `SCAN_ENABLED_STATUSES` — KHÔNG khoá scan, đúng thiết kế local-first), tự phục hồi `READY` khi heartbeat thành công trở lại.

### `POST /api/scans/submit`

- **Trạng thái**: ✅ Bước 7, API **cốt lõi nhất** của cả hệ thống — đã verify đầy đủ với server thật (2026-07-15): `SERVER_OK`, `SERVER_DUPLICATE` (cross-check chéo qua server), `LOCAL_NG_SAVED`, và **idempotency thật** (gửi lại cùng `local_scan_id` → server replay đúng `server_scan_id` cũ, message "Scan result was already saved.", không tạo bản ghi mới).
- **Mục đích trong project**: đẩy từng kết quả scan lên thành hồ sơ QA chính thức của Samsung (truy vết, tỷ lệ lỗi, audit). Toàn bộ Bước 1-6 tồn tại để làm cho lần gọi NÀY đáng tin cậy: đăng ký chứng minh máy hợp lệ, identity/status giữ chứng minh đó luôn mới, config đảm bảo OK/NG được chấm đúng theo profile hiện hành.
- **UX**: sau khi local OK, item QR bottom chuyển **VÀNG** (không phải xanh ngay), `labelResultStatus` CHƯA hiện "OK". Chỉ khi server xác nhận `SERVER_OK` mới chuyển xanh + hiện "OK" — nguyên tắc "chỉ so OK với OK" áp dụng cả với việc chờ server. NG hiện đỏ ngay lập tức (không chờ), nhưng vẫn submit lên server để giữ trace.
- **File**: `ui/main_window.py:_finalize_scan_session/_submit_scan/_handle_scan_submit_result/_reflect_scan_submit_ui` (theo dõi qua `_session_generation`/`_pending_scan_ui` để tránh cập nhật UI sai khi operator đã chuyển sang sản phẩm khác trước khi response async về), `db/local_db.py:record_full_scan/apply_scan_submit_result/mark_scan_submit_failed`.
- **Lịch sử gotcha (đã đổi 2 lần, xem kỹ trước khi "sửa lại cho giống trước")**:
  1. (2026-07-15 sáng) Phát hiện lỗi 400 thật khi QR bottom không tự parse được (sai chassis/độ dài/LED-not-match/factory) — `duplicate_key`/`full_code.led_code` là `null`, server lúc đó bác 400 (2 field bắt buộc phải là string, và còn tự đối chiếu lại `full_code` với profile). Đã thử gửi placeholder (`***`) thay vì `null` — vẫn bị bác (server tự re-validate, không tin local). Lúc đó đã sửa code CHẶN không gửi case này, đánh dấu `FAILED_BLOCKED` cục bộ.
  2. (2026-07-15 chiều) **Server đã bỏ hẳn phần validate đó** — xác nhận thật bằng 2 curl test lại y hệt 2 case đã bị bác trước đó (sai độ dài, và đúng độ dài/sai chassis, đều gửi `null`): cả 2 lần đều nhận `LOCAL_NG_SAVED` bình thường. Đã **bỏ code chặn**, quay lại đúng nguyên tắc gốc của doc — "Local NG vẫn gửi server để lưu trace" áp dụng cho MỌI loại NG, kể cả QR bottom không parse được. Đã verify lại bằng test thật (app thật + server thật): submit thành công, DB `sync_status=SYNCED`, không còn `FAILED_BLOCKED`.
  - **Bài học**: hành vi chặn/không chặn phụ thuộc hoàn toàn vào server, không phải quy tắc cố định phía local — nếu server đổi lại validate trong tương lai, cần re-test trước khi giả định hành vi nào đang đúng.
- **Bug thật tìm được + đã sửa (2026-07-15, rà lại toàn diện vì đây là API quan trọng nhất)**: `db/local_db.py:record_full_scan()` có biến `duplicate_key` RIÊNG (gate theo `is_ok` — kết quả tổng hợp cuối), khác với `qr_data["duplicate_key"]` mà `main_window.py` tính theo `own_is_ok` (đúng chủ ý: vẫn có giá trị dù final NG do LED bar lỗi). Hậu quả: cột `local_scan_records.duplicate_key` bị lưu `NULL` cho case "QR bottom hợp lệ nhưng NG vì LED bar sai" — LỆCH với giá trị THẬT đã gửi server (có duplicate_key). Xác nhận bằng dữ liệu thật (`LOCAL-20260715131957-a738235f`: `full_led_code` có giá trị nhưng `duplicate_key=NULL`). Rủi ro: Bước 8 (retry/batch submit) sẽ đọc lại từ DB để gửi lại — đọc phải `NULL` sẽ gửi SAI so với lần đầu, phá vỡ yêu cầu idempotency của doc ("giữ nguyên duplicate_key khi retry"). Đã sửa: bỏ gate theo `is_ok` cho cột lưu, chỉ giữ gate `is_ok` cho việc có ghi vào bảng `local_duplicate_keys` hay không (đúng nguyên tắc "chỉ so OK với OK" cho phần dedup chủ động).
- **Đã verify thêm với server thật (2026-07-15, sau khi rà toàn diện)**:
  - Payload nhiều LED item (LED BAR 1 x2 + LED BAR 2 x1 cùng lúc, `led_scans[]` có 3 phần tử) — đúng shape, server nhận `SERVER_OK`.
  - `NG_LOCAL_DUPLICATE` (trùng phát hiện CỤC BỘ, không phải server) — xác nhận vẫn submit lên server bình thường (không bị bỏ sót), server trả `LOCAL_NG_SAVED`.
  - QR bottom cực ngắn/rách (2 ký tự, hầu hết field `full_code.*` đều `None`) qua đúng code path thật — không crash, submit thành công.
  - `PROFILE_NOT_FOUND` thật (qua `_submit_scan` với `profile_id` giả) — xác nhận đúng tự động gọi lại `_check_machine_config()`.
  - Stale-response với TIMING THẬT (không mock): bắn 2 scan liên tiếp không chờ nhau, item của scan CŨ bị Qt xoá thật (không phải mồ côi) trước khi response của chính nó về — xác nhận generation-check (`_session_generation`/`_pending_scan_ui`) ngăn chặn đúng, KHÔNG crash, DB vẫn cập nhật đúng cho cả 2 bản ghi, item/label hiện tại chỉ phản ánh đúng sản phẩm mới nhất.

## Chưa làm

### `POST /api/sync/batches/submit` + `POST /api/sync/reconcile/check` + `.../pull`

- **Trạng thái**: ❌ Chưa làm.
- **Mục đích trong project**: app này **local-first** theo thiết kế (mất mạng vẫn phải scan được, validate cục bộ trước). Đây là cơ chế "bắt kịp": `batches/submit` gửi lô dữ liệu tồn khi offline; `reconcile/check` + `.../pull` đối chiếu số liệu/checksum để phát hiện + vá lệch dữ liệu sau 1 lần mất mạng dài hoặc crash app. Không có nó, mất mạng lâu có thể mất vĩnh viễn dữ liệu QA — đây là thứ biến "local-first" từ ý tưởng thiết kế thành thực sự an toàn.
- **Trigger**: theo doc, kích hoạt bởi `sync_batch_trigger_type` (`STARTUP`/`SHUTDOWN`/`NETWORK_RESTORED`/`MANUAL`) hoặc command `SYNC_SCAN_DATA` (Bước 5 — hiện luôn ack FAILED vì API này chưa tồn tại).

### Socket.IO `/machine-runtime`

- **Trạng thái**: ❌ Chưa làm.
- **Mục đích trong project**: KHÔNG phải hồ sơ QA chính thức (đó là việc của `scans/submit`) — kênh phụ hiển thị "đang chạy gì ngay lúc này" cho dashboard vận hành của server (đang chạy chassis nào, tổng OK/NG phiên hiện tại, reconnect count). Giá trị quan sát cho quản lý line, không ảnh hưởng tính đúng đắn của app local.
- **Vì sao đứng cuối roadmap**: cần `machine_code` (đã có) + config (đã có) + khái niệm "operator bấm Start/Stop 1 lượt chạy" mà `ui/main_window.py` hiện CHƯA có (app hiện chỉ liên tục nhận scan, không có nút Start/Stop tách rời).
- **Khác biệt kỹ thuật quan trọng**: không dùng `SamsungQrServerClient`/`ServerWorker` hiện tại (REST) — cần thư viện `python-socketio`, kết nối `http://SERVER_HOST:3979/machine-runtime` (không có `/api`), là 1 kênh hoàn toàn riêng.
