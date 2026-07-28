"""Bảng dịch tiếng Việt cho từng mã "why" trả về từ license_client.verify_license,
ported từ E:\\License-Key-main\\electron\\activation.html (MESSAGES)."""

WHY_MESSAGES = {
    "chua_kich_hoat": "Máy chưa được kích hoạt license.",
    "chu_ky_sai": "Mã kích hoạt không hợp lệ hoặc đã bị chỉnh sửa.",
    "sai_may": "Mã kích hoạt này thuộc về máy khác.",
    "sai_san_pham": "Mã kích hoạt này không dùng cho sản phẩm này.",
    "het_han": "Bản dùng thử đã hết hạn.",
    "can_nang_cap_license": "License không hỗ trợ phiên bản này. Vui lòng nâng cấp.",
    "can_gia_han_de_dung_ban_moi": "Cần gia hạn để dùng bản mới hơn.",
    "license_hong_dinh_dang": "Chuỗi kích hoạt sai định dạng.",
    "license_qua_ngan": "Chuỗi kích hoạt quá ngắn, có thể đã bị cắt khi dán.",
    "payload_hong": "Nội dung mã kích hoạt bị hỏng.",
    "public_key_chua_cau_hinh": "Ứng dụng chưa cấu hình khóa. Liên hệ hỗ trợ.",
}


def describe_why(why):
    if not why:
        return ""
    return WHY_MESSAGES.get(why, f"Lỗi: {why}")
