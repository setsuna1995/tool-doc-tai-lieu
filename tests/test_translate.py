import json

import pytest

from medbot.extract import Block, Section
from medbot.translate import (
    apply_cached_chunk,
    apply_translation,
    build_translate_prompt,
    chunk_sections,
    estimate_tokens,
    parse_translation,
    section_tokens,
    serialize_chunk,
    translate_article,
    translate_chunk,
)


def sec(heading, text="x" * 40) -> Section:
    return Section(heading=heading, blocks=[Block(kind="p", text=text)])


def test_estimate_tokens_is_roughly_four_chars_per_token():
    assert estimate_tokens("x" * 400) == 100


def test_estimate_tokens_never_returns_zero_for_nonempty_text():
    assert estimate_tokens("x") == 1


def test_section_tokens_counts_all_block_kinds():
    section = Section(heading="H" * 8, blocks=[
        Block(kind="p", text="p" * 40),
        Block(kind="list", items=["a" * 20, "b" * 20]),
        Block(kind="image", alt="c" * 8),
    ])
    assert section_tokens(section) == estimate_tokens("H" * 8) + estimate_tokens("p" * 40) + \
        estimate_tokens("a" * 20) + estimate_tokens("b" * 20) + estimate_tokens("c" * 8)


def test_chunk_sections_groups_small_sections_together():
    sections = [sec(f"H{i}", "x" * 40) for i in range(5)]
    chunks = chunk_sections(sections, max_tokens=1000)
    assert len(chunks) == 1
    assert len(chunks[0]) == 5


def test_chunk_sections_splits_when_threshold_exceeded():
    sections = [sec(f"H{i}", "x" * 4000) for i in range(3)]  # ~1000 token moi section
    chunks = chunk_sections(sections, max_tokens=1500)
    assert len(chunks) == 3  # moi section da gan sat nguong, khong ghep duoc voi nhau


def test_chunk_sections_never_drops_an_oversized_lone_section():
    huge = sec("H", "x" * 100000)
    chunks = chunk_sections([huge], max_tokens=100)
    assert len(chunks) == 1
    assert chunks[0] == [huge]


def test_chunk_sections_handles_empty_list():
    assert chunk_sections([], max_tokens=1000) == []


def test_prompt_includes_glossary_when_present():
    prompt = build_translate_prompt([sec("H")], {"cancer": "ung thư"}, "Some Title")
    assert "ung thư" in prompt and "cancer" in prompt


def test_prompt_omits_glossary_section_when_empty():
    prompt = build_translate_prompt([sec("H")], {}, "Some Title")
    assert "Sổ thuật ngữ" not in prompt


def _good_response(chunk):
    return json.dumps({
        "glossary": [{"en": "cancer", "vi": "ung thư"}],
        "sections": [
            {"heading": (f"VI:{s.heading}" if s.heading else None),
             "blocks": [_translate_block_stub(b) for b in s.blocks]}
            for s in chunk
        ],
    }, ensure_ascii=False)


def _translate_block_stub(block):
    if block.kind == "p":
        return {"type": "p", "text": f"VI:{block.text}"}
    if block.kind == "list":
        return {"type": "list", "items": [f"VI:{i}" for i in block.items]}
    return {"type": "image", "alt": f"VI:{block.alt or ''}"}


def test_parse_translation_accepts_matching_shape():
    chunk = [sec("H")]
    parsed = parse_translation(_good_response(chunk), chunk)
    assert parsed["sections"][0]["heading"] == "VI:H"


def test_parse_translation_rejects_wrong_section_count():
    chunk = [sec("A"), sec("B")]
    raw = _good_response([sec("A")])  # thiếu 1 section
    with pytest.raises(ValueError, match="section"):
        parse_translation(raw, chunk)


