# Hướng dẫn tích hợp API cho máy local Python

Tài liệu này dành cho đội phát triển chương trình máy local Python trong hệ thống Samsung QR Recorder Server. Mục tiêu là giải thích đầy đủ các API mà máy local cần tương tác, chức năng của từng API, lý do cần gọi, request body, response body, error code, notification, command polling, offline sync và cách áp dụng đúng trong dự án Python.

Contract trong tài liệu bám theo backend hiện tại:

```txt
backend/src/modules/health
backend/src/modules/machines
backend/src/modules/scans
backend/src/modules/sync
backend/src/modules/notifications
prisma/schema.prisma
shared/src/index.ts
scripts/seed-users.mjs
```

Ngày cập nhật: 2026-07-13.

## 1. Vai trò của máy local và server

Luồng tổng thể:

```txt
Máy local Python
  -> gọi API qua LAN
  -> NestJS backend trên máy server
  -> Prisma
  -> PostgreSQL
```

Máy local Python chịu trách nhiệm:

- đọc QR/barcode;
- parse full code, chassis code và LED raw;
- kiểm format theo profile cache;
- kiểm vendor, factory, chassis, LED suffix;
- kiểm duplicate trong phạm vi local nếu dự án local yêu cầu;
- lưu local DB trước khi gửi server;
- gửi scan OK và scan NG lên server;
- lưu pending khi mất mạng;
- sync lại pending khi reconnect;
- poll command từ server.

Server chịu trách nhiệm:

- quản lý máy local được phép kết nối;
- quản lý profile, chassis, vendor, LED code;
- nhận heartbeat;
- nhận scan;
- kiểm duplicate trong cửa sổ server, mặc định thường là 30 hoặc 31 ngày;
- lưu trace toàn bộ scan OK và NG;
- lưu request log, sync batch, notification và audit;
- trả kết quả cuối cùng cho máy local.

Nguyên tắc nghiệp vụ quan trọng nhất:

```txt
Chỉ so sánh OK với OK.
```

Điều này có nghĩa:

- Local OK mới được server kiểm duplicate.
- Local NG vẫn gửi server để lưu trace.
- Local NG không được insert vào bảng `recent_duplicate_keys`.
- Server duplicate chỉ so sánh với record đã final OK.
- Local không được hiển thị final OK nếu chưa nhận `SERVER_OK`.

## 2. Base URL

Trong dev trên chính máy server:

```txt
http://127.0.0.1:3979/api
```

Trong nhà máy:

```txt
http://SERVER-IP:3979/api
```

Ví dụ:

```txt
http://192.168.1.10:3979/api
```

Máy local chỉ gọi backend NestJS. Máy local không gọi Next.js UI, không gọi Electron và không kết nối trực tiếp PostgreSQL của server. Database PostgreSQL local là database riêng trên máy local.

## 3. Swagger

Swagger chạy tại:

```txt
http://SERVER-IP:3979/api/docs
```

Trong dev:

```txt
http://127.0.0.1:3979/api/docs
```

Swagger là nguồn đối chiếu nhanh về endpoint và DTO. Tài liệu này giải thích thêm nghiệp vụ, flow Python và cách xử lý đúng.

Trong Swagger, người code máy local chỉ cần xem tag `local-machine`. Các tag `machines-admin`, `machine-commands-admin`, `scan-dashboard`, `sync-dashboard` và `server-ui` là API cho màn hình server/admin/dashboard, không phải API local cần tích hợp.

## 4. Authentication

Các API dành cho máy local hiện tại không dùng Bearer token. Máy local được định danh bằng bộ `machine_code` + `serial` + `uid`. Khi gửi yêu cầu định danh lần đầu, local gửi thêm `license_key` raw để server lưu lại làm dữ liệu kích hoạt tạm thời.

Khi máy local khởi động, local nên gửi `serial` và `uid` để hỏi server trước. Vì `serial` lấy từ mainboard và `uid` là định danh ổn định của máy local, server có thể trả lại `machine_code` nếu máy đã được định danh. Nếu chưa có trên server, local mới gửi yêu cầu kết nối.

Các endpoint local public:

| Method | Path | Mục đích |
| --- | --- | --- |
| `GET` | `/api/health` | Kiểm tra API server sống. |
| `GET` | `/api/machines/identity/status?serial=...&uid=...` | Máy local startup bằng serial/uid để lấy lại `machine_code` hoặc trạng thái pairing. |
| `POST` | `/api/machines/register-request` | Máy local mới gửi yêu cầu kết nối bằng `serial`, `uid`, `license_key`, `ip_address`. |
| `GET` | `/api/machines/register-requests/:request_id/status` | Máy local tự kiểm tra server đã duyệt/định danh hay chưa. |
| `GET` | `/api/machines/:machine_code/config?serial=...&uid=...` | Lấy config server, profile active và command pending. |
| `POST` | `/api/machines/heartbeat` | Báo trạng thái online, IP, version, pending sync. |
| `GET` | `/api/machines/:machine_code/commands/poll?serial=...&uid=...` | Local chủ động lấy command từ server. |
| `POST` | `/api/machines/commands/:id/ack` | Local xác nhận đã xử lý command. |
| `POST` | `/api/scans/submit` | Gửi một scan OK hoặc NG lên server. |
| `POST` | `/api/sync/batches/submit` | Gửi batch pending hoặc offline scan. |

Server kiểm `machine_code`, `serial`, `uid` có khớp máy đã được định danh hay không. Nếu máy chưa đăng ký hoặc đã bị tắt, server trả `MACHINE_NOT_FOUND`. Nếu `machine_code` đúng nhưng `serial` hoặc `uid` không khớp, server trả `MACHINE_IDENTITY_MISMATCH`.

### Tóm tắt luồng định danh

Khi local khởi động:

1. Local gọi `GET /api/health`.
2. Local gọi `GET /api/machines/identity/status?serial=...&uid=...`.
3. Nếu server trả `MACHINE_IDENTITY_APPROVED`, local lấy `machine_code` từ response và gọi `/config`.
4. Nếu server trả `MACHINE_REGISTER_PENDING`, local tiếp tục chờ server định danh.
5. Nếu server trả `MACHINE_IDENTITY_NOT_REGISTERED`, local gọi `POST /api/machines/register-request` kèm `license_key`.
6. Server admin/dev xuất file thông tin máy gồm `serial` và `uid`, import file license raw để kích hoạt, sau đó mới duyệt và đặt `machine_code`, tên máy.
7. Local tiếp tục poll `identity/status` hoặc `request_id/status`; khi server duyệt xong, local nhận `machine_code`.
8. Nếu server trả `MACHINE_REGISTER_DUPLICATE` hoặc `MACHINE_IDENTITY_MISMATCH`, local hiển thị lỗi trùng/sai định danh và dừng pairing.

Chi tiết request, response và cách xử lý của 3 API định danh nằm ở các mục `8`, `9`, `10`.

### Phân nhóm API máy local

Người code máy local chỉ cần quan tâm các nhóm sau:

| Nhóm | API | Khi nào dùng | Local cần lưu/cập nhật |
| --- | --- | --- | --- |
| Kết nối server | `GET /api/health` | Startup, reconnect, trước khi submit/sync nếu cần kiểm nhanh. | `server_online`, `last_health_at`, `local_runtime_status`. |
| Định danh máy | `GET /api/machines/identity/status` | Startup bằng `serial`, `uid` để lấy lại `machine_code` hoặc biết đang chờ duyệt. | `machine_code`, `registration_status`, `license_activated_at`, `local_runtime_status`. |
| Gửi yêu cầu định danh | `POST /api/machines/register-request` | Máy mới chưa có trên server. | `registration_request_id`, `registration_status`, `machine_license_key`, `local_runtime_status`. |
| Poll yêu cầu định danh | `GET /api/machines/register-requests/:request_id/status` | Đã gửi request và đang chờ server import license/duyệt. | `registration_status`, `license_activated_at`, `machine_code`, `local_runtime_status`. |
| Tải cấu hình | `GET /api/machines/:machine_code/config` | Sau khi approved, khi profile đổi, khi command yêu cầu reload. | settings cache, profile cache, machine cache, `last_config_sync_at`. |
| Runtime máy | `POST /api/machines/heartbeat` | Định kỳ khi đã có `machine_code`. | `last_heartbeat_at`, tổng record, pending sync. |
| Runtime realtime | Socket.IO namespace `/machine-runtime` | Sau khi đã có `machine_code`, khi bắt đầu/dừng chạy, đổi mã hàng, cập nhật OK/NG realtime hoặc reconnect. | Không bắt buộc đổi DB local; nên lưu trạng thái socket hiện tại vào `local_runtime_status`/log local. |
| Lệnh server | `GET /commands/poll`, `POST /commands/:id/ack` | Local chủ động nhận lệnh vì server không gọi ngược local. | `command_inbox`, notification local. |
| Scan realtime | `POST /api/scans/submit` | Mỗi scan OK/NG khi server online. | `server_status`, `final_status`, `sync_status`. |
| Offline sync | `POST /api/sync/batches/submit` | Startup/reconnect/manual khi có pending. | `sync_batches`, `sync_batch_items`, từng record trong `local_scan_records`. |

API admin/dev liên quan license như export/import/approve chỉ nằm trên Server UI, máy local không gọi trực tiếp.

## 5. Response chuẩn

Hầu hết response nghiệp vụ có dạng:

```json
{
  "success": true,
  "code": "SERVER_OK",
  "message": "Server accepted scan. No duplicate was detected.",
  "data": {}
}
```

Ý nghĩa:

| Field | Kiểu | Ý nghĩa |
| --- | --- | --- |
| `success` | boolean | Request nghiệp vụ thành công hay thất bại. |
| `code` | string | Mã kết quả chuẩn để máy local xử lý logic. |
| `message` | string | Message dễ đọc để log hoặc hiển thị. Không parse logic từ field này. |
| `data` | object hoặc array | Dữ liệu chi tiết tùy endpoint. |

Máy local phải xử lý theo `code`, không xử lý theo `message`.

Lưu ý: nếu request sai schema, NestJS validation có thể trả body lỗi mặc định với `statusCode`, `message` và `error`. Python local nên log toàn bộ body lỗi.

## 6. Flow tích hợp chuẩn trong app Python

### 6.1. Startup

Khi chương trình local mở lên:

1. Đọc `server_ip`, `api_port`, `machine_code`, `serial`, `uid` từ cấu hình local.
2. Gọi `GET /api/health`.
3. Gọi `GET /api/machines/identity/status?serial=...&uid=...` để lấy lại `machine_code` hoặc trạng thái pairing.
4. Nếu chưa đăng ký, gửi `POST /api/machines/register-request` và chờ server duyệt.
5. Nếu server online và đã được định danh, gọi `GET /api/machines/:machine_code/config?serial=...&uid=...`.
6. Lưu `settings` và `profiles` vào local cache.
7. Gửi heartbeat lần đầu bằng `POST /api/machines/heartbeat`.
8. Poll command bằng `GET /api/machines/:machine_code/commands/poll?serial=...&uid=...`.
9. Nếu local DB có record pending, gửi batch bằng `POST /api/sync/batches/submit`.
10. Chuyển UI local sang trạng thái sẵn sàng scan.

Nếu server offline:

1. Hiển thị trạng thái server offline trên local UI.
2. Vẫn cho phép scan theo profile cache nếu policy local cho phép.
3. Mọi scan mới phải lưu local DB với trạng thái pending server.
4. Khi reconnect, gửi batch pending.

### 6.2. Runtime

Trong lúc app local chạy:

- gửi heartbeat định kỳ;
- giữ kết nối Socket.IO `/machine-runtime` sau khi đã định danh;
- emit `runtime:start` khi bắt đầu chạy;
- emit `runtime:update` khi có scan mới hoặc số liệu OK/NG thay đổi;
- emit `runtime:snapshot` định kỳ và ngay sau reconnect;
- emit `runtime:stop` khi dừng chạy;
- poll command định kỳ;
- mỗi scan lưu local DB trước;
- submit scan realtime nếu server online;
- giữ pending nếu server timeout hoặc mất kết nối;
- khi reconnect, emit lại `machine:hello`, gửi `runtime:snapshot`, rồi gửi batch pending nếu có.

Khuyến nghị heartbeat interval nhỏ hơn `heartbeat_timeout_seconds`. Nếu server setting là 60 giây, local nên heartbeat mỗi 5 đến 15 giây.

Khuyến nghị Socket.IO snapshot interval là 3 đến 10 giây khi đang chạy. Không gửi quá dày nếu không có thay đổi vì `POST /api/scans/submit` vẫn là API ghi từng scan chính thức.

### 6.3. Scan local OK

Luồng đúng:

