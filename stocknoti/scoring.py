from __future__ import annotations

from datetime import UTC, datetime

from stocknoti.data_sources import MarketDataClient
from stocknoti.indicators import build_technical_snapshot
from stocknoti.models import NewsItem, ScoreBreakdown, StockAnalysis, StockQuote, TechnicalSnapshot


def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def _fmt_percent(value: float | None) -> str:
    if value is None:
        return "ไม่ทราบ"
    return f"{value * 100:.1f}%"


def score_technical(tech: TechnicalSnapshot) -> tuple[float, list[str], list[str]]:
    score = 50.0
    reasons: list[str] = []
    warnings: list[str] = []

    if tech.sma20 and tech.sma50:
        if tech.close > tech.sma20 > tech.sma50:
            score += 20
            reasons.append("ราคาอยู่เหนือ SMA20 และ SMA50 แปลว่าโมเมนตัมระยะสั้นยังดี")
        elif tech.close < tech.sma20 < tech.sma50:
            score -= 20
            warnings.append("ราคาหลุด SMA20/SMA50 โมเมนตัมยังอ่อน")

    if tech.sma200:
        if tech.close > tech.sma200:
            score += 8
            reasons.append("ราคายืนเหนือ SMA200 ภาพใหญ่ยังไม่เสีย")
        else:
            score -= 10
            warnings.append("ราคายังอยู่ใต้ SMA200 ต้องระวังเทรนด์ใหญ่")

    if tech.rsi14 is not None:
        if 45 <= tech.rsi14 <= 68:
            score += 8
            reasons.append(f"RSI {tech.rsi14:.1f} อยู่ในโซนมีแรงแต่ยังไม่ร้อนเกินไป")
        elif tech.rsi14 > 75:
            score -= 8
            warnings.append(f"RSI {tech.rsi14:.1f} ค่อนข้างร้อน อาจมีแรงขายทำกำไร")
        elif tech.rsi14 < 35:
            score -= 5
            warnings.append(f"RSI {tech.rsi14:.1f} ยังอ่อน ต้องรอสัญญาณกลับตัว")

    if tech.macd is not None and tech.macd_signal is not None:
        if tech.macd > tech.macd_signal:
            score += 7
            reasons.append("MACD อยู่เหนือเส้นสัญญาณ")
        else:
            score -= 7
            warnings.append("MACD ยังต่ำกว่าเส้นสัญญาณ")

    if tech.volume_ratio is not None:
        if tech.volume_ratio >= 1.2:
            score += 5
            reasons.append(f"วอลุ่มมากกว่าค่าเฉลี่ยประมาณ {tech.volume_ratio:.1f} เท่า")
        elif tech.volume_ratio < 0.6:
            score -= 4
            warnings.append("วอลุ่มเบากว่าปกติ สัญญาณอาจยังไม่น่าเชื่อถือ")

    return _clamp(score), reasons, warnings


def score_fundamental(quote: StockQuote) -> tuple[float, list[str], list[str]]:
    score = 50.0
    reasons: list[str] = []
    warnings: list[str] = []

    if quote.revenue_growth is not None:
        if quote.revenue_growth > 0.08:
            score += 15
            reasons.append(f"รายได้เติบโต {_fmt_percent(quote.revenue_growth)}")
        elif quote.revenue_growth < 0:
            score -= 12
            warnings.append(f"รายได้หดตัว {_fmt_percent(quote.revenue_growth)}")

    if quote.earnings_growth is not None:
        if quote.earnings_growth > 0.08:
            score += 15
            reasons.append(f"กำไรเติบโต {_fmt_percent(quote.earnings_growth)}")
        elif quote.earnings_growth < 0:
            score -= 15
            warnings.append(f"กำไรหดตัว {_fmt_percent(quote.earnings_growth)}")

    if quote.profit_margin is not None:
        if quote.profit_margin > 0.15:
            score += 10
            reasons.append(f"อัตรากำไรดีที่ {_fmt_percent(quote.profit_margin)}")
        elif quote.profit_margin < 0:
            score -= 15
            warnings.append("บริษัทยังขาดทุนสุทธิ")

    if quote.latest_quarter_net_income is not None:
        if quote.latest_quarter_net_income > 0:
            reasons.append("งบไตรมาสล่าสุดยังมีกำไรสุทธิ")
        else:
            score -= 8
            warnings.append("งบไตรมาสล่าสุดขาดทุนสุทธิ")

    if quote.roe is not None:
        if quote.roe > 0.12:
            score += 8
            reasons.append(f"ROE แข็งแรง {_fmt_percent(quote.roe)}")
        elif quote.roe < 0:
            score -= 10
            warnings.append("ROE ติดลบ")

    pe = quote.forward_pe or quote.trailing_pe
    if pe is not None:
        if 0 < pe < 25:
            score += 6
            reasons.append(f"ค่า P/E ประมาณ {pe:.1f} ยังไม่แพงมากเมื่อเทียบเชิงทั่วไป")
        elif pe >= 45:
            score -= 8
            warnings.append(f"P/E สูงประมาณ {pe:.1f} ต้องระวังความคาดหวังสูง")

    if quote.debt_to_equity is not None:
        if quote.debt_to_equity < 80:
            score += 5
            reasons.append("หนี้ต่อทุนไม่สูงมาก")
        elif quote.debt_to_equity > 200:
            score -= 10
            warnings.append("หนี้ต่อทุนสูง ควรดูงบละเอียดเพิ่ม")

    return _clamp(score), reasons, warnings


