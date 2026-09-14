from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Article:
    """Kiểu dữ liệu duy nhất mà phần lõi biết. Adapter nguồn dựng ra nó;
    xếp hạng, dịch và xuất Word chỉ tiêu thụ nó."""

    source: str
    title: str
    url: str
    published: datetime
    summary: str
    fulltext: str | None = None

    # Các trường do khâu xếp hạng điền vào
    quality: int | None = None
    topic: str | None = None
    title_vi: str | None = None
    reason_vi: str | None = None