```txt
scan raw
  -> parse theo profile cache
  -> local validate OK
  -> lưu local DB
  -> POST /api/scans/submit với local_status = OK
  -> server trả SERVER_OK hoặc SERVER_DUPLICATE
  -> local cập nhật final status
```

Nếu server trả `SERVER_OK`, local hiển thị OK.

Nếu server trả `SERVER_DUPLICATE`, local hiển thị NG do server duplicate.

Nếu mất mạng, local giữ trạng thái pending server. Không được hiển thị final OK.

### 6.4. Scan local NG

Luồng đúng:

```txt
scan raw
  -> parse hoặc validate fail
  -> lưu local DB với local NG
  -> POST /api/scans/submit với local_status = NG
  -> server trả LOCAL_NG_SAVED
  -> local đánh dấu đã sync trace
```

Server không kiểm duplicate với local NG.

### 6.5. Offline sync

Khi offline:

- local vẫn lưu mọi scan;
- local OK chưa có server OK phải là pending server;
- local NG vẫn lưu đầy đủ payload để gửi trace;
- khi reconnect, local gom pending thành batch;
- local xử lý kết quả từng record trong `data.results`.

### 6.6. Trạng thái UI local cần hiển thị

App local nên có một trạng thái tổng hợp để operator/kỹ thuật viên nhìn vào là biết máy đang ở đâu trong flow. Trạng thái này nên lưu vào bảng `local_app_settings`:

- `local_runtime_status`
- `local_status_message`
- `local_status_updated_at`

Danh sách trạng thái chuẩn:

| `local_runtime_status` | Khi nào set | UI nên hiển thị |
| --- | --- | --- |
| `BOOTING` | App vừa mở, đang đọc config local và kiểm server. | Đang khởi động. |
| `SERVER_OFFLINE` | `GET /api/health`, heartbeat, submit hoặc sync timeout. | Mất kết nối server, scan sẽ lưu pending. |
| `NOT_REGISTERED` | `identity/status` trả `MACHINE_IDENTITY_NOT_REGISTERED`. | Máy chưa gửi yêu cầu định danh. |
| `REGISTERING` | Đang gọi `POST /api/machines/register-request`. | Đang gửi yêu cầu định danh. |
| `WAITING_LICENSE` | Request đang `PENDING` và `license_activated_at = null`. | Đã gửi yêu cầu, chờ server import license. |
| `WAITING_APPROVAL` | Request đang `PENDING` và đã có `license_activated_at`. | License đã kích hoạt, chờ admin/engineer/dev duyệt máy. |
| `REJECTED` | Server trả `MACHINE_REGISTER_REJECTED`. | Yêu cầu định danh bị từ chối, hiển thị lý do. |
| `READY` | Đã approved, tải config thành công, có profile active. | Sẵn sàng scan. |
| `SCANNING` | Đang xử lý một lượt scan. | Đang scan. |
| `SYNCING` | Đang gửi pending hoặc batch sync. | Đang đồng bộ dữ liệu. |
| `BLOCKED` | `MACHINE_NOT_FOUND`, `MACHINE_IDENTITY_MISMATCH`, thiếu profile active hoặc cấu hình lỗi. | Lỗi chặn vận hành, cần kiểm tra server/cấu hình. |
| `ERROR` | Lỗi runtime local, lỗi DB local hoặc exception chưa phân loại. | Lỗi hệ thống local, cần kỹ thuật viên xử lý. |

Quy tắc hiển thị:

- Không hiển thị final OK nếu `final_status` vẫn là `PENDING_SERVER`.
- Khi server offline nhưng local vẫn cho scan theo cache, UI phải ghi rõ `SERVER_OFFLINE` hoặc pending server.
- Khi `WAITING_LICENSE` hoặc `WAITING_APPROVAL`, local không nên cho vào màn scan chính.
- Khi `BLOCKED`, local phải dừng submit/heartbeat runtime và hiển thị lỗi rõ ràng.
- Khi sync xong và không còn lỗi chặn, chuyển lại `READY`.

## 7. API `GET /api/health`

### Chức năng

Kiểm tra backend API có đang chạy không.

### Tại sao cần

Local dùng API này để quyết định server online hoặc offline trước khi tải config, gửi heartbeat, submit scan hoặc sync pending.

### Request

```txt
GET /api/health
```

Không có request body.

### Response thành công

```json
{
  "success": true,
  "code": "HEALTH_OK",
  "message": "Server API is running.",
  "data": {
    "status": "ok",
    "service": "samsung-qrrecorder-server-api",
    "timestamp": "2026-07-13T02:20:30.000Z"
  }
}
```

### Cách xử lý trong Python

- Nếu HTTP 200 và `code = "HEALTH_OK"`: server online.
- Nếu timeout, connection refused hoặc response không hợp lệ: server offline, local lưu pending.

## 8. API `GET /api/machines/identity/status`

### Chức năng

Máy local gửi `serial` và `uid` để hỏi server máy này đã được định danh chưa. Nếu đã được server duyệt, API này trả về `machine_code` chính thức để local dùng cho các API runtime.

### Tại sao cần

Khi mới lắp đặt hoặc khi app local khởi động lại, máy local không nên tự đoán `machine_code`. `machine_code` là tên định danh do server cấp sau khi admin/engineer duyệt máy. `serial` và `uid` ổn định hơn, nên local dùng chúng để lấy lại `machine_code`.

API này cũng giúp trường hợp local DB bị mất hoặc cài lại app: nếu `serial` và `uid` vẫn đúng, server vẫn trả lại được định danh đã duyệt.

### Khi nào gọi

- Gọi ngay sau `GET /api/health` khi app local startup.
- Gọi lại khi local chưa có `machine_code`.
- Gọi lại khi local đang chờ server duyệt pairing.
- Gọi lại sau khi operator/admin báo đã định danh máy trên server.

### Request

```txt
GET /api/machines/identity/status?serial=SN-LOCAL01-2026&uid=UID-8f8f2f1c-local01
```

Query param:

| Field | Kiểu | Bắt buộc | Ý nghĩa |
| --- | --- | --- | --- |
| `serial` | string | Có | Serial phần cứng local, ví dụ lấy từ mainboard. |
| `uid` | string | Có | UID ổn định do app local tạo/lưu hoặc lấy từ định danh máy. |

Không có request body.

### Response khi máy đã được định danh

```json
{
  "success": true,
  "code": "MACHINE_IDENTITY_APPROVED",
  "message": "Machine identity was found and approved.",
  "data": {
    "status": "APPROVED",
    "machine_code": "LOCAL01",
    "serial": "SN-LOCAL01-2026",
    "uid": "UID-8f8f2f1c-local01",
    "machine": {
      "machine_code": "LOCAL01",
      "machine_name": "Local scanner 01",
      "line_name": "LINE-A",
      "station_name": "ST-01",
      "is_active": true
    }
  }
}
```

Local phải lưu `machine_code` vào cấu hình local và gọi tiếp:

```txt
GET /api/machines/LOCAL01/config?serial=SN-LOCAL01-2026&uid=UID-8f8f2f1c-local01
```

### Response khi yêu cầu đang chờ duyệt

```json
{
  "success": true,
  "code": "MACHINE_REGISTER_PENDING",
  "message": "Machine registration request is waiting for server identification.",
  "data": {
    "status": "PENDING",
    "request_id": "MREQ-20260713-1A2B3C4D",
    "machine_code": null,
    "machine": null,
    "serial": "SN-LOCAL01-2026",
    "uid": "UID-8f8f2f1c-local01",
    "license_activated_at": null,
    "rejected_reason": null
  }
}
```

Local nên hiển thị trạng thái đang chờ server định danh, lưu `request_id` nếu có và poll lại sau vài giây.

### Response khi chưa từng đăng ký

```json
{
  "success": true,
  "code": "MACHINE_IDENTITY_NOT_REGISTERED",
  "message": "Machine identity was not registered on the server.",
  "data": {
    "status": "NOT_REGISTERED",
    "machine_code": null,
    "request_id": null,
    "serial": "SN-LOCAL01-2026",
    "uid": "UID-8f8f2f1c-local01"
  }
}
```

Local gọi tiếp `POST /api/machines/register-request`.

### Response lỗi sai định danh

```json
{
  "success": false,
  "code": "MACHINE_IDENTITY_MISMATCH",
  "message": "Serial or uid is already assigned to another machine identity.",
  "data": {
    "status": "MISMATCH",
    "matches": [
      {
        "machine_code": "LOCAL01",
        "serial": "SN-LOCAL01-2026",
        "uid": "UID-OTHER",
        "is_active": true
      }
    ]
  }
}
```

Local phải dừng pairing, hiển thị lỗi rõ ràng và yêu cầu kiểm tra lại `serial`/`uid` hoặc dữ liệu định danh trên server.

## 9. API `POST /api/machines/register-request`

### Chức năng

Máy local mới gửi yêu cầu kết nối lên server bằng `serial`, `uid`, `license_key` raw và `ip_address`. Server kiểm tra trùng ngay tại thời điểm nhận request. Nếu không trùng, server tạo yêu cầu ở trạng thái `PENDING`.

### Tại sao cần

Server không chủ động gọi vào máy local. Vì vậy khi lắp đặt máy mới, máy local phải tự gửi yêu cầu định danh. Admin/engineer trên server sẽ xem request này và gán `machine_code`, tên máy, line, station cho máy local.

### Khi nào gọi

- Chỉ gọi khi `GET /api/machines/identity/status` trả `MACHINE_IDENTITY_NOT_REGISTERED`.
- Không gọi lặp lại mù khi server trả `MACHINE_REGISTER_PENDING`.
- Không gọi lại khi server báo `MACHINE_REGISTER_DUPLICATE` nếu chưa chỉnh thông tin bị trùng.

### Request

```txt
POST /api/machines/register-request
```

Request body:

```json
{
  "requested_machine_code": "LOCAL01",
  "serial": "SN-LOCAL01-2026",
  "uid": "UID-8f8f2f1c-local01",
  "license_key": "SN-LOCAL01-2026|UID-8f8f2f1c-local01",
  "ip_address": "192.168.1.50",
  "hostname": "PC-LINE-A-01",
  "app_version": "1.0.0",
  "local_db_version": "20260713.001"
}
```

Field request:

| Field | Kiểu | Bắt buộc | Ý nghĩa |
| --- | --- | --- | --- |
| `requested_machine_code` | string hoặc null | Không | Mã máy local đề xuất. Server có thể dùng hoặc đổi mã khác khi duyệt. |
| `serial` | string | Có | Serial phần cứng local. |
| `uid` | string | Có | UID ổn định của app/máy local. |
| `license_key` | string | Không nhưng nên gửi | Key kích hoạt tạm thời. Hiện tại để raw, khuyến nghị format `serial|uid`. Sau này có thể đổi sang chuỗi mã hóa/ký số. |
| `ip_address` | string | Có | IP hiện tại của máy local trong LAN. |
| `hostname` | string | Không | Hostname Windows hoặc tên máy local. |
| `app_version` | string | Không | Version app Python local. |
| `local_db_version` | string | Không | Version schema/migration PostgreSQL local. |

### Response thành công

```json
{
  "success": true,
  "code": "MACHINE_REGISTER_REQUEST_SENT",
  "message": "Machine registration request was sent. Waiting for server identification.",
  "data": {
    "request_id": "MREQ-20260713-1A2B3C4D",
    "status": "PENDING",
    "serial": "SN-LOCAL01-2026",
    "uid": "UID-8f8f2f1c-local01",
    "license_key_received": true,
    "ip_address": "192.168.1.50",
    "requested_machine_code": "LOCAL01",
    "created_at": "2026-07-13T02:20:30.000Z"
  }
}
```

Local phải lưu `request_id`, `serial`, `uid`, `license_key`, `registration_status = PENDING` vào DB local.

### Flow license phía server

Máy local không gọi các API bên dưới. Đây là thao tác trên Server UI dành cho admin/dev:

1. Admin/dev mở yêu cầu định danh ở màn `Máy local`.
2. Admin/dev bấm xuất file thông tin máy. File chứa `request_id`, `serial`, `uid`, IP, hostname và `raw_license_key`.
3. Người dùng gửi file thông tin đó cho bên cấp license.
4. Bên cấp license tạo file license và gửi lại. Giai đoạn hiện tại chưa mã hóa thật, file license raw chỉ cần có nội dung để import.
5. Admin/dev import file license vào đúng request.
6. Server chưa check công thức và chưa so `serial`, `uid`; miễn import được nội dung license thì lưu `license_activated_at` và xem như đã kích hoạt.
7. Sau khi license đã được import/kích hoạt, admin/engineer/dev mới duyệt request và đặt `machine_code`, `machine_name`, line, trạm.
8. Máy local poll lại `identity/status` hoặc `request_id/status` sẽ nhận trạng thái approved và `machine_code`.

