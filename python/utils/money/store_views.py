"""Discord UI views for the store."""

import sqlite3
from collections.abc import Awaitable, Callable

from discord import (
    ButtonStyle,
    Color,
    Embed,
    Interaction,
    Message,
    TextChannel,
    TextStyle,
)
from discord.ext.commands import Bot
from discord.ui import Button, Modal, TextInput, View, button
from user import User
from utils.misc.inspiration import INSPIRATION_DB_PATH, add_quote, validate_quote
from utils.money.stocks import USERS_DB_PATH
from utils.numbers import format_number


class TextModal(Modal):
    """Generic modal for text input."""

    text_input: TextInput = TextInput(
        label="Your message",
        placeholder="Type your message here...",
        min_length=1,
        max_length=500,
        style=TextStyle.paragraph,
    )

    def __init__(
        self,
        title: str,
        on_submit_fn: Callable[[Interaction, str], Awaitable[None]],
    ) -> None:
        """Initialize the modal.

        Args:
            title (str): Modal title.
            on_submit_fn (Callable[[Interaction, str], None]): Callback on submit.
        """
        super().__init__(title=title)
        self.on_submit_fn: Callable[[Interaction, str], Awaitable[None]] = on_submit_fn

    async def on_submit(self, interaction: Interaction) -> None:
        """Handle modal submission.

        Args:
            interaction (Interaction): The interaction.
        """
        await self.on_submit_fn(interaction, self.text_input.value)


