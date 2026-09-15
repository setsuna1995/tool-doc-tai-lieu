from __future__ import annotations

import re
from pathlib import Path

TASK_NAME = "MedBotCollect"
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


def build_register_script(med_ps1: Path, time_str: str) -> str:
    """Dùng module PowerShell ScheduledTasks, KHÔNG dùng schtasks.exe —
    schtasks không có cờ chạy bù khi lỡ giờ (đã ghi trong spec §14).

    -StartWhenAvailable: máy tắt lúc 8h30 thì bật lên chạy bù, không mất ngày.
    -RunOnlyIfNetworkAvailable: tránh chạy khi chưa có mạng rồi báo lỗi hết nguồn.
    -ExecutionTimeLimit: bot treo thì Windows tự kết thúc, không chiếm máy cả ngày.

    time_str đến từ config.toml (người dùng tự chỉnh) rồi bị chèn thẳng vào
    script PowerShell mà subprocess.run() sẽ thực thi — không kiểm tra định
    dạng HH:MM trước thì một giá trị chứa ";" có thể tiêm lệnh PowerShell tuỳ ý.
    """
    if not _TIME_RE.match(time_str):
        raise ValueError(f"schedule.time phải đúng định dạng HH:MM, nhận {time_str!r}")
    return "\n".join([
        f'$action = New-ScheduledTaskAction -Execute "powershell.exe" '
        f'-Argument \'-NoProfile -ExecutionPolicy Bypass -File "{med_ps1}"\'',
        f"$trigger = New-ScheduledTaskTrigger -Daily -At {time_str}",
        "$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable "
        "-RunOnlyIfNetworkAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30)",
        f'Register-ScheduledTask -TaskName "{TASK_NAME}" -Action $action '
        f"-Trigger $trigger -Settings $settings -Force | Out-Null",
        f'Write-Output "Da dang ky {TASK_NAME} chay luc {time_str} hang ngay."',
    ])


def build_unregister_script() -> str:
    return "\n".join([
        f'Unregister-ScheduledTask -TaskName "{TASK_NAME}" -Confirm:$false '
        f"-ErrorAction SilentlyContinue",
        f'Write-Output "Da go lich {TASK_NAME}."',
    ])
