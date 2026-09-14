import json
from datetime import datetime, timezone

import pytest

from medbot.models import Article
from medbot.rank import apply_scores, build_ranking_prompt, parse_ranking, rank

NOW = datetime(2026, 9, 14, 8, 30, tzinfo=timezone.utc)


def art(title: str) -> Article:
    return Article("S", title, f"https://x.test/{title}", NOW, "tóm tắt")


class FakeClient:
    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.answers.pop(0)


def payload(items):
    return json.dumps(items, ensure_ascii=False)


def test_prompt_numbers_every_article():
    prompt = build_ranking_prompt([art("A"), art("B")])
    assert "[0]" in prompt and "[1]" in prompt


def test_prompt_asks_for_all_five_fields():
    prompt = build_ranking_prompt([art("A")])
    for field in ("index", "quality", "topic", "title_vi", "reason_vi"):
        assert field in prompt


def test_parse_accepts_plain_json_array():
    raw = payload([{"index": 0, "quality": 90, "topic": "t", "title_vi": "v", "reason_vi": "r"}])
    assert parse_ranking(raw, 1)[0]["quality"] == 90


def test_parse_strips_markdown_code_fence():
    raw = "```json\n" + payload(
        [{"index": 0, "quality": 90, "topic": "t", "title_vi": "v", "reason_vi": "r"}]
    ) + "\n```"
    assert len(parse_ranking(raw, 1)) == 1


def test_parse_rejects_out_of_range_index():
    raw = payload([{"index": 7, "quality": 90, "topic": "t", "title_vi": "v", "reason_vi": "r"}])
    with pytest.raises(ValueError, match="index"):
        parse_ranking(raw, 1)


def test_parse_rejects_quality_outside_zero_to_hundred():
    raw = payload([{"index": 0, "quality": 150, "topic": "t", "title_vi": "v", "reason_vi": "r"}])
    with pytest.raises(ValueError, match="quality"):
        parse_ranking(raw, 1)


def test_parse_rejects_non_json():
    with pytest.raises(ValueError):
        parse_ranking("xin chào, tôi không phải JSON", 1)


def test_apply_scores_fills_article_fields():
    articles = [art("A")]
    apply_scores(articles, [{"index": 0, "quality": 88, "topic": "giấc ngủ",
                             "title_vi": "Ngủ đủ", "reason_vi": "vì thế"}])
    assert articles[0].quality == 88
    assert articles[0].title_vi == "Ngủ đủ"
    assert articles[0].topic == "giấc ngủ"


def test_rank_returns_highest_quality_first():
    articles = [art("A"), art("B")]
    client = FakeClient([payload([
        {"index": 0, "quality": 40, "topic": "t", "title_vi": "a", "reason_vi": "r"},
        {"index": 1, "quality": 95, "topic": "t", "title_vi": "b", "reason_vi": "r"},
    ])])
    assert [a.title for a in rank(articles, client, 2)] == ["B", "A"]


def test_rank_truncates_to_shortlist_size():
    articles = [art("A"), art("B"), art("C")]
    client = FakeClient([payload([
        {"index": i, "quality": 90 - i, "topic": "t", "title_vi": "x", "reason_vi": "r"}
        for i in range(3)
    ])])
    assert len(rank(articles, client, 2)) == 2


def test_rank_retries_once_on_malformed_json():
    articles = [art("A")]
    good = payload([{"index": 0, "quality": 80, "topic": "t", "title_vi": "x", "reason_vi": "r"}])
    client = FakeClient(["không phải json", good])
    assert len(rank(articles, client, 1)) == 1
    assert len(client.prompts) == 2


def test_rank_gives_up_after_second_failure():
    client = FakeClient(["hỏng", "vẫn hỏng"])
    with pytest.raises(ValueError):
        rank([art("A")], client, 1)


def test_rank_ignores_articles_the_model_skipped():
    articles = [art("A"), art("B")]
    client = FakeClient([payload([
        {"index": 1, "quality": 70, "topic": "t", "title_vi": "b", "reason_vi": "r"}
    ])])
    assert [a.title for a in rank(articles, client, 5)] == ["B"]
