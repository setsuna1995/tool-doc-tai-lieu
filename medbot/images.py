from __future__ import annotations

from collections.abc import Callable

from medbot.extract import Section
from medbot.sources.rss import http_get

MIN_IMAGE_BYTES = 3000  # ảnh dưới ~3KB gần như chắc chắn là icon/pixel theo dõi


def download_image(
    url: str, fetcher: Callable[[str], bytes] | None = None, min_bytes: int = MIN_IMAGE_BYTES
) -> bytes | None:
    """Tải một ảnh, trả None nếu lỗi mạng hoặc ảnh quá nhỏ.

    Lớp phòng thủ thứ hai sau bộ lọc từ khoá URL ở extract.py: trafilatura
    xoá mất width/height khi làm sạch HTML (đã kiểm chứng thật), nên không
    thể biết trước kích thước thật — chỉ biết được sau khi đã tải về.
    """
    fetch = fetcher or http_get
    try:
        data = fetch(url)
    except Exception:
        return None
    return data if len(data) >= min_bytes else None


def download_all_images(sections: list[Section], fetcher: Callable[[str], bytes] | None = None) -> None:
    """Điền image_bytes tại chỗ. Một ảnh lỗi không được làm hỏng cả bài —
    chỉ để trống, docx_writer sẽ bỏ qua khối đó khi ghi file."""
    for section in sections:
        for block in section.blocks:
            if block.kind == "image" and block.src:
                block.image_bytes = download_image(block.src, fetcher)
