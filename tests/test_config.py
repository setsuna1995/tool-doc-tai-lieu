from pathlib import Path

import pytest

from medbot.config import (
    DEFAULTS,
    deep_merge,
    detect_onedrive,
    load_api_key,
    load_config,
)


def test_deep_merge_keeps_untouched_defaults():
    base = {"a": {"x": 1, "y": 2}, "b": 3}
    assert deep_merge(base, {"a": {"y": 9}}) == {"a": {"x": 1, "y": 9}, "b": 3}


def test_deep_merge_does_not_mutate_base():
    base = {"a": {"x": 1}}
    deep_merge(base, {"a": {"x": 2}})
    assert base == {"a": {"x": 1}}


def test_detect_onedrive_prefers_folder_under_home(tmp_path: Path):
    home = tmp_path / "kiennt9"
    (home / "OneDrive").mkdir(parents=True)
    other = tmp_path / "Administrator" / "OneDrive"
    other.mkdir(parents=True)
    # Biến môi trường OneDrive trỏ sang thư mục của user khác — đã gặp thật
    found = detect_onedrive(home, {"OneDrive": str(other)})
    assert found == home / "OneDrive"


def test_detect_onedrive_falls_back_to_env_when_home_has_none(tmp_path: Path):
    home = tmp_path / "kiennt9"
    home.mkdir(parents=True)
    env_dir = tmp_path / "elsewhere" / "OneDrive"
    env_dir.mkdir(parents=True)
    assert detect_onedrive(home, {"OneDrive": str(env_dir)}) == env_dir


def test_detect_onedrive_ignores_env_pointing_at_missing_folder(tmp_path: Path):
    home = tmp_path / "kiennt9"
    home.mkdir(parents=True)
    assert detect_onedrive(home, {"OneDrive": str(tmp_path / "khong-ton-tai")}) is None


def test_load_config_returns_defaults_when_file_missing(tmp_path: Path):
    cfg = load_config(tmp_path, env={})
    assert cfg["ranking"]["shortlist_size"] == DEFAULTS["ranking"]["shortlist_size"]


def test_load_config_overrides_only_given_keys(tmp_path: Path):
    (tmp_path / "config.toml").write_text(
        '[ranking]\nshortlist_size = 8\n', encoding="utf-8"
    )
    cfg = load_config(tmp_path, env={})
    assert cfg["ranking"]["shortlist_size"] == 8
    assert cfg["ranking"]["max_age_hours"] == DEFAULTS["ranking"]["max_age_hours"]


def test_load_api_key_reads_dotenv(tmp_path: Path):
    (tmp_path / ".env").write_text("GEMINI_API_KEY=abc123\n", encoding="utf-8")
    assert load_api_key(tmp_path, env={}) == "abc123"


def test_load_api_key_prefers_process_env(tmp_path: Path):
    (tmp_path / ".env").write_text("GEMINI_API_KEY=tu-file\n", encoding="utf-8")
    assert load_api_key(tmp_path, env={"GEMINI_API_KEY": "tu-moi-truong"}) == "tu-moi-truong"


def test_load_api_key_raises_with_actionable_message(tmp_path: Path):
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        load_api_key(tmp_path, env={})
