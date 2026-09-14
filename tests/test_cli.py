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
