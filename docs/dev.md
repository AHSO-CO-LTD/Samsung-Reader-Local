# Dev notes — SR-X Reader Monitor

> **Đọc file này ĐẦU TIÊN** nếu quay lại project sau một thời gian dài / mất ngữ cảnh phiên làm việc. Mục tiêu: nắm được project đang ở đâu, vì sao lại như vậy, và cạm bẫy nào cần tránh — mà không phải đọc lại từng file hay suy luận lại từ đầu.
>
> Cập nhật file này khi có thay đổi lớn (thêm 1 bước tích hợp server, đổi kiến trúc, phát hiện cạm bẫy mới...). Không cần cập nhật cho từng commit nhỏ.

## 1. Project này là gì

Ứng dụng desktop PyQt5 chạy trên máy tính đặt tại 1 trạm QA trên dây chuyền sản xuất Samsung. Đọc mã vạch/QR từ các đầu đọc **Keyence SR-X** (vai trò LED BAR/QRCODE BOTTOM) qua TCP — và tuỳ chọn thêm 1 máy quét mã vạch cầm tay loại **Keyboard-HID** (giả lập gõ phím, xem mục 10) — so khớp cục bộ với PostgreSQL, và đồng bộ với 1 server trung tâm (NestJS) để server theo dõi/tổng hợp dữ liệu QA toàn nhà máy.

Đây là bản viết lại bằng Python thay cho 1 bản .NET cũ (xem `legacy_dotnet_sdk_approach/` — giữ lại để tham khảo SDK gốc của Keyence, không phải code đang chạy).

## 2. Bản đồ thư mục

| Thư mục/file | Vai trò |
| --- | --- |
| `main.py` | Entry point — chạy `python main.py` (trong `venv`) hoặc `LocalReaderMonitor.exe` khi đóng gói. Có `_setup_crash_logging()` ghi mọi uncaught exception ra `app_error.log`, và `QLockFile` (`app.lock`) chặn mở 2 instance cùng lúc trên 1 máy (tự phát hiện lock cũ nếu instance trước bị crash) |
| `app_paths.py` | `get_writable_dir()`/`get_bundle_dir()` — nền tảng path resolution dùng chung, phân biệt file **cần ghi/sửa được** (config JSON, log) với file **chỉ đọc bundle sẵn** (`.ui`, icon, âm thanh, `schema.sql`); tự động đúng cả khi chạy `python main.py` lẫn khi chạy `.exe` đã đóng gói — xem mục 9 |
| `app_logger.py` | Logger riêng ghi `log/app_events.log` (xoay theo ngày, giữ 30 ngày) cho sự kiện/thông báo hệ thống — TÁCH BIỆT hoàn toàn với crash logging (`app_error.log`) của `main.py`, không lẫn 2 hệ thống |
| `ui/main_window.py` + `.ui` | Màn hình chính: nhận scan (TCP + HID, xem mục 10), tìm/chọn Chassis Rear theo chuỗi con, so khớp OK/NG, gate màn scan theo trạng thái đăng ký/config, hiển thị Machine/Line/Station từ heartbeat và banner thông báo tiếng Việt (`labelNotificationBanner`) |
| `ui/register_window.py` + `.ui` | Dialog đăng ký máy với server. Tab Registration là luồng chính; tab License vẫn giữ trong code/UI nhưng đang tạm disable bằng `LICENSE_TAB_ENABLED = False` |
| `ui/config_window.py` + `.ui` | Dialog cấu hình reader (thêm/xoá/sửa IP, port) + checkbox bật/tắt máy quét HID (tên nút/tiêu đề tiếng Anh, label trạng thái đã dịch tiếng Việt) |
| `ui/mapping_window.ui` | Dialog xem danh sách profile/mapping (chỉ hiển thị) |
| `reader/reader_bridge.py` | `ReaderManager` — quản lý nhiều reader, mỗi reader 1 `QThread` giữ kết nối TCP sống |
| `reader/SRX_comm.py` | Giao thức tầng thấp nói chuyện với đầu đọc Keyence SR-X |
| `reader/reader_store.py` | Đọc/ghi danh sách reader đã cấu hình — `readers_config.json`, và trạng thái bật/tắt máy quét HID — `hid_scanner_config.json` (cả 2 ở gốc project, gitignored, riêng từng máy) |
| `data/mapping_store.py` | `load_mappings()` — **đọc DB thật** (`profile_cache`/`profile_led_code_cache`), KHÔNG còn là mock — xem mục 5 |
| `data/duplicate_key.py` | Tính `duplicate_key` từ mã QR đầy đủ |
| `db/local_db.py` | Toàn bộ hàm truy cập Postgres — điểm ghi duy nhất cho mọi bảng |
| `db/schema.sql` | DDL đầy đủ 16 bảng — **nguồn chân lý cho schema**, đọc file này thay vì suy luận từ code |
| `local_db_config.json` | Cấu hình kết nối Postgres (có mật khẩu) — **gốc project** (không phải `db/` nữa — xem mục 9), gitignored, xem mục 6 để biết cách tạo |
| `db/seed_full_schema.py` | Script dev-only sinh dữ liệu mẫu — xem mục 7 (cạm bẫy) trước khi chạy |
| `machine/hardware_id.py` | Đọc Windows MachineGuid + BIOS UUID + serial mainboard; định danh dùng MachineGuid làm serial và BIOS UUID làm uid |
| `machine/identity.py` | `ensure_machine_identity()` — cache serial/uid vào `local_app_settings` |
| `server/api_client.py` | `SamsungQrServerClient` — REST client, transcribe gần như nguyên văn từ doc API (mục 22 của doc) |
| `server/server_worker.py` | `ServerWorker(QThread)` — 1 thread nền xử lý hàng đợi job gọi API, không chặn GUI |
| `server_config.json` | Host/port server hiện tại — **gốc project** (không phải `server/` nữa — xem mục 9), gitignored, đổi qua nút "Change Server IP" trên `main_window` |
| `docs/10-huong-dan-api-may-local-python (2).md` | **Doc API chuẩn, đọc file này** (không phải bản không có "(2)" — bản cũ hơn, ít nội dung hơn) |
| `docs/11-sql-khoi-tao-db-may-local-python-postgres (3).md` | Doc SQL tham khảo mới nhất (không phải bản "(2)") — nhưng `db/schema.sql` mới là DDL thật đang chạy |
| `docs/deploy.md` | Hướng dẫn đóng gói/cài đặt `LocalReaderMonitor.exe` trên máy production — xem mục 9 |
| `LocalReaderMonitor.spec` | Cấu hình PyInstaller (`--onedir --windowed`, icon, `datas`) — build bằng `pyinstaller LocalReaderMonitor.spec --noconfirm` |
| `requirements-build.txt` | Dependency CHỈ cần lúc đóng gói (`pyinstaller`) — tách khỏi `requirements.txt` runtime |
| `setup.ps1` | Script cài PostgreSQL + tạo role/database/schema + sinh `local_db_config.json` trên máy client — nằm cạnh `.exe` trong gói release |
| `.github/workflows/build.yml` | CI build-only (tag `v*` hoặc thủ công) — KHÔNG chạy `setup.ps1`/cài Postgres trong CI |
| `tools/` | `mock_reader_server.py`/`mock_codes.json` — giả lập đầu đọc để test không cần phần cứng thật |

