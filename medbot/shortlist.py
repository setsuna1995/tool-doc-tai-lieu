from __future__ import annotations

from datetime import date

from medbot.models import Article


def render(
    day: date,
    picks: list[Article],
    scanned: int,
    total_sources: int,
    failed: list[tuple[str, str]],
) -> str:
    lines = [f"# Bài nổi bật ngày {day:%d/%m/%Y}", ""]

    if not picks:
        lines += [
            "Không tìm được bài nào hợp lệ hôm nay.",
            "",
            "Kiểm tra lại bằng `med probe <url>` xem nguồn có đổi địa chỉ feed không.",
            "",
        ]

    for position, article in enumerate(picks, start=1):
        title = article.title_vi or article.title
        lines.append(f"## {position}. {title}")
        lines.append(
            f"**Nguồn:** {article.source} · {article.published:%d/%m} · "
            f"[bản gốc]({article.url})"
        )
        if article.reason_vi:
            lines.append(f"**Vì sao chọn:** {article.reason_vi}")
        lines.append("")

    ok = total_sources - len(failed)
    footer = f"---\n\nĐã quét {ok}/{total_sources} nguồn, {scanned} bài trong 48 giờ qua."
    if failed:
        detail = "; ".join(f"{name} ({reason})" for name, reason in failed)
        footer += f" Lỗi: {detail}."
    footer += "\n\nChốt bài xong, gõ ví dụ `med 1 4` để dịch và xuất Word."
    lines.append(footer)
    return "\n".join(lines)
