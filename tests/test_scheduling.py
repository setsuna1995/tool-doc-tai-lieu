from pathlib import Path

import pytest

from medbot.scheduling import TASK_NAME, build_register_script, build_unregister_script


def test_register_script_includes_task_name():
    script = build_register_script(Path("D:/tool-doc-tai-lieu/med.ps1"), "08:30")
    assert TASK_NAME in script


def test_register_script_includes_the_med_ps1_path():
    script = build_register_script(Path("D:/tool-doc-tai-lieu/med.ps1"), "08:30")
    assert "med.ps1" in script


def test_register_script_uses_the_configured_time():
    script = build_register_script(Path("D:/tool-doc-tai-lieu/med.ps1"), "09:15")
    assert "09:15" in script


def test_register_script_enables_catch_up_after_missed_start():
    # -StartWhenAvailable: may tat luc 8h30 thi bat len chay bu, khong mat ngay
    script = build_register_script(Path("D:/tool-doc-tai-lieu/med.ps1"), "08:30")
    assert "-StartWhenAvailable" in script


def test_register_script_requires_network():
    script = build_register_script(Path("D:/tool-doc-tai-lieu/med.ps1"), "08:30")
    assert "-RunOnlyIfNetworkAvailable" in script


def test_register_script_has_a_time_limit_so_a_hang_gets_killed():
    script = build_register_script(Path("D:/tool-doc-tai-lieu/med.ps1"), "08:30")
    assert "-ExecutionTimeLimit" in script


def test_unregister_script_targets_the_same_task_name():
    script = build_unregister_script()
    assert TASK_NAME in script
    assert "Unregister-ScheduledTask" in script


def test_register_script_rejects_time_with_injected_powershell():
    # config.toml la file nguoi dung tu chinh; time_str khong duoc chen
    # thang vao script PowerShell ma khong kiem tra dinh dang HH:MM.
    with pytest.raises(ValueError, match="HH:MM"):
        build_register_script(
            Path("D:/tool-doc-tai-lieu/med.ps1"),
            "08:30; Remove-Item -Recurse -Force C:\\",
        )


def test_register_script_accepts_valid_hh_mm():
    script = build_register_script(Path("D:/tool-doc-tai-lieu/med.ps1"), "23:59")
    assert "23:59" in script