Admin APIs liên quan:

| Method | Path | Ai gọi | Ý nghĩa |
| --- | --- | --- | --- |
| `GET` | `/api/machines/register-requests/:id/license-export` | Server UI admin/dev | Xuất nội dung file thông tin máy để gửi đi cấp license. |
| `POST` | `/api/machines/register-requests/:id/license/import` | Server UI admin/dev | Import file license raw và kích hoạt request. |
| `POST` | `/api/machines/register-requests/:id/approve` | Server UI | Duyệt request sau khi license đã được import/kích hoạt. |

Ví dụ file thông tin máy xuất ra:

```json
{
  "license_format": "SAMSUNG_QR_MACHINE_INFO_RAW_V1",
  "request_id": "MREQ-20260713-1A2B3C4D",
  "requested_machine_code": "LOCAL01",
  "serial": "SN-LOCAL01-2026",
  "uid": "UID-8f8f2f1c-local01",
  "raw_license_key": "SN-LOCAL01-2026|UID-8f8f2f1c-local01",
  "ip_address": "192.168.1.50",
  "hostname": "PC-LINE-A-01",
  "app_version": "1.0.0",
  "local_db_version": "20260713.001",
  "exported_at": "2026-07-13T02:21:00.000Z"
}
```

Ví dụ file license raw import lại:

```json
{
  "license_format": "SAMSUNG_QR_MACHINE_LICENSE_RAW_V1",
  "serial": "SN-LOCAL01-2026",
  "uid": "UID-8f8f2f1c-local01",
  "license_key": "SN-LOCAL01-2026|UID-8f8f2f1c-local01"
}
```

### Response khi trùng dữ liệu

```json
{
  "success": false,
  "code": "MACHINE_REGISTER_DUPLICATE",
  "message": "Machine registration request has duplicated identity fields.",
  "data": {
    "status": "DUPLICATE",
    "duplicates": [
      {
        "field": "serial",
        "value": "SN-LOCAL01-2026",
        "source": "machine",
        "machine_code": "LOCAL01"
      }
    ]
  }
}
```

Các field có thể bị báo trùng:

| Field | Ý nghĩa |
| --- | --- |
| `serial` | Serial này đã thuộc máy khác hoặc request khác. |
| `uid` | UID này đã thuộc máy khác hoặc request khác. |
| `ip_address` | IP này đang bị dùng bởi máy/request khác. |
| `requested_machine_code` | Mã máy đề xuất đã tồn tại hoặc đã có request đang chờ. |

Local phải hiển thị field bị trùng để kỹ thuật viên chỉnh lại hoặc xử lý trên server trước khi gửi lại.

## 10. API `GET /api/machines/register-requests/:request_id/status`

### Chức năng

Máy local kiểm tra một yêu cầu định danh cụ thể đã được server duyệt, từ chối hay vẫn đang chờ.

### Tại sao cần

Sau khi gửi `POST /api/machines/register-request`, local nhận `request_id`. Local có thể dùng `request_id` này để poll trạng thái chính xác của request đã gửi.

Khi startup, local vẫn nên ưu tiên `GET /api/machines/identity/status?serial=...&uid=...` vì API đó không phụ thuộc local còn nhớ `request_id` hay không.

### Request

```txt
GET /api/machines/register-requests/MREQ-20260713-1A2B3C4D/status?serial=SN-LOCAL01-2026&uid=UID-8f8f2f1c-local01
```

Path param:

| Field | Kiểu | Bắt buộc | Ý nghĩa |
| --- | --- | --- | --- |
| `request_id` | string | Có | ID request server trả khi local gửi yêu cầu kết nối. |

Query param:

| Field | Kiểu | Bắt buộc | Ý nghĩa |
| --- | --- | --- | --- |
| `serial` | string | Có | Serial phải khớp request đã gửi. |
| `uid` | string | Có | UID phải khớp request đã gửi. |

Không có request body.

### Response khi đang chờ

```json
{
  "success": true,
  "code": "MACHINE_REGISTER_PENDING",
  "message": "Machine registration request is waiting for server identification.",
  "data": {
    "request_id": "MREQ-20260713-1A2B3C4D",
    "status": "PENDING",
    "machine_code": null,
    "serial": "SN-LOCAL01-2026",
    "uid": "UID-8f8f2f1c-local01",
    "ip_address": "192.168.1.50",
    "license_activated_at": null,
    "rejected_reason": null,
    "approved_at": null,
    "rejected_at": null
  }
}
```

Local tiếp tục hiển thị trạng thái chờ định danh và poll lại sau vài giây.

### Response khi đã được duyệt

```json
{
  "success": true,
  "code": "MACHINE_REGISTER_APPROVED",
  "message": "Machine registration request was approved.",
  "data": {
    "request_id": "MREQ-20260713-1A2B3C4D",
    "status": "APPROVED",
    "machine_code": "LOCAL01",
    "serial": "SN-LOCAL01-2026",
    "uid": "UID-8f8f2f1c-local01",
    "ip_address": "192.168.1.50",
    "license_activated_at": "2026-07-13T02:24:30.000Z",
    "rejected_reason": null,
    "approved_at": "2026-07-13T02:25:30.000Z",
    "rejected_at": null
  }
}
```

Local lưu `machine_code`, cập nhật `registration_status = APPROVED`, sau đó gọi `/config`.

### Response khi bị từ chối

```json
{
  "success": true,
  "code": "MACHINE_REGISTER_REJECTED",
  "message": "Machine registration request was rejected.",
  "data": {
    "request_id": "MREQ-20260713-1A2B3C4D",
    "status": "REJECTED",
    "machine_code": null,
    "serial": "SN-LOCAL01-2026",
    "uid": "UID-8f8f2f1c-local01",
    "ip_address": "192.168.1.50",
    "rejected_reason": "Duplicate physical station.",
    "approved_at": null,
    "rejected_at": "2026-07-13T02:25:30.000Z"
  }
}
```

Local hiển thị `rejected_reason`, dừng chờ định danh và yêu cầu kỹ thuật viên xử lý lại trên server.

### Response lỗi

```json
{
  "success": false,
  "code": "MACHINE_REGISTER_IDENTITY_MISMATCH",
  "message": "Serial or uid does not match this registration request."
}
```

Local phải dừng poll request này vì `serial` hoặc `uid` không còn khớp với request đã lưu.

## 11. API `GET /api/machines/:machine_code/config`

### Chức năng

Lấy thông tin máy, server settings, danh sách profile active và command pending hoặc sent cho máy local.

### Tại sao cần

Local cần config để biết:

- duplicate window server đang dùng;
- heartbeat timeout;
- full code length;
- LED scan length;
- vendor position;
- factory code;
- profile active;
- chassis code;
- vendor char;
- LED slot và suffix check;
- command server đang chờ local xử lý.

### Request

```txt
GET /api/machines/LOCAL01/config?serial=SN-LOCAL01-2026&uid=UID-8f8f2f1c-local01
```

Path param:

| Field | Kiểu | Bắt buộc | Ý nghĩa |
| --- | --- | --- | --- |
| `machine_code` | string | Có | Mã máy local đã đăng ký trên server. |

### Response thành công

```json
{
  "success": true,
  "code": "MACHINE_CONFIG_LOADED",
  "message": "Machine server configuration loaded.",
  "data": {
    "machine": {
      "id": 1,
      "machine_code": "LOCAL01",
      "machine_name": "Local scanner 01",
      "line_name": "LINE-A",
      "station_name": "ST-01",
      "ip_address": null,
      "is_active": true,
      "created_at": "2026-07-09T04:15:10.000Z",
      "updated_at": "2026-07-09T04:15:10.000Z"
    },
    "settings": {
      "id": 1,
      "factory_code_default": "DYS3",
      "full_code_length_default": 35,
      "full_vendor_position_default": 18,
      "led_scan_length_default": 22,
      "led_vendor_position_default": 16,
      "duplicate_days": 31,
      "heartbeat_timeout_seconds": 60,
      "updated_by": null,
      "created_at": "2026-07-09T04:15:10.000Z",
      "updated_at": "2026-07-09T04:15:10.000Z"
    },
    "profiles": [
      {
        "id": 1,
        "chassis_code_id": 1,
        "vendor_id": 1,
        "factory_code": "DYS3",
        "full_code_length": 35,
        "full_vendor_position": 18,
        "led_scan_length": 22,
        "led_vendor_position": 16,
        "version": 1,
        "is_active": true,
        "created_by": null,
        "created_at": "2026-07-09T04:15:10.000Z",
        "updated_at": "2026-07-09T04:15:10.000Z",
        "chassis_code": {
          "id": 1,
          "code_full": "BN96-60877C",
          "code_input": "60877C",
          "is_active": true,
          "created_at": "2026-07-09T04:15:10.000Z",
          "updated_at": "2026-07-09T04:15:10.000Z"
        },
        "vendor": {
          "id": 1,
          "vendor_name": "Default LED Vendor",
          "vendor_char": "L",
          "status": "ACTIVE",
          "created_at": "2026-07-09T04:15:10.000Z",
          "updated_at": "2026-07-09T04:15:10.000Z"
        },
        "profile_led_codes": [
          {
            "id": 1,
            "profile_id": 1,
            "led_code_id": 1,
            "led_slot": 1,
            "is_required": true,
            "created_at": "2026-07-09T04:15:10.000Z",
            "led_code": {
              "id": 1,
              "code_full": "BN96-60376A",
              "code_input": "60376A",
              "suffix_check": "0376A",
              "is_active": true,
              "created_at": "2026-07-09T04:15:10.000Z",
              "updated_at": "2026-07-09T04:15:10.000Z"
            }
          }
        ]
      }
    ],
    "pending_commands": [
      {
        "id": 10,
        "machine_id": 1,
        "command_type": "SYNC_PROFILE",
        "payload_json": {
          "reason": "Profile updated by engineer"
        },
        "status": "PENDING",
        "created_by": 2,
        "created_at": "2026-07-13T02:20:30.000Z",
        "sent_at": null,
        "ack_at": null,
        "error_message": null
      }
    ]
  }
}
```

### Response lỗi

```json
{
  "success": false,
  "code": "MACHINE_NOT_FOUND",
  "message": "Machine code does not exist or is inactive."
}
```

### Cách dùng `settings`

| Field | Ý nghĩa |
| --- | --- |
| `factory_code_default` | Factory code mặc định. |
| `full_code_length_default` | Độ dài full code mặc định. |
| `full_vendor_position_default` | Vị trí vendor trong full code theo rule dự án. |
| `led_scan_length_default` | Độ dài LED scan mặc định. |
| `led_vendor_position_default` | Vị trí vendor trong LED scan theo rule dự án. |
| `duplicate_days` | Cửa sổ duplicate server. Local không thay thế check này. |
| `heartbeat_timeout_seconds` | Mốc server dùng để đánh giá heartbeat quá hạn. |

### Cách dùng `profiles`

Local nên dùng các field sau:

| Field | Ý nghĩa |
| --- | --- |
| `profile.id` | Gửi lại trong `profile_id` khi submit scan. |
| `profile.version` | Version rule local đang cache. |
| `profile.factory_code` | Factory code cần match. |
| `profile.full_code_length` | Độ dài full code theo profile. |
| `profile.full_vendor_position` | Vị trí vendor trong full code theo profile. |
| `profile.led_scan_length` | Độ dài LED scan theo profile. |
| `profile.led_vendor_position` | Vị trí vendor trong LED scan theo profile. |
| `profile.vendor.vendor_char` | Vendor char hợp lệ. |
| `profile.chassis_code.code_full` | Chassis code đầy đủ. |
| `profile.chassis_code.code_input` | Đoạn input dùng để match chassis nếu local cần. |
| `profile.profile_led_codes[].led_slot` | Slot LED. |
| `profile.profile_led_codes[].led_code.code_full` | LED code đầy đủ. |
| `profile.profile_led_codes[].led_code.suffix_check` | Suffix LED cần match. |

Backend hiện tại lưu payload local gửi lên, không tự parse lại thay local. Python local phải validate đúng theo profile cache.

## 12. API `POST /api/machines/heartbeat`

### Chức năng

Cập nhật trạng thái kết nối và sync hiện tại của máy local.

### Tại sao cần

Server UI dùng heartbeat để biết máy còn online, IP gần nhất, app version, local DB version, tổng record local và số record pending sync.

### Request body

```json
{
  "machine_code": "LOCAL01",
  "serial": "SN-LOCAL01-2026",
  "uid": "UID-8f8f2f1c-local01",
  "ip_address": "192.168.1.50",
  "app_version": "1.0.0",
  "local_db_version": "20260713.001",
  "local_total_record": 1200,
  "local_ok_record": 1180,
  "local_ng_record": 20,
  "local_pending_sync": 3,
  "local_checksum": "sha256:9d0c7f3b3f5b5c1a"
}
```

