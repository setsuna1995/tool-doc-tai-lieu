from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

KEEP_DAYS = 30
LOGGER_NAME = "medbot"


def prune_old_logs(log_dir: Path, today: date, keep_days: int = KEEP_DAYS) -> list[Path]:
    removed: list[Path] = []
    for path in log_dir.glob("*.log"):
        try:
            day = date.fromisoformat(path.stem)
        except ValueError:
            continue  # file không theo quy ước tên ngày thì để yên
        if (today - day).days > keep_days:
            path.unlink()
            removed.append(path)
    return removed


def setup(log_dir: Path, today: date) -> logging.Logger:
    """Một file log mỗi ngày, UTF-8, giữ 30 ngày.

    Bot chạy 8h30 không người trực. Không có log thì hôm nào hỏng cũng
    không có cách nào biết vì sao.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    prune_old_logs(log_dir, today)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()  # gọi setup hai lần không được nhân đôi dòng log

    file_handler = logging.FileHandler(log_dir / f"{today:%Y-%m-%d}.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console)
    return logger
