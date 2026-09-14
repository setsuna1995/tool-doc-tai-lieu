from __future__ import annotations

import html
import re
from collections.abc import Callable
from datetime import datetime, timezone

import feedparser
import httpx

from medbot.models import Article

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


def http_get(url: str, timeout: float = 25.0) -> bytes:
    with httpx.Client(headers=BROWSER_HEADERS, timeout=timeout, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content


def strip_html(raw: str, limit: int = 300) -> str:
    text = html.unescape(_TAG.sub("", raw or ""))
    text = _SPACE.sub(" ", text).strip()
    return text if len(text) <= limit else text[:limit] + "…"


def _to_datetime(entry) -> datetime:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if parsed is None:
        return datetime.now(timezone.utc)
    return datetime(*parsed[:6], tzinfo=timezone.utc)


class RssSource:
    """Phục vụ cả kind="rss" và kind="rss_fulltext".

    Khác biệt duy nhất giữa hai kiểu là có đọc content:encoded hay không,
    nên tách thành hai lớp là thừa.
    """

    def __init__(
        self,
        name: str,
        feed: str,
        weight: float = 1.0,
        fulltext: bool = False,
        fetcher: Callable[[str], bytes] | None = None,
    ) -> None:
        self.name = name
        self.feed = feed
        self.weight = weight
        self.fulltext = fulltext
        self._fetch = fetcher or http_get

    def fetch_recent(self) -> list[Article]:
        parsed = feedparser.parse(self._fetch(self.feed))
        articles: list[Article] = []
        for entry in parsed.entries:
            link = getattr(entry, "link", "")
            if not link:
                continue
            articles.append(
                Article(
                    source=self.name,
                    title=strip_html(getattr(entry, "title", ""), limit=300),
                    url=link,
                    published=_to_datetime(entry),
                    summary=strip_html(getattr(entry, "summary", "")),
                    fulltext=self._extract_fulltext(entry),
                )
            )
        return articles

    def _extract_fulltext(self, entry) -> str | None:
        if not self.fulltext:
            return None
        content = getattr(entry, "content", None)
        if content:
            return content[0].get("value")
        return None
