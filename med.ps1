#Requires -Version 5.1
# Vỏ mỏng: đặt bảng mã UTF-8 rồi chuyển tiếp tham số sang Python.
# Không có dòng PYTHONIOENCODING, in tiếng Việt ra console sẽ ném UnicodeEncodeError
# vì console Windows mặc định dùng cp1252.

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Push-Location $root
try {
    & python -m medbot @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
