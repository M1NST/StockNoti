from __future__ import annotations

from io import BytesIO
from pathlib import Path
import textwrap

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from stocknoti.models import StockAnalysis


CARD_W = 900
CARD_H = 1400
BG = "#0b0f14"
PANEL = "#151a22"
PANEL_2 = "#10151c"
BORDER = "#27303b"
WHITE = "#f7fafc"
MUTED = "#a8b3c2"
GOLD = "#d6b15e"
GREEN = "#31c48d"
YELLOW = "#f6ad55"
RED = "#f05252"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    env_name = "STOCKNOTI_FONT_BOLD" if bold else "STOCKNOTI_FONT_REGULAR"
    candidates = [
        Path.home() / ".fonts" / ("NotoSansThai-Bold.ttf" if bold else "NotoSansThai-Regular.ttf"),
        Path("C:/Windows/Fonts/tahomabd.ttf" if bold else "C:/Windows/Fonts/tahoma.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansThai-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]

    import os

    configured = os.getenv(env_name)
    if configured:
        candidates.insert(0, Path(configured))

    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _money(value: float | None, currency: str = "") -> str:
    if value is None:
        return "N/A"
    suffix = f" {currency}" if currency else ""
    return f"{value:,.2f}{suffix}"


def _compact(value: float | None, currency: str = "") -> str:
    if value is None:
        return "N/A"
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        text = f"{value / 1_000_000_000:,.2f}B"
    elif abs_value >= 1_000_000:
        text = f"{value / 1_000_000:,.2f}M"
    else:
        text = f"{value:,.2f}"
    return f"{text} {currency}".strip()


def _score_label(score: float) -> tuple[str, str]:
    if score >= 70:
        return "BUY WATCH", GREEN
    if score >= 55:
        return "WAIT FOR SETUP", YELLOW
    if score >= 40:
        return "NEUTRAL", YELLOW
    return "AVOID", RED


def _status(color: str) -> tuple[str, str]:
    mapping = {"green": ("GOOD", GREEN), "yellow": ("WATCH", YELLOW), "red": ("RISK", RED)}
    return mapping.get(color, ("WATCH", YELLOW))


def _technical_statuses(analysis: StockAnalysis, history: pd.DataFrame) -> list[tuple[str, str, str]]:
    close = history["Close"].dropna() if "Close" in history else pd.Series(dtype=float)
    if close.empty:
        return [
            ("SMA", "yellow", "ไม่มีข้อมูลราคา"),
            ("EMA", "yellow", "ไม่มีข้อมูลราคา"),
            ("RSI", "yellow", "ไม่มีข้อมูลราคา"),
            ("Volatility", "yellow", "ไม่มีข้อมูลราคา"),
            ("Momentum", "yellow", "ไม่มีข้อมูลราคา"),
        ]

    last = float(close.iloc[-1])
    sma20 = close.rolling(20).mean().dropna()
    sma50 = close.rolling(50).mean().dropna()
    ema12 = close.ewm(span=12, adjust=False).mean().dropna()
    ema26 = close.ewm(span=26, adjust=False).mean().dropna()
    returns = close.pct_change().dropna()
    volatility = float(returns.tail(20).std() * (252 ** 0.5) * 100) if len(returns) >= 20 else None
    momentum = float((last / close.iloc[-20] - 1) * 100) if len(close) >= 20 and close.iloc[-20] else None

    sma_color = "yellow"
    sma_note = "รอสัญญาณ SMA"
    if not sma20.empty and not sma50.empty:
        if last > float(sma20.iloc[-1]) > float(sma50.iloc[-1]):
            sma_color, sma_note = "green", "ราคาเหนือ SMA20/50"
        elif last < float(sma20.iloc[-1]) < float(sma50.iloc[-1]):
            sma_color, sma_note = "red", "ราคาใต้ SMA20/50"

    ema_color = "yellow"
    ema_note = "EMA ยังไม่ชัด"
    if not ema12.empty and not ema26.empty:
        if float(ema12.iloc[-1]) > float(ema26.iloc[-1]):
            ema_color, ema_note = "green", "EMA12 เหนือ EMA26"
        else:
            ema_color, ema_note = "red", "EMA12 ต่ำกว่า EMA26"

    rsi = analysis.technical.rsi14
    if rsi is None:
        rsi_color, rsi_note = "yellow", "RSI ไม่ทราบ"
    elif 45 <= rsi <= 68:
        rsi_color, rsi_note = "green", f"RSI {rsi:.1f} กำลังดี"
    elif rsi > 75:
        rsi_color, rsi_note = "red", f"RSI {rsi:.1f} Overbought"
    elif rsi < 35:
        rsi_color, rsi_note = "red", f"RSI {rsi:.1f} อ่อนแรง"
    else:
        rsi_color, rsi_note = "yellow", f"RSI {rsi:.1f} เฝ้าดู"

    if volatility is None:
        vol_color, vol_note = "yellow", "Volatility ไม่ทราบ"
    elif volatility <= 28:
        vol_color, vol_note = "green", f"Vol {volatility:.1f}% คุมได้"
    elif volatility <= 45:
        vol_color, vol_note = "yellow", f"Vol {volatility:.1f}% ผันผวน"
    else:
        vol_color, vol_note = "red", f"Vol {volatility:.1f}% สูง"

    if momentum is None:
        mom_color, mom_note = "yellow", "Momentum ไม่ทราบ"
    elif momentum > 3:
        mom_color, mom_note = "green", f"20D +{momentum:.1f}%"
    elif momentum < -3:
        mom_color, mom_note = "red", f"20D {momentum:.1f}%"
    else:
        mom_color, mom_note = "yellow", f"20D {momentum:.1f}%"

    return [
        ("SMA", sma_color, sma_note),
        ("EMA", ema_color, ema_note),
        ("RSI", rsi_color, rsi_note),
        ("Volatility", vol_color, vol_note),
        ("Momentum", mom_color, mom_note),
    ]


def _draw_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, size: int, color: str = WHITE, bold: bool = False) -> None:
    draw.text(xy, text, font=_font(size, bold=bold), fill=color)


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    width: int,
    size: int,
    color: str = WHITE,
    bold: bool = False,
    line_gap: int = 8,
    max_lines: int | None = None,
) -> int:
    font = _font(size, bold=bold)
    x, y = xy
    lines: list[str] = []
    for paragraph in text.splitlines():
        lines.extend(textwrap.wrap(paragraph, width=width) or [""])
    if max_lines:
        lines = lines[:max_lines]
    for line in lines:
        draw.text((x, y), line, font=font, fill=color)
        y += size + line_gap
    return y


