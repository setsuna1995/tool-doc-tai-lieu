import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from medbot.collect import filter_seen, gather, prune_seen, run
from medbot.models import Article

NOW = datetime(2026, 9, 14, 8, 30, tzinfo=timezone.utc)


def art(title: str, source: str = "S", hours_ago: float = 2.0) -> Article:
    return Article(source, title, f"https://x.test/{title}", NOW - timedelta(hours=hours_ago), "s")


class FakeSource:
    def __init__(self, name, articles=None, error=None, weight=1.0):
        self.name = name
        self.weight = weight
        self._articles = articles or []
        self._error = error

    def fetch_recent(self):
        if self._error:
            raise self._error
        return self._articles


class FakeClient:
    def __init__(self, quality_by_title):
        self.quality = quality_by_title

    def generate(self, prompt: str) -> str:
        items = []
        for line in prompt.splitlines():
            if line.startswith("["):
                index = int(line[1 : line.index("]")])
                title = line.split(") ", 1)[1]
                items.append({
                    "index": index,
                    "quality": self.quality.get(title, 50),
                    "topic": "chủ đề",
                    "title_vi": f"VI:{title}",
                    "reason_vi": "lý do",
                })
        return json.dumps(items, ensure_ascii=False)


def base_cfg(tmp_path: Path) -> dict:
    return {
        "output": {"dir": str(tmp_path / "onedrive")},
        "ranking": {"shortlist_size": 2, "max_age_hours": 48, "prefilter_top": 60},
    }


def test_gather_collects_from_every_healthy_source():
    sources = [FakeSource("A", [art("a1")]), FakeSource("B", [art("b1")])]
    articles, failed = gather(sources)
    assert {a.title for a in articles} == {"a1", "b1"}
    assert failed == []


def test_gather_survives_a_failing_source():
    sources = [
        FakeSource("A", [art("a1")]),
        FakeSource("Mayo Clinic", error=RuntimeError("HTTP 405")),
    ]
    articles, failed = gather(sources)
    assert [a.title for a in articles] == ["a1"]
    assert failed[0][0] == "Mayo Clinic"
    assert "405" in failed[0][1]


def test_filter_seen_drops_known_urls():
    known = {"https://x.test/a1": "2026-09-13"}
    assert [a.title for a in filter_seen([art("a1"), art("a2")], known)] == ["a2"]


def test_prune_seen_drops_entries_older_than_keep_days():
    seen = {"u1": "2026-08-01", "u2": "2026-09-13"}
    assert prune_seen(seen, date(2026, 9, 14), keep_days=30) == {"u2": "2026-09-13"}


def test_run_writes_shortlist_and_state(tmp_path: Path):
    sources = [FakeSource("A", [art("a1"), art("a2")])]
    client = FakeClient({"a1": 95, "a2": 60})
    result = run(base_cfg(tmp_path), sources, client, tmp_path, NOW)

    assert result.shortlist_path.exists()
    assert "VI:a1" in result.shortlist_path.read_text(encoding="utf-8")
    state = json.loads(result.state_path.read_text(encoding="utf-8"))
    assert state["picks"][0]["title_vi"] == "VI:a1"
    assert state["date"] == "2026-09-14"


def test_run_records_failures_in_shortlist(tmp_path: Path):
    sources = [
        FakeSource("A", [art("a1")]),
        FakeSource("Mayo Clinic", error=RuntimeError("HTTP 405")),
    ]
    result = run(base_cfg(tmp_path), sources, FakeClient({}), tmp_path, NOW)
    assert "Mayo Clinic" in result.shortlist_path.read_text(encoding="utf-8")
    assert result.failed[0][0] == "Mayo Clinic"


def test_run_updates_seen_so_next_day_skips_them(tmp_path: Path):
    sources = [FakeSource("A", [art("a1")])]
    run(base_cfg(tmp_path), sources, FakeClient({}), tmp_path, NOW)
    seen = json.loads((tmp_path / "state" / "seen.json").read_text(encoding="utf-8"))
    assert "https://x.test/a1" in seen


def test_run_skips_articles_seen_yesterday(tmp_path: Path):
    (tmp_path / "state").mkdir(parents=True)
    (tmp_path / "state" / "seen.json").write_text(
        json.dumps({"https://x.test/a1": "2026-09-13"}), encoding="utf-8"
    )
    sources = [FakeSource("A", [art("a1"), art("a2")])]
    result = run(base_cfg(tmp_path), sources, FakeClient({}), tmp_path, NOW)
    assert [a.title for a in result.picks] == ["a2"]


def test_run_handles_all_sources_failing(tmp_path: Path):
    sources = [FakeSource("A", error=RuntimeError("boom"))]
    result = run(base_cfg(tmp_path), sources, FakeClient({}), tmp_path, NOW)
    assert result.picks == []
    assert "Không tìm được bài nào" in result.shortlist_path.read_text(encoding="utf-8")
