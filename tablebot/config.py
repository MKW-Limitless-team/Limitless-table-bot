from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = APP_DIR
LEGACY_DATA_DIR = Path("/mnt/c/Users/pc/Desktop/Code/limitless/Limitless-bot")
CONFIG_PATH = APP_DIR / "config.json"
EXAMPLE_CONFIG_PATH = APP_DIR / "config.example.json"


def _load_config_file() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}

    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise RuntimeError(f"Config file must contain a JSON object: {CONFIG_PATH}")

    return data


def _get_setting(config: dict[str, Any], key: str, env_key: str, default: str) -> str:
    value = config.get(key)
    if value is None:
        value = os.getenv(env_key, default)
    return str(value).strip()


def _resolve_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (APP_DIR / path).resolve()


_CONFIG = _load_config_file()

TOKEN = _get_setting(_CONFIG, "token", "LIMITLESS_TABLE_BOT_TOKEN", "")
BASE_URL = _get_setting(_CONFIG, "base_url", "LIMITLESS_BASE_URL", "http://wfc.blazico.nl").rstrip("/")
STATE_DIR = _resolve_path(_get_setting(_CONFIG, "state_dir", "LIMITLESS_STATE_DIR", str(APP_DIR / "state")))
DATA_DIR = _resolve_path(_get_setting(_CONFIG, "data_dir", "LIMITLESS_DATA_DIR", str(DEFAULT_DATA_DIR)))

SOURCE_CODE_PRO_FONT = str(DATA_DIR / "SourceCodePro.ttf")

DEFAULT_TIMEOUT_SECONDS = 5
DELETE_MESSAGE_AFTER = 45
MENTION_AFTER_PING_COMMAND = False


def data_path(filename: str) -> Path:
    primary = DATA_DIR / filename
    if primary.exists():
        return primary

    legacy = LEGACY_DATA_DIR / filename
    if legacy.exists():
        return legacy

    return primary
