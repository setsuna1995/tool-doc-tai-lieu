# MedBot — Bot tổng hợp & dịch bài y học thường thức

**Ngày:** 2026-09-14
**Trạng thái:** Thiết kế đã duyệt, chờ lập kế hoạch triển khai

---

## 1. Mục tiêu

Mỗi sáng tự động quét các trang y học thường thức tiếng Anh, chọn ra 5-6 bài đáng đọc
nhất và trình cho người dùng. Người dùng chốt 2 bài; bot lấy toàn văn, dịch sang tiếng
Việt theo văn phong báo Việt, xuất thành 2 file Word và lưu vào OneDrive.

**Ngoài phạm vi:** đăng bài lên bất kỳ nền tảng nào; dịch sang ngôn ngữ khác tiếng Việt;
giao diện web; chạy nhiều người dùng.

---

## 2. Các quyết định đã chốt

| Hạng mục | Quyết định |
|---|---|
| Engine dịch & xếp hạng | Gemini API, free tier |
| Model xếp hạng | Dòng **Flash** (20 RPD/model) — ít request, cần chất lượng |
| Model dịch | Dòng **Flash Lite** (500 RPD, 15 RPM) — nhiều request, hạn mức rộng |
| Cách chốt bài | File Markdown trong OneDrive + gõ lệnh chọn số |
| Tiêu chí "nổi bật" | Lọc thô bằng code, rồi Gemini chấm độ đáng đọc |
| Mức biên tập | Dịch thoát, văn phong báo Việt, giữ nguyên 100% dữ kiện |
| Ảnh minh hoạ | Có, đặt đúng vị trí như bài gốc, chú thích được dịch |
| Nguồn | Khởi đầu 4 nguồn đã kiểm chứng + Mayo (chờ Playwright); thêm/bớt qua `sources.toml`, mục tiêu ~20 |
| Nguồn bị WAF chặn | Playwright + Chrome hệ thống (làm sau cùng) |
| Ngôn ngữ | Lõi Python; vỏ (lệnh, lịch chạy) PowerShell |
| Nơi lưu | Thư mục OneDrive đồng bộ cục bộ, đường dẫn cấu hình được |
| Vòng học | Chỉ học **gu chọn đề tài** từ lịch sử bài được chốt. Không học văn phong dịch |
| Vai trò của gu | Chỉ phá thế hoà khi chất lượng tương đương — điểm cộng có trần cứng, không phải hệ số nhân |

---

## 3. Khảo sát nguồn — bằng chứng đo được

Đo ngày 2026-09-14 từ máy người dùng (IP Việt Nam), dùng `urllib` với header trình duyệt.
Lưu ý: đo từ máy chủ datacenter cho kết quả khác hẳn — 4 nguồn báo 403/451 từ datacenter
lại vào bình thường từ máy người dùng. **Mọi khảo sát nguồn phải chạy từ máy đích.**

| Nguồn | Feed / URL | Danh sách | Toàn văn | Dùng |
|---|---|---|---|---|
| Healthline | `/rss/health-news` | 200, 38 bài | 200 | Có |
| Prevention | `/rss/all.xml/` | 200, 50 bài | 200 | Có |
| Science Times | `/rss/archives/archives.xml` | 200, 20 bài | 200 | Có |
| Dr. Axe | `/nutrition/feed/`, `/health/feed/` | 200, 50 bài | Có sẵn trong feed | Có |
| MedicalXpress | `/rss-feed/` | 200, 30 bài | **451** | Không |
| Mayo Clinic | `newsnetwork/feed/` | **405** | 405 | Chờ Playwright |

**Ghi chú kỹ thuật:**

- Dr. Axe nhúng toàn văn trong `content:encoded` (~26KB/bài) → bỏ hẳn bước tải trang.
- Dr. Axe feed tổng (`/feed/`) rỗng; **phải dùng feed theo chuyên mục**.
- MedicalXpress trả 451 (chặn theo vùng pháp lý) ở trang bài nhưng 200 ở RSS.
  Chặn theo IP, nên đổi User-Agent hay dùng trình duyệt thật đều vô ích. Chỉ VPN qua được.