## 3. Luồng nghiệp vụ chính (scan → OK/NG)

1. Operator chọn **Chassis Rear** ở combobox (nạp từ `data/mapping_store.load_mappings()`, tức từ `profile_cache`). Có thể nhập một phần bất kỳ của mã để lọc theo chuỗi con, không phân biệt hoa/thường; chỉ mã khớp chính xác mới được áp dụng. Nếu rời ô với text chưa hoàn thiện, app fallback về mã hợp lệ gần nhất.
2. 3 đầu đọc gửi dữ liệu độc lập qua `on_data_received()`. **1 "phiên quét" = 1 sản phẩm**: Quantity của cả 3 cột là số mảnh CỦA CÙNG 1 sản phẩm (không phải nhiều sản phẩm liên tiếp). Khi đủ số lượng cả 3 cột (progress bar đầy), `_finalize_scan_session()` chạy đúng 1 lần.
3. LED BAR 1/2: `_classify_led_bar()` — so 5 ký tự cuối với `led1`/`led2` của profile đang chọn, đồng thời kiểm tra `length_led`. Không cố định theo reader vật lý — mã có thể xếp vào cột 1 hoặc 2 tuỳ khớp code nào.
4. QRCODE BOTTOM: kiểm tra thật ở `_classify_qr_bottom()`, KHÔNG kiểm tra lúc vừa nhận (vì có thể chưa đủ LED bar tham chiếu). Bảng vị trí ký tự trong mã QRCODE BOTTOM (0-indexed slice trong code, độ dài chuẩn 35):

   | Đoạn | Vị trí (0-indexed) | Ý nghĩa | Field cấu hình liên quan |
   | --- | --- | --- | --- |
   | `text[0:4]` | 1-4 | prefix | — |
   | `text[4:14]` | 5-14 | chassis segment | so với `chassis_rear` (bỏ dấu `-`) |
   | `text[14:17]` | 15-17 | before_vendor | — |
   | `text[17:18]` | 18 | **vendor_char** | vị trí = `no_bottom` (mặc định 18) |
   | `text[19:24]` | 20-24 | đoạn LED code | so 5 ký tự cuối `led1`/`led2` |
   | `text[24:28]` | 25-28 | factory_code | so với `factory_code` |
   | `text[28:]` | 29-35 | after_factory | — |

   Đối chiếu vendor: ký tự vị trí `no_bottom` của QR bottom PHẢI khớp ký tự vị trí `no_led` (mặc định 16) của **mã LED bar gần nhất đọc ĐÚNG** (`_last_ok_led_text`) — đây là cách xác định vendor, KHÔNG tra `vendor_cache` (bảng đó chỉ để hiển thị/báo cáo, không chặn OK/NG, theo đúng doc).
5. `record_full_scan()` (`db/local_db.py`) ghi `local_scan_records` + `local_scan_led_items`, tự kiểm tra trùng qua `local_duplicate_keys` — **chỉ kiểm tra trùng khi is_ok=True** ("chỉ so OK với OK", không chiếm slot dedupe nếu NG vì lý do khác).
6. Kết quả hiển thị qua `set_result_status()` — nền xanh/đỏ ở `labelResultStatus`.

**Gửi kết quả lên server (`POST /api/scans/submit`, Bước 7 — đã xong)**: UX đã thống nhất và đang chạy đúng — sau khi local OK, item QR bottom chuyển **VÀNG** (không phải xanh ngay), `labelResultStatus` CHƯA hiện "OK" — chỉ khi server xác nhận `SERVER_OK` mới chuyển xanh + hiện "OK". Nguyên tắc: "chỉ so OK với OK" áp dụng cả với việc chờ server, không tự ý coi local-OK là final.

## 4. Tích hợp server — đã làm tới đâu

Theo dõi theo "Bước" (từng bước 1 API/nhóm API nhỏ, làm xong + test xong mới sang bước sau — xem mục 8). Tính đến thời điểm viết file này:

