# Dev notes — SR-X Reader Monitor

> **Đọc file này ĐẦU TIÊN** nếu quay lại project sau một thời gian dài / mất ngữ cảnh phiên làm việc. Mục tiêu: nắm được project đang ở đâu, vì sao lại như vậy, và cạm bẫy nào cần tránh — mà không phải đọc lại từng file hay suy luận lại từ đầu.
>
> Cập nhật file này khi có thay đổi lớn (thêm 1 bước tích hợp server, đổi kiến trúc, phát hiện cạm bẫy mới...). Không cần cập nhật cho từng commit nhỏ.

## 1. Project này là gì

Ứng dụng desktop PyQt5 chạy trên máy tính đặt tại 1 trạm QA trên dây chuyền sản xuất Samsung. Đọc mã vạch/QR từ 3 đầu đọc **Keyence SR-X** (LED BAR 1, LED BAR 2, QRCODE BOTTOM) qua TCP, so khớp cục bộ với PostgreSQL, và đồng bộ với 1 server trung tâm (NestJS) để server theo dõi/tổng hợp dữ liệu QA toàn nhà máy.

Đây là bản viết lại bằng Python thay cho 1 bản .NET cũ (xem `legacy_dotnet_sdk_approach/` — giữ lại để tham khảo SDK gốc của Keyence, không phải code đang chạy).

## 2. Bản đồ thư mục

| Thư mục/file | Vai trò |
| --- | --- |
| `main.py` | Entry point — chạy `python main.py` (trong `venv`) |
| `ui/main_window.py` + `.ui` | Màn hình chính: nhận scan, so khớp OK/NG, gate màn scan theo trạng thái đăng ký/config |
| `ui/register_window.py` + `.ui` | Dialog đăng ký máy với server (tiếng Anh) |
| `ui/config_window.py` + `.ui` | Dialog cấu hình reader (thêm/xoá/sửa IP, port) (tiếng Anh) |
| `ui/mapping_window.ui` | Dialog xem danh sách profile/mapping (chỉ hiển thị) |
| `reader/reader_bridge.py` | `ReaderManager` — quản lý nhiều reader, mỗi reader 1 `QThread` giữ kết nối TCP sống |
| `reader/SRX_comm.py` | Giao thức tầng thấp nói chuyện với đầu đọc Keyence SR-X |
| `reader/reader_store.py` | Đọc/ghi danh sách reader đã cấu hình — `reader/readers_config.json` (gitignored, riêng từng máy) |
| `data/mapping_store.py` | `load_mappings()` — **đọc DB thật** (`profile_cache`/`profile_led_code_cache`), KHÔNG còn là mock — xem mục 5 |
| `data/duplicate_key.py` | Tính `duplicate_key` từ mã QR đầy đủ |
| `db/local_db.py` | Toàn bộ hàm truy cập Postgres — điểm ghi duy nhất cho mọi bảng |
| `db/schema.sql` | DDL đầy đủ 16 bảng — **nguồn chân lý cho schema**, đọc file này thay vì suy luận từ code |
| `db/local_db_config.json` | Cấu hình kết nối Postgres (có mật khẩu) — **gitignored**, xem mục 6 để biết cách tạo |
| `db/seed_full_schema.py` | Script dev-only sinh dữ liệu mẫu — xem mục 7 (cạm bẫy) trước khi chạy |
| `machine/hardware_id.py` | Đọc BIOS UUID + serial mainboard qua PowerShell WMI |
| `machine/identity.py` | `ensure_machine_identity()` — cache serial/uid vào `local_app_settings` |
| `server/api_client.py` | `SamsungQrServerClient` — REST client, transcribe gần như nguyên văn từ doc API (mục 22 của doc) |
| `server/server_worker.py` | `ServerWorker(QThread)` — 1 thread nền xử lý hàng đợi job gọi API, không chặn GUI |
| `server/server_config.json` | Host/port server hiện tại — **gitignored**, đổi qua nút "Change Server IP" trên `main_window` |
| `docs/10-huong-dan-api-may-local-python (2).md` | **Doc API chuẩn, đọc file này** (không phải bản không có "(2)" — bản cũ hơn, ít nội dung hơn) |
| `docs/11-sql-khoi-tao-db-may-local-python-postgres (3).md` | Doc SQL tham khảo mới nhất (không phải bản "(2)") — nhưng `db/schema.sql` mới là DDL thật đang chạy |
| `tools/` | `mock_reader_server.py`/`mock_codes.json` — giả lập đầu đọc để test không cần phần cứng thật |