- Mayo trả 405 cho GET — chữ ký của lớp WAF chặn trước, không phải máy chủ thật.

---

## 4. Kiến trúc

```
D:\tool-doc-tai-lieu\
├─ med.ps1                  # điểm vào duy nhất
├─ medbot\
│  ├─ cli.py                # phân lệnh
│  ├─ models.py             # dataclass Article — kiểu dữ liệu duy nhất lõi biết
│  ├─ config.py             # đọc config.toml + .env, tự dò OneDrive lần đầu
│  ├─ sources\
│  │   ├─ base.py           # giao diện Source
│  │   ├─ rss.py            # kind = "rss"
│  │   ├─ rss_fulltext.py   # kind = "rss_fulltext"
│  │   ├─ browser.py        # kind = "browser" (Playwright)
│  │   └─ registry.py       # dựng adapter từ sources.toml
│  ├─ extract.py            # trafilatura → cấu trúc section + ảnh
│  ├─ rank.py               # lọc thô + Gemini xếp hạng
│  ├─ translate.py          # dịch theo lô section + sổ thuật ngữ
│  ├─ images.py             # chọn lọc, tải, lọc rác
│  ├─ docx_writer.py        # python-docx
│  ├─ gemini.py             # lớp gọi API: retry, đổi model, đếm ngân sách
│  ├─ storage.py            # state ngày, seen.json, cache dịch
│  └─ probe.py              # dò nguồn mới
├─ sources.toml
├─ config.toml
├─ .env                     # GEMINI_API_KEY
└─ docs\specs\
```

**Nguyên tắc:** mọi khác biệt giữa các nguồn bị nhốt trong `sources/`. Phần lõi
(xếp hạng, dịch, xuất Word) chỉ làm việc với `Article` và không biết gì về HTTP, RSS
hay chống bot.

```python
@dataclass
class Article:
    source: str
    title: str
    url: str
    published: datetime
    summary: str
    fulltext: str | None = None      # có sẵn với kind="rss_fulltext"
```

---

## 5. Lệnh

```
med                  quét nguồn, sinh shortlist          (Task Scheduler gọi)
med 1 4              dịch bài số 1 và 4 của hôm nay, xuất Word
med 1 4 --date ...   dựng lại bài của một ngày cũ
med probe <url>      dò nguồn mới, in khối [[source]]
med models           liệt kê model Gemini khả dụng, ghim ID thật vào config.toml
med quota            xem đã dùng bao nhiêu request hôm nay, theo từng model
med schedule         đăng ký/cập nhật lịch theo config.toml
med schedule off     gỡ lịch
```

`med.ps1` phân lệnh theo hình dạng tham số: không tham số → `collect`; toàn chữ số →
`build`; còn lại → tên lệnh con.

---

## 6. Luồng A — `collect`

1. Dựng adapter từ `sources.toml`.
2. Chạy song song, `ThreadPoolExecutor(max_workers=8)`, timeout 25s mỗi nguồn.
   Mỗi nguồn bọc `try/except` riêng; nguồn lỗi được ghi sổ và bỏ qua.
3. Loại bài đã có trong `seen.json`.
4. Loại bài đăng quá `ranking.max_age_hours` (mặc định 48).
5. **Lọc thô bằng code** xuống `ranking.prefilter_top` (mặc định 60):
   điểm = độ mới (hàm suy giảm theo giờ) × `weight` của nguồn.
   **Gu không tham gia bước này** — xem §18.2(a).
6. Một request Gemini: gửi 60 mục (tiêu đề + sapo), yêu cầu trả JSON **cho cả 60 mục**,
   mỗi mục có `index`, `quality` (0-100), `topic`, `title_vi`, `reason_vi`.
   Nếu JSON sai định dạng hoặc thiếu mục, thử lại **tối đa một lần** — khâu này tốn 1-2 request.
7. **Áp gu và luật đa dạng** để chốt 6 suất cuối (§18.2, §18.4). Không có vòng học hoặc
   chưa đủ 7 ngày dữ liệu thì đơn giản lấy 6 bài `quality` cao nhất.
