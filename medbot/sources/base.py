from __future__ import annotations

from typing import Protocol

from medbot.models import Article


class Source(Protocol):
    """Mọi adapter nguồn tuân theo giao diện này.

    Phần lõi chỉ biết tới Protocol này, nên thêm một kiểu nguồn mới
    không đụng tới xếp hạng, dịch hay xuất Word.
    """

    name: str
    weight: float

    def fetch_recent(self) -> list[Article]: ...
