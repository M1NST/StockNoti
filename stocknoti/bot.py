from __future__ import annotations

import asyncio
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

from stocknoti.config import load_config
from stocknoti.cards import generate_analysis_card
from stocknoti.data_sources import MarketDataClient
from stocknoti.discord import make_daily_payload, make_single_payload
from stocknoti.scoring import analyze_symbol_with_history, rank_watchlist


def _payload_to_embeds(payload: dict) -> list[discord.Embed]:
    embeds: list[discord.Embed] = []
    for raw in payload.get("embeds", []):
        embed = discord.Embed(
            title=raw.get("title"),
            description=raw.get("description"),
            color=raw.get("color"),
        )
        for field in raw.get("fields", []):
            embed.add_field(
                name=field.get("name", "-"),
                value=field.get("value", "-"),
                inline=bool(field.get("inline", False)),
            )
        footer = raw.get("footer")
        if footer:
            embed.set_footer(text=footer.get("text", ""))
        embeds.append(embed)
    return embeds


def _client_from_config(config) -> MarketDataClient:
    return MarketDataClient(
        finnhub_api_key=config.finnhub_api_key,
        alpha_vantage_api_key=config.alpha_vantage_api_key,
    )


class StockNotiBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.config = load_config()
        self.market_client = _client_from_config(self.config)
        self.guild_id = int(os.getenv("DISCORD_GUILD_ID", "0") or 0)
        self.daily_channel_id = int(os.getenv("DISCORD_DAILY_CHANNEL_ID", "0") or 0)
        self.daily_enabled = os.getenv("STOCKNOTI_DAILY_ENABLED", "false").lower() == "true"
        self.daily_time = os.getenv("STOCKNOTI_DAILY_TIME", "08:30").replace(".", ":")
        self.timezone = ZoneInfo(os.getenv("STOCKNOTI_TIMEZONE", "Asia/Bangkok"))
        self._last_daily_key: str | None = None

    async def setup_hook(self) -> None:
        register_commands(self)
        if self.guild_id:
            guild = discord.Object(id=self.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

        if self.daily_enabled and self.daily_channel_id:
            self.daily_report_loop.start()

    async def on_ready(self) -> None:
        print(f"StockNoti bot logged in as {self.user}")

    async def build_daily_embeds(self, top_n: int | None = None) -> list[discord.Embed]:
        analyses = await asyncio.to_thread(
            rank_watchlist,
            self.market_client,
            self.config.watchlist,
            self.config.lookback_days,
        )
        count = top_n or self.config.top_n
        best = analyses[:count]
        avoid = list(reversed(analyses[-count:]))
        return _payload_to_embeds(make_daily_payload(best, avoid))

    async def build_single_report(self, symbol: str) -> tuple[list[discord.Embed], discord.File]:
        analysis, history = await asyncio.to_thread(
            analyze_symbol_with_history,
            self.market_client,
            symbol.upper(),
            self.config.lookback_days,
        )
        embeds = _payload_to_embeds(make_single_payload(analysis))
        image = await asyncio.to_thread(generate_analysis_card, analysis, history)
        filename = f"{analysis.symbol.lower()}_stocknoti.png"
        if embeds:
            embeds[0].set_image(url=f"attachment://{filename}")
        return embeds, discord.File(image, filename=filename)

    @tasks.loop(minutes=1)
    async def daily_report_loop(self) -> None:
        now = datetime.now(self.timezone)
        if now.strftime("%H:%M") != self.daily_time:
            return

        daily_key = now.strftime("%Y-%m-%d")
        if self._last_daily_key == daily_key:
            return

        channel = self.get_channel(self.daily_channel_id) or await self.fetch_channel(self.daily_channel_id)
        embeds = await self.build_daily_embeds()
        await channel.send(embeds=embeds)
        self._last_daily_key = daily_key


def register_commands(bot: StockNotiBot) -> None:
    @bot.tree.command(name="analyze", description="วิเคราะห์หุ้นรายตัว เช่น AAPL, NVDA, ADVANC.BK")
    @app_commands.describe(symbol="Ticker หุ้นที่ต้องการวิเคราะห์")
    async def analyze(interaction: discord.Interaction, symbol: str) -> None:
        await interaction.response.defer(thinking=True)
        try:
            embeds, file = await bot.build_single_report(symbol)
        except Exception as exc:
            await interaction.followup.send(f"วิเคราะห์ {symbol.upper()} ไม่สำเร็จ: {exc}", ephemeral=True)
            return
        await interaction.followup.send(embeds=embeds, file=file)

    @bot.tree.command(name="daily", description="จัดอันดับหุ้นน่าสนใจและหุ้นที่ควรรอก่อนจาก watchlist")
    @app_commands.describe(top="จำนวนอันดับที่ต้องการดู")
    async def daily(interaction: discord.Interaction, top: app_commands.Range[int, 1, 10] = 5) -> None:
        await interaction.response.defer(thinking=True)
        try:
            embeds = await bot.build_daily_embeds(top_n=top)
        except Exception as exc:
            await interaction.followup.send(f"สร้างรายงานรายวันไม่สำเร็จ: {exc}", ephemeral=True)
            return
        await interaction.followup.send(embeds=embeds)

    @bot.tree.command(name="watchlist", description="ดูรายชื่อหุ้นที่บอทใช้จัดอันดับ")
    async def watchlist(interaction: discord.Interaction) -> None:
        symbols = ", ".join(bot.config.watchlist)
        await interaction.response.send_message(f"Watchlist ตอนนี้: {symbols}", ephemeral=True)

    @bot.tree.command(name="stock_help", description="ดูคำสั่งของ StockNoti")
    async def stock_help(interaction: discord.Interaction) -> None:
        message = (
            "**StockNoti commands**\n"
            "`/analyze symbol:AAPL` วิเคราะห์หุ้นรายตัว\n"
            "`/daily top:5` จัดอันดับหุ้นจาก watchlist\n"
            "`/watchlist` ดูรายชื่อหุ้นที่ติดตาม\n\n"
            "ข้อมูลนี้เป็นเครื่องมือช่วยทำการบ้าน ไม่ใช่คำแนะนำการลงทุนโดยตรง"
        )
        await interaction.response.send_message(message, ephemeral=True)


def main() -> None:
    load_dotenv()
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise SystemExit("กรุณาตั้งค่า DISCORD_BOT_TOKEN ใน .env หรือ environment variable")
    bot = StockNotiBot()
    bot.run(token)


if __name__ == "__main__":
    main()