| Bước | Endpoint | Trạng thái | File chính |
| --- | --- | --- | --- |
| 1 | `GET /api/health` | ✅ Xong. QTimer 5s, `labelServerStatus` + `pushButtonChangeServerIp` | `main_window.py` (`_check_server_health`, `_apply_server_online`) |
| 2 | `POST /api/machines/register-request` + `GET .../register-requests/:id/status` | ✅ Xong. Dialog riêng, auto-poll khi PENDING | `ui/register_window.py` |
| 3 | `GET /api/machines/identity/status` | ✅ Xong. Tự gọi lúc mở app + định kỳ khi chưa READY. **Gate màn scan chính** theo `local_runtime_status` | `main_window.py` (`_handle_identity_status_result`, `_apply_runtime_status`) |
| 4 | `GET /api/machines/config` | ✅ Xong, đã verify với server thật. Tự gọi ngay sau khi identity/status APPROVED. Ghi `machine_cache`/`server_settings_cache`/`profile_cache`/`profile_led_code_cache`/`vendor_cache`/`command_inbox` | `main_window.py` (`_handle_config_result`), `db/local_db.py` (`apply_machine_config`) |
| 5 | `commands/poll` + `commands/:id/ack` | ✅ Xong, đã verify với server thật. `SYNC_PROFILE`/`RELOAD_CONFIG`/`SHOW_MESSAGE` xử lý đầy đủ; `SYNC_SCAN_DATA` xử lý ở Bước 8 | `main_window.py` (`_handle_commands_poll_result`, `_process_command`) |
| 6 | `heartbeat` | ✅ Xong, đã verify với server thật; user đã xác nhận UI cập nhật đúng `machine_name`/`line_name`/`station_name` từ giá trị thật khác `null` (2026-07-28) | `main_window.py` (`_send_heartbeat`, `_handle_heartbeat_result`, `_update_machine_location_display`) |
| 7 | `scans/submit` | ✅ Xong, đã verify với server thật — UX vàng/xanh theo mục 3 | `main_window.py` (`_submit_scan`, `_handle_scan_submit_result`) |
| 8 | `sync/batches/submit` | ✅ Xong, đã verify với server thật (2026-07-16) — xem `docs/pending_live_test.md` | `main_window.py` (`_maybe_start_sync_batch`, `_start_sync_batch`, `_handle_batch_submit_response`), `db/local_db.py` (`claim_pending_scans_for_batch`, `apply_sync_batch_result`) |
| 9 | `sync/reconcile/check` + `sync/reconcile/pull` | ✅ Xong, đã verify với server thật (2026-07-16) — dialog `ReconcileWindow` mở qua nút "Check Data" (Register window). Review gộp vào Pull from Server (không có checkbox từng dòng) | `main_window.py` (`_start_reconcile_check`, `_handle_reconcile_check_response`, `_handle_reconcile_push`/`_pull`), `db/local_db.py` (`build_reconcile_payload`, `claim_specific_scans_for_batch`, `apply_reconcile_pull`), `ui/reconcile_window.py` |
| — | Socket.IO `/machine-runtime` | ✅ Xong, đã verify với server thật — "phiên" = trọn 1 lần chạy app. Khi đóng, `runtime:stop` dùng `sio.call(..., timeout=3)`; chỉ ACK `RUNTIME_SESSION_STOPPED` mới được xác nhận thành công rồi client mới disconnect. Không gửi lại `runtime:start` sau reconnect | `server/runtime_socket_client.py` (`MachineRuntimeClient`, `_RuntimeConnectWorker`), `main_window.py` (`_start_machine_runtime_session`, `_apply_runtime_status`, `on_chassis_rear_changed`, `_finalize_scan_session`, `closeEvent`) |

**`data/mapping_store.py` đã đổi nguồn dữ liệu (Bước 4)**: trước đây là list Python hardcode (`_MOCK_MAPPINGS`), giờ đọc thật từ `profile_cache`/`profile_led_code_cache` (đã sync từ server). Đây là logic **quyết định OK/NG** — nếu combobox Chassis Rear trống hoặc sai, kiểm tra `profile_cache WHERE is_active=true` trước, không phải sửa `mapping_store.py`.

**Contract UI Chassis Rear**: `comboBoxChassisRear` là editable nhưng có
`QComboBox.NoInsert`; completer dùng `Qt.MatchContains` +
`Qt.CaseInsensitive`, tối đa 12 gợi ý trước khi cuộn. `_canonical_chassis_code`
chỉ chấp nhận mã đầy đủ có trong mapping và chuẩn hoá lại đúng chữ hoa/thường
của mã gốc. `_last_valid_chassis_code` là fallback khi Enter, `editingFinished`
hoặc click ra ngoài với text chưa hợp lệ. Popup và editor phải dùng cùng font
với combobox.

**Machine/Line/Station**: `labelMachineLocation` ở góc trên trái lấy trực tiếp
từ `data.machine` của mỗi `HEARTBEAT_ACCEPTED`, không đọc từ text hardcode.
Field rỗng hiển thị `-`; heartbeat lỗi giữ giá trị thành công gần nhất. Chỉ cập
nhật label khi bộ ba giá trị thay đổi. User đã live-test với `line_name` và
`station_name` thật khác `null`.

**Shutdown runtime**: `closeEvent()` gọi `MachineRuntimeClient.stop()` đồng bộ
trước khi dừng `server_worker`. `stop()` chờ tối đa 3 giây cho ACK
`RUNTIME_SESSION_STOPPED`; timeout/ACK sai tạo
`LOCAL_RUNTIME_STOP_UNCONFIRMED` rồi vẫn disconnect để không treo app. Callback
disconnect do client chủ động đóng có thể tạo `LOCAL_RUNTIME_DISCONNECTED`
trước notification stop; đây là transport teardown sau ACK, không phải stop
session thất bại.

### Cách thêm 1 endpoint mới (đã lặp lại nhiều lần qua Bước 1-9, quy trình ổn định)

1. `server/api_client.py`: thêm method gọi `self._request(method, path, "ten_request_type", ...)` — hầu hết method đã transcribe sẵn từ doc mục 22, có thể đã có sẵn, chỉ cần dùng.
2. `server/server_worker.py`: thêm 1 nhánh trong `_dispatch()` map `job_kind` → method ở bước 1.
3. Nơi gọi (`main_window.py` hoặc dialog riêng): `self.server_worker.enqueue("job_kind", **kwargs)`, xử lý kết quả qua `callSucceeded`/`callFailed` (đã connect sẵn ở `_init_server_worker`) — thêm nhánh `job_kind == "..."` trong `_on_server_call_succeeded`/`_on_server_call_failed`.
4. Viết `_handle_..._result(response)` — luôn dispatch theo `response["code"]`, KHÔNG theo `message`. Nếu response `success:false` (vd lỗi nghiệp vụ có `data` chi tiết), nó tới qua `callFailed` với `payload` chứa nguyên response — check `payload.get("code")` trước khi coi là lỗi mạng thuần (xem `_on_server_call_failed` nhánh `identity_status`/`config` làm ví dụ).
5. Ghi DB qua hàm mới trong `db/local_db.py` (không viết SQL trực tiếp trong `main_window.py`).
6. Nếu ảnh hưởng `local_runtime_status`: gọi `self._apply_runtime_status(status, message)` — đây LÀ điểm gate màn scan + bắn notification, không tự ý set `local_runtime_status` bằng `update_app_settings()` rồi bỏ qua hàm này.
7. `api_request_logs` tự động ghi (mọi call qua `_request()` trong `api_client.py`) — không cần làm gì thêm.
8. Test với server thật (`192.168.100.1:3979` tại thời điểm viết, đổi qua nút Change Server IP nếu server đổi địa chỉ) — KHÔNG viết mock server để test.