8. Ghi 2 file:
   - `<output.dir>/YYYY-MM-DD-shortlist.md` — cho người đọc
   - `state/YYYY-MM-DD.json` — cho bot đọc ở luồng B (lưu cả `quality` và `topic`
     của toàn bộ 60 bài, để vòng học có dữ liệu đối chứng)
9. Cập nhật `seen.json` (lưu hash URL + ngày, tự dọn sau 30 ngày).

Cuối shortlist luôn có dòng tổng kết: `Đã quét 4/5 nguồn — Mayo Clinic lỗi (WAF 405)`.

**Vì sao tách `.md` và `.json`:** file `.md` là cho mắt người và người dùng được phép
ghi chú, xoá, sửa tuỳ ý. Nếu bot phải đọc ngược lại chính file đó để biết người dùng
chọn gì, ta tạo ra một parser mong manh. File `.json` là hợp đồng giữa hai luồng.

---

## 7. Luồng B — `build N M`

1. Đọc state của **ngày hôm nay**, lấy bài theo số thứ tự. Nếu hôm nay chưa chạy
   `collect`, báo lỗi rõ và gợi ý chạy `med` trước. Muốn dựng lại bài của ngày cũ:
   `med 1 4 --date 2026-09-12`.
2. Lấy toàn văn: `rss_fulltext` dùng luôn dữ liệu trong feed; các loại khác tải trang.
3. `trafilatura` bóc nội dung, giữ cấu trúc heading → danh sách section.
4. Dịch theo lô (mục 9).
5. Tải và lọc ảnh (mục 10).
6. Xuất `.docx` (mục 11) vào `<output.dir>/<subfolder>/`.
7. Đánh dấu đã xử lý trong state.

Chạy lại `med 1 4` là an toàn: section đã dịch nằm trong cache, không dịch lại.

---

## 8. Cấu hình nguồn

```toml
[[source]]
name   = "Healthline"
kind   = "rss"                 # rss | rss_fulltext | browser
feed   = "https://www.healthline.com/rss/health-news"
weight = 1.2                   # >1 = ưu tiên khi lọc thô
```

Thêm nguồn = thêm 5 dòng, không đụng code. Chỉ nguồn thực sự dị thường mới cần adapter riêng.

`med probe <url>` thực hiện: tìm `<link rel="alternate" type="application/rss+xml">`
trong HTML; thử các đường dẫn phổ biến (`/feed/`, `/rss`, `/rss.xml`, `/feed/rss`);
đếm số `<item>`; kiểm tra feed có `content:encoded` không (→ `rss_fulltext`); tải thử
một bài để phát hiện 403/451; in khối `[[source]]` dán thẳng vào `sources.toml`.
Cũng dùng làm lệnh kiểm tra sức khoẻ định kỳ khi site đổi địa chỉ feed.

---

## 9. Dịch

**Chia lô:** gom các section liên tiếp vào một request cho tới ngưỡng ~6.000 token đầu
vào. Bài điển hình còn 2-4 request thay vì 10.

**Sổ thuật ngữ:** sau mỗi lô, trích các cặp thuật ngữ Anh-Việt vừa dùng và đưa vào prompt
của lô kế tiếp. Không có cơ chế này, cùng một thuật ngữ sẽ được dịch khác nhau giữa các
phần của cùng một bài.

**Ràng buộc trong prompt:**

- Không thêm bất kỳ dữ kiện nào không có trong bài gốc.
- Giữ nguyên mọi con số, đơn vị, tên nghiên cứu, tên tổ chức, tên thuốc.
- Thuật ngữ y học: ghi tiếng Việt kèm tiếng Anh trong ngoặc ở lần xuất hiện đầu tiên.
- Giữ nguyên cấp heading và cấu trúc danh sách của bài gốc.
- Văn phong báo sức khoẻ tiếng Việt, câu ngắn, tránh dịch từ-đối-từ.

**Vì sao không dịch cả bài một lần:** giới hạn token đầu ra. Tiếng Việt tốn nhiều token
hơn tiếng Anh cho cùng nội dung, bài dài dễ bị cắt cụt — và cắt cụt **không báo lỗi**,
file Word trông vẫn bình thường nhưng thiếu phần cuối. Dịch theo lô khiến lỗi này không
thể xảy ra âm thầm.

