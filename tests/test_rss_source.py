from datetime import timezone
from pathlib import Path

from medbot.sources.rss import RssSource, strip_html

FIXTURES = Path(__file__).parent.parent / "fixtures"


def fixture_fetcher(name: str):
    data = (FIXTURES / name).read_bytes()
    return lambda url: data


def test_strip_html_removes_tags_and_entities():
    assert strip_html("<p>A study of <b>500,000</b> people.</p>") == "A study of 500,000 people."


def test_strip_html_truncates_with_ellipsis():
    assert strip_html("x" * 400, limit=10) == "x" * 10 + "…"


def test_parses_every_item():
    source = RssSource("Healthline", "http://x", fetcher=fixture_fetcher("healthline.xml"))
    assert len(source.fetch_recent()) == 2


def test_fills_article_fields():
    source = RssSource("Healthline", "http://x", fetcher=fixture_fetcher("healthline.xml"))
    first = source.fetch_recent()[0]
    assert first.source == "Healthline"
    assert first.title.startswith("Love Your Coffee")
    assert first.url == "https://www.healthline.com/health-news/hot-coffee-risk"
    assert first.published.tzinfo is not None
    assert first.published.astimezone(timezone.utc).day == 13
    assert "temperature" in first.summary
    assert "<b>" not in first.summary


def test_plain_rss_leaves_fulltext_empty():
    source = RssSource("Healthline", "http://x", fetcher=fixture_fetcher("healthline.xml"))
    assert source.fetch_recent()[0].fulltext is None


def test_fulltext_mode_reads_content_encoded():
    source = RssSource(
        "Dr. Axe", "http://x", fulltext=True, fetcher=fixture_fetcher("draxe_fulltext.xml")
    )
    article = source.fetch_recent()[0]
    assert article.fulltext is not None
    assert "Full body text" in article.fulltext


def test_skips_item_without_link(tmp_path: Path):
    broken = b"""<?xml version="1.0"?><rss version="2.0"><channel>
      <item><title>No link here</title></item>
      <item><title>Has link</title><link>http://a/b</link>
        <pubDate>Sat, 13 Sep 2026 10:00:00 +0000</pubDate></item>
    </channel></rss>"""
    source = RssSource("X", "http://x", fetcher=lambda url: broken)
    articles = source.fetch_recent()
    assert [a.title for a in articles] == ["Has link"]


def test_weight_defaults_to_one():
    assert RssSource("X", "http://x", fetcher=lambda url: b"").weight == 1.0