## 3. Luồng nghiệp vụ chính (scan → OK/NG)

1. Operator chọn **Chassis Rear** ở combobox (nạp từ `data/mapping_store.load_mappings()`, tức từ `profile_cache`).
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

**Việc CHƯA làm**: gửi kết quả lên server (`POST /api/scans/submit`). Khi làm, đã thống nhất trước UX: sau khi local OK, item QR bottom chuyển **VÀNG** (không phải xanh ngay), `labelResultStatus` CHƯA hiện "OK" — chỉ khi server xác nhận `SERVER_OK` mới chuyển xanh + hiện "OK". Nguyên tắc: "chỉ so OK với OK" áp dụng cả với việc chờ server, không tự ý coi local-OK là final.

## 4. Tích hợp server — đã làm tới đâu

Theo dõi theo "Bước" (từng bước 1 API/nhóm API nhỏ, làm xong + test xong mới sang bước sau — xem mục 8). Tính đến thời điểm viết file này:

| Bước | Endpoint | Trạng thái | File chính |
| --- | --- | --- | --- |
| 1 | `GET /api/health` | ✅ Xong. QTimer 15s, `labelServerStatus` + `pushButtonChangeServerIp` | `main_window.py` (`_check_server_health`, `_apply_server_online`) |
| 2 | `POST /api/machines/register-request` + `GET .../register-requests/:id/status` | ✅ Xong. Dialog riêng, auto-poll khi PENDING | `ui/register_window.py` |
| 3 | `GET /api/machines/identity/status` | ✅ Xong. Tự gọi lúc mở app + định kỳ khi chưa READY. **Gate màn scan chính** theo `local_runtime_status` | `main_window.py` (`_handle_identity_status_result`, `_apply_runtime_status`) |
| 4 | `GET /api/machines/config` | ✅ Xong, đã verify với server thật. Tự gọi ngay sau khi identity/status APPROVED. Ghi `machine_cache`/`server_settings_cache`/`profile_cache`/`profile_led_code_cache`/`vendor_cache`/`command_inbox` | `main_window.py` (`_handle_config_result`), `db/local_db.py` (`apply_machine_config`) |
| 5+ | `commands/poll` + `commands/:id/ack` | ❌ Chưa làm. `command_inbox` đã có data (`pending_commands` từ config) nhưng CHƯA xử lý/ack | — |
| — | `heartbeat` | ❌ Chưa làm | — |
| — | `scans/submit` | ❌ Chưa làm — xem UX vàng/xanh ở mục 3 | — |
| — | `sync/batches/submit`, `sync/reconcile/*` | ❌ Chưa làm | — |
| — | Socket.IO `/machine-runtime` | ❌ Chưa làm — cần `machine_code` (đã có) + config (đã có) + khái niệm "Start/Stop 1 lượt chạy" (main_window CHƯA có nút này) | — |

**`data/mapping_store.py` đã đổi nguồn dữ liệu (Bước 4)**: trước đây là list Python hardcode (`_MOCK_MAPPINGS`), giờ đọc thật từ `profile_cache`/`profile_led_code_cache` (đã sync từ server). Đây là logic **quyết định OK/NG** — nếu combobox Chassis Rear trống hoặc sai, kiểm tra `profile_cache WHERE is_active=true` trước, không phải sửa `mapping_store.py`.

### Cách thêm 1 endpoint mới (đã lặp lại 4 lần, quy trình ổn định)

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

Chỉ `READY`/`SCANNING`/`SYNCING` (`SCAN_ENABLED_STATUSES` trong `main_window.py`) mới cho phép scan. Mọi trạng thái khác đều chặn.

## 6. File cấu hình riêng từng máy (gitignored)

3 file này **không có trong git**, phải tự tạo khi setup máy mới:

**`db/local_db_config.json`**:
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

**`server/server_config.json`** (tự tạo lần đầu qua nút "Change Server IP" nếu chưa có, mặc định `127.0.0.1:3979`):
```json
{ "host": "192.168.100.1", "port": 3979 }
```

**`reader/readers_config.json`** — danh sách reader đã cấu hình qua dialog Configure, tự sinh khi bấm "Add reader" lần đầu, không cần tạo tay.

