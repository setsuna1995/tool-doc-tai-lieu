from __future__ import annotations

import json
import re
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


_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$", re.M)
_REQUIRED = ("index", "quality", "topic", "title_vi", "reason_vi")

RANKING_INSTRUCTIONS = """\
Bạn là biên tập viên một chuyên trang sức khoẻ tiếng Việt.

Dưới đây là danh sách bài báo y học thường thức tiếng Anh đăng trong 48 giờ qua.
Với MỖI bài, hãy trả về một đối tượng JSON gồm đúng các trường sau:

- index:     số thứ tự trong ngoặc vuông của bài (số nguyên)
- quality:   0-100, mức đáng đọc với độc giả Việt Nam phổ thông.
             Cho điểm cao khi bài hữu ích, dễ áp dụng, dựa trên bằng chứng.
             Cho điểm thấp khi bài là quảng cáo, tin vụn, hoặc chỉ liên quan tới Mỹ.
- topic:     chủ đề ngắn gọn bằng tiếng Việt, 1-3 từ (ví dụ: "dinh dưỡng", "giấc ngủ")
- title_vi:  tiêu đề dịch sang tiếng Việt, giữ đúng nghĩa, không giật gân
- reason_vi: một câu tiếng Việt giải thích vì sao đáng đọc hoặc không

Chỉ trả về một mảng JSON. Không kèm lời dẫn, không kèm dấu ``` .
"""


def build_ranking_prompt(articles: list[Article]) -> str:
    lines = [RANKING_INSTRUCTIONS, ""]
    for position, article in enumerate(articles):
        lines.append(f"[{position}] ({article.source}) {article.title}")
        if article.summary:
            lines.append(f"    {article.summary}")
    return "\n".join(lines)


def parse_ranking(raw: str, count: int) -> list[dict]:
    text = _FENCE.sub("", raw.strip()).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini không trả về JSON hợp lệ: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError("Gemini trả về JSON nhưng không phải mảng.")

    for item in data:
        missing = [field for field in _REQUIRED if field not in item]
        if missing:
            raise ValueError(f"Thiếu trường {missing} trong một mục trả về.")
        if not isinstance(item["index"], int) or not 0 <= item["index"] < count:
            raise ValueError(f"index ngoài phạm vi: {item['index']!r}")
        quality = item["quality"]
        if not isinstance(quality, int) or not 0 <= quality <= 100:
            raise ValueError(f"quality phải là số nguyên 0-100, nhận {quality!r}")
    return data


def apply_scores(articles: list[Article], scored: list[dict]) -> list[Article]:
    touched: list[Article] = []
    for item in scored:
        article = articles[item["index"]]
        article.quality = item["quality"]
        article.topic = item["topic"]
        article.title_vi = item["title_vi"]
        article.reason_vi = item["reason_vi"]
        touched.append(article)
    return touched


def rank(articles: list[Article], client, shortlist_size: int) -> list[Article]:
    """Chấm điểm rồi trả về shortlist_size bài điểm cao nhất.

    Thử lại tối đa một lần khi JSON hỏng — model đôi khi kèm lời dẫn thừa.
    Quá một lần thì vấn đề nằm ở prompt chứ không phải may rủi.
    """
    prompt = build_ranking_prompt(articles)
    last_error: Exception | None = None
    for _ in range(2):
        try:
            scored = parse_ranking(client.generate(prompt), len(articles))
        except ValueError as exc:
            last_error = exc
            continue
        chosen = apply_scores(articles, scored)
        chosen.sort(key=lambda a: a.quality or 0, reverse=True)
        return chosen[:shortlist_size]
    raise last_error  # type: ignore[misc]
