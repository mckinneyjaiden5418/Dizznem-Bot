"""Discord UI views for stock buy/sell interactions."""

from collections.abc import Callable

from discord import ButtonStyle, Color, Embed, Interaction, Message
from discord.ui import Button, Modal, TextInput, View, button


class AmountModal(Modal, title="Enter Amount"):
    """Modal for entering a custom stock amount."""

    amount: TextInput = TextInput(
        label="Amount",
        placeholder="Enter a number...",
        min_length=1,
        max_length=10,
    )

    def __init__(self, parent_view: "BuyView | SellView") -> None:
        """Initialize the modal.

        Args:
            parent_view (BuyView | SellView): The parent view to pass the amount back to.
        """
        super().__init__()
        self.parent_view: BuyView | SellView = parent_view

    async def on_submit(self, interaction: Interaction) -> None:
        """Handle modal submission.

        Args:
            interaction (Interaction): The interaction.
        """
        try:
            amount: int = int(self.amount.value)
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid whole number.",
                ephemeral=True,
            )
            return

        if amount <= 0:
            await interaction.response.send_message(
                "Amount must be greater than 0.",
                ephemeral=True,
            )
            return

        await self.parent_view.proceed_to_confirm(interaction, amount)


class ConfirmView(View):
    """Confirm or cancel a stock transaction."""

    def __init__(
        self,
        action: str,
        stock_name: str,
        quantity: int,
        total: float,
        execute_fn: Callable[[int], tuple[bool, str]],
    ) -> None:
        """Initialize the confirm view.

        Args:
            action (str): "Buy" or "Sell".
            stock_name (str): Name of the stock.
            quantity (int): Number of shares.
            total (float): Total cost or value.
            execute_fn (Callable[[int], tuple[bool, str]]): Function to call on confirm.
        """
        super().__init__(timeout=30)
        self.action: str = action
        self.stock_name: str = stock_name
        self.quantity: int = quantity
        self.total: float = total
        self.execute_fn: Callable[[int], tuple[bool, str]] = execute_fn
        self.message: Message | None = None

    async def on_timeout(self) -> None:
        """Disable buttons on timeout."""
        for item in self.children:
            item.disabled = True  # type: ignore[union-attr]
        if self.message:
            await self.message.edit(view=self)

    @staticmethod
    def build_embed(action: str, stock_name: str, quantity: int, total: float) -> Embed:
        """Build the confirmation embed.

        Args:
            action (str): "Buy" or "Sell".
            stock_name (str): Stock name.
            quantity (int): Shares.
            total (float): Total cost or value.

        Returns:
            Embed: Confirmation embed.
        """
        color: Color = Color.green() if action == "Buy" else Color.red()
        return Embed(
            title=f"Confirm {action}",
            color=color,
            description=(
                f"{action} **{quantity}x {stock_name}** for **${total:,.2f}**?\n\n"
                "*This will expire in 30 seconds.*"
            ),
        )

    @button(label="Confirm", style=ButtonStyle.green)
    async def confirm(self, interaction: Interaction, _: Button) -> None:
        """Confirm the transaction.

        Args:
            interaction (Interaction): The interaction.
            _ (Button): Unused button reference.
        """
        self.stop()
        success: bool
        message: str
        success, message = self.execute_fn(self.quantity)
        color: Color = Color.green() if success else Color.red()
        embed: Embed = Embed(
            title=(
                f"✅ {self.action} Successful"
                if success
                else f"❌ {self.action} Failed"
            ),
            color=color,
            description=message,
        )
        await interaction.response.edit_message(embed=embed, view=None)

    @button(label="Cancel", style=ButtonStyle.red)
    async def cancel(self, interaction: Interaction, _: Button) -> None:
        """Cancel the transaction.

        Args:
            interaction (Interaction): The interaction.
            _ (Button): Unused button reference.
        """
        self.stop()
        await interaction.response.edit_message(
            embed=Embed(
                title="Cancelled",
                color=Color.greyple(),
                description="Transaction cancelled.",
            ),
            view=None,
        )