### Field request

| Field | Kiểu | Bắt buộc | Ý nghĩa |
| --- | --- | --- | --- |
| `machine_code` | string | Có | Mã máy local đã đăng ký. |
| `serial` | string | Có | Serial phần cứng local đã được server định danh. |
| `uid` | string | Có | UID định danh local đã được server định danh. |
| `ip_address` | string | Không | IP hiện tại của local. |
| `app_version` | string | Không | Version app Python local. |
| `local_db_version` | string | Không | Version schema hoặc migration local DB. |
| `local_total_record` | integer >= 0 | Không | Tổng record local. |
| `local_ok_record` | integer >= 0 | Không | Tổng record local OK. |
| `local_ng_record` | integer >= 0 | Không | Tổng record local NG. |
| `local_pending_sync` | integer >= 0 | Không | Số record đang chờ sync server. |
| `local_checksum` | string | Không | Checksum tổng hợp nếu local có cơ chế đối soát. |

### Response thành công

```json
{
  "success": true,
  "code": "HEARTBEAT_ACCEPTED",
  "message": "Heartbeat accepted.",
  "data": {
    "machine": {
      "id": 1,
      "machine_code": "LOCAL01",
      "machine_name": "Local scanner 01",
      "line_name": "LINE-A",
      "station_name": "ST-01",
      "ip_address": null,
      "is_active": true,
      "created_at": "2026-07-09T04:15:10.000Z",
      "updated_at": "2026-07-09T04:15:10.000Z"
    },
    "sync_state": {
      "id": 1,
      "machine_id": 1,
      "machine_code": "LOCAL01",
      "connection_status": "ONLINE",
      "last_seen_at": "2026-07-13T02:20:30.000Z",
      "last_ip_address": "192.168.1.50",
      "local_total_record": 1200,
      "local_ok_record": 1180,
      "local_ng_record": 20,
      "local_pending_sync": 3,
      "local_checksum": "sha256:9d0c7f3b3f5b5c1a",
      "server_total_record": 0,
      "server_ok_record": 0,
      "server_ng_record": 0,
      "server_checksum": null,
      "need_sync": false,
      "last_sync_at": null,
      "last_batch_code": null,
      "app_version": "1.0.0",
      "local_db_version": "20260713.001",
      "created_at": "2026-07-13T02:20:30.000Z",
      "updated_at": "2026-07-13T02:20:30.000Z"
    }
  }
}
```

### Cách xử lý

- `HEARTBEAT_ACCEPTED`: server online.
- `MACHINE_NOT_FOUND`: dừng submit, báo lỗi cấu hình máy.
- Timeout hoặc connection error: chuyển offline mode, giữ pending.

## 12.1. Socket.IO `/machine-runtime`

### Chức năng

Kênh Socket.IO này dùng để server biết realtime máy local nào đang kết nối, đang chạy mã hàng nào, đã chạy bao lâu, tổng số scan từ lúc bắt đầu, bao nhiêu OK, bao nhiêu NG, lần cuối gửi mã gì và có bị mất kết nối hay reconnect không.

REST API vẫn là nguồn ghi scan chính thức:

- `POST /api/scans/submit` vẫn dùng cho từng scan realtime.
- `POST /api/sync/batches/submit` vẫn dùng để đồng bộ pending/offline.
- Socket.IO chỉ tạo và cập nhật phiên runtime server để theo dõi vận hành realtime.

### Tại sao cần

Heartbeat chỉ cho biết máy còn online và tổng local hiện tại. WebSocket/Socket.IO cho biết phiên đang chạy cụ thể:

- máy nào đang chạy;
- đang chạy mã hàng/profile nào;
- trong phiên đã đổi bao nhiêu mã hàng;
- mỗi mã hàng chạy bao nhiêu, OK bao nhiêu, NG bao nhiêu;
- máy mất kết nối lúc nào;
- máy reconnect lại bao nhiêu lần;
- scan nào trên server thuộc phiên nào.

Phiên runtime được lưu trên server và không cho chỉnh sửa trên UI. Nếu sau này cần mở cơ chế chỉnh ngoại lệ, mọi chỉnh sửa bắt buộc phải ghi vào `machine_runtime_adjustment_logs`.

### URL kết nối

Đây là Socket.IO namespace, không phải raw WebSocket thuần.

```txt
http://SERVER_HOST:3979/machine-runtime
```

Ví dụ nếu server API là:

```txt
http://192.168.1.10:3979/api
```

Thì Socket.IO URL là:

```txt
http://192.168.1.10:3979/machine-runtime
```

Python local nên dùng thư viện `python-socketio`, bật reconnect tự động.

### Luồng bắt buộc

```txt
local app startup
  -> lấy machine_code bằng identity/status hoặc register flow
  -> tải config
  -> kết nối Socket.IO /machine-runtime
  -> emit machine:hello
  -> server trả machine:accepted
  -> khi operator bấm bắt đầu chạy: emit runtime:start
  -> trong lúc chạy: emit runtime:update hoặc runtime:snapshot định kỳ
  -> mỗi scan vẫn POST /api/scans/submit như cũ
  -> khi đổi mã hàng: runtime:update với profile_id/product_code mới
  -> khi dừng: emit runtime:stop
  -> nếu mất kết nối: client tự reconnect, emit lại machine:hello rồi gửi runtime:snapshot
```

### Event `machine:hello`

Gửi ngay sau khi socket connect hoặc reconnect. Chưa gửi event này thì server không nhận các event runtime khác.

```json
{
  "machine_code": "LOCAL01",
  "serial": "SN-LOCAL01-2026",
  "uid": "UID-8f8f2f1c-local01",
  "ip_address": "192.168.1.50",
  "app_version": "1.0.0",
  "local_db_version": "20260713.001"
}
```

Server kiểm tra `machine_code + serial + uid`. Nếu sai định danh, local phải set `local_runtime_status = "BLOCKED"` và dừng gửi runtime/scan.

Response/event server trả về:

```json
{
  "success": true,
  "code": "RUNTIME_SOCKET_ACCEPTED",
  "message": "Machine runtime WebSocket accepted.",
  "data": {
    "machine": {
      "id": 1,
      "machine_code": "LOCAL01",
      "serial": "SN-LOCAL01-2026",
      "uid": "UID-8f8f2f1c-local01"
    },
    "server_time": "2026-07-13T06:30:00.000Z"
  }
}
```

### Event `runtime:start`

Gửi khi bắt đầu một lượt chạy. Server sẽ tự tạo một phiên mới và đóng phiên cũ đang mở của cùng máy nếu có.

```json
{
  "profile_id": 1,
  "product_code": "CHASSIS-A-001",
  "started_at": "2026-07-13T06:30:00.000Z",
  "total_count": 0,
  "ok_count": 0,
  "ng_count": 0,
  "product_total_count": 0,
  "product_ok_count": 0,
  "product_ng_count": 0
}
```

`product_code` nên là mã hàng/operator đang chọn. Nếu local chỉ có `profile_id`, server sẽ lấy mã từ profile/chassis code.

### Event `runtime:update`

Gửi khi có scan mới hoặc khi số liệu realtime thay đổi.

```json
{
  "profile_id": 1,
  "product_code": "CHASSIS-A-001",
  "total_count": 25,
  "ok_count": 23,
  "ng_count": 2,
  "product_total_count": 25,
  "product_ok_count": 23,
  "product_ng_count": 2,
  "last_result": "OK",
  "last_code": "FULL-CODE-RAW-000025",
  "local_scan_id": "LS-LOCAL01-20260713-000025",
  "pending_sync": 0
}
```

Quy tắc:

- `total_count`, `ok_count`, `ng_count` là tổng từ lúc bắt đầu phiên hiện tại.
- `product_total_count`, `product_ok_count`, `product_ng_count` là tổng riêng của mã hàng hiện tại.
- Khi đổi mã hàng, gửi `profile_id` hoặc `product_code` mới. Server sẽ đóng đoạn mã hàng cũ và mở đoạn mã hàng mới trong cùng phiên.

### Event `runtime:snapshot`

Gửi định kỳ, ví dụ mỗi 3 đến 10 giây trong lúc đang chạy, hoặc ngay sau reconnect. Payload giống `runtime:update`.

Khác biệt ý nghĩa:

- `runtime:update`: thường gửi sau scan mới hoặc thay đổi quan trọng.
- `runtime:snapshot`: gửi ảnh chụp trạng thái hiện tại để server đồng bộ lại sau reconnect hoặc phòng trường hợp miss event.

### Event `runtime:stop`

Gửi khi operator dừng chạy hoặc app local chuẩn bị đóng.

```json
{
  "profile_id": 1,
  "product_code": "CHASSIS-A-001",
  "total_count": 120,
  "ok_count": 115,
  "ng_count": 5,
  "product_total_count": 120,
  "product_ok_count": 115,
  "product_ng_count": 5,
  "last_result": "OK",
  "last_code": "FULL-CODE-RAW-000120",
  "local_scan_id": "LS-LOCAL01-20260713-000120",
  "stopped_at": "2026-07-13T07:15:00.000Z",
  "reason": "OPERATOR_STOP"
}
```

### Event `runtime:error`

Gửi khi app local gặp lỗi runtime nhưng vẫn kết nối được server.

```json
{
  "profile_id": 1,
  "product_code": "CHASSIS-A-001",
  "total_count": 30,
  "ok_count": 28,
  "ng_count": 2,
  "last_result": "ERROR",
  "error_code": "CAMERA_DISCONNECTED",
  "message": "Camera disconnected while scanning."
}
```

### Event server broadcast `server:runtime-updated`

Server UI dùng event này để refresh realtime. Máy local không bắt buộc xử lý.

```json
{
  "event": "UPDATED",
  "machine_code": "LOCAL01",
  "data": {}
}
```

### Reconnect đúng

Khi Socket.IO reconnect:

1. Emit lại `machine:hello`.
2. Nếu app đang chạy, emit `runtime:snapshot` với tổng hiện tại.
3. Nếu có pending scan do mất REST connection, gửi batch qua `POST /api/sync/batches/submit`.
4. Tiếp tục `runtime:update` sau các scan mới.

Không cần thêm bảng DB local riêng cho phiên server. Local chỉ cần giữ biến runtime trong memory hoặc lưu nhẹ vào `local_app_settings`/log nếu muốn hiển thị trạng thái socket.

## 13. API `GET /api/machines/:machine_code/commands/poll`

### Chức năng

Máy local chủ động lấy command từ server.

### Tại sao cần

Server không gọi ngược lại máy local qua LAN. Local phải poll để nhận lệnh.

### Command hiện tại

| Command | Ý nghĩa | Local nên làm |
| --- | --- | --- |
| `SYNC_PROFILE` | Profile hoặc rule có thể đã thay đổi. | Gọi lại `/config`, lưu cache, ack. |
| `SYNC_SCAN_DATA` | Server yêu cầu local sync pending. | Gửi batch pending, ack. |
| `RELOAD_CONFIG` | Server yêu cầu reload cấu hình. | Gọi lại `/config`, reload runtime, ack. |
| `SHOW_MESSAGE` | Server gửi message cho local UI. | Hiển thị message, ack. |

### Request

```txt
GET /api/machines/LOCAL01/commands/poll?serial=SN-LOCAL01-2026&uid=UID-8f8f2f1c-local01&take=20
```

Query:

| Field | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
| --- | --- | --- | --- | --- |
| `serial` | string | Có | - | Serial phần cứng local đã được server định danh. |
| `uid` | string | Có | - | UID định danh local đã được server định danh. |
| `take` | integer | Không | 20 | Số command tối đa, server giới hạn tối đa 100. |

### Response thành công

```json
{
  "success": true,
  "code": "MACHINE_COMMANDS_POLLED",
  "message": "Pending machine commands loaded.",
  "data": [
    {
      "id": 10,
      "machine_id": 1,
      "command_type": "SYNC_PROFILE",
      "payload_json": {
        "reason": "Profile updated by engineer"
      },
      "status": "SENT",
      "created_by": 2,
      "created_at": "2026-07-13T02:20:30.000Z",
      "sent_at": "2026-07-13T02:20:35.000Z",
      "ack_at": null,
      "error_message": null
    }
  ]
}
```

### Hành vi server khi poll

Khi local poll:

1. Server kiểm tra máy active.
2. Server đổi command `PENDING` của máy đó sang `SENT`.
3. Server trả danh sách command `SENT`.

Nếu command chưa ack, lần poll sau vẫn có thể trả lại command đó. Local phải xử lý theo `command.id` và ack sau khi xử lý.

