from __future__ import annotations

import json
from collections.abc import Callable

from medbot.extract import Block, Section
from medbot.jsonutil import strip_json_fence

TRANSLATE_INSTRUCTIONS = """\
Bạn là biên tập viên dịch bài y học thường thức sang tiếng Việt cho một
chuyên trang sức khoẻ.

Quy tắc BẮT BUỘC:
- Không thêm bất kỳ dữ kiện nào không có trong bản gốc.
- Giữ nguyên mọi con số, đơn vị, tên nghiên cứu, tên tổ chức, tên thuốc.
- Thuật ngữ y học: viết tiếng Việt kèm tiếng Anh trong ngoặc ở lần đầu
  xuất hiện trong TOÀN BỘ bài (không phải chỉ đoạn này).
- Văn phong báo sức khoẻ tiếng Việt, câu ngắn, không dịch từng từ.

Dữ liệu đầu vào là một mảng JSON các section tiếng Anh. Hãy trả về ĐÚNG
một object JSON, không kèm lời dẫn, không kèm dấu ```, theo khuôn:

{
  "glossary": [{"en": "thuật ngữ gốc", "vi": "bản dịch"}],
  "sections": [
    {"heading": "tiêu đề đã dịch hoặc null nếu heading gốc là null",
     "blocks": [
        {"type": "p", "text": "đoạn văn đã dịch"},
        {"type": "list", "items": ["mục 1 đã dịch", "mục 2 đã dịch"]},
        {"type": "image", "alt": "chú thích ảnh đã dịch"}
     ]}
  ]
}

Giữ NGUYÊN số lượng section và số lượng block trong mỗi section, đúng
thứ tự, đúng "type" như đầu vào — chỉ thay nội dung chữ.
"""


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def section_tokens(section: Section) -> int:
    total = estimate_tokens(section.heading) if section.heading else 0
    for block in section.blocks:
        if block.kind == "p":
            total += estimate_tokens(block.text or "")
        elif block.kind == "list":
            total += sum(estimate_tokens(i) for i in (block.items or []))
        elif block.kind == "image":
            total += estimate_tokens(block.alt or "")
    return total


def chunk_sections(sections: list[Section], max_tokens: int = 6000) -> list[list[Section]]:
    """Gom section liên tiếp vào một lô cho tới ngưỡng token, không bao giờ
    cắt đôi một section. Một section cực dài vẫn được giữ nguyên vẹn trong
    lô của riêng nó thay vì bị bỏ sót."""
    chunks: list[list[Section]] = []
    current: list[Section] = []
    current_tokens = 0
    for section in sections:
        tokens = section_tokens(section)
        if current and current_tokens + tokens > max_tokens:
            chunks.append(current)
            current, current_tokens = [], 0
        current.append(section)
        current_tokens += tokens
    if current:
        chunks.append(current)
    return chunks


def _block_to_prompt_dict(block: Block) -> dict:
    if block.kind == "p":
        return {"type": "p", "text": block.text}
    if block.kind == "list":
        return {"type": "list", "items": block.items}
    return {"type": "image", "alt": block.alt or ""}


def build_translate_prompt(chunk: list[Section], glossary: dict[str, str], article_title_en: str) -> str:
    lines = [TRANSLATE_INSTRUCTIONS, f"Tiêu đề bài (chỉ để hiểu ngữ cảnh): {article_title_en}", ""]
    if glossary:
        lines.append("Sổ thuật ngữ đã dùng ở phần trước — giữ nhất quán, đừng dịch khác đi:")
        for en, vi in glossary.items():
            lines.append(f"- {en} → {vi}")
        lines.append("")
    skeleton = [
        {"heading": s.heading, "blocks": [_block_to_prompt_dict(b) for b in s.blocks]}
        for s in chunk
    ]
    lines.append(json.dumps(skeleton, ensure_ascii=False, indent=2))
    return "\n".join(lines)


