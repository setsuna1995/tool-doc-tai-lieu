from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from medbot import logs, scheduling
from medbot.build import parse_build_args
from medbot.build import run as run_build
from medbot.collect import run as run_collect
from medbot.config import load_api_key, load_config
from medbot.gemini import GeminiClient, QuotaExceeded, make_caller
from medbot.probe import probe, render_source_block, status_fetch
from medbot.sources.registry import build_sources

SUBCOMMANDS = {"collect", "build", "probe", "models", "quota", "schedule"}
ROOT = Path(__file__).resolve().parent.parent


def parse_command(argv: list[str]) -> tuple[str, list[str]]:
    """Phân lệnh theo hình dạng tham số, để gõ `med 1 4` là đủ."""
    if not argv:
        return "collect", []
    if argv[0].isdigit():
        return "build", argv
    if argv[0] in SUBCOMMANDS:
        return argv[0], argv[1:]
    raise ValueError(f"Lệnh không hợp lệ: {argv[0]!r}. Xem README.md.")


def _client(cfg: dict, models_key: str) -> GeminiClient:
    return GeminiClient(
        models=cfg["gemini"][models_key],
        limits=cfg["gemini"]["limits"],
        quota_path=ROOT / "state" / "quota.json",
        caller=make_caller(load_api_key(ROOT)),
    )


def _cmd_collect(cfg: dict) -> int:
    sources = build_sources(ROOT / "sources.toml")
    result = run_collect(
        cfg, sources, _client(cfg, "rank_models"), ROOT, datetime.now(timezone.utc)
    )
    print(f"Đã ghi {result.shortlist_path}")
    print(f"{len(result.picks)} bài được chọn từ {result.scanned} bài mới.")
    for name, reason in result.failed:
        print(f"  Nguồn lỗi: {name} — {reason}")
    return 0


def _cmd_probe(args: list[str]) -> int:
    if not args:
        print("Cách dùng: med probe <url>")
        return 2
    result = probe(args[0], status_fetch)
    name = args[1] if len(args) > 1 else args[0]
    try:
        print(render_source_block(result, name))
    except ValueError as exc:
        print(exc)
        return 1
    return 0


def _cmd_models(cfg: dict) -> int:
    from google import genai

    client = genai.Client(api_key=load_api_key(ROOT))
    for model in client.models.list():
        print(model.name)
    print("\nChép ID cần dùng vào rank_models / translate_models trong config.toml.")
    return 0


def _cmd_quota(cfg: dict) -> int:
    usage = _client(cfg, "rank_models").usage()
    if not usage:
        print("Hôm nay chưa gọi request nào.")
        return 0
    for model, count in sorted(usage.items()):
        print(f"{model}: {count}")
    return 0


def _cmd_build(cfg: dict, args: list[str]) -> int:
    try:
        indices, target_date = parse_build_args(args)
    except ValueError as exc:
        print(exc)
        return 2
    try:
        paths = run_build(cfg, _client(cfg, "translate_models"), ROOT, indices, target_date)
    except (FileNotFoundError, ValueError) as exc:
        # ValueError ở đây là lỗi gõ nhầm số thứ tự (resolve_picks) — lỗi
        # dùng sai của người dùng, không phải sự cố hệ thống. Bắt riêng để
        # in gọn, không rơi xuống nhánh log ERROR chung ở main().
        print(exc)
        return 1
    for path in paths:
        print(f"Đã ghi {path}")
    return 0


def _cmd_schedule(cfg: dict, args: list[str]) -> int:
    if args and args[0] == "off":
        script = scheduling.build_unregister_script()
    else:
        script = scheduling.build_register_script(ROOT / "med.ps1", cfg["schedule"]["time"])
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True, text=True,
    )
    print(result.stdout.strip())
    if result.returncode != 0:
        print(result.stderr.strip())
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        command, args = parse_command(argv)
    except ValueError as exc:
        print(exc)
        return 2

    logger = logs.setup(ROOT / "logs", datetime.now().date())
    cfg = load_config(ROOT)

    handlers = {
        "collect": lambda: _cmd_collect(cfg),
        "build": lambda: _cmd_build(cfg, args),
        "probe": lambda: _cmd_probe(args),
        "models": lambda: _cmd_models(cfg),
        "quota": lambda: _cmd_quota(cfg),
        "schedule": lambda: _cmd_schedule(cfg, args),
    }
    if command not in handlers:
        logger.error("Lệnh `%s` thuộc kế hoạch 2 hoặc 3, chưa triển khai.", command)
        return 2

    try:
        return handlers[command]()
    except QuotaExceeded as exc:
        # QuotaExceeded nghĩa là "đã thử hết mọi model" — có thể do hết quota,
        # cũng có thể do cả chuỗi model đang quá tải tạm thời (503). Không
        # quy hết về "hết hạn mức" kẻo chẩn đoán sai khi log không ai đọc kịp.
        logger.error("Không gọi được Gemini sau khi thử hết các model: %s", exc)
        return 1
    except Exception as exc:
        # Bot chạy 8h30 không người trực. Traceback trần trên một console đã
        # đóng thì vô dụng: ghi đầy đủ vào log, in ra một dòng người đọc hiểu.
        logger.error("Chạy `%s` thất bại: %s", command, exc)
        logger.debug("Chi tiết:", exc_info=True)
        return 1