## 5. State machine `local_runtime_status`

Cột `local_app_settings.local_runtime_status`, enum cố định trong `db/schema.sql`: `BOOTING, SERVER_OFFLINE, NOT_REGISTERED, REGISTERING, WAITING_LICENSE, WAITING_APPROVAL, REJECTED, READY, SCANNING, SYNCING, BLOCKED, ERROR`.

`main_window.py:_apply_runtime_status(status, message)` là **điểm trung tâm duy nhất** xử lý trạng thái này:
- Enable/disable input scan (`comboBoxChassisRear`, 3 spinbox Quantity, `pushButtonReset`).
- Hiện/ẩn banner `labelRuntimeBanner` (màu theo mức độ nghiêm trọng).
- Set `self._scan_blocked` — **đây mới là gate THẬT**, được check ở đầu `on_data_received()`. Disable widget chỉ là UX, không chặn được dữ liệu reader gửi tới qua signal (reader không quan tâm widget có enable hay không).
- Chỉ log/bắn `local_notifications` khi trạng thái THẬT SỰ đổi so với lần gọi trước (so `self._runtime_status` cũ/mới) — tránh spam notification mỗi lần poll mà trạng thái không đổi. Baseline được set TRƯỚC lần gọi đầu (đọc từ DB) để không bắn notification cho trạng thái có sẵn từ phiên trước.

Chỉ `READY`/`SCANNING`/`SYNCING`/`SERVER_OFFLINE` (`SCAN_ENABLED_STATUSES` trong `main_window.py`) mới cho phép scan. Mọi trạng thái khác đều chặn.

Gate vào `READY`/`NOT_REGISTERED`/`WAITING_LICENSE`/`WAITING_APPROVAL`/`BLOCKED` do `main_window.py:_check_identity_status()` và phản hồi server quyết định. License cục bộ ở mục 11 là tab phụ độc lập, không được phép thay đổi `local_runtime_status` hoặc `_scan_blocked`.

## 6. File cấu hình riêng từng máy (gitignored)

4 file này **không có trong git**, nằm chung trong thư mục con **`config/`** ngay cạnh `.exe`/gốc project (không phải trong `db/`/`server/`/`reader/` — gộp về 1 chỗ khi làm packaging, xem mục 9 lý do và `app_paths.py:get_config_dir()`), phải tự tạo khi setup máy mới (hoặc để `setup.ps1` tự sinh — xem mục 9). **Máy đã chạy bản cũ** (file từng nằm rải rác trực tiếp ở gốc, không có thư mục `config/`) được **tự động di chuyển** sang vị trí mới ngay lần khởi động đầu tiên sau khi cập nhật — xem `main.py:_migrate_legacy_config_files()` (idempotent, không ghi đè nếu vị trí mới đã có file, không làm mất cấu hình đang dùng thật):

**`local_db_config.json`**:
```json
{
  "host": "127.0.0.1",
  "port": 5432,
  "dbname": "samsung_qr_local",
  "user": "samsung_qr_local_user",
  "password": "<mật khẩu Postgres thật>",
  "schema": "local_qr"
}
```

**`server_config.json`** (tự tạo lần đầu qua nút "Change Server IP" nếu chưa có, mặc định `127.0.0.1:3979`):
```json
{ "host": "192.168.100.1", "port": 3979 }
```

**`readers_config.json`** — danh sách reader đã cấu hình qua dialog Configure, tự sinh khi bấm "Add reader" lần đầu, không cần tạo tay.

**`hid_scanner_config.json`** — trạng thái bật/tắt máy quét mã vạch cầm tay (checkbox trong Config Window), tự sinh khi đổi checkbox lần đầu; không có file thì mặc định coi là BẬT (xem mục 10).

## 7. Lưu ý quan trọng / cạm bẫy

