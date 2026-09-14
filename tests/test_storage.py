import json
from pathlib import Path

from medbot.storage import atomic_write_text, atomic_write_json, read_json


def test_writes_vietnamese_text_as_utf8(tmp_path: Path):
    target = tmp_path / "sub" / "shortlist.md"
    atomic_write_text(target, "Uống cà phê quá nóng")
    assert target.read_text(encoding="utf-8") == "Uống cà phê quá nóng"


def test_leaves_no_temp_file_behind(tmp_path: Path):
    target = tmp_path / "out.md"
    atomic_write_text(target, "xin chào")
    assert [p.name for p in tmp_path.iterdir()] == ["out.md"]


def test_overwrites_existing_file(tmp_path: Path):
    target = tmp_path / "out.md"
    atomic_write_text(target, "bản cũ")
    atomic_write_text(target, "bản mới")
    assert target.read_text(encoding="utf-8") == "bản mới"


def test_json_roundtrip_keeps_diacritics(tmp_path: Path):
    target = tmp_path / "state.json"
    atomic_write_json(target, {"tieu_de": "Giấc ngủ"})
    assert json.loads(target.read_text(encoding="utf-8"))["tieu_de"] == "Giấc ngủ"
    assert "\\u" not in target.read_text(encoding="utf-8")


def test_read_json_returns_default_when_missing(tmp_path: Path):
    assert read_json(tmp_path / "nope.json", {"a": 1}) == {"a": 1}


def test_read_json_returns_default_when_corrupt(tmp_path: Path):
    target = tmp_path / "bad.json"
    target.write_text("{ khong phai json", encoding="utf-8")
    assert read_json(target, []) == []
