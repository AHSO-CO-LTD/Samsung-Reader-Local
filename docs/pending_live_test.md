# Việc chưa test được với server thật

> File tạm. Xoá từng mục sau khi tự test xong với server thật (không tính test tĩnh/mock). Xoá cả file này nếu rỗng.

## Bước 5: `commands/poll` + `commands/:id/ack`

Đã verify với server thật (2026-07-15): poll hoạt động đúng (`MACHINE_COMMANDS_POLLED`, 200, nhiều lần), 3 dòng `command_inbox` cũ (id 101/102/103) xác nhận là rác test tĩnh ngày 2026-07-14 chứ không phải dữ liệu thật, không bị xử lý nhầm. `_commands_poll_timer` tự start đúng lúc.

Còn thiếu đúng 1 việc, cần admin tạo command thật trên server cho máy `Local02` mới test được:

- Chưa xác nhận command `SYNC_PROFILE`/`RELOAD_CONFIG`/`SHOW_MESSAGE` THẬT do server tạo có kích hoạt đúng luồng tự động (tải lại config + ack qua `correlation_id`) hay không — server hiện không có command nào đang chờ cho máy này để test.

**Cách test khi có command thật**: nhờ admin tạo 1 command (vd `SHOW_MESSAGE` — ít rủi ro nhất) cho `machine_code=Local02` trên server, sau đó mở app thật, đợi tối đa 30s (interval poll), xem `command_inbox`/`api_request_logs` (`request_type IN ('commands_poll','command_ack')`) qua Query Tool để xác nhận ack đúng.