def _draw_metric(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], label: str, value: str, color: str) -> None:
    draw.rounded_rectangle(box, radius=18, fill=PANEL, outline=BORDER, width=1)
    x1, y1, _x2, _y2 = box
    _draw_text(draw, (x1 + 22, y1 + 18), label.upper(), 20, MUTED, bold=True)
    _draw_text(draw, (x1 + 22, y1 + 52), value, 26, color, bold=True)


def _score_bar(score: float) -> str:
    if score >= 80:
        return "Premium Setup"
    if score >= 70:
        return "Strong Watch"
    if score >= 55:
        return "Wait for Setup"
    if score >= 40:
        return "Neutral"
    return "High Risk"


def _recent_change(history: pd.DataFrame, days: int) -> float | None:
    close = history["Close"].dropna() if "Close" in history else pd.Series(dtype=float)
    if len(close) <= days or not close.iloc[-days - 1]:
        return None
    return float((close.iloc[-1] / close.iloc[-days - 1] - 1) * 100)


def _draw_score_panel(draw: ImageDraw.ImageDraw, analysis: StockAnalysis, history: pd.DataFrame) -> None:
    score = analysis.score
    draw.rounded_rectangle((60, 386, 860, 622), radius=24, fill=PANEL_2, outline=BORDER, width=1)
    _draw_text(draw, (86, 410), "Signal Dashboard", 30, GOLD, bold=True)
    _draw_text(draw, (86, 466), f"{score.total:.1f}", 72, WHITE, bold=True)
    _draw_text(draw, (228, 492), "/100", 28, MUTED, bold=True)
    draw.rounded_rectangle((86, 552, 330, 596), radius=14, fill="#1b2028", outline=GOLD, width=1)
    _draw_text(draw, (108, 562), _score_bar(score.total), 22, GOLD, bold=True)

    change_5d = _recent_change(history, 5)
    change_20d = _recent_change(history, 20)
    change_text_5d = "N/A" if change_5d is None else f"{change_5d:+.1f}%"
    change_text_20d = "N/A" if change_20d is None else f"{change_20d:+.1f}%"

    x = 430
    rows = [
        ("Technical", f"{score.technical:.1f}", WHITE),
        ("Fundamental", f"{score.fundamental:.1f}", WHITE),
        ("News", f"{score.news:.1f}", WHITE),
        ("Risk", f"{score.risk:.1f}", WHITE),
        ("5D / 20D", f"{change_text_5d} / {change_text_20d}", GREEN if (change_20d or 0) >= 0 else RED),
    ]
    y = 426
    for label, value, color in rows:
        _draw_text(draw, (x, y), label, 20, MUTED, bold=True)
        _draw_text(draw, (650, y), value, 22, color, bold=True)
        y += 36


