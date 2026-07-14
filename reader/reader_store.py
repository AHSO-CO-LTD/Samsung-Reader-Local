import json
import os

DEFAULT_STORE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "readers_config.json")


def load_readers(path=DEFAULT_STORE_PATH):
    """Trả về list[dict] các reader đã lưu, mỗi dict có
    name, ip, data_port, command_port (command_port có thể là None)."""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_readers(readers, path=DEFAULT_STORE_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(readers, f, indent=2, ensure_ascii=False)