- **psycopg3 KHÔNG nhận `col IN %s` với tuple** như psycopg2 — lỗi `syntax error at or near "$2"`. Phải dùng `col = ANY(%s)` với **list** Python (không phải tuple). Xem `db/local_db.py:apply_machine_config` để làm ví dụ.
- **KHÔNG bao giờ `DELETE`/`TRUNCATE` thẳng `profile_cache`** nếu đã có scan ghi nhận — `local_scan_records.profile_id` có FK `ON DELETE RESTRICT`, xoá sẽ crash. Luôn UPSERT + soft-delete (`is_active=false`) cho profile không còn trong response mới. Cùng lý do, `profile_led_code_cache`/`vendor_cache`/`machine_cache`/`server_settings_cache` cũng nên UPSERT, không DELETE.
- **`db/seed_full_schema.py` vẫn TRUNCATE `local_app_settings`** mỗi lần chạy (registration_status, machine_code, machine_serial/uid...) — chạy lại script này trên máy đã đăng ký thật với server SẼ xoá mất tiến trình đăng ký. 5 bảng cache (`profile_cache` và 4 bảng liên quan) đã đổi sang `ON CONFLICT DO NOTHING` nên an toàn hơn, nhưng `local_app_settings` thì chưa — cân nhắc trước khi chạy trên máy có dữ liệu thật.
- **Dữ liệu đăng ký máy trên server dev/test có thể tự đổi** ngoài ý muốn của local (quan sát được nhiều lần trong quá trình phát triển: APPROVED → DISABLED → NOT_REGISTERED → APPROVED lại, không phải do bug local). App được thiết kế để tự đồng bộ lại theo bất cứ gì server trả về (server là nguồn chân lý) — đừng ngạc nhiên nếu trạng thái đổi giữa các lần mở app, đó là app đang hoạt động đúng.
- **Console Windows không in được tiếng Việt có dấu trực tiếp** (cp1252) khi chạy script rời qua Bash tool — dùng `PYTHONIOENCODING=utf-8` + redirect ra file rồi đọc file, đừng in thẳng ra stdout.
- **`sync/reconcile/check` bác NGUYÊN CẢ request (400) nếu BẤT KỲ record nào trong `records[]` có `server_status`/`final_status` ngoài enum server chấp nhận** (`server_status`: `OK/NG/SKIPPED`; `final_status`: `OK/NG` — KHÔNG nhận `PENDING`/`PENDING_SERVER`, dù đó là default schema của `local_scan_records` cho record chưa từng được server xác nhận, vd `FAILED_BLOCKED` do lỗi cấp batch). Phát hiện thật (lỗi 400 thật) khi build Bước 9 — `db/local_db.py:build_reconcile_payload` đã ép các giá trị này về đúng enum trước khi gửi (`SKIPPED`/`local_status` làm giá trị thay thế) — nếu sau này thêm field mới vào manifest, kiểm tra lại enum server chấp nhận trước, đừng gửi thẳng giá trị cột DB thô.
- **Repo mới có git từ 2026-07-14** (sau khi đã làm xong Bước 1-4) — lịch sử trước đó không có trong git. `.gitignore` loại trừ `venv/`, `__pycache__/`, 3 file cấu hình ở mục 6, `legacy_dotnet_sdk_approach/`.
- **`register_window.py` tự poll bằng `request_id`, `main_window.py` tự poll `identity/status` bằng `serial+uid`** — 2 cơ chế ĐỘC LẬP, chạy song song, cùng ghi `local_app_settings`. Có thể lệch nhịp vài giây nếu cả 2 cùng chạy (dialog đang mở + app đang chạy nền), nhưng tự đồng bộ lại ở lần poll kế tiếp — không cần khoá chéo.
- **Không dùng mock server để test** — luôn test với server thật/dev (địa chỉ đổi qua `server_config.json`). Tự tắt mọi instance app đã tự mở để test xong việc.
- **Quy ước ngôn ngữ**: comment code luôn tiếng Việt (toàn bộ codebase). Text UI: `main_window.py` (màn hình operator) tiếng Việt. `register_window.py`/`config_window.py` (dialog kỹ thuật/admin): tên nút/tiêu đề group box/tiêu đề cột bảng/QMessageBox giữ tiếng Anh (coi như thuật ngữ kỹ thuật), nhưng **label trạng thái/thông báo** (`STATUS_TEXT`, `STATUS_LABELS`, `local_status_message`, mọi `add_local_notification`) đã dịch tiếng Việt — phạm vi dịch đã chốt, không dịch thêm ngoài nhóm này.
- **Trạng thái chia sẻ giữa `MainWindow`/`ConfigWindow` (cùng dùng 1 `ReaderManager`) nên sống trên object dùng chung, KHÔNG nên là 2 dict riêng ở mỗi cửa sổ chỉ đồng bộ theo sự kiện** (vd lúc đóng dialog) — dict riêng tạo ra khoảng trống race condition nếu có sự kiện khác xảy ra đúng lúc đang ở trạng thái chưa đồng bộ. Bug thật đã tự verify + fix: xem mục 10, `reader.is_master`.
- **`python-socketio`: `socketio.Client.connected` KHÔNG đáng tin cậy ngay bên trong handler `connect`** — đọc source `socketio/client.py` xác nhận: `_handle_connect()` gọi `_trigger_event('connect', ...)` (chạy handler `connect` của mình) TRƯỚC KHI set `self._connect_event`, còn `self.connected = True` chỉ được gán SAU ĐÓ, trong thread gọi `.connect()` ban đầu, sau khi thread đó tỉnh dậy từ `_connect_event.wait()`. Nghĩa là handler `connect` LUÔN LUÔN chạy trong lúc `sio.connected` vẫn còn `False` — không phải race hiếm gặp mà là thứ tự cố định. Nếu code trong handler `connect` tự emit gì đó (vd `machine:hello`) mà có guard `if not self._sio.connected: return`, guard đó sẽ ÂM THẦM chặn mọi lần, không có exception, không có gì báo lỗi. Bug thật đã tự verify (trace trực tiếp trên instance sống, `sio.connected=False` mọi lần) + fix: xem `server/runtime_socket_client.py:_emit(..., require_connected=False)`, chỉ dùng cho lời gọi từ trong `_on_connect`.
- **`QThread` chạy `socketio.Client.connect()` rồi `return` ngay sau khi connect thành công SẼ làm mọi event nhận về sau đó (kể cả phản hồi trực tiếp cho gói tin vừa gửi) không bao giờ tới handler nữa**, dù `sio.connected` vẫn báo `True` — đã tự verify bằng 3 script cô lập (function thường: OK; `threading.Thread` thường dù thoát ngay: OK; `QThread` thoát ngay: LỖI; `QThread` giữ sống bằng `.wait()`: OK). Chỉ riêng `QThread` của Qt mới bị — kết luận: `QThread` bọc `socketio.Client` phải sống suốt cả phiên kết nối (chặn ở `threading.Event.wait()` sau khi connect xong), không phải chỉ lo mỗi lần gọi `.connect()` ban đầu. Xem `server/runtime_socket_client.py:_RuntimeConnectWorker`.

## 8. Quy ước làm việc đã thống nhất với user

- Làm **từng endpoint 1** (hoặc vài endpoint liên quan chặt), đúng thứ tự phụ thuộc, mỗi endpoint **hoàn thiện** (kể cả sửa `.ui` nếu cần) và **test xong** (kể cả với server thật) mới sang endpoint kế tiếp — không bundle nhiều endpoint vào 1 lần, không làm bản "tối thiểu" rồi để đó.
- "Wire as you go": bảng DB liên quan tới endpoint đang làm thì wire luôn trong cùng bước, không để dồn lại làm sau.
- Trước khi sửa logic core rủi ro cao (vd đổi nguồn dữ liệu so khớp OK/NG), cân nhắc đề xuất git để có đường lùi — không tự ý `git init`/commit/push nếu chưa được yêu cầu rõ.