class StoreView(View):
    """View for the store."""

    CUCKDIFF_ID: int = 284502028896698369
    KARMA_ID: int = 222002830964162561
    DIZZNEM_ID: int = 1229590915610574893

    def __init__(
        self,
        user_id: int,
        balance: float,
        prestige: int,
        bot: Bot,
    ) -> None:
        """Initialize the store view.

        Args:
            user_id (int): Discord user ID.
            balance (float): User's current balance.
            prestige (int): User's current prestige count.
            bot: DizznemBot instance.
        """
        super().__init__(timeout=60)
        self.user_id: int = user_id
        self.balance: float = balance
        self.prestige: int = prestige
        self.bot: Bot = bot
        self.message: Message | None = None

        prestige_cost: int = 100_000_000 * (prestige + 1)
        self.prestige_button.label = f"⭐ PRESTIGE (${format_number(prestige_cost)})"

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Ensure only the command invoker can interact.

        Args:
            interaction (Interaction): The interaction.

        Returns:
            bool: True if allowed.
        """
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This isn't your store session.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        """Disable buttons on timeout."""
        for item in self.children:
            item.disabled = True  # type: ignore[union-attr]
        if self.message:
            await self.message.edit(view=self)

    @staticmethod
    def build_embed(balance: float, prestige: int) -> Embed:
        """Build the store embed.

        Args:
            balance (float): User's balance.
            prestige (int): User's prestige.

        Returns:
            Embed: The store embed.
        """
        ping_count: int = (prestige + 1) * 5
        prestige_cost: int = 100_000_000 * (prestige + 1)
        embed = Embed(title="🛒 Store", color=Color.og_blurple())
        embed.add_field(
            name="💰 Your Balance",
            value=f"**${format_number(balance)}**",
            inline=False,
        )
        embed.add_field(
            name="🔔 Ping Cuckdiff",
            value=f"**$10,000** — Pings Cuckdiff {ping_count} times!",
            inline=False,
        )
        embed.add_field(
            name="✨ Ask Dizznem to spark",
            value="**$50,000**",
            inline=False,
        )
        embed.add_field(
            name="💬 Add inspirational quote",
            value="**$100,000** — Adds your quote to `$inspiration`",
            inline=False,
        )
        embed.add_field(
            name="🎥 Ask for inspirational video",
            value="**$500,000** — Asks Karma SB to make an inspo video!",
            inline=False,
        )
        embed.add_field(
            name="📢 Send inspo message",
            value="**$1,000,000** — Sends a message in #inspiration",
            inline=False,
        )
        embed.add_field(
            name="❓ Send QOTD",
            value="**$10,000,000** — Sends a question in #qotd",
            inline=False,
        )
        embed.add_field(
            name="⭐ PRESTIGE",
            value=f"**${format_number(prestige_cost)}** — ⚠️ Resets all your money and stocks!",
            inline=False,
        )
        return embed

    def _check_balance(self, cost: float) -> bool:
        """Check if the user can currently afford an item.

        Re-reads the live balance rather than relying on the balance the
        view was created with, since that snapshot can go stale (e.g. the
        user spends money elsewhere) while this view is still open.

        Args:
            cost (float): Item cost.

        Returns:
            bool: True if affordable.
        """
        user: User = User.create_if_not_exists(user_id=self.user_id, username="")
        return user.money >= cost

    async def _deduct(self, cost: float) -> None:
        """Deduct cost from the user's live balance.

        Args:
            cost (float): Amount to deduct.
        """
        user: User = User.create_if_not_exists(user_id=self.user_id, username="")
        user.money -= cost
        self.balance = user.money

    async def _insufficient_funds(self, interaction: Interaction) -> None:
        """Send insufficient funds message.

        Args:
            interaction (Interaction): The interaction.
        """
        await interaction.response.send_message(
            embed=Embed(
                title="❌ Insufficient Funds",
                color=Color.red(),
                description="You don't have enough money for this.",
            ),
            ephemeral=True,
        )

    @button(label="🔔 Ping Cuckdiff ($10,000)", style=ButtonStyle.blurple, row=0)
    async def ping_cuckdiff(self, interaction: Interaction, _: Button) -> None:
        """Ping Cuckdiff multiple times.

        Args:
            interaction (Interaction): The interaction.
            _ (Button): Unused button reference.
        """
        cost: float = 10_000
        if not self._check_balance(cost):
            await self._insufficient_funds(interaction)
            return

        await self._deduct(cost)
        ping_count: int = (self.prestige + 1) * 5
        await interaction.response.send_message(
            embed=Embed(
                title="🔔 Purchase Successful",
                color=Color.green(),
                description=f"Pinging Cuckdiff {ping_count} times!",
            ),
        )
        for _ in range(ping_count):  # pyright: ignore[reportAssignmentType]
            await interaction.channel.send(  # pyright: ignore[reportOptionalMemberAccess] # type: ignore  # noqa: PGH003
                f"<@{self.CUCKDIFF_ID}>",
            )

    @button(label="✨ Ask to Spark ($50,000)", style=ButtonStyle.blurple, row=0)
    async def ask_spark(self, interaction: Interaction, _: Button) -> None:
        """Ask Dizznem to spark.

        Args:
            interaction (Interaction): The interaction.
            _ (Button): Unused button reference.
        """
        cost: float = 50_000
        if not self._check_balance(cost):
            await self._insufficient_funds(interaction)
            return

        await self._deduct(cost)
        await interaction.response.send_message(
            embed=Embed(
                title="✨ Purchase Successful",
                color=Color.green(),
                description="Asked Dizznem to spark!",
            ),
        )
        await interaction.channel.send(  # pyright: ignore[reportAttributeAccessIssue] # type: ignore  # noqa: PGH003
            f"<@{self.DIZZNEM_ID}> please spark bro! please!!!",
        )

    @button(label="💬 Add Inspo Quote ($100,000)", style=ButtonStyle.blurple, row=1)
    async def add_quote(self, interaction: Interaction, _: Button) -> None:
        """Add an inspirational quote.

        Args:
            interaction (Interaction): The interaction.
            _ (Button): Unused button reference.
        """
        cost: float = 100_000
        if not self._check_balance(cost):
            await self._insufficient_funds(interaction)
            return

        async def on_submit(inter: Interaction, text: str) -> None:
            await self._deduct(cost)
            is_valid: bool
            error: str
            is_valid, error = validate_quote(text)
            if not is_valid:
                await inter.response.send_message(
                    embed=Embed(
                        title="❌ Invalid Quote",
                        color=Color.red(),
                        description=error,
                    ),
                    ephemeral=True,
                )
                return

            add_quote(INSPIRATION_DB_PATH, text)
            await inter.response.send_message(
                embed=Embed(
                    title="💬 Purchase Successful",
                    color=Color.green(),
                    description=f'Your quote has been added to `$inspiration`!\n\n*"{text}"*',
                ),
            )

        modal = TextModal(title="Add Inspirational Quote", on_submit_fn=on_submit)
        await interaction.response.send_modal(modal)

    @button(label="🎥 Inspo Video ($500,000)", style=ButtonStyle.blurple, row=1)
    async def inspo_video(self, interaction: Interaction, _: Button) -> None:
        """Ask Karma SB for an inspirational video.

        Args:
            interaction (Interaction): The interaction.
            _ (Button): Unused button reference.
        """
        cost: float = 500_000
        if not self._check_balance(cost):
            await self._insufficient_funds(interaction)
            return

        await self._deduct(cost)
        await interaction.response.send_message(
            embed=Embed(
                title="🎥 Purchase Successful",
                color=Color.green(),
                description="Asked Karma SB to make an inspirational video!",
            ),
        )
        await interaction.channel.send(  # pyright: ignore[reportAttributeAccessIssue] # type: ignore  # noqa: PGH003
            f"<@{self.KARMA_ID}> please make an inspirational video!",
        )

    @button(label="📢 Send Inspo Message ($1,000,000)", style=ButtonStyle.green, row=2)
    async def send_inspo(self, interaction: Interaction, _: Button) -> None:
        """Send an inspirational message in #inspiration.

        Args:
            interaction (Interaction): The interaction.
            _ (Button): Unused button reference.
        """
        cost: float = 1_000_000
        if not self._check_balance(cost):
            await self._insufficient_funds(interaction)
            return

        async def on_submit(inter: Interaction, text: str) -> None:
            channel: TextChannel | None = self.bot.get_channel(
                self.bot.inspiration_channel_id,  # type: ignore  # noqa: PGH003
            )
            if channel is None:
                await inter.response.send_message(
                    "Could not find the inspiration channel.",
                    ephemeral=True,
                )
                return
            await self._deduct(cost)
            await channel.send(
                embed=Embed(
                    title="✨ Inspirational Message",
                    color=Color.gold(),
                    description=text,
                ).set_footer(text=f"Sent by {inter.user.display_name}"),
            )
            await inter.response.send_message(
                embed=Embed(
                    title="📢 Purchase Successful",
                    color=Color.green(),
                    description="Your message has been sent in #inspiration!",
                ),
            )

        modal = TextModal(title="Send Inspirational Message", on_submit_fn=on_submit)
        await interaction.response.send_modal(modal)

    @button(label="❓ Send QOTD ($10,000,000)", style=ButtonStyle.green, row=2)
    async def send_qotd(self, interaction: Interaction, _: Button) -> None:
        """Send a question of the day in #qotd.

        Args:
            interaction (Interaction): The interaction.
            _ (Button): Unused button reference.
        """
        cost: float = 10_000_000
        if not self._check_balance(cost):
            await self._insufficient_funds(interaction)
            return

        async def on_submit(inter: Interaction, text: str) -> None:
            channel: TextChannel | None = self.bot.get_channel(
                self.bot.qotd_channel_id,  # type: ignore  # noqa: PGH003
            )
            if channel is None:
                await inter.response.send_message(
                    "Could not find the QOTD channel.",
                    ephemeral=True,
                )
                return
            await self._deduct(cost)
            await channel.send(
                embed=Embed(
                    title="❓ Question of the Day",
                    color=Color.blue(),
                    description=text,
                ).set_footer(text=f"Sent by {inter.user.display_name}"),
            )
            await inter.response.send_message(
                embed=Embed(
                    title="❓ Purchase Successful",
                    color=Color.green(),
                    description="Your QOTD has been sent in #qotd!",
                ),
            )

        modal = TextModal(title="Send Question of the Day", on_submit_fn=on_submit)
        await interaction.response.send_modal(modal)

    @button(label="⭐ PRESTIGE ($100,000,000)", style=ButtonStyle.red, row=3)
    async def prestige_button(  # pyright: ignore[reportRedeclaration]
        self,
        interaction: Interaction,
        _: Button,
    ) -> None:
        """Prestige — resets money and stocks.

        Args:
            interaction (Interaction): The interaction.
            _ (Button): Unused button reference.
        """
        cost: float = 100_000_000 * (self.prestige + 1)
        if not self._check_balance(cost):
            await self._insufficient_funds(interaction)
            return

        confirm_view = PrestigeConfirmView(
            user_id=self.user_id,
            bot=self.bot,
            cost=cost,
        )
        await interaction.response.send_message(
            embed=Embed(
                title="⭐ Confirm Prestige",
                color=Color.red(),
                description=(
                    f"⚠️ This will **reset all your money and stocks** and cost **${format_number(cost)}**.\n\n"  # noqa: E501
                    "Are you sure?"
                ),
            ),
            view=confirm_view,
            ephemeral=True,
        )


class PrestigeConfirmView(View):
    """Confirmation view for prestiging."""

    def __init__(self, user_id: int, bot: Bot, cost: float) -> None:
        """Initialize the prestige confirm view.

        Args:
            user_id (int): Discord user ID.
            bot (Bot): DizznemBot instance.
            cost (float): Prestige cost.
        """
        super().__init__(timeout=30)
        self.user_id: int = user_id
        self.bot: Bot = bot
        self.cost: float = cost

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Ensure only the command invoker can interact.

        Args:
            interaction (Interaction): The interaction.

        Returns:
            bool: True if allowed.
        """
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This isn't your session.",
                ephemeral=True,
            )
            return False
        return True

    @button(label="Confirm Prestige", style=ButtonStyle.red)
    async def confirm(self, interaction: Interaction, _: Button) -> None:
        """Confirm prestige.

        Args:
            interaction (Interaction): The interaction.
            _ (Button): Unused button reference.
        """
        user: User = User.create_if_not_exists(user_id=self.user_id, username="")
        if user.money < self.cost:
            self.stop()
            await interaction.response.edit_message(
                embed=Embed(
                    title="❌ Insufficient Funds",
                    color=Color.red(),
                    description="Your balance changed and you can no longer afford to prestige.",  # noqa: E501
                ),
                view=None,
            )
            return

        user.money = 0
        user.prestige += 1

        # Wipe all stock holdings
        with sqlite3.connect(USERS_DB_PATH) as conn:
            conn.execute(
                "DELETE FROM user_stocks WHERE user_id = ?",
                (self.user_id,),
            )
            conn.commit()

        self.stop()
        await interaction.response.edit_message(
            embed=Embed(
                title="⭐ Prestiged!",
                color=Color.gold(),
                description=(
                    f"You are now **Prestige {user.prestige}**!\n"
                    "Your money and stocks have been reset. Good luck!"
                ),
            ),
            view=None,
        )

    @button(label="Cancel", style=ButtonStyle.grey)
    async def cancel(self, interaction: Interaction, _: Button) -> None:
        """Cancel prestige.

        Args:
            interaction (Interaction): The interaction.
            _ (Button): Unused button reference.
        """
        self.stop()
        await interaction.response.edit_message(
            embed=Embed(
                title="Cancelled",
                color=Color.greyple(),
                description="Prestige cancelled.",
            ),
            view=None,
        )
