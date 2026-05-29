from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    watchlist: list[str]
    currency: str = "USD"
    lookback_days: int = 365
    top_n: int = 5
    discord_webhook_url: str | None = None
    finnhub_api_key: str | None = None
    alpha_vantage_api_key: str | None = None


def load_config(config_path: str | Path | None = None) -> AppConfig:
    load_dotenv()

    raw_path = config_path or os.getenv("STOCKNOTI_CONFIG") or "config/watchlist.yaml"
    path = Path(raw_path)
    data: dict = {}

    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
    else:
        example = Path("config/watchlist.example.yaml")
        if example.exists():
            with example.open("r", encoding="utf-8") as file:
                data = yaml.safe_load(file) or {}

    watchlist = [str(symbol).strip().upper() for symbol in data.get("watchlist", []) if str(symbol).strip()]
    if not watchlist:
        watchlist = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"]

    return AppConfig(
        watchlist=watchlist,
        currency=str(data.get("currency", "USD")),
        lookback_days=int(data.get("lookback_days", 365)),
        top_n=int(data.get("top_n", 5)),
        discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL") or None,
        finnhub_api_key=os.getenv("FINNHUB_API_KEY") or None,
        alpha_vantage_api_key=os.getenv("ALPHA_VANTAGE_API_KEY") or None,
    )