## 9. Đóng gói & triển khai ("Local Reader Monitor")

App đóng gói bằng PyInstaller thành `LocalReaderMonitor.exe` (`--onedir`, không phải `--onefile` — onefile giải nén lại vào thư mục tạm ngẫu nhiên mỗi lần chạy, mất hết config/DB giữa các lần mở app, đã tự verify bằng build thật). Hướng dẫn cài đặt đầy đủ cho máy production: **`docs/deploy.md`**.

Điểm quan trọng nhất cho ai sửa code sau này:

- **`app_paths.py`** là nền tảng path resolution — MỌI file cần đọc lúc chạy phải qua `get_writable_dir()` (config JSON, log — user sửa được, nằm cạnh `.exe` thật) hoặc `get_bundle_dir()` (`.ui`/icon/âm thanh/`schema.sql` — chỉ đọc, PyInstaller bundle sẵn trong `_internal/`). KHÔNG tự tính `__file__`/đường dẫn tương đối kiểu cũ — khi đóng gói `--onedir`, mọi thứ tính theo `__file__` sẽ rơi vào `_internal/` chứ không nằm cạnh `.exe`, đã tự verify bằng build thật.
- 3 file config JSON (`local_db_config.json`/`server_config.json`/`readers_config.json`) đọc bằng `encoding="utf-8-sig"` (trừ `readers_config.json` — chỉ app tự ghi, không qua PowerShell) — chấp nhận cả file có/không có BOM, vì `setup.ps1` hoặc thao tác tay bằng PowerShell 5.1 có thể ghi kèm BOM.
- **`setup.ps1` (script PowerShell) BẮT BUỘC phải lưu với UTF-8 BOM** — ngược lại với các file JSON ở trên. PowerShell 5.1 mặc định đọc file `.ps1` không-BOM theo codepage ANSI hệ thống, không phải UTF-8 — comment tiếng Việt có dấu/em-dash trong script sẽ bị hiểu sai byte, gây lỗi parse (`"The string is missing the terminator"`) rất khó đoán nguyên nhân nếu không biết cạm bẫy này. Đã tự verify bằng chạy thật (lỗi thật, không phải suy đoán).
- **Không dùng `2>&1` khi gọi `psql.exe` (hay bất kỳ native exe nào) trong PowerShell 5.1** — PowerShell bọc từng dòng stderr thành `ErrorRecord`, khiến `$ErrorActionPreference="Stop"` dừng cả script chỉ vì psql in 1 dòng NOTICE (vd `DROP TRIGGER IF EXISTS` báo "does not exist, skipping") chứ không phải lỗi thật. Chỉ dựa vào `$LASTEXITCODE` để biết thành công/thất bại, để stderr in thẳng ra console. Xem `Invoke-Psql` trong `setup.ps1`.
- **`main.py`'s crash logging phải tự `try/except` quanh phần khởi động (trước `app.exec_()`) và gọi `sys.exit()` tường minh** — nếu chỉ dựa vào `sys.excepthook` mà để exception lọt ra khỏi `main()`, bootloader PyInstaller bản `--windowed` (`runw.exe`) tự hiện thêm hộp thoại "Unhandled exception in script" của riêng nó (native, không phải do code Python), bất kể `sys.excepthook` đã ghi log xong hay chưa. Đã tự verify bằng build thật — ban đầu tưởng lỗi do gọi `sys.__excepthook__` trong hook, nhưng dựng bản build KHÔNG gọi gì thêm sau khi log vẫn bị hộp thoại này, chứng minh nó độc lập với code Python.
- Chỉ commit khi được yêu cầu rõ ràng.
- **`QApplication.instance().installEventFilter(self)` + widget con không tiêu thụ phím = Qt PHÁT LẠI CÙNG 1 event object lên từng widget cha (propagate)**, gọi lại `eventFilter()` thêm 1 lần cho MỖI cấp cha — nếu logic bên trong tích luỹ trạng thái (vd nối chuỗi ký tự) mà không tự chặn, sẽ bị nhân bản theo đúng số cấp widget cha (đã tự verify bằng bug thật khi làm máy quét HID mục 10 — 1 ký tự bị lặp 4-5 lần). Dedupe bằng `id(event)` **KHÔNG an toàn** — CPython có thể tái sử dụng đúng địa chỉ bộ nhớ cho các `QKeyEvent` ngắn hạn liên tiếp (kể cả giữa 2 lượt xử lý riêng biệt cách nhau, không chỉ trong 1 lần propagate), khiến sự kiện MỚI bị nhận nhầm trùng sự kiện CŨ và bị bỏ qua hoàn toàn (mất dữ liệu). Cách đúng: **luôn `return True` (nuốt hẳn) ngay khi xử lý xong**, không dựa vào so trùng định danh gì cả.

## 10. Máy quét mã vạch cầm tay (Keyboard-HID)

Nguồn nhập liệu thứ 2 song song với reader TCP — `ui/main_window.py`: `eventFilter()` (bắt phím toàn cục qua `QApplication`, phân biệt máy quét vs người gõ tay bằng tốc độ, `HID_SCAN_MAX_GAP_SEC`), `_detect_role_from_content()` (tự suy LED BAR/QRCODE BOTTOM từ nội dung — tiền tố `VN39` cố định = QRCODE BOTTOM, còn lại đều coi là LED BAR, KHÔNG bao giờ bỏ qua mã đã quét được), `_handle_hid_scan()` (tái sử dụng nguyên `on_data_received` pipeline, gán tạm `self._hid_scan_role` thay vì tra `self._reader_roles` — dict đó bị `_sync_reader_panel()` nạp lại từ `readers_config.json` mỗi lần đóng Config Window, sẽ xoá mất entry gán tay cho tên `"HID Scanner"`). Bật/tắt qua checkbox trong Config Window (`hid_scanner_config.json`, xem mục 6), mặc định BẬT. Xem cạm bẫy `eventFilter`/propagate ở mục 7 trước khi sửa phần này.

