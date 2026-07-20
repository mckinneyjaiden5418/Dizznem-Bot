"""AI bot commands."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from bot.bot import DizznemBot
from discord import Color, Embed, Forbidden, HTTPException, Message, TextChannel
from discord.ext import commands, tasks
from log import logger
from utils.misc.ai import get_ai_summary
from utils.misc.auto_summary import (
    MAX_INTERVAL_HOURS,
    MIN_INTERVAL_HOURS,
    clamp_interval_hours,
    disable_auto_summary,
    enable_auto_summary,
    ensure_auto_summary_db,
    get_channel_config,
    get_due_channels,
    update_last_summary,
)
from utils.misc.embeds import extract_message_embed_text

SUMMARY_CAP: int = 100
CHAR_BUDGET: int = 30_000
DISCORD_EMBED_DESC_LIMIT: int = 4096
MIN_SUMMARY_MESSAGES: int = 1

AUTO_SUMMARY_DB_PATH: Path = Path("data/auto_summary.db")
DEFAULT_AUTO_SUMMARY_INTERVAL_HOURS: int = 6
AUTO_SUMMARY_CHECK_MINUTES: int = 15


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

    Embed text (titles, descriptions, fields, footers) is appended to each
    message's line so the AI can read embedded content.

    Args:
        messages (list): discord.Message objects, newest-first.

    Returns:
        tuple[str, bool]: The formatted block and a flag indicating whether
        any lines were dropped due to the character budget.
    """
    chrono: list = list(reversed(messages))
    lines: list[str] = []
    for msg in chrono:
        parts: list[str] = []
        if msg.clean_content.strip():
            parts.append(msg.clean_content.strip())
        embed_text: str = extract_message_embed_text(msg.embeds)
        if embed_text:
            parts.append(f"[embed] {embed_text}")
        if parts:
            lines.append(f"{msg.author.display_name}: " + " ".join(parts))

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
        ensure_auto_summary_db(AUTO_SUMMARY_DB_PATH)
        self._auto_summary_loop.start()

    def cog_unload(self) -> None:
        """Stop background task on unload."""
        self._auto_summary_loop.cancel()

    @tasks.loop(minutes=AUTO_SUMMARY_CHECK_MINUTES)
    async def _auto_summary_loop(self) -> None:
        """Post an AI summary to any channel whose automatic interval has elapsed."""
        due: list[tuple[int, int, str]] = get_due_channels(AUTO_SUMMARY_DB_PATH)
        for channel_id, interval_hours, last_summary_at in due:
            try:
                await self._post_auto_summary(channel_id, interval_hours, last_summary_at)
            except (HTTPException, Forbidden) as e:
                logger.error(f"Auto-summary failed for channel {channel_id}: {e}")
            finally:
                # Always advance the timestamp so a failing channel (e.g. the
                # bot lost access) doesn't get retried every check interval.
                update_last_summary(AUTO_SUMMARY_DB_PATH, channel_id)

    @_auto_summary_loop.before_loop
    async def _before_auto_summary_loop(self) -> None:
        """Wait until bot is ready before starting the loop."""
        await self.bot.wait_until_ready()

    async def _post_auto_summary(
        self,
        channel_id: int,
        interval_hours: int,
        last_summary_at: str,
    ) -> None:
        """Fetch messages posted since the last run and post an AI summary.

        Args:
            channel_id (int): The channel to summarize and post to.
            interval_hours (int): The channel's configured summary interval,
                shown in the posted embed's footer.
            last_summary_at (str): ISO timestamp of the previous automatic
                summary; only messages after this point are considered
                (capped at SUMMARY_CAP messages).
        """
        channel: TextChannel | None = self.bot.get_channel(channel_id)  # type: ignore[assignment]
        if channel is None:
            logger.debug(f"Auto-summary: channel {channel_id} not found, skipping.")
            return

        since: datetime = datetime.fromisoformat(last_summary_at)
        messages: list = [
            msg
            async for msg in channel.history(
                after=since,
                limit=SUMMARY_CAP,
                oldest_first=False,
            )
            if not msg.author.bot and (msg.clean_content.strip() or msg.embeds)
        ]
        if not messages:
            logger.debug(f"Auto-summary: no new messages to summarize in {channel_id}.")
            return

        message_block: str
        message_block, _truncated = _build_message_block(messages)
        if not message_block.strip():
            return

        summary: str = await asyncio.to_thread(
            get_ai_summary,
            message_block,
            self.bot.ai_api_key,
        )
        if len(summary) > DISCORD_EMBED_DESC_LIMIT:
            summary = summary[: DISCORD_EMBED_DESC_LIMIT - 3] + "..."

        embed: Embed = Embed(
            title=f"📋 Automatic Channel Summary — {len(messages)} new message(s)",
            color=Color.blurple(),
            description=summary,
        )
        embed.set_footer(text=f"Posted automatically every {interval_hours}h.")
        await channel.send(embed=embed)
        logger.info(f"Posted automatic summary for channel {channel_id}.")

    async def _get_replied_message(self, ctx: commands.Context) -> Message | None:
        """Get the message the command invocation replied to, if any.

        Args:
            ctx (commands.Context): Context.

        Returns:
            Message | None: The replied-to message, or None if the command
            was not used as a reply or the message can't be fetched.
        """
        reference = ctx.message.reference
        if reference is None:
            return None
        if isinstance(reference.resolved, Message):
            return reference.resolved
        if reference.message_id is None:
            return None
        try:
            return await ctx.channel.fetch_message(reference.message_id)
        except HTTPException:
            return None

    @commands.hybrid_command(
        name="summarize",
        description=f"Summarize the last X messages in this channel (max {SUMMARY_CAP}).",
        aliases=["summary"],
    )
    @commands.cooldown(rate=1, per=60, type=commands.BucketType.user)
    async def summarize(  # noqa: C901, PLR0912, PLR0915 -- refactoring would be nice.
        self,
        ctx: commands.Context,
        count: int = SUMMARY_CAP,
    ) -> None:
        """Summarize recent messages, or a replied-to message, using AI.

        Args:
            ctx (commands.Context): Context.
            count (int): Number of messages to summarize (1-100, default 100).
                Ignored when replying to a message.
        """
        clamp_note: str | None
        count, clamp_note = _clamp_count(count)

        await ctx.defer()

        replied: Message | None = await self._get_replied_message(ctx)
        if replied is not None:
            messages: list = [replied]
            clamp_note = None
        else:
            logger.debug(
                f"Fetching messages for summarize in channel {ctx.channel.id}.",
            )
            messages: list = []
            before_msg: Message | None = None
            batch_size: int = max(count * 2, 50)
            raw_fetched: int = 0
            history_exhausted: bool = False
            while len(messages) < count:
                fetched_any: bool = False
                async for msg in ctx.channel.history(
                    limit=batch_size,
                    before=before_msg,
                ):
                    fetched_any = True
                    raw_fetched += 1
                    before_msg = msg
                    if msg.author.bot:
                        continue

                    if not msg.clean_content.strip() and not msg.embeds:
                        continue

                    messages.append(msg)
                    if len(messages) >= count:
                        break

                if not fetched_any:
                    history_exhausted = True
                    break

            logger.debug(
                f"Summarize fetch complete: {raw_fetched} raw messages scanned, "
                f"{len(messages)}/{count} valid messages collected "
                f"(exhausted={history_exhausted}).",
            )

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
        if replied is None and history_exhausted and actual_count < count:
            footer_parts.append(
                f"Note: channel history exhausted at {actual_count} valid message(s).",
            )

        title: str = (
            "📋 Message Summary"
            if replied is not None
            else f"📋 Channel Summary — last {actual_count} message(s)"
        )
        embed: Embed = Embed(
            title=title,
            color=Color.blurple(),
            description=summary,
        )
        if footer_parts:
            embed.set_footer(text=" • ".join(footer_parts))

        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="autosummary",
        description="Enable, disable, or check automatic AI summaries for this channel.",
    )
    @commands.has_permissions(manage_channels=True)
    async def autosummary(
        self,
        ctx: commands.Context,
        action: str,
        interval_hours: int = DEFAULT_AUTO_SUMMARY_INTERVAL_HOURS,
    ) -> None:
        """Enable, disable, or check automatic AI channel summaries.

        Args:
            ctx (commands.Context): Context.
            action (str): One of "enable"/"on", "disable"/"off", or "status".
            interval_hours (int): Hours between automatic summaries when
                enabling (1-168, default 6). Ignored otherwise.
        """
        action = action.lower().strip()
        channel_id: int = ctx.channel.id

        if action in {"enable", "on"}:
            clamped: int = clamp_interval_hours(interval_hours)
            enable_auto_summary(AUTO_SUMMARY_DB_PATH, channel_id, clamped)
            note: str = (
                f" (clamped from {interval_hours}h; range is "
                f"{MIN_INTERVAL_HOURS}-{MAX_INTERVAL_HOURS}h)"
                if clamped != interval_hours
                else ""
            )
            embed: Embed = Embed(
                title="✅ Automatic Summaries Enabled",
                color=Color.green(),
                description=(
                    f"I'll post an AI summary of this channel every **{clamped}h**{note}."
                ),
            )
        elif action in {"disable", "off"}:
            existed: bool = disable_auto_summary(AUTO_SUMMARY_DB_PATH, channel_id)
            embed = Embed(
                title="🛑 Automatic Summaries Disabled"
                if existed
                else "ℹ️ Already Disabled",  # noqa: RUF001
                color=Color.og_blurple() if existed else Color.blue(),
                description=(
                    "Automatic summaries are now off for this channel."
                    if existed
                    else "Automatic summaries weren't enabled for this channel."
                ),
            )
        elif action == "status":
            config: tuple[int, str] | None = get_channel_config(
                AUTO_SUMMARY_DB_PATH,
                channel_id,
            )
            if config is None:
                embed = Embed(
                    title="📋 Automatic Summaries",
                    color=Color.blue(),
                    description="Automatic summaries are **disabled** for this channel.",
                )
            else:
                config_interval, last_summary_at = config
                last: datetime = datetime.fromisoformat(last_summary_at)
                elapsed_hours: float = (
                    datetime.now(timezone.utc) - last
                ).total_seconds() / 3600
                next_in: float = max(config_interval - elapsed_hours, 0)
                embed = Embed(
                    title="📋 Automatic Summaries",
                    color=Color.green(),
                    description=(
                        f"**Enabled** — posting every **{config_interval}h**.\n"
                        f"Next summary in about **{next_in:.1f}h**."
                    ),
                )
        else:
            embed = Embed(
                title="❌ Invalid Action",
                color=Color.red(),
                description='Use "enable", "disable", or "status".',
            )

        await ctx.send(embed=embed)


async def setup(bot: DizznemBot) -> None:
    """Setup for AI.

    Args:
        bot (DizznemBot): Dizznem Bot.
    """
    await bot.add_cog(AI(bot))