## 14. API `POST /api/machines/commands/:id/ack`

### Chức năng

Máy local báo server rằng command đã xử lý xong hoặc thất bại.

### Request ACK

```txt
POST /api/machines/commands/10/ack
```

```json
{
  "machine_code": "LOCAL01",
  "serial": "SN-LOCAL01-2026",
  "uid": "UID-8f8f2f1c-local01",
  "status": "ACK",
  "error_message": null
}
```

### Request FAILED

```json
{
  "machine_code": "LOCAL01",
  "serial": "SN-LOCAL01-2026",
  "uid": "UID-8f8f2f1c-local01",
  "status": "FAILED",
  "error_message": "Cannot reload profile because local cache database is locked."
}
```

### Field request

| Field | Kiểu | Bắt buộc | Ý nghĩa |
| --- | --- | --- | --- |
| `machine_code` | string | Có | Mã máy local. |
| `serial` | string | Có | Serial phần cứng local đã được server định danh. |
| `uid` | string | Có | UID định danh local đã được server định danh. |
| `status` | `ACK` hoặc `FAILED` | Có | Kết quả xử lý command. |
| `error_message` | string hoặc null | Không | Lý do lỗi nếu `FAILED`. |

### Response ACK

```json
{
  "success": true,
  "code": "MACHINE_COMMAND_ACKED",
  "message": "Machine command acknowledged.",
  "data": {
    "id": 10,
    "machine_id": 1,
    "command_type": "SYNC_PROFILE",
    "payload_json": {
      "reason": "Profile updated by engineer"
    },
    "status": "ACK",
    "created_by": 2,
    "created_at": "2026-07-13T02:20:30.000Z",
    "sent_at": "2026-07-13T02:20:35.000Z",
    "ack_at": "2026-07-13T02:21:00.000Z",
    "error_message": null
  }
}
```

### Response FAILED

```json
{
  "success": true,
  "code": "MACHINE_COMMAND_FAILED",
  "message": "Machine command marked as failed.",
  "data": {
    "id": 10,
    "machine_id": 1,
    "command_type": "SYNC_PROFILE",
    "payload_json": {
      "reason": "Profile updated by engineer"
    },
    "status": "FAILED",
    "created_by": 2,
    "created_at": "2026-07-13T02:20:30.000Z",
    "sent_at": "2026-07-13T02:20:35.000Z",
    "ack_at": null,
    "error_message": "Cannot reload profile because local cache database is locked."
  }
}
```

### Response lỗi

```json
{
  "success": false,
  "code": "MACHINE_COMMAND_NOT_FOUND",
  "message": "Machine command was not found for this machine."
}
```

## 15. API `POST /api/scans/submit`

### Chức năng

Submit một scan từ máy local lên server. Endpoint này nhận cả local OK và local NG.

### Tại sao cần

Máy local phải gửi scan lên server để:

- server kiểm duplicate nhiều ngày;
- server lưu lịch sử tập trung;
- server lưu full code raw và LED raw;
- server tạo notification khi duplicate;
- server ghi request log để debug.

### Idempotency

Server có unique key:

```txt
machine_id + local_scan_id
```

Nếu local gửi lại cùng `local_scan_id` cho cùng máy, server replay kết quả cũ. Local phải giữ nguyên `local_scan_id` khi retry.

Quy tắc:

- `local_scan_id` unique theo máy.
- Không dùng lại `local_scan_id` cho mã khác.
- Khi timeout, retry cùng payload và cùng `local_scan_id`.
- Nếu app restart, retry từ local DB bằng ID cũ.

### Request body local OK

```json
{
  "local_scan_id": "LOCAL01-20260713-000001",
  "machine_code": "LOCAL01",
  "serial": "SN-LOCAL01-2026",
  "uid": "UID-8f8f2f1c-local01",
  "profile_id": 1,
  "duplicate_key": "1A1Y420673",
  "full_code": {
    "raw": "VN39BN9660877C1A1L60376ADYS3Y420673",
    "prefix": "VN39",
    "chassis_code": "BN96-60877C",
    "before_vendor": "1A1",
    "vendor_char": "L",
    "led_code": "BN96-60376A",
    "factory_code": "DYS3",
    "after_factory": "Y420673"
  },
  "chassis_scan_raw": "BN96-60877C",
  "led_scans": [
    {
      "slot": 1,
      "index": 1,
      "raw": "ZB36L582465U528LD0376A",
      "lot_no": "528",
      "vendor_char": "L",
      "suffix": "0376A",
      "status": "OK",
      "ng_reason": null
    }
  ],
  "local_status": "OK",
  "local_ng_reason": null,
  "scan_at": "2026-07-13T09:30:25+07:00"
}
```

### Request body local NG

```json
{
  "local_scan_id": "LOCAL01-20260713-000002",
  "machine_code": "LOCAL01",
  "serial": "SN-LOCAL01-2026",
  "uid": "UID-8f8f2f1c-local01",
  "profile_id": 1,
  "duplicate_key": "1A1Y420674",
  "full_code": {
    "raw": "VN39BN9660877C1A1L60376ADYS3Y420674",
    "prefix": "VN39",
    "chassis_code": "BN96-60877C",
    "before_vendor": "1A1",
    "vendor_char": "L",
    "led_code": "BN96-60376A",
    "factory_code": "DYS3",
    "after_factory": "Y420674"
  },
  "chassis_scan_raw": "BN96-60877C",
  "led_scans": [
    {
      "slot": 1,
      "index": 1,
      "raw": "ZB36L582465U528LD9999X",
      "lot_no": "528",
      "vendor_char": "L",
      "suffix": "9999X",
      "status": "NG",
      "ng_reason": "LED_SUFFIX_NOT_MATCH"
    }
  ],
  "local_status": "NG",
  "local_ng_reason": "LED_SUFFIX_NOT_MATCH",
  "scan_at": "2026-07-13T09:31:25+07:00"
}
```

### Field cấp scan

| Field | Kiểu | Bắt buộc | Ý nghĩa |
| --- | --- | --- | --- |
| `local_scan_id` | string | Có | ID unique do local tạo cho từng scan. |
| `machine_code` | string | Có | Mã máy local. |
| `serial` | string | Có | Serial phần cứng local đã được server định danh. |
| `uid` | string | Có | UID định danh local đã được server định danh. |
| `profile_id` | integer >= 1 | Có | ID profile lấy từ config. |
| `duplicate_key` | string | Có | Key duplicate đã parse từ full code. |
| `full_code` | object | Có | Thành phần full code đã parse. |
| `chassis_scan_raw` | string | Có | Mã chassis raw. |
| `led_scans` | array | Có | Danh sách LED scan item. |
| `local_status` | `OK` hoặc `NG` | Có | Kết quả kiểm local. |
| `local_ng_reason` | string hoặc null | Không | Lý do NG nếu local NG. |
| `scan_at` | ISO8601 string | Có | Thời điểm scan gốc, nên có timezone. |

### Field `full_code`

| Field | Ý nghĩa |
| --- | --- |
| `raw` | Full code raw từ scanner. |
| `prefix` | Prefix đầu full code. |
| `chassis_code` | Chassis code đã parse. |
| `before_vendor` | Đoạn trước vendor char. |
| `vendor_char` | Vendor char trong full code. |
| `led_code` | LED code đã parse từ full code. |
| `factory_code` | Factory code đã parse. |
| `after_factory` | Đoạn sau factory code. |

### Field `led_scans`

| Field | Ý nghĩa |
| --- | --- |
| `slot` | Slot LED theo profile. |
| `index` | Thứ tự scan LED trong lần scan. |
| `raw` | LED raw từ scanner. |
| `lot_no` | Lot number parse từ LED raw. |
| `vendor_char` | Vendor char parse từ LED raw. |
| `suffix` | Suffix parse từ LED raw. |
| `status` | `OK` hoặc `NG` cho LED item. |
| `ng_reason` | Lý do NG của LED item nếu có. |

### Response `SERVER_OK`

```json
{
  "success": true,
  "code": "SERVER_OK",
  "message": "Server accepted scan. No duplicate was detected.",
  "data": {
    "decision": "SERVER_OK",
    "server_scan_id": 123,
    "final_status": "OK",
    "ng_reason": null
  }
}
```

Local cập nhật:

```txt
server_status = OK
final_status = OK
ng_reason = null
sync_status = SYNCED
```

### Response `SERVER_DUPLICATE`

```json
{
  "success": true,
  "code": "SERVER_DUPLICATE",
  "message": "Server detected duplicate within the configured duplicate window.",
  "data": {
    "decision": "SERVER_DUPLICATE",
    "server_scan_id": 124,
    "first_scan_record_id": 123,
    "final_status": "NG",
    "ng_reason": "SERVER_DUPLICATE"
  }
}
```

Local cập nhật:

```txt
server_status = NG
final_status = NG
ng_reason = SERVER_DUPLICATE
sync_status = SYNCED
```

Đây là kết quả nghiệp vụ, không phải lỗi network. Không retry record này.

### Response `LOCAL_NG_SAVED`

```json
{
  "success": true,
  "code": "LOCAL_NG_SAVED",
  "message": "Local NG scan was saved. Server duplicate check was skipped.",
  "data": {
    "decision": "LOCAL_NG_SAVED",
    "server_scan_id": 125,
    "final_status": "NG",
    "ng_reason": "LED_SUFFIX_NOT_MATCH"
  }
}
```

Local cập nhật:

```txt
server_status = SKIPPED
final_status = NG
ng_reason = lỗi local đã gửi
sync_status = SYNCED
```

### Response replay

Nếu local retry cùng `local_scan_id`, server trả lại kết quả cũ.

Replay server OK:

```json
{
  "success": true,
  "code": "SERVER_OK",
  "message": "Scan result was already saved.",
  "data": {
    "decision": "SERVER_OK",
    "server_scan_id": 123,
    "final_status": "OK",
    "ng_reason": null
  }
}
```

Replay duplicate:

```json
{
  "success": true,
  "code": "SERVER_DUPLICATE",
  "message": "Server detected duplicate within the configured duplicate window.",
  "data": {
    "decision": "SERVER_DUPLICATE",
    "server_scan_id": 124,
    "final_status": "NG",
    "ng_reason": "SERVER_DUPLICATE"
  }
}
```

### Response lỗi `PROFILE_NOT_FOUND`

```json
{
  "success": false,
  "code": "PROFILE_NOT_FOUND",
  "message": "Profile does not exist or is inactive."
}
```

Local nên reload config và yêu cầu operator chọn profile active.

### Response lỗi `MACHINE_NOT_FOUND`

```json
{
  "success": false,
  "code": "MACHINE_NOT_FOUND",
  "message": "Machine code does not exist or is inactive."
}
```

Local nên dừng submit và báo lỗi cấu hình máy.

### Lưu ý về `scan_at`

`scan_at` phải là thời điểm scan gốc tại local, không phải thời điểm sync. Nên gửi ISO8601 có timezone:

```txt
2026-07-13T09:30:25+07:00
```

## 16. API `POST /api/sync/batches/submit`

### Chức năng

Submit nhiều scan pending hoặc offline trong một batch.

### Tại sao cần

Batch giúp server và UI truy vết một lần sync gồm bao nhiêu record, bao nhiêu OK, bao nhiêu NG và bao nhiêu failed.

### Khi nào gọi

- Startup nếu có pending.
- Network restored.
- Shutdown nếu cần flush pending.
- Manual sync.
- Khi nhận command `SYNC_SCAN_DATA`.

### Request body

```json
{
  "batch_code": "LOCAL01-20260713-NETWORK_RESTORED-0001",
  "machine_code": "LOCAL01",
  "serial": "SN-LOCAL01-2026",
  "uid": "UID-8f8f2f1c-local01",
  "trigger_type": "NETWORK_RESTORED",
  "scans": [
    {
      "local_scan_id": "LOCAL01-20260713-000001",
      "machine_code": "LOCAL01",
      "serial": "SN-LOCAL01-2026",
      "uid": "UID-8f8f2f1c-local01",
      "profile_id": 1,
      "duplicate_key": "1A1Y420673",
      "full_code": {
        "raw": "VN39BN9660877C1A1L60376ADYS3Y420673",
        "prefix": "VN39",
        "chassis_code": "BN96-60877C",
        "before_vendor": "1A1",
        "vendor_char": "L",
        "led_code": "BN96-60376A",
        "factory_code": "DYS3",
        "after_factory": "Y420673"
      },
      "chassis_scan_raw": "BN96-60877C",
      "led_scans": [
        {
          "slot": 1,
          "index": 1,
          "raw": "ZB36L582465U528LD0376A",
          "lot_no": "528",
          "vendor_char": "L",
          "suffix": "0376A",
          "status": "OK",
          "ng_reason": null
        }
      ],
      "local_status": "OK",
      "local_ng_reason": null,
      "scan_at": "2026-07-13T09:30:25+07:00"
    }
  ],
  "summary_json": {
    "local_pending_before_batch": 1,
    "network_restored_at": "2026-07-13T09:40:00+07:00"
  }
}
```

