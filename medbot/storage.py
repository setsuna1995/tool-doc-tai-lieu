from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_text(path: Path, text: str) -> None:
    """Ghi ra file tạm cùng thư mục rồi đổi tên.

    Thư mục đích thường nằm trong OneDrive. Ghi thẳng dễ bị OneDrive
    khoá file giữa chừng khi nó bắt đầu đồng bộ; os.replace là thao tác
    nguyên tử nên người đọc không bao giờ thấy file ghi dở.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def atomic_write_json(path: Path, data: Any) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def read_json(path: Path, default: Any) -> Any:
    """Trả về default khi file thiếu hoặc hỏng.

    State hỏng không được làm sập bot: mất lịch sử còn hơn mất buổi sáng.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default