---

## 10. Ảnh

- Lấy URL thật: ưu tiên `srcset` (chọn độ phân giải cao nhất), rồi `data-src`, cuối cùng
  mới tới `src`. Nhiều site để `src` trỏ vào ảnh giữ chỗ 1x1 pixel.
- Loại bỏ: ảnh nhỏ hơn 300px, URL chứa `logo|icon|avatar|pixel|badge|sprite`, ảnh trùng.
- Chèn vào Word đúng vị trí xuất hiện trong bài gốc, rộng tối đa 5.5 inch.
- `figcaption` đi qua khâu dịch cùng lô với section chứa nó.
- Ảnh tải lỗi thì bỏ qua, ghi log, không làm hỏng cả bài.

---

## 11. File Word

Bố cục: Heading 1 (tiêu đề tiếng Việt) → dòng metadata xám (`Nguồn · ngày · "Xem bài
gốc"` là hyperlink thật) → đường kẻ → sapo in nghiêng → nội dung giữ đúng cấp heading,
bullet và ảnh → chân trang ghi `Bản dịch tham khảo, thực hiện <ngày>` kèm URL gốc.

Mặc định: Times New Roman 13pt, giãn dòng 1.15. Đều cấu hình được.

**Tên file:** `YYYY-MM-DD - <tiêu đề đã bỏ dấu>.docx`, lọc bỏ `\ / : * ? " < > |`,
cắt còn tối đa 80 ký tự.

**Ghi vào OneDrive:** ghi ra file tạm trong cùng thư mục rồi `os.replace()` sang tên
thật. Ghi thẳng dễ bị OneDrive khoá file giữa chừng khi nó bắt đầu đồng bộ.

---

## 12. Ngân sách request và chống lỗi

Google không công bố hạn mức free tier trong tài liệu; số liệu thật nằm ở
`aistudio.google.com/rate-limit` theo từng tài khoản.

**Hạn mức đo được của tài khoản này (2026-09-14):**

| Model | RPM | TPM | RPD |
|---|---|---|---|
| Gemini 3 / 3.5 / 3.6 / 3.7 / 3.8 Flash | 5 | 250K | **20 mỗi model** |
| Gemini 3.1 / 3.5 Flash Lite | 15 | 250K | **500 mỗi model** |
| Gemma 4 26B / 31B | 30 | 16K | 14.4K |

Ba hệ quả chi phối thiết kế:

1. **Quota RPD tính riêng theo từng model.** Năm model Flash cộng lại cho 100 request/ngày
   ở tầng Flash, dù mỗi model chỉ 20. Chuỗi dự phòng xoay vòng khai thác điều này.
2. **Flash Lite rộng gấp 25 lần Flash.** Việc tốn nhiều request (dịch) phải đi vào Flash
   Lite; việc ít request nhưng cần chất lượng (xếp hạng) mới dùng Flash.
3. **RPM là ràng buộc thật, TPM thì không.** Flash 5 RPM = giãn tối thiểu 12s/request;
   Flash Lite 15 RPM = 4s. TPM 250K quá rộng so với nhu cầu, bỏ qua.

**Phân công model:**

| Khâu | Model | Lượng dùng |
|---|---|---|
| Xếp hạng | Flash (mặc định bản mới nhất) | 1-2 req/ngày trên 20 |
| Dịch | Flash Lite | 4-6 req/bài, 8-12 req/ngày trên 500 |

Tổng **~10-14 request/ngày**, nằm sâu trong hạn mức ngay cả khi anh còn dùng API cho
việc khác.

**Chuỗi dự phòng khi gặp 429:** thử lại 3 lần với giãn cách 2s/4s/8s kèm nhiễu ngẫu
nhiên → chuyển sang model cùng tầng còn quota (Flash Lite 3.5 → 3.1; Flash 3.8 → 3.7 →
3.6 → 3.5 → 3) → vẫn lỗi thì dừng sạch, giữ nguyên state, cache lại mọi section đã dịch
xong, ghi log rõ ràng. Chạy lại hôm sau làm tiếp phần còn thiếu.