def test_parse_translation_rejects_wrong_block_count():
    chunk = [Section(heading="H", blocks=[Block(kind="p", text="a"), Block(kind="p", text="b")])]
    bad = json.dumps({"glossary": [], "sections": [{"heading": "H", "blocks": [{"type": "p", "text": "chỉ 1"}]}]})
    with pytest.raises(ValueError, match="block"):
        parse_translation(bad, chunk)


def test_parse_translation_rejects_mismatched_block_type():
    chunk = [Section(heading="H", blocks=[Block(kind="list", items=["a"])])]
    bad = json.dumps({"glossary": [], "sections": [{"heading": "H", "blocks": [{"type": "p", "text": "sai loai"}]}]})
    with pytest.raises(ValueError, match="type"):
        parse_translation(bad, chunk)


def test_apply_translation_fills_vi_fields_in_place():
    chunk = [Section(heading="H", blocks=[Block(kind="p", text="hello")])]
    parsed = parse_translation(_good_response(chunk), chunk)
    glossary = apply_translation(chunk, parsed)
    assert chunk[0].heading_vi == "VI:H"
    assert chunk[0].blocks[0].text_vi == "VI:hello"
    assert glossary == {"cancer": "ung thư"}


def test_apply_translation_handles_null_heading_for_lead_section():
    chunk = [Section(heading=None, blocks=[Block(kind="p", text="mở đầu")])]
    parsed = parse_translation(_good_response(chunk), chunk)
    apply_translation(chunk, parsed)
    assert chunk[0].heading_vi is None


class FakeClient:
    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return self.answers.pop(0)


def test_translate_chunk_returns_updated_glossary():
    chunk = [sec("H")]
    client = FakeClient([_good_response(chunk)])
    glossary = translate_chunk(chunk, client, {}, "Title")
    assert glossary == {"cancer": "ung thư"}
    assert chunk[0].heading_vi == "VI:H"


def test_translate_chunk_retries_once_on_malformed_json():
    chunk = [sec("H")]
    client = FakeClient(["không phải json", _good_response(chunk)])
    translate_chunk(chunk, client, {}, "Title")
    assert len(client.prompts) == 2


def test_translate_chunk_gives_up_after_second_failure():
    chunk = [sec("H")]
    client = FakeClient(["hỏng", "vẫn hỏng"])
    with pytest.raises(ValueError):
        translate_chunk(chunk, client, {}, "Title")


def test_serialize_and_restore_chunk_roundtrip():
    chunk = [sec("H")]
    client = FakeClient([_good_response(chunk)])
    translate_chunk(chunk, client, {}, "Title")
    dumped = serialize_chunk(chunk)

    fresh = [sec("H")]  # section moi, chua dich
    apply_cached_chunk(fresh, dumped)
    assert fresh[0].heading_vi == chunk[0].heading_vi
    assert fresh[0].blocks[0].text_vi == chunk[0].blocks[0].text_vi


def test_translate_article_skips_chunks_already_in_cache():
    sections = [sec("H1"), sec("H2")]
    calls = []

    class CountingClient:
        def generate(self, prompt):
            calls.append(prompt)
            # Chỉ còn H2 trong prompt vì H1 đã có sẵn trong cache
            return _good_response([sections[1]])

    # Cache tay một mục ĐÃ DỊCH THẬT — không dùng serialize_chunk() trên
    # section chưa dịch, vì nó sẽ chỉ tạo ra toàn giá trị None, khiến test
    # không phân biệt được "phục hồi từ cache" với "chưa dịch bao giờ".
    cache = {
        "chunk_0": [{
            "heading_vi": "VI:H1",
            "blocks": [{"text_vi": "VI:đã dịch từ trước", "items_vi": None, "alt_vi": None}],
        }]
    }
    saved = []
    translate_article(
        sections, CountingClient(), cache, saved.append, "Title", max_tokens_per_chunk=1
    )
    assert sections[0].heading_vi == "VI:H1"   # phục hồi từ cache, không gọi model
    assert sections[1].heading_vi is not None  # gọi model thật cho phần còn thiếu
    assert len(calls) == 1                     # chỉ 1 request cho chunk còn lại