**Tương tác với ô Chassis Rear**: khi editor của combobox đang có focus,
`eventFilter()` không đưa phím vào HID buffer để operator có thể gõ tìm kiếm
bình thường. Chọn từ autocomplete/dropdown, nhấn Enter hoặc click ra ngoài sẽ
gọi `_finish_chassis_rear_search()`, ẩn popup và `clearFocus()` để trả keyboard
events lại cho HID. Click nền được bắt ở cấp `QApplication` vì Qt không phải
lúc nào cũng phát `editingFinished` khi click panel không focusable. Không thêm
buffer trì hoãn 80 ms. User đã live-test bằng máy quét HID vật lý qua toàn bộ
đường focus trên và xác nhận hoạt động ổn định (2026-07-28).

**`_detect_role_from_content()` dùng chung cho CẢ chế độ Master/Slave** (reader Keyence SR-X): bảng Readers trong Config Window có thêm 1 cột checkbox độc lập **"Master"** NGAY TRÊN TỪNG DÒNG reader (`ConfigWindow._add_table_row`/`on_master_checkbox_toggled`, KHÔNG phải 1 giá trị Role riêng — vẫn giữ nguyên Role LED BAR/QRCODE BOTTOM đã chọn, `readers_config.json` lưu thêm field `is_master`) — tick/bỏ tick được BẤT KỲ LÚC NÀO trong lúc chạy, không cần xoá/thêm lại reader (khác với Role/IP/Port chỉ chọn được lúc thêm mới). Lý do: 1 Slave thật gửi dữ liệu ĐỒNG THỜI qua 2 đường — TCP trực tiếp tới PC, VÀ qua UDP nội bộ Master/Slave của phần cứng tới Master rồi Master lại gửi tiếp qua TCP — nên nếu app kết nối TCP tới CẢ Slave lẫn Master, dữ liệu Slave bị nhận 2 lần. `MainWindow._is_master_mode_active()` (`any(self._reader_is_master(n) for n in self.manager.names())`, tính lại mỗi lần gọi, không cache) quyết định "chế độ" hiện tại: hễ có ÍT NHẤT 1 reader bật cờ này, `on_data_received()` sẽ (1) bỏ qua HOÀN TOÀN dữ liệu từ mọi reader KHÔNG bật cờ (Slave — tránh đếm trùng), (2) với (các) reader Master, tự suy role qua `_detect_role_from_content()` thay vì tin theo Role cố định (Master relay cả dữ liệu của chính nó lẫn Slave, không còn "1 reader = 1 vai trò" nữa). Nếu KHÔNG reader nào bật cờ này, hành vi giữ nguyên như cũ (chế độ TCP độc lập, mỗi reader xử lý theo Role đã gán).

**Cờ `is_master` sống TRỰC TIẾP trên object reader** (`reader.is_master`, thuộc tính của `SRXReaderQt` — `reader/reader_bridge.py`), **KHÔNG phải dict riêng ở từng cửa sổ**. `MainWindow._reader_is_master(name)` chỉ là 1 method đọc thẳng `self.manager.get(name).is_master`, không cache. Lý do bắt buộc phải thiết kế vậy: bản đầu tiên dùng 2 dict riêng (`ConfigWindow._is_master` và `MainWindow._reader_is_master` — dict, không phải method như hiện tại), chỉ đồng bộ lúc đóng Config Window (`_sync_reader_panel()`) — gây **1 bug thật đã tự verify** (hẹp, chỉ xảy ra nếu có mã quét tới ĐÚNG lúc dialog Config đang mở): tick checkbox Master ngay trên dòng trong lúc dialog Config vẫn đang mở (tính năng "đổi bất kỳ lúc nào không cần đóng dialog" ở trên), nếu dữ liệu Slave tới ĐÚNG lúc đó thì `MainWindow` vẫn đọc dict CŨ (chưa đồng bộ) và xử lý nhầm dữ liệu Slave. Vì `MainWindow`/`ConfigWindow` luôn dùng CHUNG 1 `ReaderManager` (truyền qua constructor), đưa cờ lên thẳng object reader khiến 2 cửa sổ luôn thấy CÙNG 1 giá trị tức thời — không còn khái niệm "chưa đồng bộ" nữa, dù dialog đang mở hay đóng. Test tái hiện đúng kịch bản race condition này (mở `ConfigWindow` thật, tick Master trong lúc KHÔNG đóng dialog, gọi `on_data_received` ngay sau) nằm trong `test_master_slave_mode.py` (case "RACE CONDITION"). **Lưu ý: đây KHÔNG phải nguyên nhân của bug "lâu lâu vẫn nhận của slave" user báo cáo thật trên dây chuyền** — xem đoạn ngay bên dưới.