def score_news(news: list[NewsItem]) -> tuple[float, list[str], list[str]]:
    if not news:
        return 50, [], ["ยังไม่มีข่าวล่าสุดจากแหล่งข้อมูลที่ตั้งค่าไว้"]

    values = [item.sentiment for item in news if item.sentiment is not None]
    if not values:
        return 50, [], ["ข่าวมีอยู่ แต่ยังประเมิน sentiment ไม่ได้"]

    avg = sum(values) / len(values)
    score = _clamp(50 + avg * 35)
    reasons: list[str] = []
    warnings: list[str] = []

    if avg > 0.12:
        reasons.append("โทนข่าวล่าสุดออกไปทางบวก")
    elif avg < -0.12:
        warnings.append("โทนข่าวล่าสุดออกไปทางลบ")
    else:
        reasons.append("โทนข่าวล่าสุดค่อนข้างกลาง")

    return score, reasons, warnings


def score_risk(quote: StockQuote, tech: TechnicalSnapshot) -> tuple[float, list[str], list[str]]:
    score = 75.0
    reasons: list[str] = []
    warnings: list[str] = []

    if quote.beta is not None:
        if quote.beta <= 1.2:
            reasons.append(f"Beta {quote.beta:.2f} ความผันผวนไม่สูงมาก")
        elif quote.beta > 1.8:
            score -= 18
            warnings.append(f"Beta {quote.beta:.2f} ผันผวนสูง")

    if tech.support and tech.close:
        downside = (tech.close - tech.support) / tech.close
        if downside <= 0.06:
            reasons.append("ราคาอยู่ใกล้แนวรับ ทำให้วางจุดตัดขาดทุนได้ชัดขึ้น")
        elif downside > 0.18:
            score -= 10
            warnings.append("ราคาอยู่ห่างแนวรับมาก ความเสี่ยงต่อจุดตัดขาดทุนกว้าง")

    if tech.resistance and tech.close:
        upside = (tech.resistance - tech.close) / tech.close
        if upside >= 0.08:
            reasons.append("ยังมีระยะถึงแนวต้านพอสมควร")
        elif upside < 0.03:
            score -= 8
            warnings.append("ราคาใกล้แนวต้านมาก อัตราส่วนกำไรต่อความเสี่ยงอาจไม่คุ้ม")

    return _clamp(score), reasons, warnings


def build_score(quote: StockQuote, tech: TechnicalSnapshot, news: list[NewsItem]) -> ScoreBreakdown:
    technical, tech_reasons, tech_warnings = score_technical(tech)
    fundamental, fundamental_reasons, fundamental_warnings = score_fundamental(quote)
    news_score, news_reasons, news_warnings = score_news(news)
    risk, risk_reasons, risk_warnings = score_risk(quote, tech)

    total = technical * 0.38 + fundamental * 0.32 + news_score * 0.18 + risk * 0.12
    reasons = [*tech_reasons, *fundamental_reasons, *news_reasons, *risk_reasons]
    warnings = [*tech_warnings, *fundamental_warnings, *news_warnings, *risk_warnings]
    return ScoreBreakdown(
        total=round(_clamp(total), 1),
        technical=round(technical, 1),
        fundamental=round(fundamental, 1),
        news=round(news_score, 1),
        risk=round(risk, 1),
        reasons=reasons[:8],
        warnings=warnings[:8],
    )


def analyze_symbol(client: MarketDataClient, symbol: str, lookback_days: int = 365) -> StockAnalysis:
    history = client.get_history(symbol, lookback_days=lookback_days)
    quote = client.get_quote(symbol)
    technical = build_technical_snapshot(history)
    news = client.get_news(symbol)
    score = build_score(quote, technical, news)
    return StockAnalysis(
        symbol=symbol.upper(),
        quote=quote,
        technical=technical,
        news=news,
        score=score,
        generated_at=datetime.now(UTC),
    )


def rank_watchlist(client: MarketDataClient, symbols: list[str], lookback_days: int = 365) -> list[StockAnalysis]:
    analyses = []
    for symbol in symbols:
        try:
            analyses.append(analyze_symbol(client, symbol, lookback_days=lookback_days))
        except Exception as exc:
            print(f"[WARN] ข้าม {symbol}: {exc}")
    return sorted(analyses, key=lambda item: item.score.total, reverse=True)