`gemini.py` giữ bộ đếm **theo từng model** trong `state/quota.json`, tự đặt lại lúc nửa
đêm giờ Thái Bình Dương (mốc Google dùng để reset RPD), và tôn trọng khoảng giãn RPM
riêng của từng model.

**Tên model không hardcode.** Dòng model đổi nhanh (tài khoản này đã ở Gemini 3.x trong
khi tài liệu phổ biến còn nói 2.5). `config.toml` chỉ ghi *tầng* muốn dùng; `med models`
gọi endpoint liệt kê model của API để lấy ID thật và ghim vào config. Sai tên model là
lỗi 404 khó đoán, không phải lỗi rõ ràng.

---

## 13. Cấu hình

```toml
[schedule]
time    = "08:30"
enabled = true

[output]
dir            = ""            # rỗng = tự dò %OneDrive% lần chạy đầu rồi ghi vào đây
subfolder      = "{year}-{month}"
font           = "Times New Roman"
font_size      = 13
include_images = true

[gemini]
# ID thật do `med models` dò và ghim vào đây. Thứ tự = thứ tự ưu tiên dự phòng.
rank_models      = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash"]
translate_models = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]

[gemini.limits]        # trần an toàn để bot tự dừng trước khi bị 429
flash      = { rpd = 20,  rpm = 5  }
flash_lite = { rpd = 500, rpm = 15 }

[ranking]
shortlist_size = 6
max_age_hours  = 48
prefilter_top  = 60

[learning]
enabled         = true
taste_cap       = 5      # trần điểm thưởng trên thang chất lượng 100. 0 = tắt gu
w_topic         = 3.0
w_source        = 2.0
negative_weight = 0.25   # mẫu "không chọn" nhẹ hơn mẫu "được chọn"
min_days        = 7      # dưới ngưỡng này không áp gu
profile_every   = 7      # số ngày giữa hai lần sinh lại hồ sơ gu

[learning.diversity]
enabled            = true
max_per_topic      = 2   # tối đa 2 bài cùng chủ đề trong shortlist
explore_slots      = 1   # suất dành cho chủ đề ngoài top-3 ái lực
```

---

## 14. Lịch chạy

`med schedule` đọc `config.toml` rồi đăng ký Scheduled Task bằng module PowerShell
`ScheduledTasks`. **Không** dùng `schtasks`, vì `schtasks` không có cờ chạy bù khi lỡ giờ.

Các tuỳ chọn bắt buộc, đặt qua `New-ScheduledTaskSettingsSet`:

- `-StartWhenAvailable`: máy tắt lúc 8h30 thì bật lên chạy bù, không mất ngày.
- `-RunOnlyIfNetworkAvailable`: tránh chạy khi chưa có mạng rồi báo toàn bộ nguồn lỗi.
- `-ExecutionTimeLimit` 30 phút: bot treo thì Windows tự kết thúc.

Config là nguồn sự thật duy nhất; sửa `config.toml` xong phải gõ `med schedule` để
Windows nhận.

---

## 15. Dữ liệu trên đĩa

| File | Vai trò |
|---|---|
| `state/YYYY-MM-DD.json` | 6 bài đã chọn, đánh số, đánh dấu đã xử lý |
| `state/seen.json` | Hash URL + ngày, chống lặp lại bài cũ, dọn sau 30 ngày |
| `state/cache/<hash>.json` | Section đã dịch, cho phép chạy lại không tốn quota |
| `state/quota.json` | Đếm request theo từng model, đặt lại lúc nửa đêm giờ Thái Bình Dương |
| `knowledge/history.jsonl` | Lịch sử ứng viên và lựa chọn mỗi ngày — nguồn dữ liệu của vòng học |
| `knowledge/profile.md` | Hồ sơ gu: phần người dùng viết tay + phần bot tự học |
| `knowledge/affinity.json` | Bảng ái lực nguồn/chủ đề đã tính, kèm số mẫu |
| `logs/YYYY-MM-DD.log` | UTF-8, giữ 30 ngày |

---

## 16. Bảo mật và môi trường

