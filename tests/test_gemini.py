from datetime import datetime, timezone
from pathlib import Path

import pytest

from medbot.gemini import (
    GeminiClient,
    QuotaExceeded,
    RateLimited,
    pacific_date,
    tier_of,
)

# RPM rộng: để cơ chế lùi-dần khi 429 chi phối, không bị giãn RPM cộng chồng lên.
LIMITS_FAST = {"flash": {"rpd": 2, "rpm": 60}, "flash_lite": {"rpd": 500, "rpm": 15}}
# RPM chật: dành riêng cho test giãn cách theo phút.
LIMITS_SLOW = {"flash": {"rpd": 20, "rpm": 5}, "flash_lite": {"rpd": 500, "rpm": 15}}


class Clock:
    def __init__(self):
        self.t = 0.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.t += seconds


def fixed_now():
    return datetime(2026, 9, 14, 18, 0, tzinfo=timezone.utc)


def make_client(tmp_path: Path, caller, models=("a-flash", "b-flash"), clock=None, limits=None):
    clock = clock or Clock()
    return GeminiClient(
        models=list(models),
        limits=limits or LIMITS_FAST,
        quota_path=tmp_path / "quota.json",
        caller=caller,
        now=fixed_now,
        sleeper=clock.sleep,
        monotonic=clock.monotonic,
    ), clock


def test_tier_of_recognises_flash_lite():
    assert tier_of("gemini-3.5-flash-lite") == "flash_lite"
    assert tier_of("gemini-3.8-flash") == "flash"


def test_pacific_date_rolls_back_from_utc_evening():
    # 2026-09-15 04:00 UTC vẫn là 2026-09-14 ở giờ Thái Bình Dương
    assert pacific_date(datetime(2026, 9, 15, 4, 0, tzinfo=timezone.utc)) == "2026-09-14"


def test_uses_first_model_when_healthy(tmp_path: Path):
    calls = []
    client, _ = make_client(tmp_path, lambda m, p: calls.append(m) or "ok")
    assert client.generate("xin chào") == "ok"
    assert calls == ["a-flash"]


def test_falls_back_to_next_model_after_repeated_429(tmp_path: Path):
    calls = []

    def caller(model, prompt):
        calls.append(model)
        if model == "a-flash":
            raise RateLimited("429")
        return "ok"

    client, clock = make_client(tmp_path, caller)
    assert client.generate("x") == "ok"
    assert calls == ["a-flash", "a-flash", "a-flash", "b-flash"]
    assert clock.slept[:2] == [2.0, 4.0]


def test_raises_when_every_model_is_rate_limited(tmp_path: Path):
    def caller(model, prompt):
        raise RateLimited("429")

    client, _ = make_client(tmp_path, caller)
    with pytest.raises(QuotaExceeded):
        client.generate("x")


def test_stops_using_a_model_once_rpd_is_reached(tmp_path: Path):
    calls = []
    client, _ = make_client(tmp_path, lambda m, p: calls.append(m) or "ok")
    client.generate("1")
    client.generate("2")  # a-flash đạt rpd=2
    client.generate("3")
    assert calls == ["a-flash", "a-flash", "b-flash"]


def test_quota_survives_restart(tmp_path: Path):
    client, _ = make_client(tmp_path, lambda m, p: "ok")
    client.generate("1")
    again, _ = make_client(tmp_path, lambda m, p: "ok")
    assert again.usage()["a-flash"] == 1


def test_quota_resets_on_new_pacific_day(tmp_path: Path):
    (tmp_path / "quota.json").write_text(
        '{"date": "2026-09-13", "counts": {"a-flash": 2}}', encoding="utf-8"
    )
    client, _ = make_client(tmp_path, lambda m, p: "ok")
    assert client.usage() == {}


def test_waits_to_respect_rpm_spacing(tmp_path: Path):
    client, clock = make_client(tmp_path, lambda m, p: "ok", limits=LIMITS_SLOW)
    client.generate("1")
    client.generate("2")
    # flash = 5 RPM -> giãn tối thiểu 12 giây giữa hai request
    assert clock.slept == [12.0]


def test_non_rate_limit_errors_propagate(tmp_path: Path):
    def caller(model, prompt):
        raise ValueError("prompt hỏng")

    client, _ = make_client(tmp_path, caller)
    with pytest.raises(ValueError, match="prompt hỏng"):
        client.generate("x")
