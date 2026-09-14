from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from medbot.storage import atomic_write_json, read_json

PACIFIC = ZoneInfo("America/Los_Angeles")
ATTEMPTS = 3
BACKOFF = (2.0, 4.0)  # chờ giữa các lần thử; độ dài = ATTEMPTS - 1


class RateLimited(Exception):
    """Lỗi tạm thời phía nhà cung cấp — đáng thử lại hoặc đổi model.

    Không chỉ 429 (hết hạn mức): 503 UNAVAILABLE ("quá tải tạm thời") và
    500 INTERNAL cũng thuộc nhóm này theo khuyến nghị chính thức của Google
    về retry. Tên lớp giữ RateLimited vì đây là điều kiện thường gặp nhất
    và code gọi nó đã ổn định qua test — chỉ mở rộng ĐIỀU KIỆN NHẬN DIỆN.
    """


class QuotaExceeded(Exception):
    """Đã thử hết mọi model trong chuỗi mà không model nào còn quota hoặc còn khả dụng."""


_RETRYABLE_MARKERS = ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "500", "INTERNAL")


def is_retryable_error(exc: Exception) -> bool:
    """True nếu lỗi là loại tạm thời, đáng thử lại thay vì báo chết ngay.

    Phát hiện thật ngày 2026-09-14: gọi API thật gặp 503 UNAVAILABLE
    (Gemini quá tải tạm thời), nhưng bản đầu chỉ nhận diện 429 nên lỗi này
    đi thẳng ra ngoài như lỗi chết, bỏ qua toàn bộ retry/xoay-model — dù
    cơ chế đó đã tồn tại và được test kỹ, chỉ vì điều kiện kích hoạt quá hẹp.
    """
    text = str(exc)
    return any(marker in text for marker in _RETRYABLE_MARKERS)


def pacific_date(now: datetime) -> str:
    """Google đặt lại RPD lúc nửa đêm giờ Thái Bình Dương, không phải giờ máy."""
    return now.astimezone(PACIFIC).strftime("%Y-%m-%d")


def tier_of(model: str) -> str:
    return "flash_lite" if "flash-lite" in model else "flash"


class GeminiClient:
    def __init__(
        self,
        models: list[str],
        limits: dict[str, dict[str, int]],
        quota_path: Path,
        caller: Callable[[str, str], str],
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if not models:
            raise ValueError("Danh sách model rỗng. Chạy `med models` để ghim ID vào config.toml.")
        self.models = models
        self.limits = limits
        self.quota_path = quota_path
        self._call = caller
        self._now = now
        self._sleep = sleeper
        self._monotonic = monotonic
        self._last_call: dict[str, float] = {}

    # -- hạn mức theo ngày ------------------------------------------------

    def _load_quota(self) -> dict[str, int]:
        today = pacific_date(self._now())
        stored = read_json(self.quota_path, {})
        if stored.get("date") != today:
            return {}
        return dict(stored.get("counts", {}))

    def _save_quota(self, counts: dict[str, int]) -> None:
        atomic_write_json(
            self.quota_path, {"date": pacific_date(self._now()), "counts": counts}
        )

    def usage(self) -> dict[str, int]:
        return self._load_quota()

    def _has_budget(self, model: str) -> bool:
        cap = self.limits[tier_of(model)]["rpd"]
        return self._load_quota().get(model, 0) < cap

    def _record(self, model: str) -> None:
        counts = self._load_quota()
        counts[model] = counts.get(model, 0) + 1
        self._save_quota(counts)

    # -- giãn cách theo phút ----------------------------------------------

    def _respect_rpm(self, model: str) -> None:
        rpm = self.limits[tier_of(model)]["rpm"]
        min_gap = 60.0 / rpm
        last = self._last_call.get(model)
        if last is None:
            return
        waited = self._monotonic() - last
        if waited < min_gap:
            self._sleep(min_gap - waited)

    # -- API công khai -----------------------------------------------------

    def generate(self, prompt: str) -> str:
        """Thử lần lượt từng model trong chuỗi.

        Quota RPD tính riêng cho từng model, nên model kế tiếp thường còn
        nguyên hạn mức khi model đầu đã cạn.
        """
        for model in self.models:
            if not self._has_budget(model):
                continue
            result = self._try_model(model, prompt)
            if result is not None:
                return result
        raise QuotaExceeded(
            "Mọi model đều hết quota hoặc bị 429. Chạy `med quota` để xem chi tiết."
        )

    def _try_model(self, model: str, prompt: str) -> str | None:
        """Trả None nếu model này hết cách; None báo cho generate() đổi model.

        Giãn RPM và lùi-dần khi 429 dùng chung một đồng hồ: _respect_rpm chỉ
        chờ thêm phần còn thiếu so với khoảng giãn, nên hai cơ chế không cộng
        chồng lên nhau.
        """
        for attempt in range(ATTEMPTS):
            self._respect_rpm(model)
            try:
                answer = self._call(model, prompt)
            except RateLimited:
                self._last_call[model] = self._monotonic()
                if attempt == ATTEMPTS - 1:
                    return None
                self._sleep(BACKOFF[attempt])
                continue
            self._last_call[model] = self._monotonic()
            self._record(model)
            return answer
        return None


def make_caller(api_key: str) -> Callable[[str, str], str]:
    """Bọc google-genai và chuẩn hoá 429 thành RateLimited.

    Nhập khẩu nằm trong hàm để test không cần cài SDK.
    """
    from google import genai

    client = genai.Client(api_key=api_key)

    def call(model: str, prompt: str) -> str:
        try:
            response = client.models.generate_content(model=model, contents=prompt)
        except Exception as exc:  # SDK không phơi ra lớp lỗi riêng cho lỗi tạm thời
            if is_retryable_error(exc):
                raise RateLimited(str(exc)) from exc
            raise
        return response.text or ""

    return call