### Field request

| Field | Kiểu | Bắt buộc | Ý nghĩa |
| --- | --- | --- | --- |
| `batch_code` | string | Có | ID unique của batch. |
| `machine_code` | string | Có | Mã máy local gửi batch. |
| `serial` | string | Có | Serial phần cứng local đã được server định danh. |
| `uid` | string | Có | UID định danh local đã được server định danh. |
| `trigger_type` | enum | Có | Lý do gửi batch. |
| `scans` | array | Có | Danh sách scan theo schema submit scan. |
| `summary_json` | object | Không | Metadata debug do local gửi. |

`trigger_type` hợp lệ:

```txt
STARTUP
SHUTDOWN
NETWORK_RESTORED
MANUAL
```

### Response batch thành công

```json
{
  "success": true,
  "code": "BATCH_SUBMIT_DONE",
  "message": "Batch submitted.",
  "data": {
    "batch": {
      "id": 20,
      "batch_code": "LOCAL01-20260713-NETWORK_RESTORED-0001",
      "machine_id": 1,
      "trigger_type": "NETWORK_RESTORED",
      "total_received": 1,
      "total_ok": 1,
      "total_ng": 0,
      "status": "DONE",
      "summary_json": {
        "input": {
          "local_pending_before_batch": 1,
          "network_restored_at": "2026-07-13T09:40:00+07:00"
        },
        "total_failed": 0,
        "results": [
          {
            "local_scan_id": "LOCAL01-20260713-000001",
            "success": true,
            "code": "SERVER_OK",
            "message": "Server accepted scan. No duplicate was detected.",
            "data": {
              "decision": "SERVER_OK",
              "server_scan_id": 123,
              "final_status": "OK",
              "ng_reason": null
            }
          }
        ]
      },
      "started_at": "2026-07-13T02:40:00.000Z",
      "finished_at": "2026-07-13T02:40:01.000Z",
      "created_at": "2026-07-13T02:40:00.000Z",
      "machine": {
        "id": 1,
        "machine_code": "LOCAL01",
        "machine_name": "Local scanner 01",
        "line_name": "LINE-A",
        "station_name": "ST-01",
        "ip_address": null,
        "is_active": true,
        "created_at": "2026-07-09T04:15:10.000Z",
        "updated_at": "2026-07-09T04:15:10.000Z"
      }
    },
    "results": [
      {
        "local_scan_id": "LOCAL01-20260713-000001",
        "success": true,
        "code": "SERVER_OK",
        "message": "Server accepted scan. No duplicate was detected.",
        "data": {
          "decision": "SERVER_OK",
          "server_scan_id": 123,
          "final_status": "OK",
          "ng_reason": null
        }
      }
    ]
  }
}
```

### Response partial failed

```json
{
  "success": false,
  "code": "BATCH_SUBMIT_PARTIAL_FAILED",
  "message": "Batch submitted with failed scan records.",
  "data": {
    "batch": {
      "id": 21,
      "batch_code": "LOCAL01-20260713-MANUAL-0001",
      "machine_id": 1,
      "trigger_type": "MANUAL",
      "total_received": 2,
      "total_ok": 1,
      "total_ng": 0,
      "status": "FAILED",
      "summary_json": {
        "input": {
          "local_pending_before_batch": 2
        },
        "total_failed": 1,
        "results": [
          {
            "local_scan_id": "LOCAL01-20260713-000003",
            "success": true,
            "code": "SERVER_OK",
            "message": "Server accepted scan. No duplicate was detected.",
            "data": {
              "decision": "SERVER_OK",
              "server_scan_id": 130,
              "final_status": "OK",
              "ng_reason": null
            }
          },
          {
            "local_scan_id": "LOCAL01-20260713-000004",
            "success": false,
            "code": "PROFILE_NOT_FOUND",
            "message": "Profile does not exist or is inactive."
          }
        ]
      },
      "started_at": "2026-07-13T03:00:00.000Z",
      "finished_at": "2026-07-13T03:00:01.000Z",
      "created_at": "2026-07-13T03:00:00.000Z",
      "machine": {
        "id": 1,
        "machine_code": "LOCAL01",
        "machine_name": "Local scanner 01",
        "line_name": "LINE-A",
        "station_name": "ST-01",
        "ip_address": null,
        "is_active": true,
        "created_at": "2026-07-09T04:15:10.000Z",
        "updated_at": "2026-07-09T04:15:10.000Z"
      }
    },
    "results": [
      {
        "local_scan_id": "LOCAL01-20260713-000003",
        "success": true,
        "code": "SERVER_OK",
        "message": "Server accepted scan. No duplicate was detected.",
        "data": {
          "decision": "SERVER_OK",
          "server_scan_id": 130,
          "final_status": "OK",
          "ng_reason": null
        }
      },
      {
        "local_scan_id": "LOCAL01-20260713-000004",
        "success": false,
        "code": "PROFILE_NOT_FOUND",
        "message": "Profile does not exist or is inactive."
      }
    ]
  }
}
```

### Cách cập nhật local DB sau batch

Local phải xử lý từng item trong `data.results`.

Nếu item `success = true`:

- cập nhật record theo `code`;
- set `sync_status = SYNCED`;
- lưu `server_scan_id` nếu có.

Nếu item `success = false`:

- giữ record pending hoặc failed theo policy local;
- log `code` và `message`;
- nếu `PROFILE_NOT_FOUND`, reload config trước khi retry;
- nếu `MACHINE_NOT_FOUND`, dừng sync và báo lỗi cấu hình máy.

### Lỗi machine_code mismatch trong batch

Trong batch, `machine_code` của batch và từng scan phải giống nhau. Nếu khác, server trả result:

```json
{
  "local_scan_id": "LOCAL02-20260713-000001",
  "success": false,
  "code": "BATCH_MACHINE_CODE_MISMATCH",
  "message": "Scan machine_code does not match batch machine_code."
}
```

## 17. Error code và cách xử lý

| Code | Nguồn | Ý nghĩa | Local nên xử lý |
| --- | --- | --- | --- |
| `SERVER_DUPLICATE` | Server | Duplicate key đã tồn tại trong cửa sổ server. | Hiển thị NG, không retry record đó. |
| `LED_SUFFIX_NOT_MATCH` | Local | LED suffix không match profile. | Lưu local NG, submit trace. |
| `LOCAL_DUPLICATE` | Local | Local phát hiện duplicate trong phạm vi local. | Lưu local NG, submit trace. |
| `FULL_CODE_INVALID_LENGTH` | Local | Full code sai độ dài. | Lưu local NG, submit trace nếu có đủ payload. |
| `FULL_VENDOR_NOT_MATCH` | Local | Vendor trong full code không match profile. | Lưu local NG, submit trace. |
| `FULL_FACTORY_NOT_MATCH` | Local | Factory trong full code không match profile. | Lưu local NG, submit trace. |
| `CHASSIS_NOT_MATCH` | Local | Chassis scan không match profile. | Lưu local NG, submit trace. |
| `LED_VENDOR_NOT_MATCH` | Local | Vendor trong LED scan không match profile. | Lưu local NG, submit trace. |
| `MACHINE_NOT_FOUND` | Server | Machine code không tồn tại hoặc inactive. | Dừng submit, báo cấu hình máy. |
| `MACHINE_IDENTITY_DISABLED` | Server | `serial` và `uid` đúng nhưng máy đã bị disable trên server. | Dừng vận hành, báo admin/engineer bật lại máy nếu cần. |
| `MACHINE_IDENTITY_MISMATCH` | Server | `machine_code`, `serial`, `uid` không khớp định danh server đã duyệt. | Dừng submit, yêu cầu kiểm tra pairing máy. |
| `MACHINE_REGISTER_DUPLICATE` | Server | Yêu cầu kết nối trùng `serial`, `uid`, `ip_address` hoặc `machine_code`. | Hiển thị field bị trùng, không gửi lại mù. |
| `MACHINE_REGISTER_PENDING` | Server | Yêu cầu kết nối đang chờ server duyệt. | Tiếp tục chờ và poll status. |
| `MACHINE_REGISTER_APPROVED` | Server | Server đã định danh máy local. | Lưu `machine_code`, bắt đầu load config. |
| `MACHINE_REGISTER_REJECTED` | Server | Server từ chối định danh máy local. | Hiển thị lý do reject, yêu cầu admin xử lý. |
| `MACHINE_REGISTER_REQUEST_NOT_FOUND` | Server | `request_id` local đang poll không tồn tại trên server. | Gọi lại `identity/status`; nếu vẫn chưa có thì gửi request mới. |
| `MACHINE_REGISTER_IDENTITY_MISMATCH` | Server | `serial` hoặc `uid` không khớp với request đang poll. | Dừng poll request đó, kiểm tra lại DB local và định danh máy. |
| `MACHINE_LICENSE_ACTIVATED` | Server UI | Đã import file license raw và kích hoạt request. | Server UI cho phép bước duyệt định danh. Local tiếp tục chờ approved. |
| `MACHINE_LICENSE_INVALID` | Server UI | Không có nội dung license để import. | Import lại file có nội dung. Local không xử lý code này. |
| `MACHINE_LICENSE_NOT_IMPORTED` | Server UI | Chưa import license nhưng đã bấm approve. | Import license trước rồi duyệt lại. |
| `PROFILE_NOT_FOUND` | Server | Profile không tồn tại hoặc inactive. | Reload config, yêu cầu chọn profile mới. |
| `PROFILE_VERSION_OUTDATED` | Dự kiến | Profile cache local cũ. | Reload config. |
| `SERVER_DISCONNECTED` | Local | Local không gọi được server. | Chuyển offline, lưu pending. |
| `SYNC_BATCH_HAS_NG` | Local hoặc Server UI | Batch sync có NG hoặc failed. | Hiển thị cảnh báo và cho phép xem chi tiết. |
| `PAYLOAD_INVALID` | API hoặc Local | Payload sai schema. | Log body, sửa parser hoặc mapping. |

## 18. Notification và ý nghĩa

### Server notification

Server có bảng `notification_templates` và `notification_events`. Các notification này chủ yếu phục vụ Server UI. Máy local hiện chưa có endpoint riêng để lấy `notification_events`.

Local nhận tác động từ server qua:

- response của submit scan;
- response của batch sync;
- command polling;
- command `SHOW_MESSAGE`.

### Notification code thống nhất

| Notification code | Target | Ý nghĩa | Local nên dùng khi nào |
| --- | --- | --- | --- |
| `LOCAL_SERVER_OFFLINE` | Local UI | Local mất kết nối server. | Health, heartbeat hoặc submit timeout. |
| `LOCAL_SERVER_RECONNECTED` | Local UI | Local kết nối lại server. | Health thành công sau offline. |
| `OFFLINE_SYNC_DONE_OK` | Local UI hoặc Both | Sync pending hoàn tất không có failed. | Sau `BATCH_SUBMIT_DONE`. |
| `OFFLINE_SYNC_HAS_NG` | Local UI hoặc Both | Batch sync có NG hoặc failed. | Sau partial failed hoặc có result final NG. |
| `MACHINE_OFFLINE` | Server UI | Server thấy máy quá hạn heartbeat. | Server UI dùng, local không cần poll event này. |
| `PROFILE_UPDATED` | Both | Profile được cập nhật. | Local reload khi nhận `SYNC_PROFILE` hoặc `RELOAD_CONFIG`. |
| `DUPLICATE_REPORT_READY` | Server UI | Job duplicate lịch sử hoàn tất. | Không cần cho runtime scan local. |
| `SERVER_DUPLICATE` | Server UI và local scan UI | Server phát hiện duplicate khi submit scan. | Local hiển thị NG từ response `SERVER_DUPLICATE`. |

### Severity gợi ý

| Severity | Ý nghĩa | Ví dụ |
| --- | --- | --- |
| `INFO` | Thông tin bình thường. | Server reconnected, sync done. |
| `WARNING` | Cần chú ý nhưng chưa dừng line. | Pending sync còn nhiều, profile reload. |
| `ERROR` | Lỗi ảnh hưởng thao tác hoặc record. | Server duplicate, payload invalid. |
| `CRITICAL` | Lỗi cần dừng vận hành. | Machine not found, không có profile active, local DB lỗi. |

### Mapping response sang notification local

