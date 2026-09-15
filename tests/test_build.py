import json
from datetime import date
from pathlib import Path

import pytest

from medbot.build import (
    mark_built,
    output_path,
    parse_build_args,
    resolve_picks,
    slugify_vi,
)


def test_slugify_converts_dinh_stroke_letter():
    # unicodedata.normalize thường không tach duoc "Đ" -- phai thay tay
    assert "Do" in slugify_vi("Đồ uống quá nóng")


def test_slugify_removes_forbidden_windows_characters():
    result = slugify_vi('Tên: có "ngoặc" / gạch chéo * sao?')
    for ch in '\\/:*?"<>|':
        assert ch not in result


def test_slugify_truncates_to_limit():
    assert len(slugify_vi("x" * 200, limit=80)) == 80


def test_resolve_picks_converts_one_indexed_to_state_rows():
    state = {"picks": [{"title": "A"}, {"title": "B"}, {"title": "C"}]}
    assert [p["title"] for p in resolve_picks(state, [1, 3])] == ["A", "C"]


def test_resolve_picks_rejects_out_of_range_index():
    state = {"picks": [{"title": "A"}]}
    with pytest.raises(ValueError, match="bài số 5"):
        resolve_picks(state, [5])


def test_parse_build_args_extracts_numbers():
    numbers, target = parse_build_args(["1", "4"])
    assert numbers == [1, 4]
    assert target is None


def test_parse_build_args_extracts_date_flag():
    numbers, target = parse_build_args(["1", "4", "--date", "2026-09-12"])
    assert numbers == [1, 4]
    assert target == "2026-09-12"


def test_parse_build_args_rejects_empty_list():
    with pytest.raises(ValueError, match="số thứ tự"):
        parse_build_args([])


def test_parse_build_args_rejects_date_flag_with_no_value():
    with pytest.raises(ValueError, match="--date"):
        parse_build_args(["1", "4", "--date"])


def test_output_path_uses_year_month_subfolder_and_sanitized_title():
    cfg = {"output": {"dir": "C:/OneDrive", "subfolder": "{year}-{month}"}}
    path = output_path(cfg, date(2026, 9, 14), "Đồ uống quá nóng")
    assert "2026-09" in str(path)
    assert path.name.startswith("2026-09-14 - Do uong")
    assert path.suffix == ".docx"


def test_mark_built_sets_flag_for_matching_url(tmp_path: Path):
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({
        "picks": [{"url": "https://x.test/a", "built": False},
                  {"url": "https://x.test/b", "built": False}]
    }), encoding="utf-8")
    mark_built(state_path, "https://x.test/a")
    updated = json.loads(state_path.read_text(encoding="utf-8"))
    assert updated["picks"][0]["built"] is True
    assert updated["picks"][1]["built"] is False


from medbot.build import build_one, run
from medbot.extract import Block, Section


class FakeClient:
    def generate(self, prompt):
        import json
        # Trich cau truc tu prompt de tra ve dung so luong section/block
        # (gia lap don gian: luon dich 1 section co 1 block "p")
        return json.dumps({
            "glossary": [],
            "sections": [{"heading": None, "blocks": [{"type": "p", "text": "Đã dịch"}]}],
        }, ensure_ascii=False)


def test_build_one_writes_docx_and_marks_state(tmp_path: Path, monkeypatch):
    root = tmp_path
    (root / "state").mkdir()
    state_path = root / "state" / "2026-09-14.json"
    pick = {
        "title": "Original", "title_vi": "Đã dịch tiêu đề",
        "url": "https://x.test/a", "source": "Healthline",
        "published": "2026-09-14T06:00:00+00:00",
        "fulltext": "<p>toàn văn gốc</p><p></p>", "built": False,
    }
    state_path.write_text(json.dumps({"picks": [pick]}), encoding="utf-8")

    cfg = {
        "output": {"dir": str(root / "onedrive"), "subfolder": "{year}-{month}",
                   "font": "Times New Roman", "font_size": 13, "include_images": False},
    }

    monkeypatch.setattr("medbot.build.download_all_images", lambda sections, fetcher=None: None)

    path = build_one(pick, date(2026, 9, 14), cfg, FakeClient(), root)

    assert path.exists()
    updated = json.loads(state_path.read_text(encoding="utf-8"))
    assert updated["picks"][0]["built"] is True


def test_run_resolves_state_for_target_date_and_builds_each_pick(tmp_path: Path, monkeypatch):
    root = tmp_path
    (root / "state").mkdir()
    pick = {
        "title": "A", "title_vi": "Bài A", "url": "https://x.test/a",
        "source": "S", "published": "2026-09-12T06:00:00+00:00",
        "fulltext": "<p>nội dung</p><p></p>", "built": False,
    }
    (root / "state" / "2026-09-12.json").write_text(json.dumps({"picks": [pick]}), encoding="utf-8")

    cfg = {"output": {"dir": str(root / "onedrive"), "subfolder": "{year}-{month}",
                       "font": "Times New Roman", "font_size": 13, "include_images": False}}
    monkeypatch.setattr("medbot.build.download_all_images", lambda sections, fetcher=None: None)

    paths = run(cfg, FakeClient(), root, [1], "2026-09-12")
    assert len(paths) == 1
    assert paths[0].exists()


def test_run_raises_actionable_error_when_state_missing(tmp_path: Path):
    cfg = {"output": {"dir": str(tmp_path / "onedrive"), "subfolder": "{year}-{month}",
                       "font": "Times New Roman", "font_size": 13, "include_images": False}}
    with pytest.raises(FileNotFoundError, match="med"):
        run(cfg, FakeClient(), tmp_path, [1], "2026-01-01")
