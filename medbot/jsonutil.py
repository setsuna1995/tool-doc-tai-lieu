from __future__ import annotations

import re

_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$", re.M)


def strip_json_fence(raw: str) -> str:
    """Gemini đôi khi bọc JSON trong ```json ... ``` dù prompt đã dặn không làm vậy.

    Dùng chung cho cả rank.py (chấm điểm) và translate.py (dịch) để không
    lặp lại cùng một biểu thức chính quy ở hai nơi.
    """
    return _FENCE.sub("", raw.strip()).strip()