| Response code | Local notification | Severity |
| --- | --- | --- |
| `SERVER_OK` | Scan accepted by server | `INFO` |
| `SERVER_DUPLICATE` | Server duplicate detected | `ERROR` |
| `LOCAL_NG_SAVED` | Local NG saved on server | `WARNING` hoặc `ERROR` tùy lỗi local |
| `HEARTBEAT_ACCEPTED` | Server online | `INFO` nếu trước đó offline |
| `BATCH_SUBMIT_DONE` | Offline sync done | `INFO` |
| `BATCH_SUBMIT_PARTIAL_FAILED` | Offline sync has failed items | `WARNING` |
| `MACHINE_NOT_FOUND` | Machine config invalid | `CRITICAL` |
| `PROFILE_NOT_FOUND` | Profile inactive or missing | `ERROR` |

## 19. Data model local khuyến nghị

Máy local nên có local DB riêng. Theo yêu cầu hiện tại, local cũng dùng PostgreSQL để đồng nhất engine với server và dễ truy vấn bằng Query Tool.

Script SQL khởi tạo toàn bộ database local PostgreSQL nằm tại `document/11-sql-khoi-tao-db-may-local-python-postgres.md`.

### Bảng cấu hình local

| Field | Ý nghĩa |
| --- | --- |
| `server_host` | IP hoặc hostname server. |
| `api_port` | Port API, mặc định 3979. |
| `machine_code` | Mã máy local. |
| `machine_serial` | Serial phần cứng local. |
| `machine_uid` | UID ổn định local. |
| `machine_license_key` | License key raw local gửi khi register. |
| `registration_request_id` | Request ID server trả khi gửi yêu cầu định danh. |
| `registration_status` | NOT_REQUESTED, PENDING, APPROVED, REJECTED, DUPLICATE. |
| `license_activated_at` | Thời điểm server đã import/kích hoạt license, nếu có. |
| `active_profile_id` | Profile đang chạy. |
| `last_config_sync_at` | Lần cuối tải config. |
| `server_online` | Trạng thái kết nối gần nhất. |
| `local_runtime_status` | Trạng thái tổng hợp để UI local hiển thị. |
| `local_status_message` | Nội dung ngắn giải thích trạng thái hiện tại. |
| `local_status_updated_at` | Thời điểm cập nhật trạng thái UI gần nhất. |

### Bảng profile cache

| Field | Ý nghĩa |
| --- | --- |
| `profile_id` | ID profile server. |
| `version` | Version profile. |
| `chassis_code_full` | Chassis hiển thị. |
| `vendor_char` | Vendor hợp lệ. |
| `factory_code` | Factory code hợp lệ. |
| `raw_json` | JSON profile đầy đủ. |
| `synced_at` | Thời điểm cache. |

### Bảng scan local

| Field | Ý nghĩa |
| --- | --- |
| `local_scan_id` | Unique theo máy. |
| `machine_code` | Mã máy local. |
| `profile_id` | Profile server ID. |
| `profile_version` | Version local dùng khi scan. |
| `duplicate_key` | Key duplicate. |
| `full_code_raw` | Full code raw. |
| `full_code_json` | JSON full_code gửi server. |
| `led_scans_json` | JSON led_scans gửi server. |
| `local_status` | OK hoặc NG. |
| `local_ng_reason` | Lý do NG local. |
| `server_code` | Code server trả. |
| `server_scan_id` | ID scan trên server nếu có. |
| `final_status` | OK, NG hoặc PENDING_SERVER. |
| `final_ng_reason` | Lý do NG cuối cùng. |
| `sync_status` | PENDING, SYNCED, FAILED_RETRYABLE, FAILED_BLOCKED. |
| `scan_at` | Thời điểm scan gốc. |
| `last_sync_at` | Lần sync gần nhất. |
| `retry_count` | Số lần retry. |

### Bảng sync batch local

| Field | Ý nghĩa |
| --- | --- |
| `batch_code` | Unique batch local. |
| `trigger_type` | STARTUP, SHUTDOWN, NETWORK_RESTORED, MANUAL. |
| `total_sent` | Số scan gửi. |
| `total_ok` | Số result final OK. |
| `total_ng` | Số result final NG. |
| `total_failed` | Số result failed. |
| `server_batch_id` | ID batch server nếu có. |
| `status` | DONE, FAILED, PARTIAL_FAILED. |
| `created_at` | Thời điểm tạo batch. |
| `finished_at` | Thời điểm hoàn tất. |

## 20. Quy tắc tạo ID

### `local_scan_id`

Format khuyến nghị:

```txt
{machine_code}-{yyyyMMdd}-{sequence_6_digits}
```

Ví dụ:

```txt
LOCAL01-20260713-000001
LOCAL01-20260713-000002
LOCAL01-20260713-000003
```

Nếu app local có nhiều thread, sequence phải cấp từ local DB bằng transaction hoặc lock.

### `batch_code`

Format khuyến nghị:

```txt
{machine_code}-{yyyyMMddHHmmss}-{trigger_type}-{sequence_4_digits}
```

Ví dụ:

```txt
LOCAL01-20260713094000-NETWORK_RESTORED-0001
LOCAL01-20260713170000-SHUTDOWN-0001
```

Nếu retry cùng batch do timeout, có thể dùng lại `batch_code`. Server hiện tại upsert batch theo `batch_code`.

## 21. Quy tắc parse và validate phía local

Server hiện tại không tự parse lại full code để quyết định local đúng hay sai. Server tin payload local gửi lên và lưu để truy vết. Vì vậy Python local phải validate đầy đủ trước khi submit.

Local cần kiểm full code:

- độ dài theo `profile.full_code_length`;
- chassis segment match profile;
- vendor char match `profile.vendor.vendor_char`;
- factory code match `profile.factory_code`;
- LED code trong full code match LED của profile;
- duplicate key parse đúng theo rule dự án.

Local cần kiểm LED scan:

- độ dài theo `profile.led_scan_length`;
- vendor char trong LED scan match profile vendor;
- suffix match `led_code.suffix_check`;
- slot required có đủ LED scan;
- mapping LED raw vào đúng slot.

Nếu fail, local submit:

```json
{
  "local_status": "NG",
  "local_ng_reason": "LED_SUFFIX_NOT_MATCH"
}
```

## 22. Python client mẫu

Cài thư viện:

```bash
pip install requests
```

File `server_api_client.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


class ServerApiError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, payload: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


@dataclass(frozen=True)
class ServerApiConfig:
    host: str
    port: int = 3979
    timeout_seconds: float = 5.0

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/api"


class SamsungQrServerClient:
    def __init__(self, config: ServerApiConfig) -> None:
        self.config = config
        self.session = requests.Session()

    def health(self) -> Dict[str, Any]:
        return self._request("GET", "/health")

    def get_identity_status(self, serial: str, uid: str) -> Dict[str, Any]:
        return self._request("GET", "/machines/identity/status", params={"serial": serial, "uid": uid})

    def register_request(
        self,
        serial: str,
        uid: str,
        ip_address: str,
        requested_machine_code: Optional[str] = None,
        license_key: Optional[str] = None,
        hostname: Optional[str] = None,
        app_version: Optional[str] = None,
        local_db_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        body = {
            "requested_machine_code": requested_machine_code,
            "serial": serial,
            "uid": uid,
            "license_key": license_key or f"{serial}|{uid}",
            "ip_address": ip_address,
            "hostname": hostname,
            "app_version": app_version,
            "local_db_version": local_db_version,
        }
        return self._request("POST", "/machines/register-request", json=body)

    def get_registration_status(self, request_id: str, serial: str, uid: str) -> Dict[str, Any]:
        return self._request(
            "GET",
            f"/machines/register-requests/{request_id}/status",
            params={"serial": serial, "uid": uid},
        )

    def get_machine_config(self, machine_code: str, serial: str, uid: str) -> Dict[str, Any]:
        return self._request("GET", f"/machines/{machine_code}/config", params={"serial": serial, "uid": uid})

    def heartbeat(
        self,
        machine_code: str,
        serial: str,
        uid: str,
        ip_address: Optional[str],
        app_version: str,
        local_db_version: str,
        local_total_record: int,
        local_ok_record: int,
        local_ng_record: int,
        local_pending_sync: int,
        local_checksum: Optional[str],
    ) -> Dict[str, Any]:
        body = {
            "machine_code": machine_code,
            "serial": serial,
            "uid": uid,
            "ip_address": ip_address,
            "app_version": app_version,
            "local_db_version": local_db_version,
            "local_total_record": local_total_record,
            "local_ok_record": local_ok_record,
            "local_ng_record": local_ng_record,
            "local_pending_sync": local_pending_sync,
            "local_checksum": local_checksum,
        }
        return self._request("POST", "/machines/heartbeat", json=body)

    def poll_commands(self, machine_code: str, serial: str, uid: str, take: int = 20) -> Dict[str, Any]:
        return self._request("GET", f"/machines/{machine_code}/commands/poll", params={"serial": serial, "uid": uid, "take": take})

    def ack_command(
        self,
        command_id: int,
        machine_code: str,
        serial: str,
        uid: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        body = {
            "machine_code": machine_code,
            "serial": serial,
            "uid": uid,
            "status": status,
            "error_message": error_message,
        }
        return self._request("POST", f"/machines/commands/{command_id}/ack", json=body)

    def submit_scan(self, scan_payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/scans/submit", json=scan_payload)

    def submit_batch(
        self,
        batch_code: str,
        machine_code: str,
        serial: str,
        uid: str,
        trigger_type: str,
        scans: List[Dict[str, Any]],
        summary_json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body = {
            "batch_code": batch_code,
            "machine_code": machine_code,
            "serial": serial,
            "uid": uid,
            "trigger_type": trigger_type,
            "scans": scans,
            "summary_json": summary_json,
        }
        return self._request("POST", "/sync/batches/submit", json=body)

    def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.config.base_url}{path}"
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=json,
                params=params,
                timeout=self.config.timeout_seconds,
            )
        except requests.Timeout as exc:
            raise ServerApiError(f"Server timeout: {url}") from exc
        except requests.ConnectionError as exc:
            raise ServerApiError(f"Cannot connect to server: {url}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise ServerApiError(
                message=f"Server returned non-JSON response: HTTP {response.status_code}",
                status_code=response.status_code,
                payload={"raw_text": response.text},
            ) from exc

        if response.status_code < 200 or response.status_code >= 300:
            message = payload.get("message") if isinstance(payload, dict) else response.text
            raise ServerApiError(
                message=str(message),
                status_code=response.status_code,
                payload=payload if isinstance(payload, dict) else {"response": payload},
            )

        if not isinstance(payload, dict):
            raise ServerApiError(
                message="Server response is not an object.",
                status_code=response.status_code,
                payload={"response": payload},
            )

        return payload
```

## 23. Python flow mẫu cho một scan

```python
from server_api_client import SamsungQrServerClient, ServerApiConfig, ServerApiError


def build_sample_ok_scan(machine_code: str, serial: str, uid: str) -> dict:
    return {
        "local_scan_id": f"{machine_code}-20260713-000001",
        "machine_code": machine_code,
        "serial": serial,
        "uid": uid,
        "profile_id": 1,
        "duplicate_key": "1A1Y420673",
        "full_code": {
            "raw": "VN39BN9660877C1A1L60376ADYS3Y420673",
            "prefix": "VN39",
            "chassis_code": "BN96-60877C",
            "before_vendor": "1A1",
            "vendor_char": "L",
            "led_code": "BN96-60376A",
            "factory_code": "DYS3",
            "after_factory": "Y420673",
        },
        "chassis_scan_raw": "BN96-60877C",
        "led_scans": [
            {
                "slot": 1,
                "index": 1,
                "raw": "ZB36L582465U528LD0376A",
                "lot_no": "528",
                "vendor_char": "L",
                "suffix": "0376A",
                "status": "OK",
                "ng_reason": None,
            }
        ],
        "local_status": "OK",
        "local_ng_reason": None,
        "scan_at": "2026-07-13T09:30:25+07:00",
    }


def apply_submit_result(local_scan_id: str, result: dict) -> None:
    code = result.get("code")
    data = result.get("data") or {}

    if code == "SERVER_OK":
        print(local_scan_id, "final OK", data.get("server_scan_id"))
        return

    if code == "SERVER_DUPLICATE":
        print(local_scan_id, "final NG", "SERVER_DUPLICATE", data.get("server_scan_id"))
        return

    if code == "LOCAL_NG_SAVED":
        print(local_scan_id, "final NG", data.get("ng_reason"), data.get("server_scan_id"))
        return

    print(local_scan_id, "unhandled server code", code, result)


def submit_one_scan() -> None:
    machine_code = "LOCAL01"
    serial = "SN-LOCAL01-2026"
    uid = "UID-8f8f2f1c-local01"
    client = SamsungQrServerClient(ServerApiConfig(host="127.0.0.1", port=3979))
    scan_payload = build_sample_ok_scan(machine_code, serial, uid)

    print("save local first", scan_payload["local_scan_id"])

    try:
        result = client.submit_scan(scan_payload)
        apply_submit_result(scan_payload["local_scan_id"], result)
    except ServerApiError as exc:
        print("keep pending", scan_payload["local_scan_id"], exc.status_code, exc.payload)
```

