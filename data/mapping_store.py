# Dữ liệu mapping TẠM THỜI (mock), thay cho việc lấy từ server (chưa kết nối).
# Khi nối server thật, chỉ cần thay nội dung load_mappings() để đọc từ server,
# giữ nguyên cấu trúc dict trả về (các key bên dưới) để không phải sửa code gọi nó.

_MOCK_MAPPINGS = [
    {
        "profile_id": 1,
        "chassis_rear": "BN96-58285A",
        "led1": "BN96-60376A",
        "led2": "BN96-60377A",
        "length_led": 22,
        "length_bottom": 35,
        "no_led": 16,
        "no_bottom": 18,
        "factory_code": "DZLV",
    },
    {
        "profile_id": 2,
        "chassis_rear": "BN96-60875C",
        "led1": "BN96-60374A",
        "led2": "",
        "length_led": 22,
        "length_bottom": 35,
        "no_led": 16,
        "no_bottom": 18,
        "factory_code": "DZLV",
    },
    {
        "profile_id": 3,
        "chassis_rear": "BN96-58578A",
        "led1": "BN96-58291A",
        "led2": "BN96-58289A",
        "length_led": 22,
        "length_bottom": 35,
        "no_led": 16,
        "no_bottom": 18,
        "factory_code": "DZLV",
    },
    {
        "profile_id": 4,
        "chassis_rear": "BN96-60877C",
        "led1": "BN96-60376A",
        "led2": "BN96-60377A",
        "length_led": 22,
        "length_bottom": 35,
        "no_led": 16,
        "no_bottom": 18,
        "factory_code": "DZLV",
    },
]


def load_mappings():
    return _MOCK_MAPPINGS
