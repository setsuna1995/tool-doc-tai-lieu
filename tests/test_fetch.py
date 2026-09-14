import pytest

from medbot.fetch import get_article_html

FULL_PAGE = """<!DOCTYPE html>
<html><head><title>Test</title></head>
<body>
<nav><a href="/">Home</a><a href="/sub">Subscribe now for $9.99/month!</a></nav>
<header><div class="ad">Buy our supplements today!</div></header>
<article>
<h1>Coffee Too Hot May Raise Esophageal Cancer Risk</h1>
<p class="byline">By Jane Doe, updated Sept 13</p>
<img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ycAAAAAAQABAAACAUwAOw==" data-src="https://cdn.example.com/coffee-full.jpg" srcset="https://cdn.example.com/coffee-200.jpg 200w, https://cdn.example.com/coffee-full.jpg 1200w" alt="Steaming cup of coffee">
<p>A large new study of over <b>500,000</b> people found that drinking very hot beverages regularly is linked to a higher risk of esophageal cancer.</p>
<h2>The heat is the culprit</h2>
<p>Researchers at a major university tracked participants for 12 years and found that temperature, not the beverage itself, was the key risk factor.</p>
</article>
<footer><a href="/privacy">Privacy</a> Copyright 2026</footer>
<div class="comments"><p>Great article!</p></div>
</body></html>"""


def test_returns_fulltext_directly_when_present():
    result = get_article_html("<h2>Đã có sẵn</h2><p>Không cần tải trang</p>", "https://x.test/a")
    assert "Đã có sẵn" in result


def test_does_not_call_fetcher_when_fulltext_present():
    def boom(url):
        raise AssertionError("Không được gọi fetcher khi đã có fulltext")
    get_article_html("<p>có sẵn</p>", "https://x.test/a", fetcher=boom)


def test_fetches_and_cleans_page_when_no_fulltext():
    result = get_article_html(None, "https://x.test/a", fetcher=lambda url: FULL_PAGE)
    assert "500,000" in result
    assert "Subscribe now" not in result
    assert "Great article" not in result


def test_raises_when_page_has_no_extractable_content():
    with pytest.raises(ValueError, match="Không bóc được nội dung"):
        get_article_html(None, "https://x.test/a", fetcher=lambda url: "<html><body></body></html>")