- `GEMINI_API_KEY` chỉ nằm trong `.env`. Không hardcode, không ghi ra log.
- `.gitignore` chặn `.env`, `state/`, `logs/`.
- Mọi thao tác file mở với `encoding="utf-8"` tường minh; đặt `PYTHONIOENCODING=utf-8`
  trong `med.ps1`. Console Windows mặc định dùng cp1252, in tiếng Việt sẽ ném
  `UnicodeEncodeError` — đã gặp thật khi khảo sát.
- File Word luôn ghi kèm nguồn và link gốc; bản dịch dùng để đọc và lưu trữ.

---

## 17. Kiểm thử

- **Adapter nguồn:** dựng từ file RSS mẫu lưu sẵn, không gọi mạng trong test.
- **Lọc thô:** kiểm tra thứ tự điểm với các mốc thời gian và `weight` khác nhau.
- **Chia lô dịch:** section dài/ngắn/rỗng phải ra đúng số lô mong đợi.
- **Lọc ảnh:** `srcset` nhiều độ phân giải, ảnh giữ chỗ 1x1, URL chứa `logo`.
- **Tên file:** tiêu đề có dấu, có ký tự cấm, dài quá 80 ký tự.
- **Chịu lỗi:** một adapter ném exception thì `collect` vẫn ra shortlist từ các nguồn còn lại.
- **Lớp Gemini:** giả lập 429 để kiểm tra retry và chuyển model dự phòng.
- **Trần gu:** dựng lịch sử giả có ái lực cực đoan, khẳng định bài `quality = 90` luôn
  xếp trên bài `quality = 80` dù bài 80 thuộc chủ đề ưa thích. Đây là bất biến quan trọng
  nhất của vòng học — nếu vỡ, bot bắt đầu ưu tiên gu hơn chất lượng.
- **Luật đa dạng:** 6 bài điểm cao nhất cùng một chủ đề thì kết quả phải còn tối đa 2.
- **Khởi động nguội:** dưới 7 ngày dữ liệu, kết quả phải trùng khớp với khi tắt vòng học.

---

## 18. Vòng học gu chọn bài

Mỗi sáng bot đưa 6 ứng viên, người dùng chốt 2. Đó là dữ liệu có nhãn sinh ra miễn phí,
không đòi thêm thao tác nào. Sau một tháng có ~60 mẫu dương và ~120 mẫu "chưa chọn".

**Phạm vi:** chỉ cải thiện khâu **xếp hạng**. Không học văn phong dịch, không theo dõi
file Word sau khi đã ghi ra OneDrive.

### 18.1 Thu thập

`knowledge/history.jsonl`, mỗi ngày một dòng, ghi lúc `build` chạy (khi đã biết người
dùng chọn gì):

```json
{"date": "2026-09-14",
 "candidates": [{"title_en": "...", "title_vi": "...", "source": "Healthline",
                 "topic": "dinh dưỡng", "url": "...", "rank": 1}, ...],
 "chosen": [1, 4]}
```

Trường `topic` không tốn thêm request: thêm nó vào JSON mà khâu xếp hạng vốn đã yêu cầu
Gemini trả về.

### 18.2 Tầng 1 — gu chỉ phá thế hoà, không quyết định thắng thua

**Nguyên tắc:** chất lượng quyết định; gu chỉ xen vào khi các bài **chất lượng tương
đương**. Hai hệ quả thiết kế bắt buộc:

**(a) Gu không được tham gia bước lọc thô.** Bước lọc thô (250 bài → 60 ở §6 bước 5)
chỉ dùng độ mới và `weight` độ tin cậy của nguồn do người dùng đặt tay. Nếu nghiêng theo
gu ngay từ đây, bài chất lượng cao thuộc chủ đề lạ bị loại **trước khi Gemini kịp nhìn
thấy** — bot tự bịt mắt mình rồi mới chấm điểm.

**(b) Gu là điểm cộng có trần cứng, không phải hệ số nhân.** Gemini chấm điểm chất lượng
0-100 cho cả 60 bài. Sau đó:

```
điểm_cuối = quality            (0-100, do Gemini chấm)
          + min(taste_cap, taste_bonus)

taste_bonus  = w_topic × topic_affinity + w_source × source_affinity
taste_cap    = 5           # trần cứng, cấu hình được
```

