from __future__ import annotations

from datetime import datetime

import requests

from stocknoti.models import StockAnalysis


BUY_COLOR = 0x31C48D
WATCH_COLOR = 0xF6AD55
AVOID_COLOR = 0xF05252


def _score_color(score: float) -> int:
    if score >= 70:
        return BUY_COLOR
    if score >= 45:
        return WATCH_COLOR
    return AVOID_COLOR


def _score_label(score: float) -> str:
    if score >= 80:
        return "เด่นมาก"
    if score >= 70:
        return "น่าสนใจ"
    if score >= 55:
        return "รอดูจังหวะ"
    if score >= 40:
        return "เฝ้าดู"
    return "เลี่ยงก่อน"


def _score_bar(score: float) -> str:
    filled = max(0, min(10, round(score / 10)))
    return f"[{'#' * filled}{'-' * (10 - filled)}] {score:.1f}/100"


def _money(value: float | None, currency: str = "") -> str:
    if value is None:
        return "ไม่ทราบ"
    suffix = f" {currency}" if currency else ""
    return f"{value:,.2f}{suffix}"


def _compact_money(value: float | None, currency: str = "") -> str:
    if value is None:
        return "ไม่ทราบ"
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        text = f"{value / 1_000_000_000:,.2f}B"
    elif abs_value >= 1_000_000:
        text = f"{value / 1_000_000:,.2f}M"
    else:
        text = f"{value:,.2f}"
    return f"{text} {currency}".strip()


def _line_reasons(items: list[str]) -> str:
    if not items:
        return "ยังไม่มีสัญญาณเด่น"
    return "\n".join(f"• {item}" for item in items[:4])


def _signal_lines(analysis: StockAnalysis) -> str:
    tech = analysis.technical
    quote = analysis.quote
    return (
        f"ราคา: **{_money(quote.price, quote.currency)}**\n"
        f"Trend: **{tech.trend}**\n"
        f"แนวรับ: **{_money(tech.support, quote.currency)}**\n"
        f"แนวต้าน: **{_money(tech.resistance, quote.currency)}**"
    )


def _score_lines(analysis: StockAnalysis) -> str:
    score = analysis.score
    return (
        f"รวม: `{_score_bar(score.total)}`\n"
        f"เทคนิค: `{score.technical:.1f}` | พื้นฐาน: `{score.fundamental:.1f}` | "
        f"ข่าว: `{score.news:.1f}` | เสี่ยง: `{score.risk:.1f}`"
    )


def _news_lines(analysis: StockAnalysis) -> str:
    lines = []
    for item in analysis.news[:3]:
        link = f" [อ่านต่อ]({item.url})" if item.url else ""
        lines.append(f"• {item.title} - {item.source}{link}")
    return "\n".join(lines) if lines else "ยังไม่มีข่าวล่าสุด"


def _ranking_title(index: int, analysis: StockAnalysis) -> str:
    label = _score_label(analysis.score.total)
    if label == analysis.recommendation:
        return f"{index}. {analysis.symbol} | {label}"
    return f"{index}. {analysis.symbol} | {label} | {analysis.recommendation}"


def make_daily_payload(best: list[StockAnalysis], avoid: list[StockAnalysis]) -> dict:
    today = datetime.now().strftime("%d/%m/%Y")
    embeds = [
        {
            "title": f"StockNoti Daily Brief | {today}",
            "description": (
                "สรุปหุ้นที่เด่นและหุ้นที่ควรรอก่อนจากราคา, กราฟเทคนิค, งบการเงิน, ข่าว และความเสี่ยง\n"
                "ใช้เป็น radar ก่อนตัดสินใจ และควรเช็กข่าว/งบล่าสุดซ้ำทุกครั้ง"
            ),
            "color": BUY_COLOR,
            "fields": [],
            "footer": {"text": "StockNoti | Educational use only"},
        }
    ]

    for index, analysis in enumerate(best, start=1):
        embeds[0]["fields"].append(
            {
                "name": _ranking_title(index, analysis),
                "value": (
                    f"`{_score_bar(analysis.score.total)}`\n"
                    f"{_signal_lines(analysis)}\n"
                    f"เหตุผลหลัก:\n{_line_reasons(analysis.score.reasons[:3])}"
                ),
                "inline": False,
            }
        )

    avoid_embed = {
        "title": "Waitlist | หุ้นที่ควรรอก่อน",
        "description": "กลุ่มนี้คะแนนต่ำกว่าเพื่อนใน watchlist เพราะสัญญาณรวมยังไม่ชัด หรือความเสี่ยงยังสูง",
        "color": AVOID_COLOR,
        "fields": [],
    }
    for index, analysis in enumerate(avoid, start=1):
        avoid_embed["fields"].append(
            {
                "name": _ranking_title(index, analysis),
                "value": (
                    f"`{_score_bar(analysis.score.total)}`\n"
                    f"{_signal_lines(analysis)}\n"
                    f"สิ่งที่ต้องระวัง:\n{_line_reasons(analysis.score.warnings[:3])}"
                ),
                "inline": False,
            }
        )
    embeds.append(avoid_embed)

    return {"username": "StockNoti", "embeds": embeds}


def make_single_payload(analysis: StockAnalysis) -> dict:
    color = _score_color(analysis.score.total)
    tech = analysis.technical
    quote = analysis.quote
    rsi_line = f"RSI: {tech.rsi14:.1f}" if tech.rsi14 is not None else "RSI: ไม่ทราบ"

    embed = {
        "title": f"{analysis.symbol} | {quote.name}",
        "description": (
            f"สถานะ: **{analysis.recommendation}**\n"
            f"คะแนนรวม: `{_score_bar(analysis.score.total)}`\n"
            f"ภาพรวม: **{_score_label(analysis.score.total)}**"
        ),
        "color": color,
        "fields": [
            {
                "name": "Snapshot",
                "value": (
                    f"ราคา: {_money(quote.price, quote.currency)}\n"
                    f"Trend: {tech.trend}\n"
                    f"แนวรับ: {_money(tech.support, quote.currency)}\n"
                    f"แนวต้าน: {_money(tech.resistance, quote.currency)}\n"
                    f"{rsi_line}"
                ),
                "inline": False,
            },
            {
                "name": "Scorecard",
                "value": _score_lines(analysis),
                "inline": False,
            },
            {
                "name": "Quarterly Snapshot",
                "value": (
                    f"วันที่งบ: {quote.latest_quarter_date or 'ไม่ทราบ'}\n"
                    f"รายได้: {_compact_money(quote.latest_quarter_revenue, quote.currency)}\n"
                    f"กำไรสุทธิ: {_compact_money(quote.latest_quarter_net_income, quote.currency)}"
                ),
                "inline": False,
            },
            {"name": "เหตุผลที่น่าสนใจ", "value": _line_reasons(analysis.score.reasons), "inline": False},
            {"name": "จุดที่ต้องระวัง", "value": _line_reasons(analysis.score.warnings), "inline": False},
            {"name": "ข่าวล่าสุด", "value": _news_lines(analysis), "inline": False},
        ],
        "footer": {"text": "StockNoti | ใช้เป็นข้อมูลประกอบเท่านั้น ควรกำหนดแผนและจุดตัดขาดทุนเอง"},
    }
    return {"username": "StockNoti", "embeds": [embed]}


def send_discord(webhook_url: str, payload: dict) -> None:
    response = requests.post(webhook_url, json=payload, timeout=15)
    response.raise_for_status()