## 7. Lưu ý quan trọng / cạm bẫy

- **psycopg3 KHÔNG nhận `col IN %s` với tuple** như psycopg2 — lỗi `syntax error at or near "$2"`. Phải dùng `col = ANY(%s)` với **list** Python (không phải tuple). Xem `db/local_db.py:apply_machine_config` để làm ví dụ.
- **KHÔNG bao giờ `DELETE`/`TRUNCATE` thẳng `profile_cache`** nếu đã có scan ghi nhận — `local_scan_records.profile_id` có FK `ON DELETE RESTRICT`, xoá sẽ crash. Luôn UPSERT + soft-delete (`is_active=false`) cho profile không còn trong response mới. Cùng lý do, `profile_led_code_cache`/`vendor_cache`/`machine_cache`/`server_settings_cache` cũng nên UPSERT, không DELETE.
- **`db/seed_full_schema.py` vẫn TRUNCATE `local_app_settings`** mỗi lần chạy (registration_status, machine_code, machine_serial/uid...) — chạy lại script này trên máy đã đăng ký thật với server SẼ xoá mất tiến trình đăng ký. 5 bảng cache (`profile_cache` và 4 bảng liên quan) đã đổi sang `ON CONFLICT DO NOTHING` nên an toàn hơn, nhưng `local_app_settings` thì chưa — cân nhắc trước khi chạy trên máy có dữ liệu thật.
- **Dữ liệu đăng ký máy trên server dev/test có thể tự đổi** ngoài ý muốn của local (quan sát được nhiều lần trong quá trình phát triển: APPROVED → DISABLED → NOT_REGISTERED → APPROVED lại, không phải do bug local). App được thiết kế để tự đồng bộ lại theo bất cứ gì server trả về (server là nguồn chân lý) — đừng ngạc nhiên nếu trạng thái đổi giữa các lần mở app, đó là app đang hoạt động đúng.
- **Console Windows không in được tiếng Việt có dấu trực tiếp** (cp1252) khi chạy script rời qua Bash tool — dùng `PYTHONIOENCODING=utf-8` + redirect ra file rồi đọc file, đừng in thẳng ra stdout.
- **Repo mới có git từ 2026-07-14** (sau khi đã làm xong Bước 1-4) — lịch sử trước đó không có trong git. `.gitignore` loại trừ `venv/`, `__pycache__/`, 3 file cấu hình ở mục 6, `legacy_dotnet_sdk_approach/`.
- **`register_window.py` tự poll bằng `request_id`, `main_window.py` tự poll `identity/status` bằng `serial+uid`** — 2 cơ chế ĐỘC LẬP, chạy song song, cùng ghi `local_app_settings`. Có thể lệch nhịp vài giây nếu cả 2 cùng chạy (dialog đang mở + app đang chạy nền), nhưng tự đồng bộ lại ở lần poll kế tiếp — không cần khoá chéo.
- **Không dùng mock server để test** — luôn test với server thật/dev (địa chỉ đổi qua `server/server_config.json`). Tự tắt mọi instance app đã tự mở để test xong việc.
- **Quy ước ngôn ngữ**: comment code luôn tiếng Việt (toàn bộ codebase). Text UI: `main_window.py` (màn hình operator) tiếng Việt; `register_window.py`/`config_window.py` (dialog kỹ thuật/admin) tiếng Anh.

## 8. Quy ước làm việc đã thống nhất với user

- Làm **từng endpoint 1** (hoặc vài endpoint liên quan chặt), đúng thứ tự phụ thuộc, mỗi endpoint **hoàn thiện** (kể cả sửa `.ui` nếu cần) và **test xong** (kể cả với server thật) mới sang endpoint kế tiếp — không bundle nhiều endpoint vào 1 lần, không làm bản "tối thiểu" rồi để đó.
- "Wire as you go": bảng DB liên quan tới endpoint đang làm thì wire luôn trong cùng bước, không để dồn lại làm sau.
- Trước khi sửa logic core rủi ro cao (vd đổi nguồn dữ liệu so khớp OK/NG), cân nhắc đề xuất git để có đường lùi — không tự ý `git init`/commit/push nếu chưa được yêu cầu rõ.
- Chỉ commit khi được yêu cầu rõ ràng.
