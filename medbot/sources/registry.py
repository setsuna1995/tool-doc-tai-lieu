from __future__ import annotations

import tomllib
from collections.abc import Callable
from pathlib import Path

from medbot.sources.base import Source
from medbot.sources.rss import RssSource

_RSS_KINDS = {"rss": False, "rss_fulltext": True}


def build_sources(path: Path, fetcher: Callable[[str], bytes] | None = None) -> list[Source]:
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy sources.toml tại {path}")
    with path.open("rb") as handle:
        data = tomllib.load(handle)

    sources: list[Source] = []
    for entry in data.get("source", []):
        name = entry.get("name", "(không tên)")
        kind = entry.get("kind")
        if kind in _RSS_KINDS:
            sources.append(
                RssSource(
                    name=name,
                    feed=entry["feed"],
                    weight=float(entry.get("weight", 1.0)),
                    fulltext=_RSS_KINDS[kind],
                    fetcher=fetcher,
                )
            )
        elif kind == "browser":
            raise NotImplementedError(
                f"Nguồn '{name}' dùng kind=browser — adapter Playwright thuộc kế hoạch 3."
            )
        else:
            raise ValueError(f"Nguồn '{name}' có kind không hợp lệ: {kind!r}")
    return sources
