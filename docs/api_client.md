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
- **Ghi chú**: gọi lại **mọi lần** `identity/status` xác nhận APPROVED (không chỉ lần đầu) — vì local có thể miss thay đổi server trong lúc app đóng. Không có polling định kỳ riêng — chỉ re-sync khi có command `SYNC_PROFILE`/`RELOAD_CONFIG` (Bước 5) hoặc lỗi `PROFILE_NOT_FOUND` lúc submit scan (chưa làm).

## Chưa làm

### `GET /api/machines/commands/poll` + `POST /api/machines/commands/:id/ack`

- **Trạng thái**: 🚧 Bước 5 (đang làm).
- **Mục đích trong project**: kênh để **server chủ động ra lệnh cho máy này** mà không cần đến tận nơi — server không gọi ngược được vào local qua LAN, local phải chủ động hỏi. 4 loại lệnh: `SYNC_PROFILE`/`RELOAD_CONFIG` (tải lại config — vd kỹ sư vừa đổi profile), `SYNC_SCAN_DATA` (đẩy dữ liệu pending ngay), `SHOW_MESSAGE` (hiện thông báo cho operator, vd cảnh báo an toàn). Trong project: quản lý tập trung nhiều trạm scan mà không cần đi từng máy.
- **Contract**: xem chi tiết trong `docs/dev.md` mục 4 (cookbook) và plan Bước 5. Poll không destructive — command chưa ack sẽ xuất hiện lại ở lần poll sau.

### `POST /api/machines/heartbeat`

- **Trạng thái**: ❌ Chưa làm.
- **Mục đích trong project**: khác `health` (hỏi server còn sống không), đây là báo cho server biết **MÁY NÀY** còn sống + số liệu local hiện tại (tổng/OK/NG/pending). Cho phép dashboard trung tâm biết trạm nào đang online/offline gần thời gian thực — quản lý line phát hiện 1 trạm bị treo/mất mạng ngay, không phải đợi hàng giờ mới nhận ra không có dữ liệu về. Cũng là điều kiện để mở kênh Socket.IO runtime.
- **Vị trí trong flow**: sau `config`, trước khi poll command lần đầu (theo doc mục 6.1).

### `POST /api/scans/submit`

- **Trạng thái**: ❌ Chưa làm — API **cốt lõi nhất** của cả hệ thống.
- **Mục đích trong project**: đẩy từng kết quả scan lên thành hồ sơ QA chính thức của Samsung (truy vết, tỷ lệ lỗi, audit). Toàn bộ Bước 1-5 tồn tại để làm cho lần gọi NÀY đáng tin cậy: đăng ký chứng minh máy hợp lệ, identity/status giữ chứng minh đó luôn mới, config đảm bảo OK/NG được chấm đúng theo profile hiện hành.
- **UX đã thống nhất trước (chưa implement)**: sau khi local OK, item QR bottom chuyển **VÀNG** (không phải xanh ngay), `labelResultStatus` CHƯA hiện "OK". Chỉ khi server xác nhận `SERVER_OK` mới chuyển xanh + hiện "OK" — nguyên tắc "chỉ so OK với OK" áp dụng cả với việc chờ server.
- **File liên quan hiện có**: `db/local_db.py:record_full_scan()` đã ghi local đầy đủ, nhưng chưa trả `local_scan_id` ra ngoài để dùng cho việc submit sau — cần xem lại khi làm bước này.

### `POST /api/sync/batches/submit` + `POST /api/sync/reconcile/check` + `.../pull`

- **Trạng thái**: ❌ Chưa làm.
- **Mục đích trong project**: app này **local-first** theo thiết kế (mất mạng vẫn phải scan được, validate cục bộ trước). Đây là cơ chế "bắt kịp": `batches/submit` gửi lô dữ liệu tồn khi offline; `reconcile/check` + `.../pull` đối chiếu số liệu/checksum để phát hiện + vá lệch dữ liệu sau 1 lần mất mạng dài hoặc crash app. Không có nó, mất mạng lâu có thể mất vĩnh viễn dữ liệu QA — đây là thứ biến "local-first" từ ý tưởng thiết kế thành thực sự an toàn.
- **Trigger**: theo doc, kích hoạt bởi `sync_batch_trigger_type` (`STARTUP`/`SHUTDOWN`/`NETWORK_RESTORED`/`MANUAL`) hoặc command `SYNC_SCAN_DATA` (Bước 5 — hiện luôn ack FAILED vì API này chưa tồn tại).

### Socket.IO `/machine-runtime`

- **Trạng thái**: ❌ Chưa làm.
- **Mục đích trong project**: KHÔNG phải hồ sơ QA chính thức (đó là việc của `scans/submit`) — kênh phụ hiển thị "đang chạy gì ngay lúc này" cho dashboard vận hành của server (đang chạy chassis nào, tổng OK/NG phiên hiện tại, reconnect count). Giá trị quan sát cho quản lý line, không ảnh hưởng tính đúng đắn của app local.
- **Vì sao đứng cuối roadmap**: cần `machine_code` (đã có) + config (đã có) + khái niệm "operator bấm Start/Stop 1 lượt chạy" mà `ui/main_window.py` hiện CHƯA có (app hiện chỉ liên tục nhận scan, không có nút Start/Stop tách rời).
- **Khác biệt kỹ thuật quan trọng**: không dùng `SamsungQrServerClient`/`ServerWorker` hiện tại (REST) — cần thư viện `python-socketio`, kết nối `http://SERVER_HOST:3979/machine-runtime` (không có `/api`), là 1 kênh hoàn toàn riêng.
