from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from medbot import shortlist
from medbot.models import Article
from medbot.rank import prefilter, rank
from medbot.storage import atomic_write_json, atomic_write_text, read_json

MAX_WORKERS = 8


@dataclass
class CollectResult:
    picks: list[Article]
    scanned: int
    failed: list[tuple[str, str]]
    shortlist_path: Path
    state_path: Path


def gather(sources, timeout: float = 25.0) -> tuple[list[Article], list[tuple[str, str]]]:
    """Mỗi nguồn có rào chắn riêng: một nguồn chết không kéo sập cả buổi sáng.

    Với 20 nguồn thì vài nguồn hỏng mỗi ngày là chuyện thường, không phải sự cố.
    """
    articles: list[Article] = []
    failed: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(source.fetch_recent): source for source in sources}
        for future, source in futures.items():
            try:
                articles.extend(future.result(timeout=timeout))
            except Exception as exc:
                failed.append((source.name, str(exc) or type(exc).__name__))
    return articles, failed


def filter_seen(articles: list[Article], seen: dict[str, str]) -> list[Article]:
    return [a for a in articles if a.url not in seen]


def prune_seen(seen: dict[str, str], today: date, keep_days: int = 30) -> dict[str, str]:
    cutoff = today - timedelta(days=keep_days)
    return {
        url: day
        for url, day in seen.items()
        if date.fromisoformat(day) >= cutoff
    }


def _state_payload(day: date, picks: list[Article], scored: list[Article]) -> dict:
    def row(article: Article) -> dict:
        return {
            "source": article.source,
            "title": article.title,
            "title_vi": article.title_vi,
            "url": article.url,
            "published": article.published.isoformat(),
            "summary": article.summary,
            "topic": article.topic,
            "quality": article.quality,
            "reason_vi": article.reason_vi,
            "built": False,
        }

    return {
        "date": day.isoformat(),
        "picks": [row(a) for a in picks],
        "candidates": [row(a) for a in scored if a.quality is not None],
    }


def run(cfg: dict, sources, client, root: Path, now: datetime) -> CollectResult:
    day = now.date()
    articles, failed = gather(sources)

    seen_path = root / "state" / "seen.json"
    seen: dict[str, str] = read_json(seen_path, {})
    fresh = filter_seen(articles, seen)

    weights = {source.name: source.weight for source in sources}
    shortlisted = prefilter(
        fresh,
        now,
        cfg["ranking"]["prefilter_top"],
        cfg["ranking"]["max_age_hours"],
        weights,
    )

    picks: list[Article] = []
    if shortlisted:
        picks = rank(shortlisted, client, cfg["ranking"]["shortlist_size"])

    out_dir = Path(cfg["output"]["dir"])
    shortlist_path = out_dir / f"{day:%Y-%m-%d}-shortlist.md"
    atomic_write_text(
        shortlist_path,
        shortlist.render(day, picks, len(shortlisted), len(sources), failed),
    )

    state_path = root / "state" / f"{day:%Y-%m-%d}.json"
    atomic_write_json(state_path, _state_payload(day, picks, shortlisted))

    for article in articles:
        seen.setdefault(article.url, day.isoformat())
    atomic_write_json(seen_path, prune_seen(seen, day))

    return CollectResult(picks, len(shortlisted), failed, shortlist_path, state_path)
