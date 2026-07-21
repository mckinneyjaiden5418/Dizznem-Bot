"""Miscellaneous bot commands."""

import asyncio
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bot.bot import DizznemBot
from discord import Color, Embed, Member, TextChannel, User
from discord.ext import commands, tasks
from log import logger
from utils.misc.count import ensure_count_db, increment_count
from utils.misc.help import get_help_text
from utils.misc.inspiration import ensure_inspiration_db, get_random_quote

INSPIRATION_DB_PATH: Path = Path("data/inspiration.db")
COUNT_DB_PATH: Path = Path("data/count.db")

DAILY_INSPIRATION_HOUR_UTC: int = (
    0  # 7 PM EST (might be 8 PM during daylight saving time)
)
DAILY_INSPIRATION_MINUTE_UTC: int = 0
SUS_USER_ID: int = (
    514079395636576259  # Replace with the actual user ID you want to always be 100% sus
)


class Misc(commands.Cog):
    """Miscellaneous bot commands."""

    def __init__(self, bot: DizznemBot) -> None:
        """Initiate Misc.

        Args:
            bot (commands.Bot): Dizznem Bot.
        """
        self.bot: DizznemBot = bot
        ensure_inspiration_db(INSPIRATION_DB_PATH)
        ensure_count_db(COUNT_DB_PATH)
        self.daily_inspiration.start()

    def cog_unload(self) -> None:
        """Stop background task on unload."""
        self.daily_inspiration.cancel()

    @tasks.loop(hours=24)
    async def daily_inspiration(self) -> None:
        """Send a daily inspirational quote to the inspiration channel."""
        channel: TextChannel | None = self.bot.get_channel(self.bot.inspiration_channel_id)  # type: ignore[assignment]
        if channel is None:
            logger.error("Inspiration channel not found.")
            return

        quote: str | None = get_random_quote(INSPIRATION_DB_PATH)
        if quote is None:
            logger.error("No inspirational quotes found in the database.")
            return

        embed: Embed = Embed(
            title="✨ Daily Inspiration",
            color=Color.gold(),
            description=quote,
        )
        await channel.send(embed=embed)
        logger.info("Daily inspiration sent.")

    @daily_inspiration.before_loop
    async def before_daily_inspiration(self) -> None:
        """Wait until bot is ready, then sleep until 7 PM EST."""
        await self.bot.wait_until_ready()

        now: datetime = datetime.now(timezone.utc)
        target: datetime = now.replace(
            hour=DAILY_INSPIRATION_HOUR_UTC,
            minute=DAILY_INSPIRATION_MINUTE_UTC,
            second=0,
            microsecond=0,
        )

        # If 7 PM EST has already passed today, schedule for tomorrow.
        if now >= target:
            target += timedelta(days=1)

        wait_seconds: float = (target - now).total_seconds()
        logger.debug(f"Daily inspiration scheduled in {wait_seconds / 3600:.2f} hours.")
        await asyncio.sleep(wait_seconds)

    @commands.hybrid_command(name="help", description="Get all Dizznem Bot commands")
    async def help(self, ctx: commands.Context) -> None:
        """Help command.

        Args:
            ctx (commands.Context): Context.
        """
        help_text: str = get_help_text(ctx.bot)
        embed: Embed = Embed(
            title="Commands",
            color=Color.og_blurple(),
            description=help_text,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="inspiration",
        description="Get an inspirational quote",
    )
    async def inspiration(self, ctx: commands.Context) -> None:
        """Inspiration command.

        Args:
            ctx (commands.Context): Context.
        """
        quote: str | None = get_random_quote(INSPIRATION_DB_PATH)
        if quote is None:
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description="No inspirational quotes found in the database.",
                ),
                ephemeral=True,
            )
            return

        embed: Embed = Embed(
            title="✨ Inspiration",
            color=Color.gold(),
            description=quote,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="count", description="Increase count by 1")
    async def count(self, ctx: commands.Context) -> None:
        """Count command.

        Args:
            ctx (commands.Context): Context.
        """
        new_count: int = increment_count(COUNT_DB_PATH)
        embed: Embed = Embed(
            title="🔢 Count",
            color=Color.og_blurple(),
            description=f"The count is now **{new_count}**.",
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="sus", description="How sus is someone? 🌈")
    async def sus(self, ctx: commands.Context, user: Member | User | None = None) -> None:
        """Sus command.

        Args:
            ctx (commands.Context): Context.
            user (discord.Member | discord.User | None): The user to check.
        """
        user = user or ctx.author
        percentage: int = (
            100 if user.id == SUS_USER_ID else random.randint(0, 100)  # noqa: S311
        )

        MAX_SUS_THRESHOLD: int = 100
        VERY_SUS_THRESHOLD: int = 75
        KINDA_SUS_THRESHOLD: int = 50
        NOT_THAT_SUS_THRESHOLD: int = 25
        if percentage == MAX_SUS_THRESHOLD:
            color: Color = Color.red()
            verdict: str = "MAXIMUM SUS 🚨"
            bar: str = "🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥"
        elif percentage >= VERY_SUS_THRESHOLD:
            color: Color = Color.orange()
            verdict: str = "Very sus 👀"
            bar: str = "🟧" * (percentage // 10) + "⬛" * (10 - percentage // 10)
        elif percentage >= KINDA_SUS_THRESHOLD:
            color: Color = Color.yellow()
            verdict: str = "Kinda sus 🤔"
            bar: str = "🟨" * (percentage // 10) + "⬛" * (10 - percentage // 10)
        elif percentage >= NOT_THAT_SUS_THRESHOLD:
            color: Color = Color.green()
            verdict: str = "Not that sus 😌"
            bar: str = "🟩" * (percentage // 10) + "⬛" * (10 - percentage // 10)
        else:
            color: Color = Color.blue()
            verdict: str = "Completely innocent 😇"
            bar: str = "🟦" * (percentage // 10) + "⬛" * (10 - percentage // 10)

        embed: Embed = Embed(
            title="🌈 Sus Detector",
            color=color,
            description=(
                f"**{user.display_name}** is **{percentage}% sus**\n\n"
                f"{bar}\n\n"
                f"*Verdict: {verdict}*"
            ),
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="Among Us Investigation Bureau • Results may vary 🔍")
        await ctx.send(embed=embed)


async def setup(bot: DizznemBot) -> None:
    """Setup for misc.

    Args:
        bot (commands.Bot): Dizznem Bot
    """
    await bot.add_cog(Misc(bot))
