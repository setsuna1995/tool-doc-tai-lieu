import pytest

from medbot.cli import parse_command


def test_no_argument_means_collect():
    assert parse_command([]) == ("collect", [])


def test_all_digits_means_build():
    assert parse_command(["1", "4"]) == ("build", ["1", "4"])


def test_single_digit_means_build():
    assert parse_command(["3"]) == ("build", ["3"])


def test_named_subcommand_passes_through():
    assert parse_command(["probe", "https://x.test/"]) == ("probe", ["https://x.test/"])


def test_models_subcommand():
    assert parse_command(["models"]) == ("models", [])


def test_quota_subcommand():
    assert parse_command(["quota"]) == ("quota", [])


def test_build_with_date_flag():
    assert parse_command(["1", "4", "--date", "2026-09-12"]) == (
        "build", ["1", "4", "--date", "2026-09-12"]
    )


def test_unknown_subcommand_is_rejected():
    with pytest.raises(ValueError, match="telepathy"):
        parse_command(["telepathy"])


def test_parse_command_still_routes_build_correctly_after_wiring():
    # Bao ve hanh vi da co tu ke hoach 1, khong duoc doi khi noi them build
    assert parse_command(["1", "4"]) == ("build", ["1", "4"])
    assert parse_command(["1", "4", "--date", "2026-09-12"]) == (
        "build", ["1", "4", "--date", "2026-09-12"]
    )


def test_schedule_off_still_parses_as_schedule_subcommand():
    assert parse_command(["schedule", "off"]) == ("schedule", ["off"])


def test_schedule_alone_parses_with_empty_args():
    assert parse_command(["schedule"]) == ("schedule", [])