def generate_analysis_card(analysis: StockAnalysis, history: pd.DataFrame) -> BytesIO:
    image = Image.new("RGB", (CARD_W, CARD_H), BG)
    draw = ImageDraw.Draw(image)
    quote = analysis.quote
    tech = analysis.technical
    label, label_color = _score_label(analysis.score.total)

    draw.rounded_rectangle((36, 36, CARD_W - 36, CARD_H - 36), radius=34, fill=BG, outline="#2b3442", width=2)
    draw.rounded_rectangle((60, 60, CARD_W - 60, 218), radius=26, fill=PANEL, outline=BORDER, width=1)

    _draw_text(draw, (86, 82), analysis.symbol, 58, GOLD, bold=True)
    _draw_wrapped(draw, (86, 148), quote.name, 42, 23, MUTED, max_lines=1)
    draw.rounded_rectangle((610, 86, 800, 138), radius=16, fill="#18251f", outline=label_color, width=2)
    _draw_text(draw, (632, 100), label, 21, label_color, bold=True)
    _draw_text(draw, (610, 154), f"{analysis.score.total:.1f}/100", 36, WHITE, bold=True)

    _draw_metric(draw, (60, 244, 316, 350), "Close", _money(quote.price, quote.currency), WHITE)
    _draw_metric(draw, (332, 244, 588, 350), "Support", _money(tech.support, quote.currency), GREEN)
    _draw_metric(draw, (604, 244, 860, 350), "Resistance", _money(tech.resistance, quote.currency), RED)

    _draw_score_panel(draw, analysis, history)

    draw.rounded_rectangle((60, 650, 860, 934), radius=24, fill=PANEL, outline=BORDER, width=1)
    _draw_text(draw, (86, 674), "Technical Status", 30, GOLD, bold=True)
    y = 726
    for name, status_color, note in _technical_statuses(analysis, history):
        status_text, color = _status(status_color)
        draw.rounded_rectangle((86, y, 814, y + 36), radius=12, fill="#0f141b", outline="#27303b", width=1)
        draw.ellipse((108, y + 9, 126, y + 27), fill=color)
        _draw_text(draw, (146, y + 6), name, 21, WHITE, bold=True)
        _draw_text(draw, (330, y + 6), status_text, 19, color, bold=True)
        _draw_text(draw, (470, y + 6), note, 18, MUTED)
        y += 40

    draw.rounded_rectangle((60, 964, 860, 1318), radius=24, fill=PANEL, outline=BORDER, width=1)
    _draw_text(draw, (86, 988), "Bottom Line Analysis", 30, GOLD, bold=True)
    summary_items = [*analysis.score.reasons[:3], *analysis.score.warnings[:3]]
    if not summary_items:
        summary_items = [analysis.recommendation]
    summary = " • ".join(summary_items)
    y = _draw_wrapped(draw, (86, 1038), summary, 66, 22, WHITE, line_gap=9, max_lines=6)
    y += 12
    _draw_text(draw, (86, y), f"Trend: {tech.trend}", 22, MUTED, bold=True)
    _draw_text(draw, (86, y + 34), f"Quarter: {quote.latest_quarter_date or 'N/A'} | Revenue {_compact(quote.latest_quarter_revenue, quote.currency)} | Net {_compact(quote.latest_quarter_net_income, quote.currency)}", 18, MUTED)
    _draw_text(draw, (86, 1340), "StockNoti | Educational use only", 18, "#6f7c8d")

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return buffer
