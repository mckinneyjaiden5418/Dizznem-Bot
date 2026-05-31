"""AI bot commands."""

import asyncio

from bot.bot import DizznemBot
from discord import Color, Embed
from discord.ext import commands
from log import logger
from utils.misc.ai import get_ai_summary

SUMMARY_CAP: int = 50
CHAR_BUDGET: int = 30_000
DISCORD_EMBED_DESC_LIMIT: int = 4096
MIN_SUMMARY_MESSAGES: int = 10


def _clamp_count(count: int) -> tuple[int, str | None]:
    """Clamp a requested message count into [MIN_SUMMARY_MESSAGES, SUMMARY_CAP].

    Args:
        count (int): The raw count argument supplied by the user.

    Returns:
        tuple[int, str | None]: The clamped count, and a notification string
        if clamping occurred (None otherwise).
    """
    if MIN_SUMMARY_MESSAGES <= count <= SUMMARY_CAP:
        return count, None
    clamped: int = max(MIN_SUMMARY_MESSAGES, min(count, SUMMARY_CAP))
    note: str = (
        f"Count **{count}** is out of range ({MIN_SUMMARY_MESSAGES}\u2013{SUMMARY_CAP}). "
        f"Using **{clamped}** instead."
    )
    return clamped, note


def _build_message_block(messages: list) -> tuple[str, bool]:
    """Flatten a list of messages into a plain-text block within the char budget.

    Args:
        messages (list): discord.Message objects, newest-first.

    Returns:
        tuple[str, bool]: The formatted block and a flag indicating whether
        any lines were dropped due to the character budget.
    """
    chrono: list = list(reversed(messages))
    lines: list[str] = [
        f"{msg.author.display_name}: {msg.clean_content}"
        for msg in chrono
        if msg.clean_content.strip()
    ]

    truncated: bool = False
    while lines and len("\n".join(lines)) > CHAR_BUDGET:
        lines.pop(0)
        truncated = True

    return "\n".join(lines), truncated


class AI(commands.Cog):
    """AI bot commands."""

    def __init__(self, bot: DizznemBot) -> None:
        """Initiate AI.

        Args:
            bot (DizznemBot): Dizznem Bot.
        """
        self.bot: DizznemBot = bot

    @commands.hybrid_command(
        name="summarize",
        description=f"Summarize the last X messages in this channel (max {SUMMARY_CAP}).",
    )
    @commands.cooldown(rate=1, per=60, type=commands.BucketType.user)
    async def summarize(self, ctx: commands.Context, count: int = SUMMARY_CAP) -> None:
        """Summarize recent messages in this channel using AI.

        Args:
            ctx (commands.Context): Context.
            count (int): Number of messages to summarize (10-50, default 50).
        """
        clamp_note: str | None
        count, clamp_note = _clamp_count(count)

        await ctx.defer()

        logger.debug(f"Fetching messages for summarize in channel {ctx.channel.id}.")
        messages: list = []
        async for msg in ctx.channel.history(limit=count * 3):
            if msg.author.bot or not msg.clean_content.strip():
                continue
            messages.append(msg)
            if len(messages) >= count:
                break

        if not messages:
            embed: Embed = Embed(
                title="📭 Nothing to summarize",
                color=Color.red(),
                description="No non-bot messages were found in this channel.",
            )
            await ctx.send(embed=embed)
            return

        actual_count: int = len(messages)
        message_block: str
        truncated: bool
        message_block, truncated = _build_message_block(messages)

        if not message_block.strip():
            embed: Embed = Embed(
                title="📭 Nothing to summarize",
                color=Color.red(),
                description="All fetched messages were empty after filtering.",
            )
            await ctx.send(embed=embed)
            return

        logger.debug(f"Sending {len(message_block)} chars to DeepSeek for summarize.")
        summary: str = await asyncio.to_thread(
            get_ai_summary,
            message_block,
            self.bot.ai_api_key,
        )

        if len(summary) > DISCORD_EMBED_DESC_LIMIT:
            summary = summary[: DISCORD_EMBED_DESC_LIMIT - 3] + "..."

        footer_parts: list[str] = []
        if clamp_note:
            footer_parts.append(clamp_note)
        if truncated:
            footer_parts.append("Note: some older messages were trimmed due to length.")
        footer: str = " • ".join(footer_parts)

        embed: Embed = Embed(
            title=f"📋 Channel Summary — last {actual_count} message(s)",
            color=Color.blurple(),
            description=summary,
        )
        if footer:
            embed.set_footer(text=footer)

        await ctx.send(embed=embed)


async def setup(bot: DizznemBot) -> None:
    """Setup for AI.

    Args:
        bot (DizznemBot): Dizznem Bot.
    """
    await bot.add_cog(AI(bot))
