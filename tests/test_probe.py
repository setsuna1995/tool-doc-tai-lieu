import pytest

from medbot.probe import ProbeResult, find_embedded_feeds, probe, render_source_block

HTML = b"""<html><head>
<link rel="alternate" type="application/rss+xml" href="/nutrition/feed/">
<link rel="alternate" type="application/rss+xml" href="https://x.test/comments/feed/">
</head><body>xin chao</body></html>"""

FEED = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>A</title><link>https://x.test/a</link></item>
<item><title>B</title><link>https://x.test/b</link></item>
</channel></rss>"""

FEED_FULLTEXT = b"""<?xml version="1.0"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel>
<item><title>A</title><link>https://x.test/a</link>
<content:encoded>day la toan van</content:encoded></item>
</channel></rss>"""


def make_fetcher(pages: dict[str, tuple[int, bytes]]):
    def fetch(url: str) -> tuple[int, bytes]:
        return pages.get(url, (404, b""))
    return fetch


def test_find_embedded_feeds_resolves_relative_urls():
    feeds = find_embedded_feeds(HTML, "https://x.test/nutrition/")
    assert "https://x.test/nutrition/feed/" in feeds


def test_find_embedded_feeds_keeps_absolute_urls():
    assert "https://x.test/comments/feed/" in find_embedded_feeds(HTML, "https://x.test/")


def test_probe_prefers_feed_with_most_items():
    fetcher = make_fetcher({
        "https://x.test/": (200, HTML),
        "https://x.test/nutrition/feed/": (200, FEED),
        "https://x.test/comments/feed/": (200, b"<rss><channel></channel></rss>"),
        "https://x.test/a": (200, b"noi dung bai"),
    })
    result = probe("https://x.test/", fetcher)
    assert result.feed_url == "https://x.test/nutrition/feed/"
    assert result.item_count == 2


def test_probe_detects_fulltext_feed():
    fetcher = make_fetcher({
        "https://x.test/": (200, b"<html></html>"),
        "https://x.test/feed/": (200, FEED_FULLTEXT),
        "https://x.test/a": (200, b"noi dung"),
    })
    assert probe("https://x.test/", fetcher).has_fulltext is True


def test_probe_reports_blocked_article_page():
    fetcher = make_fetcher({
        "https://x.test/": (200, b"<html></html>"),
        "https://x.test/feed/": (200, FEED),
        "https://x.test/a": (451, b""),
    })
    result = probe("https://x.test/", fetcher)
    assert result.article_status == 451


def test_probe_returns_empty_result_when_no_feed_found():
    fetcher = make_fetcher({"https://x.test/": (200, b"<html></html>")})
    result = probe("https://x.test/", fetcher)
    assert result.feed_url is None
    assert result.item_count == 0


def test_render_source_block_marks_fulltext_kind():
    result = ProbeResult("https://x.test/", "https://x.test/feed/", 30, True, None, 200)
    block = render_source_block(result, "Dr. Axe")
    assert 'kind   = "rss_fulltext"' in block
    assert 'feed   = "https://x.test/feed/"' in block


def test_render_source_block_warns_when_article_blocked():
    result = ProbeResult("https://x.test/", "https://x.test/feed/", 30, False, None, 451)
    assert "451" in render_source_block(result, "X")


def test_render_source_block_refuses_when_no_feed():
    result = ProbeResult("https://x.test/", None, 0, False, None, None)
    with pytest.raises(ValueError, match="Không tìm được feed"):
        render_source_block(result, "X")