def parse_translation(raw: str, chunk: list[Section]) -> dict:
    text = strip_json_fence(raw)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini không trả về JSON hợp lệ: {exc}") from exc

    if not isinstance(data, dict) or "sections" not in data:
        raise ValueError("Thiếu trường 'sections' trong JSON trả về.")
    sections = data["sections"]
    if len(sections) != len(chunk):
        raise ValueError(f"Số section không khớp: gửi {len(chunk)}, nhận {len(sections)}.")

    for original, translated in zip(chunk, sections):
        blocks = translated.get("blocks", [])
        if len(blocks) != len(original.blocks):
            raise ValueError(
                f"Số block không khớp ở section {original.heading!r}: "
                f"gửi {len(original.blocks)}, nhận {len(blocks)}."
            )
        for orig_block, trans_block in zip(original.blocks, blocks):
            if trans_block.get("type") != orig_block.kind:
                raise ValueError(
                    f"type không khớp: gửi {orig_block.kind!r}, nhận {trans_block.get('type')!r}."
                )
    data.setdefault("glossary", [])
    return data


def apply_translation(chunk: list[Section], parsed: dict) -> dict[str, str]:
    for section, translated in zip(chunk, parsed["sections"]):
        section.heading_vi = translated.get("heading")
        for block, trans_block in zip(section.blocks, translated["blocks"]):
            if block.kind == "p":
                block.text_vi = trans_block.get("text")
            elif block.kind == "list":
                block.items_vi = trans_block.get("items")
            elif block.kind == "image":
                block.alt_vi = trans_block.get("alt")
    return {item["en"]: item["vi"] for item in parsed["glossary"]}


def translate_chunk(
    chunk: list[Section], client, glossary: dict[str, str], article_title_en: str
) -> dict[str, str]:
    """Dịch một lô, điền _vi tại chỗ, trả về glossary đã gộp thêm thuật ngữ mới.

    Thử lại tối đa một lần khi JSON hỏng — cùng quy ước với rank.rank().
    """
    prompt = build_translate_prompt(chunk, glossary, article_title_en)
    last_error: Exception | None = None
    for _ in range(2):
        try:
            parsed = parse_translation(client.generate(prompt), chunk)
        except ValueError as exc:
            last_error = exc
            continue
        new_terms = apply_translation(chunk, parsed)
        return {**glossary, **new_terms}
    raise last_error  # type: ignore[misc]


def _block_to_cache_dict(block: Block) -> dict:
    return {
        "text_vi": block.text_vi,
        "items_vi": block.items_vi,
        "alt_vi": block.alt_vi,
    }


def serialize_chunk(chunk: list[Section]) -> list[dict]:
    """Chỉ lưu phần đã dịch — không bao giờ lưu image_bytes vào cache JSON."""
    return [
        {"heading_vi": s.heading_vi, "blocks": [_block_to_cache_dict(b) for b in s.blocks]}
        for s in chunk
    ]


def apply_cached_chunk(chunk: list[Section], cached: list[dict]) -> None:
    for section, cached_section in zip(chunk, cached):
        section.heading_vi = cached_section["heading_vi"]
        for block, cached_block in zip(section.blocks, cached_section["blocks"]):
            block.text_vi = cached_block.get("text_vi")
            block.items_vi = cached_block.get("items_vi")
            block.alt_vi = cached_block.get("alt_vi")


def translate_article(
    sections: list[Section],
    client,
    cache: dict,
    save_cache: Callable[[dict], None],
    article_title_en: str,
    max_tokens_per_chunk: int = 6000,
) -> None:
    """Dịch toàn bài theo lô, mang sổ thuật ngữ giữa các lô, cache từng lô
    ngay sau khi xong để chạy lại giữa chừng không tốn quota đã dùng.
    """
    chunks = chunk_sections(sections, max_tokens_per_chunk)
    glossary: dict[str, str] = {}
    for index, chunk in enumerate(chunks):
        key = f"chunk_{index}"
        cached = cache.get(key)
        if cached is not None:
            apply_cached_chunk(chunk, cached)
            continue
        glossary = translate_chunk(chunk, client, glossary, article_title_en)
        cache[key] = serialize_chunk(chunk)
        save_cache(cache)
