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


async def setup(bot: DizznemBot) -> None:
    """Setup for Admin.

    Args:
        bot (DizznemBot): Dizznem Bot.
    """
    await bot.add_cog(Admin(bot))
