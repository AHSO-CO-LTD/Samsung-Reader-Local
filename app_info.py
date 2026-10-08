"""
Thông tin release + license của app — FILE DUY NHẤT cần sửa mỗi lần release.

Checklist mỗi lần release:
1. APP_VERSION: đủ 3 số "MAJOR.MINOR.PATCH" (hiển thị trên UI). License chỉ
   so số MAJOR với max_major của license (licensing/license_client.py:_major),
   nên đổi MINOR/PATCH không bắt máy kích hoạt lại; đổi MAJOR thì license cũ
   (max_major thấp hơn) sẽ báo "can_nang_cap_license".
2. APP_RELEASE_DATE: NGÀY PHÁT HÀNH bản build ("YYYY-MM-DD"), KHÔNG phải hôm
   nay — dùng so với update_until của license. CI (.github/workflows/build.yml)
   fail build tag nếu giá trị rỗng/sai định dạng.

APP_PRODUCT phải khớp TUYỆT ĐỐI với "product" bên vận hành ký vào license
(sai lệch -> "sai_san_pham"); chỉ đổi khi đã thống nhất với bên vận hành.
"""

APP_NAME = "Local Reader Monitor"
APP_VERSION = "1.0.0"
APP_RELEASE_DATE = "2026-09-23"
APP_PRODUCT = "samsung-reader-local"
