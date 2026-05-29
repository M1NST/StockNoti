from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class StockQuote:
    symbol: str
    name: str
    currency: str
    price: float
    previous_close: float | None
    market_cap: float | None
    trailing_pe: float | None
    forward_pe: float | None
    roe: float | None
    profit_margin: float | None
    revenue_growth: float | None
    earnings_growth: float | None
    debt_to_equity: float | None
    beta: float | None
    sector: str | None
    latest_quarter_date: str | None = None
    latest_quarter_revenue: float | None = None
    latest_quarter_net_income: float | None = None


@dataclass(frozen=True)
class NewsItem:
    title: str
    source: str
    url: str | None
    published_at: datetime | None
    sentiment: float | None = None
    summary: str | None = None


@dataclass(frozen=True)
class TechnicalSnapshot:
    trend: str
    close: float
    sma20: float | None
    sma50: float | None
    sma200: float | None
    rsi14: float | None
    macd: float | None
    macd_signal: float | None
    support: float | None
    resistance: float | None
    volume_ratio: float | None


@dataclass(frozen=True)
class ScoreBreakdown:
    total: float
    technical: float
    fundamental: float
    news: float
    risk: float
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StockAnalysis:
    symbol: str
    quote: StockQuote
    technical: TechnicalSnapshot
    news: list[NewsItem]
    score: ScoreBreakdown
    generated_at: datetime

    @property
    def recommendation(self) -> str:
        if self.score.total >= 70:
            return "น่าสนใจเข้าซื้อ"
        if self.score.total >= 55:
            return "รอดูจังหวะ"
        if self.score.total >= 40:
            return "ถือ/เฝ้าดู"
        return "หลีกเลี่ยงก่อน"
