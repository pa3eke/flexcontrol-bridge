import json
import os
from pathlib import Path


def get_settings_file() -> Path:
    return Path.home() / ".pa3eke_flexcontrol_bridge" / "flexcontrol_bridge_settings.json"


def load_settings() -> dict:
    try:
        data = json.loads(get_settings_file().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(flex_port: str, tci_url: str, autostart: bool = True) -> None:
    path = get_settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"flex_port": flex_port, "tci_url": tci_url,
                                     "autostart": autostart}, indent=2), encoding="utf-8")
    os.replace(temporary, path)
