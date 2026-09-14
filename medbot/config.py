from __future__ import annotations

import copy
import os
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "schedule": {"time": "08:30", "enabled": True},
    "output": {
        "dir": "",
        "subfolder": "{year}-{month}",
        "font": "Times New Roman",
        "font_size": 13,
        "include_images": True,
    },
    "gemini": {
        "rank_models": [],
        "translate_models": [],
        "limits": {
            "flash": {"rpd": 20, "rpm": 5},
            "flash_lite": {"rpd": 500, "rpm": 15},
        },
    },
    "ranking": {"shortlist_size": 6, "max_age_hours": 48, "prefilter_top": 60},
}

_ENV_CANDIDATES = ("OneDrive", "OneDriveConsumer", "OneDriveCommercial")


def deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def detect_onedrive(home: Path, env: Mapping[str, str]) -> Path | None:
    """Ưu tiên thư mục dưới home, sau đó mới tới biến môi trường.

    Biến %OneDrive% có thể trỏ sang hồ sơ của user khác (trên máy này nó
    trỏ vào C:\\Users\\Administrator\\OneDrive trong khi thư mục thật là
    C:\\Users\\kiennt9\\OneDrive). Thư mục dưới home đáng tin hơn.
    """
    candidate = home / "OneDrive"
    if candidate.is_dir():
        return candidate
    for name in _ENV_CANDIDATES:
        raw = env.get(name)
        if raw and Path(raw).is_dir():
            return Path(raw)
    return None


def load_config(root: Path, env: Mapping[str, str] | None = None) -> dict:
    env = os.environ if env is None else env
    path = root / "config.toml"
    user: dict[str, Any] = {}
    if path.is_file():
        with path.open("rb") as handle:
            user = tomllib.load(handle)
    cfg = deep_merge(DEFAULTS, user)
    if not cfg["output"]["dir"]:
        found = detect_onedrive(Path.home(), env)
        cfg["output"]["dir"] = str(found) if found else str(root / "output")
    return cfg


def _parse_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_api_key(root: Path, env: Mapping[str, str] | None = None) -> str:
    env = os.environ if env is None else env
    key = env.get("GEMINI_API_KEY") or _parse_dotenv(root / ".env").get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError(
            "Thiếu GEMINI_API_KEY. Tạo file .env ở gốc dự án với nội dung:\n"
            "GEMINI_API_KEY=<khoá lấy ở https://aistudio.google.com/apikey>"
        )
    return key
