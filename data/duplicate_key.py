"""
Tính duplicate_key từ mã QRCODE BOTTOM — dùng để kiểm tra mã độc nhất trong
ngày (db/local_db.py) và sau này gửi lên server (theo
docs/11-sql-khoi-tao-db-may-local-python-postgres (2).md: "tạo từ
before_vendor + vendor_char + after_factory").

duplicate_key = đoạn before_vendor + ký tự vendor + đoạn after_factory, dùng
đúng vị trí cố định theo cấu trúc mã thực tế hiện có:
    prefix(1-4) + chassis(5-14) + before_vendor(15-17) + vendor(18)
    + led(19-24) + factory(25-28) + after_factory(29-35) = 35 ký tự

Có vendor_char trong khóa để không nhầm 2 vendor LED khác nhau cùng
chassis_rear là trùng nhau, dù đoạn before_vendor/after_factory tình cờ giống
(mỗi vendor đánh số lô riêng).

Cố tình KHÔNG tổng quát hóa theo no_bottom/length_bottom của từng mã hàng —
chưa có gì đảm bảo mã hàng khác cũng theo đúng cấu trúc này, viết cứng theo
mã hàng thực tế đang biết an toàn hơn suy diễn tổng quát chưa kiểm chứng.
"""


def compute_duplicate_key(text):
    """Trả về duplicate_key (str), hoặc None nếu text không đúng 35 ký tự."""
    if len(text) != 35:
        return None
    before_vendor = text[14:17]
    vendor_char = text[17:18]
    after_factory = text[28:]
    return before_vendor + vendor_char + after_factory
