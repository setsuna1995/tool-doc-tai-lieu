from pathlib import Path

from medbot.extract import Block, Section, extract_sections, is_junk_image

FIXTURE = (Path(__file__).parent.parent / "fixtures" / "article_full_page.html").read_text(encoding="utf-8")


def test_is_junk_image_matches_known_keywords():
    assert is_junk_image("https://cdn.example.com/logo-icon.png")
    assert is_junk_image("https://cdn.example.com/user-AVATAR.jpg")
    assert not is_junk_image("https://cdn.example.com/coffee-full.jpg")


def test_skips_the_leading_h1():
    sections = extract_sections(FIXTURE)
    all_text = " ".join(
        (b.text or "") for s in sections for b in s.blocks if b.kind == "p"
    )
    assert "Esophageal Cancer" not in all_text  # H1 không lọt vào bất kỳ block nào


def test_first_section_is_the_lead_with_no_heading():
    sections = extract_sections(FIXTURE)
    assert sections[0].heading is None
    assert any(b.kind == "p" and "500,000 people" in (b.text or "") for b in sections[0].blocks)


def test_lead_keeps_its_image():
    sections = extract_sections(FIXTURE)
    images = [b for b in sections[0].blocks if b.kind == "image"]
    assert images[0].src == "https://cdn.example.com/coffee-full.jpg"


def test_splits_into_sections_by_h2():
    sections = extract_sections(FIXTURE)
    headings = [s.heading for s in sections if s.heading is not None]
    assert headings == ["The heat is the culprit", "What you can do"]


def test_keeps_bullet_list_inside_its_section():
    sections = extract_sections(FIXTURE)
    culprit = next(s for s in sections if s.heading == "The heat is the culprit")
    lists = [b for b in culprit.blocks if b.kind == "list"]
    assert lists[0].items == ["Above 65C: risk increased 90%", "Below 60C: no significant increase"]


def test_drops_junk_logo_image():
    sections = extract_sections(FIXTURE)
    all_images = [b.src for s in sections for b in s.blocks if b.kind == "image"]
    assert "https://cdn.example.com/logo-icon.png" not in all_images


def test_deduplicates_repeated_image_url():
    html = """<html><body><h2>A</h2>
    <img src="https://x.test/pic.jpg" alt="1"/>
    <p>x</p>
    <img src="https://x.test/pic.jpg" alt="2"/>
    </body></html>"""
    sections = extract_sections(html)
    images = [b for s in sections for b in s.blocks if b.kind == "image"]
    assert len(images) == 1


def test_empty_paragraphs_are_skipped():
    html = "<html><body><h2>A</h2><p>   </p><p>Nội dung thật</p></body></html>"
    sections = extract_sections(html)
    assert len(sections[0].blocks) == 1


def test_no_h2_at_all_puts_everything_in_lead():
    html = "<html><body><p>Chỉ có một đoạn, không H2.</p></body></html>"
    sections = extract_sections(html)
    assert len(sections) == 1
    assert sections[0].heading is None


def test_new_dataclasses_carry_translation_fields_side_by_side():
    block = Block(kind="p", text="hello")
    block.text_vi = "xin chào"
    section = Section(heading="H", blocks=[block])
    section.heading_vi = "Tiêu đề"
    assert section.heading == "H" and section.heading_vi == "Tiêu đề"


def test_prefers_srcset_highest_resolution_over_placeholder_src():
    # Nguồn RSS fulltext (Dr. Axe) không qua trafilatura nên không được giải
    # quyết lazy-load — spec §10 yêu cầu tự ưu tiên srcset > data-src > src.
    html = (
        '<html><body><h2>A</h2>'
        '<img src="https://cdn.example.com/placeholder.gif" '
        'srcset="https://cdn.example.com/small.jpg 200w, '
        'https://cdn.example.com/big.jpg 1200w" alt="x"/>'
        '</body></html>'
    )
    sections = extract_sections(html)
    images = [b for s in sections for b in s.blocks if b.kind == "image"]
    assert images[0].src == "https://cdn.example.com/big.jpg"


def test_falls_back_to_data_src_when_no_srcset():
    html = (
        '<html><body><h2>A</h2>'
        '<img src="https://cdn.example.com/placeholder.gif" '
        'data-src="https://cdn.example.com/real.jpg" alt="x"/>'
        '</body></html>'
    )
    sections = extract_sections(html)
    images = [b for s in sections for b in s.blocks if b.kind == "image"]
    assert images[0].src == "https://cdn.example.com/real.jpg"


def test_single_top_level_element_without_body_wrapper_is_not_dropped():
    # lxml.html.fromstring("<p>...</p>") trả về chính thẻ <p> làm root thay
    # vì bọc trong <body> — nguồn RSS fulltext (Dr. Axe) đưa thẳng HTML dạng
    # này vào extract_sections, không qua trafilatura để được bọc <html><body>.
    html = "<p>Đoạn văn duy nhất, không có thẻ bao ngoài.</p>"
    sections = extract_sections(html)
    assert any(
        b.kind == "p" and "Đoạn văn duy nhất" in (b.text or "")
        for s in sections
        for b in s.blocks
    )