**Bug thật sự user báo cáo** ("lâu lâu vẫn còn nhận của slave mặc dù đã tích master... ngẫu nhiên nhưng tần suất nhiều, Config đã đóng từ lâu không đụng gì mà vẫn bị") — biểu hiện thật: 1 phiên vừa quét đủ và chốt OK, banner/kết quả CHƯA KỊP hiện (hoặc vừa hiện) thì màn hình tự xoá ngay. **KHÔNG liên quan đến dialog Config mở/đóng** — nguyên nhân là THỨ TỰ xử lý sai trong `on_data_received()`: khối "có mã mới → tự xoá kết quả phiên trước" (cờ `self._session_pending_clear`, chỉ bật khi phiên vừa chốt OK — xem `_finalize_scan_session()`, comment "chờ mã mới của sản phẩm tiếp theo mới xoá, để operator kịp nhìn kết quả") từng chạy TRƯỚC khối bỏ qua dữ liệu Slave khi đang ở chế độ Master. Slave thật vẫn giữ nguyên kết nối TCP trực tiếp song song với Master (không bị ngắt khi bật Is Master — Is Master chỉ lọc bỏ dữ liệu ở tầng xử lý, không đóng socket), nên bản sao TRÙNG LẶP của mã cuối cùng trong phiên vẫn tới qua Slave — do Master phải relay thêm qua 1 chặng UDP/TCP nội bộ phần cứng nên bản sao của Slave **thường tới SAU Master**, tức là sau khi phiên đã chốt xong. Dữ liệu trùng này tuy vẫn bị lọc bỏ đúng lúc so khớp (không lên cột nào), nhưng ĐÃ kịp kích hoạt "có mã mới" TRƯỚC KHI bị lọc bỏ, tự xoá mất banner/kết quả vừa chốt — khớp đúng mô tả "ngẫu nhiên nhưng tần suất nhiều" (xảy ra bất cứ khi nào bản sao của Slave tới sau khi Master đã chốt phiên, không phụ thuộc Config Window). **Fix**: khối bỏ qua Slave chuyển thành **điều kiện ĐẦU TIÊN** trong `on_data_received()` (chỉ sau `_scan_blocked`) — KHÔNG chỉ "đổi chỗ 2 khối", mà đặt hẳn thành dòng đầu tiên để loại bỏ hẳn kiểu bug "phụ thuộc thứ tự": sau này có thêm bao nhiêu bước xử lý mới trong hàm cũng không thể vô tình chèn trước khối này nữa. Slave bị bỏ qua HOÀN TOÀN — kể cả `_update_reader_input()` (cập nhật cột "Input" trên bảng Reader màn hình chính) cũng nằm SAU khối này, nên khi đang chế độ Master, cột Input của Slave dừng cập nhật luôn (theo yêu cầu user: "không quan tâm slave" — trước đó Input vẫn cập nhật để chẩn đoán, đã đổi theo lựa chọn của user). Đã tự verify bằng cách tạm revert về thứ tự cũ — test FAIL đúng 4/14 case liên quan, khôi phục đúng thì PASS lại 14/14 — xem `test_master_slave_session_clear_bug.py` (dựng 1 phiên OK thật qua Master bằng dữ liệu profile thật, gửi thêm 1 bản sao trùng qua Slave, xác nhận `_clear_session()` — hàm xoá hiển thị thật — KHÔNG bị gọi) và `test_master_slave_mode.py` case "3b" (xác nhận cột Input của Slave không cập nhật, còn Master vẫn cập nhật bình thường).

## 11. Kích hoạt license cục bộ — tính năng phụ, đang bypass

Luồng chính vẫn là đăng ký server bằng `serial`+`uid`, chờ admin duyệt và kiểm tra `identity/status`. Đây là gate duy nhất quyết định `local_runtime_status`, `_scan_blocked` và quyền quét.

Package `licensing/` vẫn được giữ để verify license Ed25519 hoàn toàn offline.
Dialog `"Machine Registration"` có tab Registration ở trước và tab License ở
sau, nhưng **tab License hiện đang disable** bằng
`ui/register_window.py:LICENSE_TAB_ENABLED = False` theo yêu cầu tạm thời. Toàn
bộ widget/service license vẫn được giữ; khi cần dùng lại chỉ đổi flag sau khi có
approval và test license thật. Dù bật hay tắt, kết quả license không gọi ngược
`MainWindow`, không đổi banner/gate và không tác động registration.

**Cách ly DB bắt buộc**:

- License chỉ dùng cột `machine_license_key`.
- `evaluate_local_license()` tính lại Machine ID và trạng thái `active`/`unactivated`/`invalid` mỗi lần gọi, không lưu Machine ID/trạng thái vào DB.
- `activate_local_license()` chỉ ghi `machine_license_key` khi verify thành công.
- `machine_code`, `registration_status`, `license_activated_at` và `local_runtime_status` thuộc luồng đăng ký server; code license tuyệt đối không ghi các cột này.

**Cơ chế**: `licensing/license_client.py:get_machine_id()` hash SHA-256 từ BIOS/SMBIOS UUID (fallback MachineGuid nếu rác), khác thuật toán `machine/hardware_id.py` dùng cho `serial`/`uid`. `verify_license()` dùng public key Ed25519 nhúng sẵn; private key/công cụ ký không nằm trong repo.

**Việc gửi `machine_code`+`license_key` lên API server mới** sẽ làm sau khi contract/API sẵn sàng; lần này không sửa hoặc thêm API server.

**Nút "Xuất file thông tin máy"** (`pushButtonExportMachineInfo` → `on_export_machine_info_clicked` → `licensing/service.py:build_machine_info_export()`) — theo yêu cầu user: operator KHÔNG cần tự đọc/gõ lại Machine ID hay trao đổi riêng với bên cấp license, chỉ cần xuất 1 file JSON (qua `QFileDialog`) rồi gửi nguyên file đó. File gồm `machine_id`, `app_version`, `app_release_date`, `app_product`, `local_db_version`, `exported_at`. **KHÔNG có `hostname`** (tạm bỏ theo yêu cầu — giá trị dễ đổi, không phải định danh ổn định như `machine_id`, không nên dùng để phân biệt máy). **Lưu ý**: License-Key-main KHÔNG định nghĩa sẵn format file "machine info export" nào (khác hẳn API cũ của Samsung server, có contract `license-export`/`license/import` rõ ràng) — cấu trúc JSON này do dự án tự thiết kế dựa trên các field hợp lý sẵn có, cần đối chiếu lại với đúng tool bên cấp license đang dùng để import (có thể cần đổi tên field cho khớp).

**`APP_PRODUCT`** (như `APP_VERSION`/`APP_RELEASE_DATE`) sống ở `ui/main_window.py` (không phải file `licensing/` riêng — đã gộp về 1 chỗ cho dễ tìm, cả 3 đều là "cấu hình bắt buộc trước khi build" theo `E:\License-Key-main\INTEGRATION.md` mục 3). `ui/register_window.py` nhận cả 3 giá trị qua tham số constructor (`app_version`/`app_release_date`/`app_product`), không tự import — giống hệt cách `APP_VERSION`/`APP_RELEASE_DATE` đã làm, tránh vòng lặp import với `main_window.py`.

**Dependency mới**: `pynacl` (verify Ed25519) — `LocalReaderMonitor.spec` KHÔNG cần sửa `hiddenimports`, `_pyinstaller_hooks_contrib` đã có sẵn `hook-nacl.py` tự động bundle đúng `nacl/_sodium.pyd` (đã tự verify bằng build `--onedir` thật).