class BuyView(View):
    """View for selecting how many shares to buy."""

    def __init__(
        self,
        user_id: int,
        stock_name: str,
        price: float,
        balance: float,
        execute_fn: Callable[[int], tuple[bool, str]],
    ) -> None:
        """Initialize the buy view.

        Args:
            user_id (int): Discord user ID.
            stock_name (str): Name of the stock.
            price (float): Current stock price.
            balance (float): User's current balance.
            execute_fn (Callable[[int], tuple[bool, str]]): Function to execute the buy.
        """
        super().__init__(timeout=60)
        self.user_id: int = user_id
        self.stock_name: str = stock_name
        self.price: float = price
        self.balance: float = balance
        self.execute_fn: Callable[[int], tuple[bool, str]] = execute_fn
        self.max_shares: int = int(balance // price)
        self.message: Message | None = None

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Ensure only the command invoker can interact.

        Args:
            interaction (Interaction): The interaction.

        Returns:
            bool: True if the user is allowed.
        """
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This isn't your transaction.",
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

    async def proceed_to_confirm(self, interaction: Interaction, quantity: int) -> None:
        """Transition to the confirmation view.

        Args:
            interaction (Interaction): The interaction.
            quantity (int): Number of shares selected.
        """
        if quantity > self.max_shares:
            await interaction.response.send_message(
                f"You can only afford **{self.max_shares}x {self.stock_name}**.",
                ephemeral=True,
            )
            return

        total: float = quantity * self.price
        confirm_view = ConfirmView(
            action="Buy",
            stock_name=self.stock_name,
            quantity=quantity,
            total=total,
            execute_fn=self.execute_fn,
        )
        embed: Embed = ConfirmView.build_embed("Buy", self.stock_name, quantity, total)
        await interaction.response.edit_message(embed=embed, view=confirm_view)
        confirm_view.message = await interaction.original_response()

    @staticmethod
    def build_embed(
        stock_name: str,
        price: float,
        balance: float,
        max_shares: int,
    ) -> Embed:
        """Build the buy selection embed.

        Args:
            stock_name (str): Stock name.
            price (float): Current price.
            balance (float): User balance.
            max_shares (int): Max affordable shares.

        Returns:
            Embed: The embed.
        """
        return Embed(
            title=f"Buy {stock_name}",
            color=Color.green(),
            description=(
                f"**Price:** ${price:,.2f} per share\n"
                f"**Balance:** ${balance:,.2f}\n"
                f"**Max you can buy:** {max_shares} shares\n\n"
                "Select an amount below."
            ),
        )

    @button(label="All", style=ButtonStyle.green)
    async def buy_all(self, interaction: Interaction, _: Button) -> None:
        """Buy all affordable shares.

        Args:
            interaction (Interaction): The interaction.
            _ (Button): Unused button reference.
        """
        if self.max_shares == 0:
            await interaction.response.send_message(
                f"You can't afford any **{self.stock_name}** shares.",
                ephemeral=True,
            )
            return
        await self.proceed_to_confirm(interaction, self.max_shares)

    @button(label="Half", style=ButtonStyle.blurple)
    async def buy_half(self, interaction: Interaction, _: Button) -> None:
        """Buy half of the affordable shares.

        Args:
            interaction (Interaction): The interaction.
            _ (Button): Unused button reference.
        """
        if self.max_shares == 0:
            await interaction.response.send_message(
                f"You can't afford any **{self.stock_name}** shares.",
                ephemeral=True,
            )
            return
        half: int = max(1, self.max_shares // 2)
        await self.proceed_to_confirm(interaction, half)

    @button(label="Custom", style=ButtonStyle.grey)
    async def buy_custom(self, interaction: Interaction, _: Button) -> None:
        """Open a modal for a custom amount.

        Args:
            interaction (Interaction): The interaction.
            _ (Button): Unused button reference.
        """
        await interaction.response.send_modal(AmountModal(parent_view=self))


class SellView(View):
    """View for selecting how many shares to sell."""

    def __init__(
        self,
        user_id: int,
        stock_name: str,
        price: float,
        owned: int,
        execute_fn: Callable[[int], tuple[bool, str]],
    ) -> None:
        """Initialize the sell view.

        Args:
            user_id (int): Discord user ID.
            stock_name (str): Name of the stock.
            price (float): Current stock price.
            owned (int): Number of shares owned.
            execute_fn (Callable[[int], tuple[bool, str]]): Function to execute the sell.
        """
        super().__init__(timeout=60)
        self.user_id: int = user_id
        self.stock_name: str = stock_name
        self.price: float = price
        self.owned: int = owned
        self.execute_fn: Callable[[int], tuple[bool, str]] = execute_fn
        self.message: Message | None = None

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Ensure only the command invoker can interact.

        Args:
            interaction (Interaction): The interaction.

        Returns:
            bool: True if the user is allowed.
        """
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This isn't your transaction.",
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

    async def proceed_to_confirm(self, interaction: Interaction, quantity: int) -> None:
        """Transition to the confirmation view.

        Args:
            interaction (Interaction): The interaction.
            quantity (int): Number of shares selected.
        """
        if quantity > self.owned:
            await interaction.response.send_message(
                f"You only own **{self.owned}x {self.stock_name}**.",
                ephemeral=True,
            )
            return

        total: float = quantity * self.price
        confirm_view = ConfirmView(
            action="Sell",
            stock_name=self.stock_name,
            quantity=quantity,
            total=total,
            execute_fn=self.execute_fn,
        )
        embed: Embed = ConfirmView.build_embed("Sell", self.stock_name, quantity, total)
        await interaction.response.edit_message(embed=embed, view=confirm_view)
        confirm_view.message = await interaction.original_response()

    @staticmethod
    def build_embed(stock_name: str, price: float, owned: int) -> Embed:
        """Build the sell selection embed.

        Args:
            stock_name (str): Stock name.
            price (float): Current price.
            owned (int): Shares owned.

        Returns:
            Embed: The embed.
        """
        return Embed(
            title=f"Sell {stock_name}",
            color=Color.red(),
            description=(
                f"**Price:** ${price:,.2f} per share\n"
                f"**You own:** {owned} shares\n"
                f"**Total value:** ${owned * price:,.2f}\n\n"
                "Select an amount below."
            ),
        )

    @button(label="All", style=ButtonStyle.red)
    async def sell_all(self, interaction: Interaction, _: Button) -> None:
        """Sell all owned shares.

        Args:
            interaction (Interaction): The interaction.
            _ (Button): Unused button reference.
        """
        await self.proceed_to_confirm(interaction, self.owned)

    @button(label="Half", style=ButtonStyle.blurple)
    async def sell_half(self, interaction: Interaction, _: Button) -> None:
        """Sell half of owned shares.

        Args:
            interaction (Interaction): The interaction.
            _ (Button): Unused button reference.
        """
        half: int = max(1, self.owned // 2)
        await self.proceed_to_confirm(interaction, half)

    @button(label="Custom", style=ButtonStyle.grey)
    async def sell_custom(self, interaction: Interaction, _: Button) -> None:
        """Open a modal for a custom amount.

        Args:
            interaction (Interaction): The interaction.
            _ (Button): Unused button reference.
        """
        await interaction.response.send_modal(AmountModal(parent_view=self))
