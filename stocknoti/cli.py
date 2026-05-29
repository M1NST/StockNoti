from __future__ import annotations

import argparse
import json

from tabulate import tabulate

from stocknoti.config import load_config
from stocknoti.data_sources import MarketDataClient
from stocknoti.discord import make_daily_payload, make_single_payload, send_discord
from stocknoti.scoring import analyze_symbol, rank_watchlist


def _client_from_config(config) -> MarketDataClient:
    return MarketDataClient(
        finnhub_api_key=config.finnhub_api_key,
        alpha_vantage_api_key=config.alpha_vantage_api_key,
    )


def _print_summary(analyses) -> None:
    rows = []
    for item in analyses:
        rows.append(
            [
                item.symbol,
                item.recommendation,
                item.score.total,
                item.quote.price,
                item.technical.trend,
                item.technical.support,
                item.technical.resistance,
            ]
        )
    print(
        tabulate(
            rows,
            headers=["Symbol", "คำแนะนำ", "Score", "Price", "Trend", "Support", "Resistance"],
            tablefmt="github",
            floatfmt=".2f",
        )
    )


def daily(args) -> None:
    config = load_config(args.config)
    client = _client_from_config(config)
    analyses = rank_watchlist(client, config.watchlist, lookback_days=config.lookback_days)
    top_n = args.top or config.top_n
    best = analyses[:top_n]
    avoid = list(reversed(analyses[-top_n:]))

    print("\nหุ้นที่น่าสนใจ")
    _print_summary(best)
    print("\nหุ้นที่ควรเลี่ยง/รอก่อน")
    _print_summary(avoid)

    payload = make_daily_payload(best, avoid)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.send_discord:
        if not config.discord_webhook_url:
            raise SystemExit("กรุณาตั้งค่า DISCORD_WEBHOOK_URL ในไฟล์ .env ก่อนส่งเข้า Discord")
        send_discord(config.discord_webhook_url, payload)
        print("ส่งรายงานเข้า Discord แล้ว")


def analyze(args) -> None:
    config = load_config(args.config)
    client = _client_from_config(config)
    symbol = args.symbol.upper()
    analysis = analyze_symbol(client, symbol, lookback_days=args.lookback_days or config.lookback_days)

    _print_summary([analysis])
    print("\nเหตุผลที่น่าสนใจ")
    for reason in analysis.score.reasons:
        print(f"- {reason}")
    print("\nจุดที่ต้องระวัง")
    for warning in analysis.score.warnings:
        print(f"- {warning}")
    print("\nข่าวล่าสุด")
    for item in analysis.news[:5]:
        print(f"- {item.title} ({item.source}) {item.url or ''}")

    payload = make_single_payload(analysis)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.send_discord:
        if not config.discord_webhook_url:
            raise SystemExit("กรุณาตั้งค่า DISCORD_WEBHOOK_URL ในไฟล์ .env ก่อนส่งเข้า Discord")
        send_discord(config.discord_webhook_url, payload)
        print("ส่งบทวิเคราะห์เข้า Discord แล้ว")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="StockNoti - ระบบแจ้งเตือนและวิเคราะห์หุ้นรายวัน")
    parser.add_argument("--config", help="path ของไฟล์ watchlist.yaml")
    subparsers = parser.add_subparsers(dest="command", required=True)

    daily_parser = subparsers.add_parser("daily", help="จัดอันดับหุ้นที่น่าซื้อและไม่น่าซื้อจาก watchlist")
    daily_parser.add_argument("--top", type=int, help="จำนวนอันดับที่ต้องการแสดง")
    daily_parser.add_argument("--json", action="store_true", help="แสดง Discord payload เป็น JSON")
    daily_parser.add_argument("--send-discord", action="store_true", help="ส่งผลลัพธ์เข้า Discord webhook")
    daily_parser.set_defaults(func=daily)

    analyze_parser = subparsers.add_parser("analyze", help="วิเคราะห์หุ้นรายตัว")
    analyze_parser.add_argument("symbol", help="ชื่อหุ้น เช่น AAPL, NVDA, ADVANC.BK")
    analyze_parser.add_argument("--lookback-days", type=int, help="จำนวนวันย้อนหลังสำหรับกราฟ")
    analyze_parser.add_argument("--json", action="store_true", help="แสดง Discord payload เป็น JSON")
    analyze_parser.add_argument("--send-discord", action="store_true", help="ส่งผลลัพธ์เข้า Discord webhook")
    analyze_parser.set_defaults(func=analyze)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
