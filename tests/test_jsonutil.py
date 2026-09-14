from medbot.jsonutil import strip_json_fence


def test_returns_plain_json_unchanged():
    assert strip_json_fence('{"a": 1}') == '{"a": 1}'


def test_strips_markdown_fence_with_language_tag():
    raw = "```json\n{\"a\": 1}\n```"
    assert strip_json_fence(raw) == '{"a": 1}'


def test_strips_markdown_fence_without_language_tag():
    raw = "```\n[1, 2]\n```"
    assert strip_json_fence(raw) == "[1, 2]"


def test_strips_surrounding_whitespace():
    assert strip_json_fence("   \n{\"a\": 1}\n  ") == '{"a": 1}'
