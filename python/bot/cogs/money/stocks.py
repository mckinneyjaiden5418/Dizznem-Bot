"""Stock market commands."""

import asyncio
from datetime import datetime, timezone
from typing import Literal

from bot.bot import DizznemBot
from discord import Color, Embed
from discord.ext import commands, tasks
from log import logger
from utils.money.stock_views import BuyView, SellView
from utils.money.stocks import (
    STOCK_MAP,
    USERS_DB_PATH,
    buy_stock,
    ensure_stocks_tables,
    get_all_prices,
    get_price,
    get_user_balance,
    get_user_stocks,
    is_market_open,
    refresh_prices,
    sell_stock,
)


class Stocks(commands.Cog):
    """Stock market commands."""

    def __init__(self, bot: DizznemBot) -> None:
        """Initialize the cog.

        Args:
            bot (DizznemBot): Dizznem Bot.
        """
        self.bot: DizznemBot = bot
        self._market_was_open: bool = False
        ensure_stocks_tables(USERS_DB_PATH)
        self.market_open_watcher.start()

    def cog_unload(self) -> None:
        """Stop background task on unload."""
        self.market_open_watcher.cancel()

    @tasks.loop(minutes=1)
    async def market_open_watcher(self) -> None:
        """Refresh stock prices once when the market opens each day."""
        market_open: bool = is_market_open()
        if market_open and not self._market_was_open:
            logger.info("Market opened — refreshing stock prices.")
            await asyncio.to_thread(refresh_prices, USERS_DB_PATH)
        self._market_was_open = market_open

    @market_open_watcher.before_loop
    async def before_watcher(self) -> None:
        """Wait until bot is ready before starting the loop."""
        await self.bot.wait_until_ready()
        logger.info("Refreshing stock prices on startup.")
        await asyncio.to_thread(refresh_prices, USERS_DB_PATH)

    @commands.hybrid_command(
        name="stockmarket",
        description="View all stocks and their current prices",
    )
    async def stockmarket(self, ctx: commands.Context) -> None:
        """Show all stocks, their prices, and change since market open.

        Args:
            ctx (commands.Context): Context.
        """
        prices: list[tuple[str, float, float]] = get_all_prices(USERS_DB_PATH)
        embed = Embed(
            title="📈 Stock Market",
            color=Color.green(),
            timestamp=datetime.now(timezone.utc),
        )
        for name, price, open_price in prices:
            change: float = price - open_price
            change_pct: float | Literal[0] = (
                (change / open_price * 100) if open_price else 0
            )
            arrow: Literal["🟢"] | Literal["🔴"] = (  # noqa: PYI030
                "🟢" if change >= 0 else "🔴"
            )
            embed.add_field(
                name=f"{arrow} {name}",
                value=f"**${price:,.2f}** ({change_pct:+.2f}%)",
                inline=True,
            )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="buystock", description="Buy shares of a stock")
    async def buystock(self, ctx: commands.Context, stock: str) -> None:
        """Buy shares of a stock.

        Args:
            ctx (commands.Context): Context.
            stock (str): Name of the stock to buy.
        """
        match: str | None = next(
            (n for n in STOCK_MAP if n.lower() == stock.lower()),
            None,
        )
        if match is None:
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description=f"`{stock}` is not a valid stock. Use `/stockmarket` to see all stocks.",  # noqa: E501
                ),
                ephemeral=True,
            )
            return

        price: float | None = get_price(USERS_DB_PATH, match)
        if price is None:
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description="Could not retrieve stock price.",
                ),
                ephemeral=True,
            )
            return

        balance: float = get_user_balance(ctx.author.id, ctx.author.name)
        view = BuyView(
            user_id=ctx.author.id,
            stock_name=match,
            price=price,
            balance=balance,
            execute_fn=lambda qty: buy_stock(
                USERS_DB_PATH,
                ctx.author.id,
                ctx.author.name,
                match,
                qty,
            ),
        )
        embed: Embed = BuyView.build_embed(match, price, balance, view.max_shares)
        view.message = await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="sellstock", description="Sell shares of a stock")
    async def sellstock(self, ctx: commands.Context, stock: str) -> None:
        """Sell shares of a stock.

        Args:
            ctx (commands.Context): Context.
            stock (str): Name of the stock to sell.
        """
        match: str | None = next(
            (n for n in STOCK_MAP if n.lower() == stock.lower()),
            None,
        )
        if match is None:
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description=f"`{stock}` is not a valid stock. Use `/stockmarket` to see all stocks.",  # noqa: E501
                ),
                ephemeral=True,
            )
            return

        price: float | None = get_price(USERS_DB_PATH, match)
        if price is None:
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description="Could not retrieve stock price.",
                ),
                ephemeral=True,
            )
            return

        holdings: list[tuple[str, int, float]] = get_user_stocks(
            USERS_DB_PATH,
            ctx.author.id,
        )
        owned: int = next((qty for name, qty, _ in holdings if name == match), 0)
        if owned == 0:
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description=f"You don't own any **{match}** shares.",
                ),
                ephemeral=True,
            )
            return

        view: SellView = SellView(
            user_id=ctx.author.id,
            stock_name=match,
            price=price,
            owned=owned,
            execute_fn=lambda qty: sell_stock(
                USERS_DB_PATH,
                ctx.author.id,
                ctx.author.name,
                match,
                qty,
            ),
        )
        embed: Embed = SellView.build_embed(match, price, owned)
        view.message = await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="stocks", description="View your stock portfolio")
    async def stocks(self, ctx: commands.Context) -> None:
        """Show your owned stocks and their total value.

        Args:
            ctx (commands.Context): Context.
        """
        holdings: list[tuple[str, int, float]] = get_user_stocks(
            USERS_DB_PATH,
            ctx.author.id,
        )
        if not holdings:
            await ctx.send(
                "You don't own any stocks yet. Use `/stockmarket` to browse.",
                ephemeral=True,
            )
            return

        total_value: float = sum(value for _, _, value in holdings)
        embed = Embed(
            title=f"💼 {ctx.author.display_name}'s Portfolio",
            color=Color.og_blurple(),
            description=f"**Total Value: ${total_value:,.2f}**",
        )
        for name, qty, value in holdings:
            embed.add_field(
                name=name,
                value=f"{qty} shares — **${value:,.2f}**",
                inline=True,
            )
        await ctx.send(embed=embed)


async def setup(bot: DizznemBot) -> None:
    """Load the cog.

    Args:
        bot (DizznemBot): Dizznem Bot.
    """
    await bot.add_cog(Stocks(bot))
