from datetime import datetime, timedelta, timezone

from medbot.models import Article
from medbot.rank import dedupe, normalize_url, prefilter

NOW = datetime(2026, 9, 14, 8, 30, tzinfo=timezone.utc)


def art(title: str, hours_ago: float, source: str = "S", url: str | None = None) -> Article:
    return Article(
        source=source,
        title=title,
        url=url or f"https://x.test/{title}",
        published=NOW - timedelta(hours=hours_ago),
        summary="tóm tắt",
    )


def test_normalize_url_strips_tracking_and_trailing_slash():
    assert normalize_url("https://X.test/a/?utm_source=rss&id=3") == "https://x.test/a?id=3"


def test_dedupe_keeps_first_occurrence():
    first = art("A", 1, url="https://x.test/a")
    second = art("A bis", 2, url="https://x.test/a/?utm_source=rss")
    assert [a.title for a in dedupe([first, second])] == ["A"]


def test_drops_articles_older_than_max_age():
    kept = prefilter([art("moi", 5), art("cu", 100)], NOW, 10, 48, {})
    assert [a.title for a in kept] == ["moi"]


def test_newer_article_outranks_older_one():
    kept = prefilter([art("cu", 40), art("moi", 2)], NOW, 10, 48, {})
    assert [a.title for a in kept] == ["moi", "cu"]


def test_source_weight_can_flip_near_ties():
    articles = [art("nhe", 10, source="A"), art("nang", 11, source="B")]
    kept = prefilter(articles, NOW, 10, 48, {"B": 2.0})
    assert kept[0].title == "nang"


def test_respects_top_n():
    articles = [art(f"a{i}", i) for i in range(20)]
    assert len(prefilter(articles, NOW, 5, 48, {})) == 5


def test_unknown_source_defaults_to_weight_one():
    kept = prefilter([art("x", 1, source="chua-khai-bao")], NOW, 5, 48, {"S": 3.0})
    assert len(kept) == 1


def test_future_dated_article_is_not_boosted_above_fresh_one():
    # Một số feed ghi sai ngày về tương lai; không được cho nó điểm vô hạn
    articles = [art("tuong-lai", -10), art("vua-dang", 0.5)]
    kept = prefilter(articles, NOW, 5, 48, {})
    assert kept[0].title == "vua-dang"
