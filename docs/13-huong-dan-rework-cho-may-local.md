# Hướng dẫn tích hợp REWORK cho máy local

Tài liệu này dành cho đội phát triển máy local. Luồng REWORK dùng trực tiếp API submit scan hiện có, không có endpoint riêng.

## 1. Mục tiêu

Khi một lượt quét NG được quét lại thành công:

- Server giữ bản ghi NG gốc và thời gian NG ban đầu.
- Server đổi trạng thái bản ghi NG gốc thành `NG_REWORK`.
- Server tạo một bản ghi REWORK mới, đầy đủ dữ liệu quét lại.
- `NG_REWORK` vẫn được tính vào tổng NG; bản ghi mới được tính vào tổng REWORK.

## 2. Endpoint

```txt
POST http://<SERVER-IP>:3979/api/scans/submit
Content-Type: application/json
```

REWORK sử dụng cùng endpoint với OK và NG.

## 3. Quy tắc local_scan_id

Chọn một bản ghi local đang là NG để rework. Giả sử:

```txt
NG gốc: LOCAL-20260720161113-a3fdee48
```

ID của lượt REWORK phải là:

```txt
RW-LOCAL-20260720161113-a3fdee48
```

Quy tắc bắt buộc:

- Tiền tố đúng là `RW-` (dấu gạch ngang), không phải `RW_`.
- Phần sau `RW-` phải đúng tuyệt đối `local_scan_id` của lượt NG gốc đã gửi server.
- Lượt NG gốc phải thuộc cùng `machine_code`.
- Không được rework lại một lượt đã là `NG_REWORK`.
- Khi retry vì lỗi mạng, giữ nguyên toàn bộ payload và `local_scan_id` `RW-...`.

## 4. Payload bắt buộc

REWORK phải gửi dữ liệu đầy đủ như lượt OK, đồng thời dùng `local_status: "REWORK"`.

```json
{
  "local_scan_id": "RW-LOCAL-20260720161113-a3fdee48",
  "machine_code": "LOCAL01",
  "serial": "SN-LOCAL01-2026",
  "uid": "UID-8f8f2f1c-local01",
  "profile_id": 5,
  "duplicate_key": "1A1Y420675",
  "full_code": {
    "raw": "VN39BN9660877C1A1L60376ADYS3Y420675",
    "prefix": "VN39",
    "chassis_code": "BN96-60877C",
    "before_vendor": "1A1",
    "vendor_char": "L",
    "led_code": "BN96-60376A",
    "factory_code": "DYS3",
    "after_factory": "Y420675"
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
      "status": "REWORK",
      "ng_reason": "LED_SUFFIX_NOT_MATCH"
    }
  ],
  "local_status": "REWORK",
  "local_ng_reason": "LED_SUFFIX_NOT_MATCH",
  "scan_at": "2026-08-06T14:32:25+07:00"
}
```

Lưu ý:

- `local_ng_reason` hoặc `led_scans[].ng_reason` là mã lỗi NG gốc đang được sửa; gửi lại để server truy vết nguyên nhân rework.
- `scan_at` là thời điểm quét lại, không phải thời điểm NG gốc.
- `duplicate_key`, `full_code`, `chassis_scan_raw` và `led_scans` là bắt buộc. Payload thiếu hoặc sai cấu trúc bị từ chối.

## 5. Xử lý response

### 5.1 REWORK thành công

```json
{
  "success": true,
  "code": "LOCAL_REWORK_SAVED",
  "data": {
    "decision": "LOCAL_REWORK_SAVED",
    "server_scan_id": 126,
    "reworked_scan_record_id": 125,
    "final_status": "REWORK",
    "ng_reason": "LED_SUFFIX_NOT_MATCH"
  }
}
```

Máy local cần:

1. Lưu/cập nhật lượt `RW-...` với `server_status = OK`, `final_status = REWORK`, `sync_status = SYNCED`.
2. Đánh dấu lượt NG gốc đã được rework (nếu local lưu trạng thái server, cập nhật thành `NG_REWORK`).
3. Không thay đổi thời gian và dữ liệu quét gốc của lượt NG.
4. Lưu `server_scan_id` của lượt REWORK và `reworked_scan_record_id` để hỗ trợ truy vết.

