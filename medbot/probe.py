from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from medbot.sources.rss import BROWSER_HEADERS

CANDIDATE_PATHS = ("/feed/", "/rss", "/rss.xml", "/feed/rss", "/rss/all.xml")

_FEED_LINK = re.compile(
    rb"""<link[^>]+type=["']application/(?:rss|atom)\+xml["'][^>]*>""", re.I
)
_HREF = re.compile(rb"""href=["']([^"']+)["']""", re.I)
_ITEM_LINK = re.compile(rb"<link>\s*(https?://[^<\s]+)\s*</link>")


@dataclass
class ProbeResult:
    site: str
    feed_url: str | None
    item_count: int
    has_fulltext: bool
    article_url: str | None
    article_status: int | None


def status_fetch(url: str, timeout: float = 25.0) -> tuple[int, bytes]:
    """Trả về mã trạng thái thay vì ném lỗi — chính mã lỗi là thông tin cần đo."""
    try:
        with httpx.Client(
            headers=BROWSER_HEADERS, timeout=timeout, follow_redirects=True
        ) as client:
            response = client.get(url)
            return response.status_code, response.content
    except httpx.HTTPError:
        return 0, b""


def find_embedded_feeds(html_bytes: bytes, base_url: str) -> list[str]:
    feeds: list[str] = []
    for tag in _FEED_LINK.findall(html_bytes):
        match = _HREF.search(tag)
        if match:
            feeds.append(urljoin(base_url, match.group(1).decode("utf-8", "ignore")))
    return feeds


def probe(url: str, fetcher: Callable[[str], tuple[int, bytes]]) -> ProbeResult:
    _, html_bytes = fetcher(url)
    candidates = find_embedded_feeds(html_bytes, url)
    candidates += [urljoin(url, path) for path in CANDIDATE_PATHS]

    best_url: str | None = None
    best_body = b""
    best_count = 0
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        status, body = fetcher(candidate)
        if status != 200:
            continue
        count = body.count(b"<item")
        if count > best_count:
            best_url, best_body, best_count = candidate, body, count

    if best_url is None:
        return ProbeResult(url, None, 0, False, None, None)

    article_url = None
    article_status = None
    match = _ITEM_LINK.search(best_body)
    if match:
        article_url = match.group(1).decode("utf-8", "ignore")
        article_status, _ = fetcher(article_url)

    return ProbeResult(
        site=url,
        feed_url=best_url,
        item_count=best_count,
        has_fulltext=b"content:encoded" in best_body,
        article_url=article_url,
        article_status=article_status,
    )


def render_source_block(result: ProbeResult, name: str) -> str:
    if result.feed_url is None:
        raise ValueError(f"Không tìm được feed cho {result.site}")

    kind = "rss_fulltext" if result.has_fulltext else "rss"
    lines = [
        "[[source]]",
        f'name   = "{name}"',
        f'kind   = "{kind}"',
        f'feed   = "{result.feed_url}"',
        "weight = 1.0",
        "",
        f"# {result.item_count} bài trong feed.",
    ]
    if result.has_fulltext:
        lines.append("# Feed kèm toàn văn — không cần tải trang bài.")
    if result.article_status not in (None, 200):
        lines.append(
            f"# CẢNH BÁO: trang bài trả {result.article_status}. "
            "Lấy được danh sách nhưng KHÔNG đọc được toàn văn."
        )
    return "\n".join(lines)
