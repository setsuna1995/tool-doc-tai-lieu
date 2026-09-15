# MedBot

Bot tổng hợp và dịch bài y học thường thức. Thiết kế: `docs/specs/2026-09-14-medbot-design.md`.

## Cài đặt

```powershell
pip install -r requirements.txt
Set-Content .env "GEMINI_API_KEY=<khoá từ https://aistudio.google.com/apikey>" -Encoding utf8
.\med.ps1 models               # ghim ID model vào config.toml
```

## Lệnh

| Lệnh | Việc |
|---|---|
| `.\med.ps1` | Quét nguồn, ghi shortlist vào OneDrive |
| `.\med.ps1 probe <url>` | Dò feed của một trang mới |
| `.\med.ps1 models` | Liệt kê model Gemini khả dụng |
| `.\med.ps1 quota` | Xem đã dùng bao nhiêu request hôm nay |
| `.\med.ps1 1 4` | Dịch bài số 1 và 4 của hôm nay, xuất Word |
| `.\med.ps1 1 4 --date 2026-09-12` | Dựng lại bài của một ngày cũ |
| `.\med.ps1 schedule` | Đăng ký chạy `collect` tự động theo giờ trong config.toml |
| `.\med.ps1 schedule off` | Gỡ lịch tự động |

## Thêm nguồn

Chạy `.\med.ps1 probe https://trang-moi.com/`, chép khối `[[source]]` in ra vào `sources.toml`.

