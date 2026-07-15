# Triển khai "Local Reader Monitor" trên máy production

Hướng dẫn cài đặt cho người lắp đặt máy tại chỗ (máy production sạch — chưa có Python/PostgreSQL). Không cần cài Python thủ công.

## Cài đặt lần đầu

1. Tải bản release mới nhất từ GitHub (file `.zip`) → giải nén ra 1 thư mục bất kỳ trên máy (ví dụ `C:\LocalReaderMonitor`).
2. Trong thư mục vừa giải nén, chuột phải `setup.ps1` → **Run with PowerShell** (hoặc mở PowerShell tại thư mục đó, chạy `.\setup.ps1`).
   - Script tự kiểm tra và cài PostgreSQL nếu máy chưa có, tạo role/database/schema, và sinh `local_db_config.json` cạnh `LocalReaderMonitor.exe`.
   - Script chạy lại được nhiều lần một cách an toàn (không tạo trùng, không ghi đè cấu hình đã có) — nếu có lỗi giữa chừng, chạy lại `setup.ps1` là đủ.
   - Nếu máy chưa có PowerShell/winget hỗ trợ cài tự động, script sẽ dừng lại và in hướng dẫn cài PostgreSQL thủ công (kèm mật khẩu cần đặt) — cài xong thì chạy lại `setup.ps1`.
3. Mở `LocalReaderMonitor.exe`.
4. Bấm **Change Server IP** — nhập đúng địa chỉ IP:port của server thật tại nhà máy (không phải địa chỉ mặc định lúc dev).
5. Bấm **Configure** — thêm 3 đầu đọc thật (LED BAR 1, LED BAR 2, QRCODE BOTTOM) với đúng IP/port thật của từng đầu đọc (không phải cấu hình mock/test).
6. Bấm **Register** — gửi yêu cầu đăng ký máy, chờ admin phía server duyệt (xem trạng thái ngay trong dialog).
7. Sau khi được duyệt (trạng thái chuyển READY), quét thử 1 sản phẩm thật để xác nhận toàn bộ chuỗi hoạt động (đọc mã → so khớp OK/NG → gửi server).
8. Nếu gặp lỗi ở bất kỳ bước nào, gửi kèm file `app_error.log` (nằm cạnh `LocalReaderMonitor.exe`, chỉ xuất hiện khi có lỗi chưa xử lý được) cho kỹ sư phụ trách.

## Khắc phục sự cố cơ bản

- **Mở app báo lỗi kết nối DB ngay lập tức**: `setup.ps1` chưa chạy hoặc chạy chưa xong — chạy lại `setup.ps1`.
- **App mở được nhưng không kết nối server**: kiểm tra lại IP:port đã nhập ở "Change Server IP", và máy có thật sự nối được vào mạng LAN nhà máy không.
- **Đầu đọc hiện "Mất kết nối"**: kiểm tra IP/port đầu đọc trong "Configure", và cáp mạng/nguồn của đầu đọc vật lý.
- **App tự đóng không rõ lý do**: xem `app_error.log` cạnh `.exe` — file này ghi lại traceback đầy đủ của lỗi gần nhất.

---

## Thông tin quản trị (dành cho kỹ sư — không phải operator)

Mật khẩu PostgreSQL dùng **cố định, giống nhau trên mọi máy** (quyết định có chủ đích — Postgres chỉ chạy nội bộ `127.0.0.1`, không mở ra mạng ngoài, nên ưu tiên "ai cũng tra được đúng mật khẩu khi cần" hơn là mỗi máy 1 mật khẩu ngẫu nhiên rồi mất dấu nếu `local_db_config.json` bị sửa/xoá nhầm). Giá trị đúng bằng 2 tham số mặc định trong `setup.ps1`:

| Tài khoản | Mật khẩu | Dùng khi nào |
| --- | --- | --- |
| `postgres` (superuser) | `LRM_PgSuper_2026_Change_If_Needed!` | Thao tác quản trị Postgres trực tiếp (pgAdmin/psql), hoặc khi cài PostgreSQL thủ công trên máy chưa hỗ trợ cài tự động |
| `samsung_qr_local_user` (role app) | `LRM_AppRole_2026_Change_If_Needed!` | Giá trị nằm trong `local_db_config.json` — nếu file này bị mất/sửa nhầm, xoá đi và chạy lại `setup.ps1` sẽ tự sinh lại đúng file với mật khẩu này |

Nếu cần đổi 2 giá trị này (ví dụ theo yêu cầu bảo mật riêng của nhà máy): sửa tham số mặc định `$PgSuperPassword`/`$AppRolePassword` ở đầu `setup.ps1`, cập nhật lại đúng giá trị mới vào bảng trên, và áp dụng nhất quán cho MỌI máy sẽ cài từ bản release đó trở đi (đổi giá trị nhưng không cập nhật lại doc này sẽ khiến không ai tra được mật khẩu đúng khi cần).

`setup.ps1` cũng nhận tham số `-AppRoleName`/`-AppDbName`/`-PgPort` để đổi tên role/database/cổng nếu cần test hoặc triển khai khác chuẩn — không dùng cho máy production thật (giữ nguyên mặc định `samsung_qr_local_user`/`samsung_qr_local`/`5432`).
