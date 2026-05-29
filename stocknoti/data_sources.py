from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import requests
import yfinance as yf

from stocknoti.models import NewsItem, StockQuote


POSITIVE_WORDS = {
    "beat",
    "beats",
    "growth",
    "upgrade",
    "surge",
    "record",
    "profit",
    "strong",
    "bullish",
    "buy",
    "outperform",
    "raises",
}
NEGATIVE_WORDS = {
    "miss",
    "misses",
    "downgrade",
    "fall",
    "falls",
    "drop",
    "lawsuit",
    "weak",
    "bearish",
    "sell",
    "cuts",
    "loss",
    "debt",
}


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _latest_quarter_value(financials, row_names: tuple[str, ...]) -> tuple[str | None, float | None]:
    if financials is None or financials.empty:
        return None, None

    for row_name in row_names:
        if row_name not in financials.index:
            continue
        series = financials.loc[row_name].dropna()
        if series.empty:
            return None, None
        quarter = series.index[0]
        quarter_label = quarter.strftime("%Y-%m-%d") if hasattr(quarter, "strftime") else str(quarter)
        return quarter_label, _float_or_none(series.iloc[0])
    return None, None


def _sentiment_from_title(title: str) -> float:
    words = {word.strip(".,:;!?()[]{}'\"").lower() for word in title.split()}
    positive = len(words & POSITIVE_WORDS)
    negative = len(words & NEGATIVE_WORDS)
    if positive == negative:
        return 0
    return max(-1, min(1, (positive - negative) / max(positive + negative, 1)))


class MarketDataClient:
    def __init__(self, finnhub_api_key: str | None = None, alpha_vantage_api_key: str | None = None) -> None:
        self.finnhub_api_key = finnhub_api_key
        self.alpha_vantage_api_key = alpha_vantage_api_key
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "StockNoti/0.1"})

    def get_history(self, symbol: str, lookback_days: int):
        ticker = yf.Ticker(symbol)
        return ticker.history(period=f"{lookback_days}d", interval="1d", auto_adjust=False)

    def get_quote(self, symbol: str) -> StockQuote:
        ticker = yf.Ticker(symbol)
        info = ticker.get_info()
        price = _float_or_none(info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")) or 0
        try:
            quarterly_financials = ticker.quarterly_financials
        except Exception:
            quarterly_financials = None
        revenue_quarter, revenue = _latest_quarter_value(quarterly_financials, ("Total Revenue", "Operating Revenue"))
        income_quarter, net_income = _latest_quarter_value(quarterly_financials, ("Net Income", "Net Income Common Stockholders"))

        return StockQuote(
            symbol=symbol.upper(),
            name=str(info.get("shortName") or info.get("longName") or symbol.upper()),
            currency=str(info.get("currency") or ""),
            price=price,
            previous_close=_float_or_none(info.get("previousClose")),
            market_cap=_float_or_none(info.get("marketCap")),
            trailing_pe=_float_or_none(info.get("trailingPE")),
            forward_pe=_float_or_none(info.get("forwardPE")),
            roe=_float_or_none(info.get("returnOnEquity")),
            profit_margin=_float_or_none(info.get("profitMargins")),
            revenue_growth=_float_or_none(info.get("revenueGrowth")),
            earnings_growth=_float_or_none(info.get("earningsGrowth")),
            debt_to_equity=_float_or_none(info.get("debtToEquity")),
            beta=_float_or_none(info.get("beta")),
            sector=info.get("sector"),
            latest_quarter_date=revenue_quarter or income_quarter,
            latest_quarter_revenue=revenue,
            latest_quarter_net_income=net_income,
        )

    def get_news(self, symbol: str, limit: int = 6) -> list[NewsItem]:
        news = []
        news.extend(self._alpha_vantage_news(symbol, limit=limit))
        news.extend(self._finnhub_news(symbol, limit=limit))
        news.extend(self._yfinance_news(symbol, limit=limit))

        deduped: list[NewsItem] = []
        seen_titles: set[str] = set()
        for item in news:
            title_key = item.title.strip().lower()
            if not title_key or title_key in seen_titles:
                continue
            seen_titles.add(title_key)
            deduped.append(item)
            if len(deduped) >= limit:
                break
        return deduped

    def _alpha_vantage_news(self, symbol: str, limit: int) -> list[NewsItem]:
        if not self.alpha_vantage_api_key:
            return []

        try:
            response = self.session.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "NEWS_SENTIMENT",
                    "tickers": symbol,
                    "apikey": self.alpha_vantage_api_key,
                    "limit": limit,
                },
                timeout=12,
            )
            response.raise_for_status()
            feed = response.json().get("feed", [])
        except requests.RequestException:
            return []

        items = []
        for row in feed[:limit]:
            published_at = None
            raw_time = row.get("time_published")
            if raw_time:
                try:
                    published_at = datetime.strptime(raw_time, "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
                except ValueError:
                    published_at = None
            items.append(
                NewsItem(
                    title=str(row.get("title") or ""),
                    source=str(row.get("source") or "Alpha Vantage"),
                    url=row.get("url"),
                    published_at=published_at,
                    sentiment=_float_or_none(row.get("overall_sentiment_score")),
                    summary=row.get("summary"),
                )
            )
        return items

    def _finnhub_news(self, symbol: str, limit: int) -> list[NewsItem]:
        if not self.finnhub_api_key:
            return []

        today = datetime.now(UTC).date()
        start = today - timedelta(days=14)
        try:
            response = self.session.get(
                "https://finnhub.io/api/v1/company-news",
                params={"symbol": symbol, "from": start.isoformat(), "to": today.isoformat(), "token": self.finnhub_api_key},
                timeout=12,
            )
            response.raise_for_status()
            rows = response.json()
        except requests.RequestException:
            return []

        items = []
        for row in rows[:limit]:
            published_at = None
            if row.get("datetime"):
                published_at = datetime.fromtimestamp(row["datetime"], tz=UTC)
            title = str(row.get("headline") or "")
            items.append(
                NewsItem(
                    title=title,
                    source=str(row.get("source") or "Finnhub"),
                    url=row.get("url"),
                    published_at=published_at,
                    sentiment=_sentiment_from_title(title),
                    summary=row.get("summary"),
                )
            )
        return items

    def _yfinance_news(self, symbol: str, limit: int) -> list[NewsItem]:
        try:
            rows = yf.Ticker(symbol).news or []
        except Exception:
            return []

        items = []
        for row in rows[:limit]:
            content = row.get("content", row)
            title = str(content.get("title") or row.get("title") or "")
            provider = content.get("provider") or row.get("publisher") or {}
            provider_name = provider.get("displayName") if isinstance(provider, dict) else provider
            raw_time = content.get("pubDate") or row.get("providerPublishTime")
            published_at = None
            if isinstance(raw_time, int | float):
                published_at = datetime.fromtimestamp(raw_time, tz=UTC)
            elif isinstance(raw_time, str):
                try:
                    published_at = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                except ValueError:
                    published_at = None

            url = content.get("canonicalUrl") or content.get("clickThroughUrl") or row.get("link")
            if isinstance(url, dict):
                url = url.get("url")

            items.append(
                NewsItem(
                    title=title,
                    source=str(provider_name or "Yahoo Finance"),
                    url=url,
                    published_at=published_at,
                    sentiment=_sentiment_from_title(title),
                    summary=content.get("summary"),
                )
            )
        return items