## 24. Retry và timeout

Khuyến nghị:

- request realtime timeout khoảng 5 giây;
- batch lớn timeout khoảng 15 đến 30 giây;
- không để request treo vô hạn;
- timeout hoặc connection error thì giữ pending;
- retry phải dùng lại cùng `local_scan_id`;
- không retry mù với `SERVER_DUPLICATE`, `LOCAL_NG_SAVED`, `MACHINE_NOT_FOUND`, `PROFILE_NOT_FOUND`.

Backoff gợi ý:

```txt
lần 1: sau 2 giây
lần 2: sau 5 giây
lần 3: sau 10 giây
sau đó: đưa vào pending sync và báo UI
```

## 25. Checklist tích hợp

### Cấu hình

- [ ] Có `SERVER-IP`.
- [ ] Có `API_PORT`, mặc định 3979.
- [ ] Có `machine_code` đúng với server.
- [ ] Có `serial` và `uid` đúng với máy đã được server định danh.
- [ ] Nếu chưa có `machine_code`, đã lưu `request_id` từ flow register request.
- [ ] Có `machine_license_key` raw để gửi khi register.
- [ ] Có local DB.
- [ ] Có profile cache.
- [ ] Có trạng thái server online/offline trên UI local.
- [ ] Có `local_runtime_status`, `local_status_message`, `local_status_updated_at` để UI local hiển thị trạng thái tổng hợp.

### Startup

- [ ] Gọi `/api/health`.
- [ ] Gọi `/api/machines/identity/status?serial=...&uid=...` để lấy `machine_code` hoặc trạng thái pairing.
- [ ] Nếu máy mới, gọi `/api/machines/register-request`.
- [ ] Nếu đang chờ định danh, poll `/api/machines/register-requests/:request_id/status`.
- [ ] Set đúng UI status: `NOT_REGISTERED`, `REGISTERING`, `WAITING_LICENSE`, `WAITING_APPROVAL`, `REJECTED` hoặc `READY`.
- [ ] Gọi `/api/machines/:machine_code/config?serial=...&uid=...`.
- [ ] Lưu settings và profiles vào local cache.
- [ ] Gửi heartbeat đầu tiên.
- [ ] Kết nối Socket.IO `/machine-runtime`.
- [ ] Emit `machine:hello` bằng `machine_code`, `serial`, `uid`.
- [ ] Poll command.
- [ ] Gửi pending batch nếu có.

### Runtime WebSocket

- [ ] Dùng Socket.IO client, không dùng raw WebSocket thuần.
- [ ] Sau connect/reconnect luôn emit `machine:hello` trước.
- [ ] Khi bắt đầu chạy, emit `runtime:start`.
- [ ] Khi có scan mới hoặc đổi số liệu OK/NG, emit `runtime:update`.
- [ ] Khi đổi mã hàng/profile, gửi `profile_id` hoặc `product_code` mới trong `runtime:update`.
- [ ] Định kỳ 3 đến 10 giây khi đang chạy, emit `runtime:snapshot`.
- [ ] Khi reconnect, emit `runtime:snapshot` với tổng hiện tại để server nối lại phiên.
- [ ] Khi dừng chạy hoặc app đóng, emit `runtime:stop` nếu còn kết nối.
- [ ] Nếu socket bị lỗi định danh, set `local_runtime_status = "BLOCKED"` và dừng submit runtime.

### Scan OK

- [ ] Lưu local DB trước khi gửi server.
- [ ] Tạo `local_scan_id` unique.
- [ ] Parse `full_code` đầy đủ.
- [ ] Parse `led_scans` đầy đủ.
- [ ] Gửi `local_status = "OK"`.
- [ ] Chỉ hiển thị final OK sau `SERVER_OK`.
- [ ] Nếu `SERVER_DUPLICATE`, hiển thị final NG.

### Scan NG

- [ ] Lưu local DB trước.
- [ ] Ghi đúng `local_ng_reason`.
- [ ] Ghi từng LED item lỗi nếu có.
- [ ] Vẫn submit server để trace.
- [ ] Xử lý `LOCAL_NG_SAVED` là sync thành công.

### Offline sync

- [ ] Timeout hoặc connection error không làm mất scan.
- [ ] Record pending giữ nguyên `local_scan_id`.
- [ ] Batch giữ `scan_at` gốc.
- [ ] Xử lý từng item trong `data.results`.
- [ ] Partial failed không đánh dấu toàn bộ batch là synced.
- [ ] Sau sync, gửi heartbeat cập nhật `local_pending_sync`.
- [ ] Khi đang sync set `local_runtime_status = "SYNCING"`, xong thì trả về `READY` nếu không còn lỗi chặn.

### Command

- [ ] Poll command định kỳ.
- [ ] Xử lý `SYNC_PROFILE`.
- [ ] Xử lý `RELOAD_CONFIG`.
- [ ] Xử lý `SYNC_SCAN_DATA`.
- [ ] Xử lý `SHOW_MESSAGE`.
- [ ] Ack `ACK` khi thành công.
- [ ] Ack `FAILED` khi lỗi.

## 26. Kịch bản test bắt buộc

1. Health: gọi `/api/health`, kỳ vọng `HEALTH_OK`.
2. Identity status: gọi `/api/machines/identity/status?serial=...&uid=...`, kỳ vọng trả approved, pending hoặc not registered rõ ràng.
3. Register request: máy mới gửi `serial`, `uid`, `license_key`, `ip_address`, kỳ vọng `MACHINE_REGISTER_REQUEST_SENT`.
4. Register pending chưa import license: local set `WAITING_LICENSE`.
5. Register pending đã có `license_activated_at`: local set `WAITING_APPROVAL`.
6. Register status: poll đến khi server duyệt, kỳ vọng `MACHINE_REGISTER_APPROVED` và local set `READY`.
7. Config: gọi `/api/machines/LOCAL01/config?serial=...&uid=...`, kỳ vọng `MACHINE_CONFIG_LOADED`.
8. Heartbeat: gửi heartbeat có `serial` và `uid`, kỳ vọng `HEARTBEAT_ACCEPTED`.
9. Identity mismatch: gửi sai `uid`, kỳ vọng `MACHINE_IDENTITY_MISMATCH` và local set `BLOCKED`.
10. Submit OK: gửi duplicate key mới, kỳ vọng `SERVER_OK`.
11. Submit duplicate: gửi scan khác cùng `profile_id + duplicate_key`, kỳ vọng `SERVER_DUPLICATE`.
12. Submit local NG: gửi `local_status = "NG"`, kỳ vọng `LOCAL_NG_SAVED`.
13. Retry idempotent: gửi lại cùng `local_scan_id`, kỳ vọng replay kết quả cũ.
14. Offline batch: tạo pending khi mất mạng, reconnect rồi gửi batch, kỳ vọng cập nhật từng result.
15. Command polling: poll command, xử lý và ack.
16. Socket hello: kết nối `/machine-runtime`, emit `machine:hello`, kỳ vọng `RUNTIME_SOCKET_ACCEPTED`.
17. Runtime start: emit `runtime:start`, server UI xuất hiện phiên `RUNNING`.
18. Runtime update: emit `runtime:update` sau scan, server UI tăng `total_count`, `ok_count`, `ng_count`.
19. Runtime đổi mã: emit `runtime:update` với `product_code` mới, server UI có thêm mã hàng trong cùng phiên.
20. Runtime reconnect: ngắt socket, kết nối lại, emit `machine:hello` và `runtime:snapshot`, kỳ vọng phiên tăng `reconnect_count`.
21. Runtime stop: emit `runtime:stop`, server UI chuyển phiên sang `STOPPED`.

## 27. Lỗi tích hợp thường gặp

### Local gửi thiếu timezone

Sai:

```txt
2026-07-13T09:30:25
```

Đúng:

```txt
2026-07-13T09:30:25+07:00
```

### Local dùng lại `local_scan_id`

Server sẽ replay kết quả cũ. Đây là lỗi nghiêm trọng phía local.

### Local NG không gửi server

Server mất trace và báo cáo thiếu dữ liệu. Local NG vẫn phải submit hoặc pending sync.

### Local tự báo OK khi server offline

Không được báo final OK. Chỉ có thể báo local OK và pending server.

### Local không reload profile khi rule đổi

Local phải xử lý `SYNC_PROFILE` và `RELOAD_CONFIG`.

### Batch partial failed nhưng local đánh dấu tất cả synced

Sai. Local phải xử lý từng item trong `data.results`.

## 28. Quick reference

| API | Success code chính | Error code chính |
| --- | --- | --- |
| `GET /api/health` | `HEALTH_OK` | Timeout, connection error |
| `GET /api/machines/identity/status` | `MACHINE_IDENTITY_APPROVED`, `MACHINE_REGISTER_PENDING`, `MACHINE_IDENTITY_NOT_REGISTERED`, `MACHINE_IDENTITY_DISABLED` | `MACHINE_IDENTITY_MISMATCH` |
| `POST /api/machines/register-request` | `MACHINE_REGISTER_REQUEST_SENT` | `MACHINE_REGISTER_DUPLICATE` |
| `GET /api/machines/register-requests/{request_id}/status` | `MACHINE_REGISTER_PENDING`, `MACHINE_REGISTER_APPROVED`, `MACHINE_REGISTER_REJECTED` | `MACHINE_REGISTER_REQUEST_NOT_FOUND`, `MACHINE_REGISTER_IDENTITY_MISMATCH` |
| `GET /api/machines/{machine_code}/config` | `MACHINE_CONFIG_LOADED` | `MACHINE_NOT_FOUND`, `MACHINE_IDENTITY_MISMATCH` |
| `POST /api/machines/heartbeat` | `HEARTBEAT_ACCEPTED` | `MACHINE_NOT_FOUND`, `MACHINE_IDENTITY_MISMATCH` |
| `GET /api/machines/{machine_code}/commands/poll` | `MACHINE_COMMANDS_POLLED` | `MACHINE_NOT_FOUND`, `MACHINE_IDENTITY_MISMATCH` |
| `POST /api/machines/commands/{id}/ack` | `MACHINE_COMMAND_ACKED`, `MACHINE_COMMAND_FAILED` | `MACHINE_COMMAND_NOT_FOUND`, `MACHINE_IDENTITY_MISMATCH` |
| `POST /api/scans/submit` | `SERVER_OK`, `SERVER_DUPLICATE`, `LOCAL_NG_SAVED` | `MACHINE_NOT_FOUND`, `MACHINE_IDENTITY_MISMATCH`, `PROFILE_NOT_FOUND` |
| `POST /api/sync/batches/submit` | `BATCH_SUBMIT_DONE`, `BATCH_SUBMIT_PARTIAL_FAILED` | `MACHINE_NOT_FOUND`, `MACHINE_IDENTITY_MISMATCH`, per-record errors |

API server admin/dev trong flow license, máy local không gọi:

| API | Success code chính | Error code chính |
| --- | --- | --- |
| `GET /api/machines/register-requests/{id}/license-export` | `MACHINE_LICENSE_INFO_EXPORTED` | `MACHINE_REGISTER_REQUEST_NOT_FOUND` |
| `POST /api/machines/register-requests/{id}/license/import` | `MACHINE_LICENSE_ACTIVATED` | `MACHINE_LICENSE_INVALID` |
| `POST /api/machines/register-requests/{id}/approve` | `MACHINE_REGISTER_APPROVED` | `MACHINE_LICENSE_NOT_IMPORTED`, `MACHINE_REGISTER_DUPLICATE` |

## 29. Kết luận

Máy local Python phải coi server là nguồn quyết định cuối cùng cho duplicate nhiều ngày. Local được phép kiểm format, rule và duplicate local, nhưng final OK chỉ được chốt sau khi server trả `SERVER_OK`.

Luồng đúng:

```txt
Scan
  -> local parse và validate
  -> local lưu DB
  -> submit server nếu online
  -> server trả SERVER_OK, SERVER_DUPLICATE hoặc LOCAL_NG_SAVED
  -> local cập nhật final status
  -> nếu offline thì giữ pending và batch sync sau
```

Nếu đội Python bám đúng các API và quy tắc trong tài liệu này, dữ liệu server sẽ đủ trace, duplicate sẽ đúng nguyên tắc OK với OK, và offline sync sẽ không làm mất record sản xuất.
