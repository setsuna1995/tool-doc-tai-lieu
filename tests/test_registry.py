from pathlib import Path

import pytest

from medbot.sources.registry import build_sources


def write_toml(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "sources.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_builds_plain_rss_source(tmp_path: Path):
    path = write_toml(tmp_path, """
[[source]]
name = "Healthline"
kind = "rss"
feed = "https://example.test/feed"
weight = 1.2
""")
    sources = build_sources(path)
    assert len(sources) == 1
    assert sources[0].name == "Healthline"
    assert sources[0].weight == 1.2
    assert sources[0].fulltext is False


def test_fulltext_kind_sets_flag(tmp_path: Path):
    path = write_toml(tmp_path, """
[[source]]
name = "Dr. Axe"
kind = "rss_fulltext"
feed = "https://example.test/feed"
""")
    assert build_sources(path)[0].fulltext is True


def test_weight_defaults_to_one(tmp_path: Path):
    path = write_toml(tmp_path, """
[[source]]
name = "X"
kind = "rss"
feed = "https://example.test/feed"
""")
    assert build_sources(path)[0].weight == 1.0


def test_browser_kind_not_supported_yet(tmp_path: Path):
    path = write_toml(tmp_path, """
[[source]]
name = "Mayo Clinic"
kind = "browser"
url = "https://example.test/"
""")
    with pytest.raises(NotImplementedError, match="browser"):
        build_sources(path)


def test_unknown_kind_names_the_offending_source(tmp_path: Path):
    path = write_toml(tmp_path, """
[[source]]
name = "Lạ"
kind = "telepathy"
feed = "https://example.test/feed"
""")
    with pytest.raises(ValueError, match="Lạ"):
        build_sources(path)


def test_missing_file_gives_actionable_error(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="sources.toml"):
        build_sources(tmp_path / "sources.toml")


def test_shipped_sources_file_is_valid():
    sources = build_sources(Path(__file__).parent.parent / "sources.toml")
    assert {s.name for s in sources} == {
        "Healthline", "Prevention", "Science Times", "Dr. Axe",
    }