### 5.2 REWORK bị duplicate

```json
{
  "success": true,
  "code": "SERVER_DUPLICATE",
  "data": {
    "decision": "SERVER_DUPLICATE",
    "server_scan_id": null,
    "first_scan_record_id": 87,
    "final_status": "NG",
    "ng_reason": "SERVER_DUPLICATE"
  }
}
```

Ý nghĩa:

- Server không lưu lượt REWORK.
- Server không tạo thêm bản ghi NG.
- Lượt NG gốc vẫn là `NG`, chưa thành `NG_REWORK`.
- Local hiển thị kết quả NG/duplicate cho lần rework; không tự gửi thêm một request NG mới.
- Không retry response này như lỗi mạng. Chỉ gửi lại khi nghiệp vụ cho phép quét lại sau.

### 5.3 ID REWORK không hợp lệ

Server trả HTTP 400 với mã `REWORK_SOURCE_INVALID` nếu ID không có dạng `RW-<id_NG_gốc>`.

```json
{
  "success": false,
  "code": "REWORK_SOURCE_INVALID"
}
```

Sửa ID local rồi gửi lại; không tự đổi thành request NG.

### 5.4 Không tìm thấy NG gốc

Server trả HTTP 400 với `REWORK_SOURCE_NOT_FOUND` khi không tìm được `local_scan_id` NG gốc trên cùng máy.

Kiểm tra lại ID NG đã đồng bộ thành công, `machine_code`, và tiền tố `RW-`.

### 5.5 NG gốc đã được rework

Server trả HTTP 409 với `REWORK_SOURCE_NOT_NG` khi lượt gốc không còn là `NG` (đã là `NG_REWORK` hoặc trạng thái khác).

Không tạo REWORK thứ hai cho cùng lượt NG gốc.

## 6. Pseudocode phía local

```python
def submit_rework(source_ng, rework_scan):
    assert source_ng.final_status == "NG"

    payload = build_full_scan_payload(rework_scan)
    payload["local_scan_id"] = f"RW-{source_ng.local_scan_id}"
    payload["local_status"] = "REWORK"
    payload["local_ng_reason"] = source_ng.ng_reason

    response = post_json("/api/scans/submit", payload)
    code = response["code"]

    if code == "LOCAL_REWORK_SAVED":
        mark_rework_synced(payload["local_scan_id"], response["data"])
        mark_source_ng_reworked(source_ng.local_scan_id)
        return

    if code == "SERVER_DUPLICATE":
        mark_rework_duplicate(payload["local_scan_id"], response["data"])
        return

    raise ReworkSubmitError(code)
```

## 7. Retry và offline sync

- Timeout, mất mạng, HTTP 5xx: giữ nguyên payload `RW-...` và đưa vào hàng chờ retry/offline sync.
- `LOCAL_REWORK_SAVED`: không gửi lại như một lượt mới; retry cùng ID chỉ nhận replay an toàn.
- `SERVER_DUPLICATE`, `REWORK_SOURCE_INVALID`, `REWORK_SOURCE_NOT_FOUND`, `REWORK_SOURCE_NOT_NG`: không tự retry nền; hiển thị rõ cho người vận hành hoặc xử lý theo nghiệp vụ.
- Không đổi `RW-...` thành một ID mới khi retry. Đổi ID sẽ tạo một lượt nghiệp vụ khác.

## 8. Checklist tích hợp

- [ ] Chỉ cho chọn bản ghi local đang là NG để bắt đầu REWORK.
- [ ] Sinh ID đúng `RW-<id_NG_gốc>`.
- [ ] Gửi `local_status = REWORK`.
- [ ] Gửi đầy đủ dữ liệu code và LED như lượt OK.
- [ ] Gửi lại mã lỗi NG gốc qua `local_ng_reason` hoặc LED item.
- [ ] Lưu response thành công, duplicate và lỗi nghiệp vụ riêng biệt.
- [ ] Chỉ retry lỗi mạng/5xx với cùng ID và payload.
- [ ] Cập nhật hiển thị nguồn NG là đã rework sau `LOCAL_REWORK_SAVED`.
