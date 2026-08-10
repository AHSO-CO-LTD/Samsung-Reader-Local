import json
import os

from app_paths import get_config_dir

PLC_CONFIG_PATH = os.path.join(get_config_dir(), "plc_config.json")
DEFAULT_PLC_CONFIG = {
    "enabled": False,
    "port": "",
    "d_register": 100,
    "ng_value": 1,
    "mode": "pulse",
    "pulse_duration_ms": 1500,
    "ok_reset_value": 0,
    "send_on_normal_ng": True,
    "send_on_rework_ng": True,
}


def load_plc_config(path=PLC_CONFIG_PATH):
    data = dict(DEFAULT_PLC_CONFIG)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                data.update(loaded)
        except (OSError, ValueError):
            pass
    return data


def save_plc_config(config, path=PLC_CONFIG_PATH):
    data = dict(DEFAULT_PLC_CONFIG)
    data.update(config or {})
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
    return data
