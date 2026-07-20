"""Prediction market commands."""

from datetime import datetime, timezone

from bot.bot import DizznemBot
from discord import Color, Embed
from discord.ext import commands
from log import logger  # noqa: F401
from user import User
from utils.money.prediction_market import (
    USERS_DB_PATH,
    create_market,
    ensure_prediction_market_tables,
    get_market,
    get_market_pools,
    get_open_markets,
    get_user_bets,
    place_bet,
)
from utils.numbers import convert_money_str, format_number


def _odds_text(yes_total: float, no_total: float) -> str:
    """Build a "Yes X% / No Y%" odds string from pool totals.

    Args:
        yes_total (float): Total staked on Yes.
        no_total (float): Total staked on No.

    Returns:
        str: Formatted odds string.
    """
    total: float = yes_total + no_total
    if total == 0:
        return "No bets yet"
    yes_pct: float = yes_total / total * 100
    no_pct: float = no_total / total * 100
    return f"Yes {yes_pct:.0f}% / No {no_pct:.0f}%"


class PredictionMarket(commands.Cog):
    """Prediction market commands."""

    def __init__(self, bot: DizznemBot) -> None:
        """Initialize the cog.

        Args:
            bot (DizznemBot): Dizznem Bot.
        """
        self.bot: DizznemBot = bot
        ensure_prediction_market_tables(USERS_DB_PATH)

    @commands.hybrid_command(
        name="createmarket",
        description="Create a new yes/no prediction market",
        aliases=["newmarket"],
    )
    @commands.cooldown(rate=1, per=300, type=commands.BucketType.user)
    async def create_market_cmd(self, ctx: commands.Context, *, question: str) -> None:
        """Create a new prediction market.

        Args:
            ctx (commands.Context): Context.
            question (str): The yes/no question being predicted.
        """
        success, message = create_market(USERS_DB_PATH, ctx.author.id, question)
        if not success:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(
                embed=Embed(title="Error", color=Color.red(), description=message),
                ephemeral=True,
            )
            return

        await ctx.send(
            embed=Embed(
                title="🔮 Market Created",
                color=Color.green(),
                description=f"{message}\n\nUse `/predict` to bet on it.",
            ),
        )

    @commands.hybrid_command(
        name="markets",
        description="View all open prediction markets",
    )
    async def markets(self, ctx: commands.Context) -> None:
        """List all open prediction markets.

        Args:
            ctx (commands.Context): Context.
        """
        open_markets: list[tuple[int, str, int]] = get_open_markets(USERS_DB_PATH)
        if not open_markets:
            await ctx.send(
                "There are no open prediction markets right now. Use `/createmarket` to start one.",  # noqa: E501
                ephemeral=True,
            )
            return

        embed = Embed(
            title="🔮 Open Prediction Markets",
            color=Color.og_blurple(),
            timestamp=datetime.now(timezone.utc),
        )
        for market_id, question, _creator_id in open_markets:
            yes_total, no_total = get_market_pools(USERS_DB_PATH, market_id)
            pool: float = yes_total + no_total
            embed.add_field(
                name=f"#{market_id} — {question}",
                value=f"{_odds_text(yes_total, no_total)} • Pool: **${pool:,.2f}**",
                inline=False,
            )
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="market",
        description="View details about a specific prediction market",
    )
    async def market(self, ctx: commands.Context, market_id: int) -> None:
        """Show details for a single prediction market.

        Args:
            ctx (commands.Context): Context.
            market_id (int): Market ID.
        """
        market_row: tuple | None = get_market(USERS_DB_PATH, market_id)
        if market_row is None:
            await ctx.send(f"Market **#{market_id}** does not exist.", ephemeral=True)
            return

        _id, question, creator_id, status, outcome, _created_at, _resolved_at = market_row
        yes_total, no_total = get_market_pools(USERS_DB_PATH, market_id)
        pool: float = yes_total + no_total

        color: Color = Color.og_blurple() if status == "open" else Color.greyple()
        embed = Embed(
            title=f"🔮 Market #{market_id}",
            color=color,
            description=question,
        )
        embed.add_field(name="Status", value=status.capitalize(), inline=True)
        if outcome is not None:
            embed.add_field(name="Outcome", value=outcome.upper(), inline=True)
        embed.add_field(name="Pool", value=f"${pool:,.2f}", inline=True)
        embed.add_field(name="Yes Pool", value=f"${yes_total:,.2f}", inline=True)
        embed.add_field(name="No Pool", value=f"${no_total:,.2f}", inline=True)
        embed.add_field(name="Odds", value=_odds_text(yes_total, no_total), inline=True)
        embed.set_footer(text=f"Created by user ID {creator_id}")

        bets: list[tuple[str, float]] = get_user_bets(USERS_DB_PATH, market_id, ctx.author.id)
        if bets:
            your_bets: str = "\n".join(
                f"**${amount:,.2f}** on {side.upper()}" for side, amount in bets
            )
            embed.add_field(name="Your Bets", value=your_bets, inline=False)

        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="predict",
        description="Bet on a prediction market",
    )
    async def predict(
        self,
        ctx: commands.Context,
        market_id: int,
        side: str,
        amount: str,
    ) -> None:
        """Place a bet on a prediction market.

        Args:
            ctx (commands.Context): Context.
            market_id (int): Market ID to bet on.
            side (str): "yes" or "no".
            amount (str): Amount to stake.
        """
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

        success, message = place_bet(
            USERS_DB_PATH,
            ctx.author.id,
            ctx.author.name,
            market_id,
            side,
            amount_float,
        )

        if not success:
            await ctx.send(
                embed=Embed(title="Error", color=Color.red(), description=message),
                ephemeral=True,
            )
            return

        user: User = User.create_if_not_exists(user_id=ctx.author.id, username=ctx.author.name)
        await ctx.send(
            embed=Embed(
                title="🔮 Bet Placed",
                color=Color.green(),
                description=(
                    f"{message}\n\nNew balance: **${format_number(user.money)}**"
                ),
            ),
        )


async def setup(bot: DizznemBot) -> None:
    """Load the cog.

    Args:
        bot (DizznemBot): Dizznem Bot.
    """
    await bot.add_cog(PredictionMarket(bot))
