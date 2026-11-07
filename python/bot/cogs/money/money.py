"""Money bot commands."""

from typing import Final

from bot.bot import DizznemBot
from discord import Asset, Color, Embed, Member, Message
from discord.ext import commands
from log import logger  # noqa: F401
from user import User
from utils.general import reset_cd
from utils.money.stocks import USERS_DB_PATH
from utils.money.store_views import StoreView
from utils.numbers import convert_money_str, format_number, get_net_worth


class Money(commands.Cog):
    """Money bot commands."""

    def __init__(self, bot: DizznemBot) -> None:
        """Initiate Money.

        Args:
            bot (commands.Bot): Dizznem Bot.
        """
        self.bot: commands.Bot = bot

    @commands.hybrid_command(
        name="balance",
        description="Get your balance",
        aliases=["bal"],
    )
    async def balance(self, ctx: commands.Context, member: Member | None = None) -> None:
        """Balance command.

        Args:
            ctx (commands.Context): Context.
            member (Member | None): Member if mentioned.
        """
        user_id: int = member.id if member else ctx.author.id
        username: str = member.name if member else ctx.author.name
        display_name: str = member.display_name if member else ctx.author.display_name
        avatar_url: str = (
            member.display_avatar.url if member else ctx.author.display_avatar.url
        )

        user: User = User.create_if_not_exists(user_id=user_id, username=username)

        embed: Embed = Embed(
            title=f"💰 {display_name}'s Balance",
            color=Color.og_blurple(),
            description=f"## ${format_number(user.money)}",
        )
        embed.set_thumbnail(url=avatar_url)
        embed.set_footer(text=f"User ID: {user_id}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="give",
        description="Give your money to another user",
        aliases=["transfer"],
    )
    @commands.cooldown(rate=1, per=3600, type=commands.BucketType.user)
    async def give(
        self,
        ctx: commands.Context,
        member: Member,
        amount: str,
    ) -> None:
        """Give command.

        Args:
            ctx (commands.Context): Context.
            member (Member | None): Member to give money to.
            amount (str): Amount to give.
        """
        try:
            amount_float: float = convert_money_str(money_str=amount)
        except ValueError:
            reset_cd(ctx=ctx)
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description="Invalid money format.",
                ),
                ephemeral=True,
            )
            return

        if amount_float <= 0:
            reset_cd(ctx=ctx)
            embed: Embed = Embed(
                title="Error",
                color=Color.red(),
                description="Amount must be greater than 0.",
            )
            await ctx.send(embed=embed, ephemeral=True)
            return

        MAX_TRANSFER_AMOUNT: Final[int] = 5_000_000

        if amount_float > MAX_TRANSFER_AMOUNT:
            reset_cd(ctx=ctx)
            embed: Embed = Embed(
                title="Error",
                color=Color.red(),
                description="Amount must be less than or equal to 5 Million.",
            )
            await ctx.send(embed=embed, ephemeral=True)
            return

        if member.id == ctx.author.id:
            reset_cd(ctx=ctx)
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description="You cannot give money to yourself.",
                ),
                ephemeral=True,
            )
            return

        formatted_amount: str = format_number(number=amount_float)
        sender_id: int = ctx.author.id
        sender_username: str = ctx.author.name
        recipient_id: int = member.id
        recipient_username: str = member.name
        recipient_display_name: str = member.display_name

        sender_user: User = User.create_if_not_exists(
            user_id=sender_id,
            username=sender_username,
        )

        if sender_user.money < amount_float:
            reset_cd(ctx=ctx)
            embed: Embed = Embed(
                title="Error",
                color=Color.red(),
                description="You do not have enough money to send this amount.",
            )
            await ctx.send(embed=embed, ephemeral=True)
            return

        recipient_user: User = User.create_if_not_exists(
            user_id=recipient_id,
            username=recipient_username,
        )

        recipient_user.money += amount_float
        sender_user.money -= amount_float

        embed: Embed = Embed(
            title="💸 Success",
            color=Color.green(),
            description=f"Successfully gave {recipient_display_name} ${formatted_amount}",
        )

        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="networth",
        description="Get your net worth",
    )
    async def networth(
        self,
        ctx: commands.Context,
        member: Member | None = None,
    ) -> None:
        """Net worth command.

        Args:
            ctx (commands.Context): Context.
            member (Member | None): Member if mentioned.
        """
        user_id: int = member.id if member else ctx.author.id
        username: str = member.name if member else ctx.author.name
        display_name: str = member.display_name if member else ctx.author.display_name
        avatar: Asset | None = member.avatar if member else ctx.author.avatar

        user: User = User.create_if_not_exists(user_id=user_id, username=username)
        total_networth: float = get_net_worth(user=user, db_path=USERS_DB_PATH)
        stock_value: float = total_networth - user.money

        embed: Embed = Embed(
            title="Net Worth",
            color=Color.og_blurple(),
            description=f"${format_number(number=total_networth)}",
        )
        embed.add_field(
            name="Balance",
            value=f"${format_number(number=user.money)}",
            inline=True,
        )
        embed.add_field(
            name="Stocks",
            value=f"${format_number(number=stock_value)}",
            inline=True,
        )
        embed.set_author(name=display_name, icon_url=avatar)

        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="store",
        description="View the store",
        aliases=["shop"],
    )
    async def store(self, ctx: commands.Context) -> None:
        """Store command.

        Args:
            ctx (commands.Context): Context.
        """
        user: User = User.create_if_not_exists(
            user_id=ctx.author.id,
            username=ctx.author.name,
        )

        view = StoreView(
            user_id=ctx.author.id,
            balance=user.money,
            prestige=user.prestige,
            bot=self.bot,
        )
        embed: Embed = StoreView.build_embed(
            balance=user.money,
            prestige=user.prestige,
        )
        message: Message = await ctx.send(embed=embed, view=view)
        view.message = message


async def setup(bot: DizznemBot) -> None:
    """Setup for money.

    Args:
        bot (commands.Bot): Dizznem Bot
    """
    await bot.add_cog(Money(bot))
