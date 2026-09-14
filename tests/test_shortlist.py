from datetime import date, datetime, timezone

from medbot.models import Article
from medbot.shortlist import render

DAY = date(2026, 9, 14)


def pick(title_vi: str, source: str = "Healthline") -> Article:
    article = Article(
        source=source,
        title="Original English Title",
        url="https://x.test/bai-viet",
        published=datetime(2026, 9, 13, 10, 0, tzinfo=timezone.utc),
        summary="tóm tắt",
    )
    article.title_vi = title_vi
    article.reason_vi = "Nghiên cứu mới, thói quen phổ biến ở Việt Nam."
    article.topic = "dinh dưỡng"
    article.quality = 91
    return article


def test_header_shows_the_date_in_vietnamese_order():
    assert "14/09/2026" in render(DAY, [pick("A")], 40, 4, [])


def test_numbers_items_from_one():
    out = render(DAY, [pick("A"), pick("B")], 40, 4, [])
    assert "## 1. A" in out
    assert "## 2. B" in out


def test_shows_source_date_and_link():
    out = render(DAY, [pick("A")], 40, 4, [])
    assert "Healthline" in out
    assert "13/09" in out
    assert "https://x.test/bai-viet" in out


def test_shows_reason():
    assert "thói quen phổ biến" in render(DAY, [pick("A")], 40, 4, [])


def test_footer_reports_healthy_run():
    assert "Đã quét 4/4 nguồn" in render(DAY, [pick("A")], 40, 4, [])


def test_footer_names_failed_sources():
    out = render(DAY, [pick("A")], 30, 5, [("Mayo Clinic", "HTTP 405")])
    assert "Đã quét 4/5 nguồn" in out
    assert "Mayo Clinic" in out
    assert "405" in out


def test_footer_reminds_how_to_build():
    assert "med 1 4" in render(DAY, [pick("A")], 40, 4, [])


def test_handles_empty_shortlist_without_crashing():
    out = render(DAY, [], 0, 4, [("A", "x"), ("B", "y"), ("C", "z"), ("D", "w")])
    assert "Không tìm được bài nào" in out
