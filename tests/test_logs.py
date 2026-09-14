from datetime import date
from pathlib import Path

from medbot.logs import prune_old_logs, setup

TODAY = date(2026, 9, 14)


def test_prune_removes_logs_older_than_keep_days(tmp_path: Path):
    (tmp_path / "2026-07-01.log").write_text("cũ", encoding="utf-8")
    (tmp_path / "2026-09-13.log").write_text("mới", encoding="utf-8")
    prune_old_logs(tmp_path, TODAY, keep_days=30)
    assert [p.name for p in sorted(tmp_path.iterdir())] == ["2026-09-13.log"]


def test_prune_ignores_files_that_are_not_dates(tmp_path: Path):
    (tmp_path / "ghi-chu.log").write_text("x", encoding="utf-8")
    prune_old_logs(tmp_path, TODAY, keep_days=1)
    assert (tmp_path / "ghi-chu.log").exists()


def test_setup_writes_vietnamese_to_a_dated_file(tmp_path: Path):
    logger = setup(tmp_path, TODAY)
    logger.info("Đã quét 4/5 nguồn")
    for handler in logger.handlers:
        handler.flush()
    content = (tmp_path / "2026-09-14.log").read_text(encoding="utf-8")
    assert "Đã quét 4/5 nguồn" in content


def test_setup_twice_does_not_duplicate_handlers(tmp_path: Path):
    setup(tmp_path, TODAY)
    logger = setup(tmp_path, TODAY)
    assert len(logger.handlers) == 2
