from __future__ import annotations

from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from medbot.models import Article

HALF_LIFE_HOURS = 24.0
_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid")


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query)
        if not key.lower().startswith(_TRACKING_PREFIXES)
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), "")
    )


def dedupe(articles: list[Article]) -> list[Article]:
    seen: set[str] = set()
    result: list[Article] = []
    for article in articles:
        key = normalize_url(article.url)
        if key in seen:
            continue
        seen.add(key)
        result.append(article)
    return result


def _freshness(article: Article, now: datetime) -> float:
    """Dùng trị tuyệt đối của độ lệch, không phải max(age, 0).

    Một số feed ghi sai ngày về tương lai. Kẹp về 0 sẽ cho bài đề ngày mai
    điểm tươi tuyệt đối 1.0 — cao hơn cả bài vừa đăng nửa tiếng trước. Như
    vậy là thưởng cho ngày sai. Lệch khỏi hiện tại bao nhiêu, về phía nào,
    cũng đều là tín hiệu kém tin cậy.
    """
    drift_hours = abs((now - article.published).total_seconds()) / 3600.0
    return 0.5 ** (drift_hours / HALF_LIFE_HOURS)


def prefilter(
    articles: list[Article],
    now: datetime,
    top_n: int,
    max_age_hours: int,
    weights: dict[str, float],
) -> list[Article]:
    """Cắt vài trăm bài xuống còn top_n trước khi gọi model.

    Việc gì code làm được thì đừng trả tiền cho model làm. Gu người dùng
    KHÔNG tham gia bước này (§18.2a của spec): nghiêng theo gu ở đây sẽ
    loại bài hay thuộc chủ đề lạ trước khi Gemini kịp chấm điểm.
    """
    fresh = [
        a
        for a in dedupe(articles)
        if 0 <= (now - a.published).total_seconds() / 3600.0 <= max_age_hours
        or a.published > now
    ]
    fresh.sort(key=lambda a: _freshness(a, now) * weights.get(a.source, 1.0), reverse=True)
    return fresh[:top_n]