Trần chính là định nghĩa toán học của "tương đồng": với `taste_cap = 5`, bài 80 điểm
**không bao giờ** vượt bài 90; nhưng 78 và 80 thì gu lật được. Tăng trần lên 15 nghĩa là
cho gu quyền lớn hơn; đặt về 0 là tắt hẳn vòng học.

Dùng hệ số nhân (`× (1 + 0.3 × ái_lực)`) là sai ở đây: nó cho gu quyền đẩy lệch tới 30%,
đủ để một bài tầm thường thuộc chủ đề quen vượt mặt một bài xuất sắc thuộc chủ đề lạ.

**Cách tính ái lực** (thuần cục bộ, 0 request):

- **Theo nguồn / theo chủ đề:** tỷ lệ `được chọn / được đưa vào shortlist`, chuẩn hoá về
  thang [-1, 1] để ái lực âm cũng trừ điểm được.
- **Trọng số bất đối xứng:** mẫu dương tính 1.0; mẫu "không chọn" chỉ tính **0.25**.
  Không chọn ≠ không thích — rất có thể người dùng thích cả 6 nhưng chỉ đủ thời gian
  đọc 2. Coi chúng là mẫu âm đầy đủ sẽ làm bot học lệch một cách có hệ thống.
- **Làm trơn Laplace:** nguồn hoặc chủ đề mới có vài mẫu không được nhảy điểm đột ngột.

Bảng trọng số, toàn bộ nằm trong `config.toml`:

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `taste_cap` | 5 | Trần điểm thưởng trên thang chất lượng 100. Đặt 0 = tắt gu |
| `w_topic` | 3.0 | Phần đóng góp tối đa của ái lực chủ đề |
| `w_source` | 2.0 | Phần đóng góp tối đa của ái lực nguồn |
| `negative_weight` | 0.25 | Trọng số của mẫu "không chọn" so với mẫu "được chọn" |
| `min_days` | 7 | Dưới ngưỡng này thì không áp gu |

### 18.3 Tầng 2 — hồ sơ gu bằng chữ (1 request/tuần)

Mỗi 7 ngày, gửi lịch sử 30 ngày gần nhất cho Gemini, sinh ra đoạn mô tả gu ~200 từ,
chèn vào prompt xếp hạng hàng ngày. Kích thước cố định nên prompt không phình theo thời gian.

`knowledge/profile.md` chia hai phần rõ ràng:

```markdown
## Do bạn viết — bot không bao giờ sửa
Ưu tiên dinh dưỡng và giấc ngủ. Tránh bài về thẩm mỹ.

## Bot tự học — cập nhật hàng tuần
(phần này bot ghi đè)
```

Kiến thức học được **phải ở dạng người đọc và sửa được**. Không dùng embedding hay vector
store: bot hiểu sai gu mà người dùng không nhìn thấy để sửa là kiểu hỏng tệ nhất.

### 18.4 Chống bong bóng lọc

Trần `taste_cap` đã hạn chế phần lớn rủi ro thu hẹp. Còn lại một nguy cơ nữa mà trần không
chặn được: **đơn điệu chủ đề** — 6 bài cùng nói về dinh dưỡng, không phải vì gu đẩy lên
mà vì hôm đó các nguồn đăng nhiều bài dinh dưỡng chất lượng cao.

Hai luật đa dạng, áp **sau** khi đã xếp theo `điểm_cuối`:

1. **Tối đa 2 bài cùng chủ đề** trong 6 suất. Bài thứ ba cùng chủ đề bị đẩy xuống, nhường
   cho bài điểm cao nhất thuộc chủ đề khác.
2. **Ít nhất 1 suất** dành cho bài điểm cao nhất thuộc chủ đề **nằm ngoài top-3 ái lực**.
   Suất này đánh dấu 🔍 trong shortlist để người dùng biết đây là đề tài bot cố ý đưa ra
   ngoài vùng quen thuộc.

Luật 2 cũng là cách duy nhất để vòng học tự sửa sai: nếu bot đã học lệch, chỉ có bài ngoài
vùng quen mới tạo ra dữ liệu chứng minh điều đó. Cả hai luật tắt được qua `diversity.enabled`.

