"""Main file for bot."""

import asyncio
import os
import time
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, cast

from discord import (
    Color,
    Embed,
    Forbidden,
    HTTPException,
    Intents,
    Message,
    TextChannel,
)
from discord.app_commands import AppCommandError
from discord.ext import commands
from log import logger
from user import User, autosave
from utils.misc.ai import get_ai_response
from utils.numbers import format_duration

if TYPE_CHECKING:
    from discord.app_commands.models import AppCommand

AI_COOLDOWN: float = 5.0
MAX_PROMPT_LENGTH: int = 1000


class DizznemBot(commands.Bot):
    """Dizznem Bot class."""

    def __init__(self) -> None:
        """Initiate Dizznem Bot config/intents."""
        intents: Intents = Intents.default()
        intents.message_content = True

        super().__init__(command_prefix="$", intents=intents, help_command=None)

        self.token: str = cast("str", os.getenv("DISCORD_BOT_TOKEN"))
        self.bot_tag: str = cast("str", os.getenv("DISCORD_BOT_TAG", "dizznem"))
        self.test_channel_id: int = int(cast("str", os.getenv("TEST_CHANNEL_ID", "0")))
        self.inspiration_channel_id: int = int(
            cast("str", os.getenv("INSPIRATION_CHANNEL_ID", "0")),
        )
        self.qotd_channel_id: int = int(
            cast("str", os.getenv("QOTD_CHANNEL_ID", "0")),
        )
        self.admin_id: int = int(
            cast("str", os.getenv("ADMIN_ID", "222002830964162561")),
        )
        self.ai_api_key: str = cast("str", os.getenv("AI_API_KEY", ""))
        self.cache: dict[int, deque] = {}
        self.ai_cooldowns: dict[int, float] = {}
        self.ai_semaphore: asyncio.Semaphore = asyncio.Semaphore(3)

    async def setup_hook(self) -> None:
        """Load all cogs and start autosave for database."""
        logger.info("Loading cogs...")
        cogs_path: Path = Path(__file__).parent / "cogs"
        for file in cogs_path.rglob("*.py"):
            if file.name.startswith("_"):
                continue

            relative: Path = file.relative_to(Path(__file__).parent.parent)
            ext: str = ".".join(relative.with_suffix("").parts)

            try:
                await self.load_extension(ext)
                logger.info(f"Loaded cog {ext}.")
            except commands.NoEntryPointError:
                logger.debug(f"Cog {ext} does not have a setup function, skipping.")
            except (commands.ExtensionError, commands.ExtensionFailed) as e:
                logger.error(f"Failed to load cog {ext}: {e}.")

        try:
            logger.info("Syncing slash commands...")
            synced: list[AppCommand] = await self.tree.sync()
            logger.info(f"Successfully synced {len(synced)} commands.")
        except (HTTPException, AppCommandError) as e:
            logger.error(f"Failed to sync commands: {e}")

        self.loop.create_task(autosave())
        logger.info("Autosave task started.")

    async def on_ready(self) -> None:
        """Bot startup."""
        channel: TextChannel = cast(
            "TextChannel",
            self.get_channel(self.test_channel_id),
        )
        await channel.send("Hello")
        logger.info("Bot started.")

    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        """Command error messages.

        Args:
            ctx (commands.Context): Context.
            error (Exception): The error.

        Raises:
            error: Any unexpected error.
        """
        if ctx.command and hasattr(ctx.command, "on_error"):
            return

        error = getattr(error, "original", error)

        if (
            isinstance(
                error,
                (
                    commands.BadArgument,
                    commands.MissingRequiredArgument,
                    commands.UserInputError,
                ),
            )
            and ctx.command
        ):
            ctx.command.reset_cooldown(ctx)

        if isinstance(error, commands.CommandOnCooldown):
            formatted_time: str = format_duration(error.retry_after)
            embed = Embed(
                title="Cooldown",
                color=Color.orange(),
                description=(f"Try again in **{formatted_time}**."),
            )

        elif isinstance(error, commands.MissingRequiredArgument):
            embed = Embed(
                title="Missing Argument",
                color=Color.red(),
                description=f"Missing argument: `{error.param.name}`",
            )

        elif isinstance(error, commands.BadArgument):
            embed = Embed(
                title="Invalid Argument",
                color=Color.red(),
                description="One or more arguments are invalid.",
            )

        elif isinstance(error, commands.MissingPermissions):
            embed = Embed(
                title="Missing Permissions",
                color=Color.red(),
                description="You do not have permission to use this command.",
            )

        elif isinstance(error, commands.CommandNotFound):
            return

        else:
            raise error

        await ctx.send(embed=embed)

    async def _handle_level_up(self, message: Message, user: User) -> None:
        """Notify user of level up via channel, falling back to DM.

        Args:
            message (Message): The message that triggered the level up.
            user (User): The user who leveled up.
        """
        level_up_message: str = (
            f"Congratulations {message.author.mention}, you "
            f"leveled up to **level {user.level}**!"
        )

        try:
            await message.channel.send(level_up_message)
        except Forbidden:
            try:
                await message.author.send(level_up_message)
            except Forbidden:
                logger.debug(
                    f"Could not notify {message.author} of level up "
                    f"(no channel or DM permission)",
                )
        except HTTPException as e:
            logger.error(f"Failed to send level up message: {e}")

    async def _handle_triggers(self, message: Message) -> None:
        """Check message content against triggers and respond accordingly.

        Args:
            message (Message): The message to check.
        """
        triggers: list[tuple[str, str]] = [
            (self.bot_tag, ""),
            ("wackdiff", "cuckdiff*"),
            ("wack", "cuck*"),
            ("minor", "A MINORRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRR"),
            ("spark", "Please spark Dizznem please!!!!!!"),
            ("dizznem", "dihhnem*"),
            ("cook", "We need to cook."),
            ("call", "Better Call Saul!"),
            # ("gay", "Dizznem Bot is an LGBTQ+ ally!"),  # Vaulted pride month command
            (
                "pride",
                "https://tenor.com/view/subaru-edit-pride-subaru-rezero-pride-rezero-edit-subaru-natsuki-gif-11978560993207825692",
            ),
            ("limit", "WE SAIYANS HAVE NO LIMITS!!!"),
            (
                "super speed clicker",
                "https://www.roblox.com/games/139600379808227/Super-Speed-Clicker",
            ),
            ("good bot", "Thank you! I try my best!"),
            ("monster", "Aura Monster."),
            ("all girls", "All girls are the same bro..."),
            ("67", "67"),
            ("six seven", "SIX SEVEN!"),
            ("wallahi", "Say wallahi bro, say wallahi!"),
        ]

        content: str = message.content.lower()
        for trigger, response in triggers:
            if trigger not in content:
                continue

            if trigger == self.bot_tag:
                now: float = time.monotonic()
                last: float = self.ai_cooldowns.get(message.author.id, 0)
                if now - last < AI_COOLDOWN:
                    remaining: float = AI_COOLDOWN - (now - last)
                    await message.channel.send(
                        f"Slow down! Try again in **{remaining:.1f}** seconds.",
                    )
                    break

                self.ai_cooldowns[message.author.id] = now
                prompt: str = message.content.replace(self.bot_tag, "").strip()

                if not prompt:
                    await message.channel.send("Ask me something!")
                elif len(prompt) > MAX_PROMPT_LENGTH:
                    await message.channel.send(
                        f"Your prompt is too long! Keep it under **{MAX_PROMPT_LENGTH}** characters.",  # noqa: E501
                    )
                else:
                    channel_id: int = message.channel.id
                    if channel_id not in self.cache:
                        self.cache[channel_id] = deque(
                            maxlen=20,
                        )  # 10 messages each from user/bot

                    cache: deque = self.cache[channel_id]

                    async with self.ai_semaphore, message.channel.typing():
                        ai_response: str = await asyncio.to_thread(
                            get_ai_response,
                            prompt,
                            self.ai_api_key,
                            list(cache),
                        )

                    cache.append({"role": "user", "content": prompt})
                    cache.append({"role": "assistant", "content": ai_response})
                    await message.channel.send(ai_response)
            else:
                await message.channel.send(response)

            break

    async def on_message(self, message: Message) -> None:
        """Handle message events.

        Args:
            message (Message): User message.
        """
        if message.author == self.user or message.author.bot:
            return

        user_id: int = message.author.id
        username: str = message.author.name
        user: User = User.create_if_not_exists(user_id=user_id, username=username)
        user.message_count += 1

        if user.level_up_if_able():
            await self._handle_level_up(message, user)

        await self._handle_triggers(message)
        await self.process_commands(message)

    def run_bot(self) -> None:
        """Run bot."""
        super().run(self.token)
