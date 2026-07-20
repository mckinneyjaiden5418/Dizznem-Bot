"""Admin commands.

Quick note:
I'm using discord IDs here to check for admin because I don't have admin in the discord server this
bot is being used.

"""

from bot.bot import DizznemBot
from discord import Color, Embed, Member
from discord.ext import commands
from log import logger  # noqa: F401
from user import User
from utils.money.prediction_market import cancel_market, resolve_market
from utils.money.stocks import USERS_DB_PATH, liquidate_stock
from utils.numbers import convert_money_str, format_number


class Admin(commands.Cog):
    """Admin commands."""

    def __init__(self, bot: DizznemBot) -> None:
        """Initialize Admin.

        Args:
            bot (DizznemBot): Dizznem Bot.
        """
        self.bot: DizznemBot = bot

    @commands.hybrid_command(
        name="addmoney",
        description="Add money to a user's balance (admin command).",
    )
    async def add_money(
        self,
        ctx: commands.Context,
        member: Member,
        amount: str,
    ) -> None:
        """Add money to a user's balance.

        Args:
            ctx (commands.Context): Context.
            member (Member): Member to add money to.
            amount (str): Money amount to add.
        """
        if ctx.author.id != self.bot.admin_id:
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description="You do not have access to this command.",
                ),
                ephemeral=True,
            )
            return

        try:
            amount_float: float = convert_money_str(money_str=amount)
        except ValueError:
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description="Invalid money format.",
                ),
                ephemeral=True,
            )
            return

        user: User = User.create_if_not_exists(user_id=member.id, username=member.name)
        user.money += amount_float

        await ctx.send(
            embed=Embed(
                title="🏦",
                color=Color.green(),
                description=(
                    f"Added **${format_number(amount_float)}** to **{member.display_name}**'s balance.\n"  # noqa: E501
                    f"New balance: **${format_number(user.money)}**"
                ),
            ),
        )

    @commands.hybrid_command(
        name="setmoney",
        description="Set money for a user (admin command).",
    )
    async def set_money(
        self,
        ctx: commands.Context,
        member: Member,
        amount: str,
    ) -> None:
        """Set money for a user.

        Args:
            ctx (commands.Context): Context.
            member (Member): Member to set money for.
            amount (str): Money amount.
        """
        if ctx.author.id != self.bot.admin_id:
            embed: Embed = Embed(
                title="Error",
                color=Color.red(),
                description="You do not have access to this command.",
            )
            await ctx.send(embed=embed, ephemeral=True)
            return

        try:
            amount_float: float = convert_money_str(money_str=amount)
        except ValueError:
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description="Invalid money format.",
                ),
                ephemeral=True,
            )
            return

        user: User = User.create_if_not_exists(user_id=member.id, username=member.name)
        user.money = amount_float

        formatted_amount: str = format_number(amount_float)

        embed: Embed = Embed(
            title="🏦",
            color=Color.green(),
            description=f"Set **{member.display_name}**'s balance to **${formatted_amount}**.",
        )

        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="resetcooldown",
        description="Reset all cooldowns for a given command (admin command).",
    )
    async def reset_cooldown(
        self,
        ctx: commands.Context,
        command_name: str,
    ) -> None:
        """Reset all cooldowns for a given command.

        Args:
            ctx (commands.Context): Context.
            command_name (str): Command name to reset cooldowns for.
        """
        if ctx.author.id != self.bot.admin_id:
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description="You do not have access to this command.",
                ),
                ephemeral=True,
            )
            return

        cmd: commands.Command | None = self.bot.get_command(command_name)
        if cmd is None:
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description=f"Command **{command_name}** not found.",
                ),
                ephemeral=True,
            )
            return

        if cmd._buckets._cache:  # noqa: SLF001
            cmd._buckets._cache.clear()  # noqa: SLF001
            await ctx.send(
                embed=Embed(
                    title="✅ Cooldowns Reset",
                    color=Color.green(),
                    description=f"All cooldowns for **{command_name}** have been reset.",
                ),
            )
        else:
            await ctx.send(
                embed=Embed(
                    title="ℹ️ No Cooldowns",  # noqa: RUF001
                    color=Color.blue(),
                    description=f"**{command_name}** has no active cooldowns.",
                ),
            )


    @commands.hybrid_command(
        name="retirestock",
        description="Pay out and clear everyone's shares of a stock (admin command).",
    )
    async def retire_stock(self, ctx: commands.Context, stock: str) -> None:
        """Force-sell every holder's shares of a stock at its current price.

        Run this before repointing a stock's ticker in STOCK_MAP — it settles
        every holder at the pre-swap price so the ticker change itself can't
        hand anyone a free windfall or wipe out their position.

        Args:
            ctx (commands.Context): Context.
            stock (str): Name of the stock to retire (case-insensitive).
        """
        if ctx.author.id != self.bot.admin_id:
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description="You do not have access to this command.",
                ),
            )
            return

        try:
            settlements: list[tuple[int, int, float, float]] = liquidate_stock(
                USERS_DB_PATH,
                stock,
            )
        except ValueError:
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description=f"`{stock}` is not a valid stock.",
                ),
            )
            return

        if not settlements:
            await ctx.send(
                embed=Embed(
                    title="ℹ️ No Holders",  # noqa: RUF001
                    color=Color.blue(),
                    description=f"No one currently holds **{stock}**. Safe to change its ticker.",  # noqa: E501
                ),
            )
            return

        total_paid: float = sum(payout for _, _, _, payout in settlements)
        lines: list[str] = [
            f"<@{user_id}>: {quantity}x @ ${price:,.2f} = **${payout:,.2f}**"
            for user_id, quantity, price, payout in settlements
        ]

        embed: Embed = Embed(
            title=f"🏦 {stock} Retired",
            color=Color.gold(),
            description=(
                f"Paid out **{len(settlements)}** holder(s), **${total_paid:,.2f}** total.\n\n"
                + "\n".join(lines)
            ),
        )
        await ctx.send(embed=embed)


    @commands.hybrid_command(
        name="resolvemarket",
        description="Resolve a prediction market and pay out winners (admin command).",
    )
    async def resolve_market_cmd(
        self,
        ctx: commands.Context,
        market_id: int,
        outcome: str,
    ) -> None:
        """Resolve a prediction market, paying out the winning side.

        Args:
            ctx (commands.Context): Context.
            market_id (int): Market ID to resolve.
            outcome (str): "yes" or "no".
        """
        if ctx.author.id != self.bot.admin_id:
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description="You do not have access to this command.",
                ),
                ephemeral=True,
            )
            return

        try:
            settlements: list[tuple[int, float, float]] = resolve_market(
                USERS_DB_PATH,
                market_id,
                outcome,
            )
        except ValueError as exc:
            await ctx.send(
                embed=Embed(title="Error", color=Color.red(), description=str(exc)),
                ephemeral=True,
            )
            return

        if not settlements:
            await ctx.send(
                embed=Embed(
                    title=f"🔮 Market #{market_id} Resolved: {outcome.upper()}",
                    color=Color.gold(),
                    description="No bets were placed on this market.",
                ),
            )
            return

        total_paid: float = sum(payout for _, _, payout in settlements)
        lines: list[str] = [
            f"<@{user_id}>: staked ${stake:,.2f} → **${payout:,.2f}**"
            for user_id, stake, payout in settlements
        ]

        embed: Embed = Embed(
            title=f"🔮 Market #{market_id} Resolved: {outcome.upper()}",
            color=Color.gold(),
            description=(
                f"Paid out **{len(settlements)}** bettor(s), **${total_paid:,.2f}** total.\n\n"
                + "\n".join(lines)
            ),
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="cancelmarket",
        description="Cancel a prediction market and refund all bets (admin command).",
    )
    async def cancel_market_cmd(self, ctx: commands.Context, market_id: int) -> None:
        """Cancel a prediction market and refund every bettor.

        Args:
            ctx (commands.Context): Context.
            market_id (int): Market ID to cancel.
        """
        if ctx.author.id != self.bot.admin_id:
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description="You do not have access to this command.",
                ),
                ephemeral=True,
            )
            return

        try:
            refunds: list[tuple[int, float]] = cancel_market(USERS_DB_PATH, market_id)
        except ValueError as exc:
            await ctx.send(
                embed=Embed(title="Error", color=Color.red(), description=str(exc)),
                ephemeral=True,
            )
            return

        total_refunded: float = sum(amount for _, amount in refunds)
        embed = Embed(
            title=f"🔮 Market #{market_id} Cancelled",
            color=Color.greyple(),
            description=f"Refunded **{len(refunds)}** bettor(s), **${total_refunded:,.2f}** total.",  # noqa: E501
        )
        await ctx.send(embed=embed)


async def setup(bot: DizznemBot) -> None:
    """Setup for Admin.

    Args:
        bot (DizznemBot): Dizznem Bot.
    """
    await bot.add_cog(Admin(bot))