### 18.5 Khởi động nguội

Dưới 7 ngày dữ liệu thì **không áp dụng gì cả** — chạy đúng như khi chưa có vòng học.
Học vội từ 2-3 mẫu sẽ lệch nặng hơn là không học.

### 18.6 Đo xem vòng học có thật sự hiệu quả

Ghi lại **thứ hạng trung bình của bài được chọn** trong shortlist mỗi ngày. Bot học đúng
thì con số này giảm dần — bài người dùng muốn đọc nổi lên đầu danh sách.

`med taste` in ra đường xu hướng này cùng bảng ái lực nguồn/chủ đề. Nếu sau một tháng chỉ
số không cải thiện, vòng học không có tác dụng và nên tắt (`learning.enabled = false`).
Một hệ thống học mà không đo được thì không có cách nào biết nó đang giúp hay đang hại.

### 18.7 Lệnh

```
med taste            xem hồ sơ gu, bảng ái lực, và đường xu hướng thứ hạng
med taste rebuild    buộc sinh lại hồ sơ ngay, không đợi chu kỳ tuần
```

---

## 19. Thứ tự triển khai

1. Bộ khung + `med probe` → dò được nguồn, sinh `sources.toml`
2. `med collect` → sáng ra có shortlist trong OneDrive *(nửa giá trị)*
3. `med 1 4` → ra 2 file Word hoàn chỉnh *(trọn vẹn giá trị)*
   — **kèm luôn việc ghi `knowledge/history.jsonl`**, xem ghi chú bên dưới
4. `med schedule` → tự chạy hàng ngày
5. Adapter Mayo bằng Playwright
6. Vòng học gu: `med taste`, tính ái lực, áp `taste_cap` và luật đa dạng

**Ghi chú quan trọng về thứ tự:** phần **thu thập** dữ liệu học (ghi `history.jsonl`)
phải làm ngay ở mốc 3, dù phần **áp dụng** mãi mốc 6 mới làm. Vòng học cần tối thiểu
7 ngày dữ liệu; nếu để việc ghi lịch sử tới mốc 6 mới bắt đầu thì sau khi code xong còn
phải chờ thêm một tuần nữa mới thấy tác dụng. Ghi sớm thì tới mốc 6 dữ liệu đã sẵn sàng.
Chi phí của việc ghi sớm gần như bằng không — vài dòng nối vào một file.

Mốc 5 xếp gần cuối là cố ý: rủi ro cao, giá trị thấp (một nguồn trong hai mươi, chưa chắc
qua được WAF). Đặt ở cuối thì thất bại tốn ít nhất — vẫn còn nguyên một con bot chạy tốt.

---

## 20. Rủi ro đã biết

| Rủi ro | Cách ứng phó |
|---|---|
| Hạn mức free tier bị siết thêm | Ngân sách 10-14 req/ngày so với 500 RPD của Flash Lite — dư địa rất lớn; có chuỗi dự phòng xoay vòng qua 7 model |
| Google đổi tên model | `med models` dò ID thật; config chỉ ghim, không hardcode trong code |
| Site đổi cấu trúc/địa chỉ feed | `med probe` phát hiện; adapter theo cấu hình nên sửa nhanh |
| Mayo vẫn chặn dù dùng Playwright | Chấp nhận bỏ nguồn; 4 nguồn còn lại đã đủ |
| Gemini dịch sai số liệu y học | Prompt cấm thêm dữ kiện và cấm sửa số; file Word luôn kèm link gốc để đối chiếu |
| OneDrive khoá file khi đang đồng bộ | Ghi file tạm rồi `os.replace()` |
| Bài gốc quá dài, vượt token đầu ra | Chia lô theo section; thiếu lô nào phát hiện được ngay |
| Vòng học làm hẹp gu người dùng | `taste_cap` giới hạn gu thành yếu tố phá thế hoà; luật đa dạng giữ 1 suất ngoài vùng quen; §18.6 đo được để biết khi nào nên tắt |
| Vòng học học từ dữ liệu sai lệch | Mẫu "không chọn" chỉ tính 0.25; dưới 7 ngày không áp gu; `profile.md` sửa tay được |
