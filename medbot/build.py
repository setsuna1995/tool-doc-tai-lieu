from __future__ import annotations

import hashlib
import unicodedata
from datetime import date
from pathlib import Path

from medbot.storage import atomic_write_json, read_json

FORBIDDEN_FILENAME_CHARS = '\\/:*?"<>|'


def slugify_vi(text: str, limit: int = 80) -> str:
    """Bỏ dấu tiếng Việt để dùng làm tên file trên Windows.

    'Đ'/'đ' không tách được bằng NFKD (đã kiểm chứng thật: unicodedata coi
    đây là chữ cái gốc có nét gạch, không phải chữ cái + dấu phụ) — phải
    thay bằng tay trước khi chuẩn hoá, nếu không toàn bộ ký tự này biến mất
    thay vì chuyển thành "D".
    """
    text = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    ascii_only = stripped.encode("ascii", "ignore").decode("ascii")
    for ch in FORBIDDEN_FILENAME_CHARS:
        ascii_only = ascii_only.replace(ch, "")
    ascii_only = " ".join(ascii_only.split())
    return ascii_only[:limit].strip()


def resolve_picks(state: dict, indices: list[int]) -> list[dict]:
    picks = state.get("picks", [])
    resolved = []
    for index in indices:
        if not 1 <= index <= len(picks):
            raise ValueError(
                f"Không có bài số {index}. Shortlist hôm nay chỉ có {len(picks)} bài."
            )
        resolved.append(picks[index - 1])
    return resolved


def parse_build_args(args: list[str]) -> tuple[list[int], str | None]:
    target_date = None
    if "--date" in args:
        pos = args.index("--date")
        target_date = args[pos + 1]
        args = args[:pos] + args[pos + 2 :]
    numbers = [int(a) for a in args if a.isdigit()]
    if not numbers:
        raise ValueError("Cần ít nhất một số thứ tự bài, ví dụ: med 1 4")
    return numbers, target_date


def output_path(cfg: dict, day: date, title_vi: str) -> Path:
    subfolder = cfg["output"]["subfolder"].format(year=f"{day:%Y}", month=f"{day:%m}")
    filename = f"{day:%Y-%m-%d} - {slugify_vi(title_vi)}.docx"
    return Path(cfg["output"]["dir"]) / subfolder / filename


def mark_built(state_path: Path, url: str) -> None:
    state = read_json(state_path, {"picks": []})
    for pick in state.get("picks", []):
        if pick["url"] == url:
            pick["built"] = True
    atomic_write_json(state_path, state)


def _cache_path(root: Path, url: str) -> Path:
    url_hash = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return root / "state" / "cache" / f"{url_hash}.json"


from medbot.extract import extract_sections
from medbot.fetch import get_article_html
from medbot.images import download_all_images
from medbot.translate import translate_article
from medbot.docx_writer import write_docx


def build_one(pick: dict, day: date, cfg: dict, client, root: Path) -> Path:
    html = get_article_html(pick.get("fulltext"), pick["url"])
    sections = extract_sections(html)

    cache_path = _cache_path(root, pick["url"])
    cache = read_json(cache_path, {})

    def save_cache(updated_cache: dict) -> None:
        atomic_write_json(cache_path, updated_cache)

    translate_article(sections, client, cache, save_cache, pick.get("title") or pick["title_vi"])

    if cfg["output"].get("include_images", True):
        download_all_images(sections)

    path = output_path(cfg, day, pick.get("title_vi") or pick["title"])
    write_docx(path, pick, sections, cfg)

    # day đã được run() truyền vào đúng ngày state chứa pick này (kể cả khi
    # dùng --date cho một ngày cũ) — dùng thẳng, không cần dò lại từ đầu.
    state_path = root / "state" / f"{day:%Y-%m-%d}.json"
    mark_built(state_path, pick["url"])

    return path


def run(cfg: dict, client, root: Path, indices: list[int], target_date: str | None) -> list[Path]:
    day = date.fromisoformat(target_date) if target_date else date.today()
    state_path = root / "state" / f"{day:%Y-%m-%d}.json"
    state = read_json(state_path, None)
    if state is None:
        raise FileNotFoundError(
            f"Chưa có shortlist cho ngày {day:%Y-%m-%d}. Chạy `med` (collect) trước, "
            f"hoặc dùng --date đúng ngày đã chạy."
        )
    picks = resolve_picks(state, indices)
    return [build_one(pick, day, cfg, client, root) for pick in picks]
