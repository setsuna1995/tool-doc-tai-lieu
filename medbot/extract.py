from __future__ import annotations

from dataclasses import dataclass, field

from lxml import html as lxml_html

JUNK_IMAGE_KEYWORDS = ("logo", "icon", "avatar", "pixel", "badge", "sprite", "spacer")


@dataclass
class Block:
    """Một khối nội dung: đoạn văn, danh sách, hoặc ảnh.

    Mang cả trường tiếng Anh lẫn tiếng Việt trên cùng object — cùng quy ước
    với Article ở models.py — để translate.py chỉ cần điền thêm, không phải
    dựng object song song.
    """

    kind: str  # "p" | "list" | "image"
    text: str | None = None
    text_vi: str | None = None
    items: list[str] | None = None
    items_vi: list[str] | None = None
    src: str | None = None
    alt: str | None = None
    alt_vi: str | None = None
    image_bytes: bytes | None = None  # điền ở Task 5, không bao giờ ghi vào cache


@dataclass
class Section:
    """heading=None nghĩa là phần mở đầu trước H2 đầu tiên — render thành sapo in nghiêng."""

    heading: str | None
    heading_vi: str | None = None
    blocks: list[Block] = field(default_factory=list)


def is_junk_image(src: str) -> bool:
    low = src.lower()
    return any(keyword in low for keyword in JUNK_IMAGE_KEYWORDS)


def extract_sections(clean_html: str) -> list[Section]:
    """Tách HTML ĐÃ LÀM SẠCH (đầu ra của trafilatura) thành các Section.

    Bỏ qua thẻ H1 — đó là tiêu đề gốc, ta đã có title_vi từ khâu xếp hạng.
    trafilatura xoá thuộc tính width/height khi làm sạch (đã kiểm chứng
    thật), nên lọc ảnh rác chỉ dựa vào từ khoá URL ở đây; lọc theo dung
    lượng tải về nằm ở images.py (Task 5), lớp phòng thủ thứ hai.
    """
    root = lxml_html.fromstring(clean_html)
    body = root.find("body")
    if body is None:
        body = root

    sections: list[Section] = [Section(heading=None)]
    seen_images: set[str] = set()

    for el in body.iterchildren():
        tag = el.tag
        if tag == "h1":
            continue
        if tag == "h2":
            sections.append(Section(heading=(el.text_content() or "").strip()))
            continue
        if tag == "p":
            text = (el.text_content() or "").strip()
            if not text:
                continue
            block = Block(kind="p", text=text)
        elif tag in ("ul", "ol"):
            items = [li.text_content().strip() for li in el.findall("li") if li.text_content().strip()]
            if not items:
                continue
            block = Block(kind="list", items=items)
        elif tag == "img":
            src = el.get("src", "")
            if not src or is_junk_image(src) or src in seen_images:
                continue
            seen_images.add(src)
            block = Block(kind="image", src=src, alt=el.get("alt", ""))
        else:
            continue
        sections[-1].blocks.append(block)

    # Bỏ Section mở đầu nếu rỗng (bài không có đoạn dẫn trước H2 đầu tiên)
    if not sections[0].blocks and len(sections) > 1:
        sections.pop(0)
    return sections
