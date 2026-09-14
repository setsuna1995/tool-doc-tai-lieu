from __future__ import annotations

from collections.abc import Callable

import trafilatura

from medbot.sources.rss import http_get


def _fetch_text(url: str) -> str:
    return http_get(url).decode("utf-8", errors="replace")


def get_article_html(
    fulltext: str | None,
    url: str,
    fetcher: Callable[[str], str] | None = None,
) -> str:
    """Trả về HTML sạch của một bài, ưu tiên fulltext có sẵn trong feed.

    Dr. Axe (kind=rss_fulltext) đã có toàn văn từ lúc collect — dùng thẳng,
    khỏi tải lại trang. Các nguồn khác phải tải trang rồi để trafilatura
    lọc bỏ nav/quảng cáo/bình luận (đã kiểm chứng thật: nó tự động giải
    quyết ảnh lazy-load về URL thật, nhưng xoá mất width/height).
    """
    if fulltext:
        return fulltext

    fetch = fetcher or _fetch_text
    raw_html = fetch(url)
    cleaned = trafilatura.extract(
        raw_html, output_format="html", include_images=True, favor_precision=True
    )
    if not cleaned:
        raise ValueError(f"Không bóc được nội dung từ {url}")
    return cleaned
