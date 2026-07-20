"""Money bot commands."""

import random
from typing import Final

import aiohttp
from bot.bot import DizznemBot
from discord import Color, Embed, Member, Message
from discord.ext import commands
from log import logger  # noqa: F401
from user import User
from utils.general import get_user_answer, reset_cd
from utils.money.roblox import check_answer, question
from utils.money.steal import MIN_TARGET_BALANCE, MIN_THIEF_BALANCE, resolve_steal
from utils.money.trivia import VALID_ANSWERS, build_trivia_embed, get_random_question
from utils.numbers import convert_money_str, format_number


class MoneyMaking(commands.Cog):
    """Money making bot commands."""

    def __init__(self, bot: DizznemBot) -> None:
        """Initiate Money.

        Args:
            bot (commands.Bot): Dizznem Bot.
        """
        self.bot: commands.Bot = bot

    # NOTE: Could probably refactor daily and weekly command to use 1 function as a way to prevent
    # redundant code.

    @commands.hybrid_command(
        name="daily",
        description="Daily money",
    )
    @commands.cooldown(rate=1, per=86400, type=commands.BucketType.user)
    async def daily(self, ctx: commands.Context) -> None:
        """Daily command.

        Args:
            ctx (commands.Context): Context.
        """
        user_id: int = ctx.author.id
        username: str = ctx.author.name
        user: User = User.create_if_not_exists(user_id=user_id, username=username)
        daily_value: int = random.randint(100_000, 1_000_000) * (  # noqa: S311
            user.prestige + 1
        )
        formatted_daily_value: str = format_number(number=daily_value)

        user.money += daily_value

        embed: Embed = Embed(
            title="💰 Daily",
            color=Color.green(),
            description=f"You earned **${formatted_daily_value}**",
        )

        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="weekly",
        description="Weekly money",
    )
    @commands.cooldown(rate=1, per=604800, type=commands.BucketType.user)
    async def weekly(self, ctx: commands.Context) -> None:
        """Weekly command.

        Args:
            ctx (commands.Context): Context.
        """
        user_id: int = ctx.author.id
        username: str = ctx.author.name
        user: User = User.create_if_not_exists(user_id=user_id, username=username)
        weekly_value: int = random.randint(1_000_000, 5_000_000) * (  # noqa: S311
            user.prestige + 1
        )
        formatted_weekly_value: str = format_number(number=weekly_value)

        user.money += weekly_value

        embed: Embed = Embed(
            title="🤑 Weekly",
            color=Color.green(),
            description=f"You earned **${formatted_weekly_value}**",
        )

        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="gamble",
        description="Gamble your money",
        aliases=["gamba"],
    )
    @commands.cooldown(rate=1, per=3, type=commands.BucketType.user)
    async def gamble(self, ctx: commands.Context, amount: str) -> None:
        """Gamble command.

        Args:
            ctx (commands.Context): Context.
            amount (str): Gamble amount, all, half, or numerical.
        """
        user_id: int = ctx.author.id
        username: str = ctx.author.name
        user: User = User.create_if_not_exists(user_id=user_id, username=username)

        try:
            if amount.lower() == "all":
                gamble_amount: float = user.money
            elif amount.lower() == "half":
                gamble_amount: float = user.money / 2
            else:
                gamble_amount: float = convert_money_str(money_str=amount)
        except ValueError:
            reset_cd(ctx=ctx)
            embed: Embed = Embed(
                title="❌ Invalid Amount",
                color=Color.red(),
                description=(
                    f"**{amount}** isn't a valid amount.\n\n"
                    "Try a number like `500`, `1,000`, or `$250` — "
                    "or use `all` / `half`."
                ),
            )
            await ctx.send(embed=embed, ephemeral=True)
            return

        user_money_rounded: float = round(user.money, 2)
        gamble_amount = round(gamble_amount, 2)

        if gamble_amount <= 0:
            reset_cd(ctx=ctx)
            embed: Embed = Embed(
                title="Error",
                color=Color.red(),
                description="Gamble amount must be greater than 0.",
            )
            await ctx.send(embed=embed, ephemeral=True)
            return

        if user_money_rounded < gamble_amount:
            reset_cd(ctx=ctx)
            embed: Embed = Embed(
                title="❌ Not Enough Money",
                color=Color.red(),
                description=(
                    f"You only have **${format_number(user_money_rounded)}** "
                    f"but tried to gamble **${format_number(gamble_amount)}**."
                ),
            )
            await ctx.send(embed=embed, ephemeral=True)
            return

        WIN: Final[int] = 400
        LOSE: Final[int] = 950
        TRIPLE_WIN: Final[int] = 999
        roll: int = random.randint(1, 1000)  # noqa: S311
        formatted_amount: str = format_number(number=gamble_amount)

        if roll <= WIN:
            user.money += gamble_amount
            embed: Embed = Embed(
                title="🎉 You won!",
                color=Color.green(),
                description=f"You won **${formatted_amount}**!",
            )
        elif roll <= LOSE:
            user.money -= gamble_amount
            embed: Embed = Embed(
                title="💀 You Lost",
                color=Color.red(),
                description=f"You lost **${formatted_amount}**!",
            )
        elif roll <= TRIPLE_WIN:
            winnings: float = gamble_amount * 3
            formatted_winnings: str = format_number(number=winnings)
            user.money += winnings
            embed: Embed = Embed(
                title="🔥 3x WIN!",
                color=Color.green(),
                description=f"You won **${formatted_winnings}**!",
            )
        else:
            winnings: float = gamble_amount * 10
            formatted_winnings: str = format_number(number=winnings)
            user.money += winnings
            embed: Embed = Embed(
                title="💎 JACKPOT!",
                color=Color.gold(),
                description=f"You hit the jackpot and won **${formatted_winnings}**!",
            )

        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="steal",
        description="Attempt to steal money from another user",
    )
    @commands.cooldown(rate=1, per=3600, type=commands.BucketType.user)
    async def steal(self, ctx: commands.Context, member: Member) -> None:
        """Steal command.

        Args:
            ctx (commands.Context): Context.
            member (Member): Member to attempt to steal from.
        """
        if member.id == ctx.author.id:
            reset_cd(ctx=ctx)
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description="You cannot steal from yourself.",
                ),
                ephemeral=True,
            )
            return

        thief: User = User.create_if_not_exists(
            user_id=ctx.author.id,
            username=ctx.author.name,
        )
        target: User = User.create_if_not_exists(
            user_id=member.id, username=member.name,
        )

        if thief.money < MIN_THIEF_BALANCE:
            reset_cd(ctx=ctx)
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description="You need at least $1,000 to attempt a steal.",
                ),
                ephemeral=True,
            )
            return

        if target.money < MIN_TARGET_BALANCE:
            reset_cd(ctx=ctx)
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description=f"**{member.display_name}** doesn't have enough money to be worth stealing from.",  # noqa: E501
                ),
                ephemeral=True,
            )
            return

        success: bool
        amount: float
        success, amount = resolve_steal(
            stealer_money=thief.money,
            target_money=target.money,
        )

        if success:
            thief.money += amount
            target.money -= amount
            embed: Embed = Embed(
                title="🕵️ Heist Successful",
                color=Color.green(),
                description=f"You stole **${format_number(amount)}** from **{member.display_name}**!",  # noqa: E501
            )
        else:
            thief.money -= amount
            embed: Embed = Embed(
                title="🚨 Caught!",
                color=Color.red(),
                description=f"You got caught trying to steal from **{member.display_name}** and paid a **${format_number(amount)}** fine!",  # noqa: E501
            )

        await ctx.send(embed=embed)

    async def run_roblox_trivia(self, ctx: commands.Context, game: str) -> None:
        """Run Roblox trivia.

        Args:
            ctx (commands.Context): Context.
            game (str): "aba" or "rogue".
        """
        title: str = "ABA Trivia" if game == "aba" else "Rogue Lineage Trivia"

        user_id: int = ctx.author.id
        username: str = ctx.author.name
        user: User = User.create_if_not_exists(user_id=user_id, username=username)
        earnings: int = random.randint(25000, 50000) * (user.prestige + 1)  # noqa: S311

        loading_message: Message = await ctx.send(
            embed=Embed(
                title=title,
                description="Loading question...",
                color=Color.og_blurple(),
            ),
        )

        try:
            image_url: str | None
            trivia_question: str
            answer: str
            image_url, trivia_question, answer = await question(game=game)
        except aiohttp.ClientError:
            await loading_message.edit(
                embed=Embed(
                    title="⚠️ Wiki Unavailable",
                    description="Couldn't reach the wiki right now. Try again in a moment.",
                    color=Color.orange(),
                ),
            )
            return

        question_embed: Embed = Embed(
            title=title,
            color=Color.og_blurple(),
            description=trivia_question,
        )

        if image_url:
            question_embed.set_image(url=image_url)
        else:
            question_embed.set_footer(text="(No image available for this entry)")

        await loading_message.edit(embed=question_embed)

        user_answer: str | None = await get_user_answer(
            bot=self.bot,
            ctx=ctx,
        )

        if user_answer is None:
            user.money -= earnings
            embed: Embed = Embed(
                title="⏰ Time's Up!",
                description=f"You lost $**{format_number(earnings)}!**\n\nThe correct answer was **{answer}**.",  # noqa: E501
                color=Color.red(),
            )
            await ctx.send(embed=embed)
            return

        if check_answer(answer=answer, user_answer=user_answer):
            user.money += earnings
            embed: Embed = Embed(
                title="✅ Correct!",
                description=f"You won **${format_number(earnings)}**!\n\nThe answer was **{answer}**.",  # noqa: E501
                color=Color.green(),
            )
            await ctx.send(embed=embed)
        else:
            user.money -= earnings
            embed: Embed = Embed(
                title="❌ Incorrect",
                description=f"You lost **${format_number(earnings)}**!\n\nThe correct answer was **{answer}**.",  # noqa: E501
                color=Color.red(),
            )
            await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="aba",
        description="Anime Battle Arena trivia for money",
        aliases=["animebattlearena"],
    )
    @commands.cooldown(rate=1, per=60, type=commands.BucketType.user)
    async def aba(self, ctx: commands.Context) -> None:
        """ABA command.

        Args:
            ctx (commands.Context): Context.
        """
        await self.run_roblox_trivia(ctx, "aba")

    @commands.hybrid_command(
        name="roguelineage",
        description="Rogue Lineage trivia for money",
        aliases=["rogue"],
    )
    @commands.cooldown(rate=1, per=60, type=commands.BucketType.user)
    async def rogue(self, ctx: commands.Context) -> None:
        """Rogue command.

        Args:
            ctx (commands.Context): Context.
        """
        await self.run_roblox_trivia(ctx, "rogue")

    @commands.hybrid_command(
        name="trivia",
        description="Trivia for money",
    )
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.user)
    async def trivia(self, ctx: commands.Context) -> None:
        """Trivia command.

        Args:
            ctx (commands.Context): Context.
        """
        user_id: int = ctx.author.id
        username: str = ctx.author.name
        user: User = User.create_if_not_exists(user_id=user_id, username=username)
        earnings: int = random.randint(5_000, 10_000) * (  # noqa: S311
            user.prestige + 1
        )

        question: str
        choices: list[str]
        answer: str
        question, choices, answer = get_random_question()
        embed: Embed = build_trivia_embed(question, choices)
        await ctx.send(embed=embed)

        user_answer: str | None = await get_user_answer(bot=self.bot, ctx=ctx)

        if user_answer is None:
            reset_cd(ctx=ctx)
            await ctx.send(
                embed=Embed(
                    title="⏰ Time's Up!",
                    color=Color.red(),
                    description="You took too long to answer!",
                ),
            )
            return

        if user_answer.lower() not in VALID_ANSWERS:
            reset_cd(ctx=ctx)
            await ctx.send(
                embed=Embed(
                    title="❌ Invalid Answer",
                    color=Color.red(),
                    description="Please answer with **a**, **b**, **c**, or **d**.",
                ),
                ephemeral=True,
            )
            return

        formatted_earnings: str = format_number(number=earnings)
        if user_answer.lower() == answer:
            user.money += earnings
            await ctx.send(
                embed=Embed(
                    title="✅ Correct!",
                    color=Color.green(),
                    description=f"You won **${formatted_earnings}**!",
                ),
            )
        else:
            user.money -= earnings
            answer_text: str = choices[ord(answer) - ord("a")]
            await ctx.send(
                embed=Embed(
                    title="❌ Incorrect",
                    color=Color.red(),
                    description=(
                        f"You lost **${formatted_earnings}**!\n\n"
                        f"The correct answer was **{answer.upper()}. {answer_text}**."
                    ),
                ),
            )


async def setup(bot: DizznemBot) -> None:
    """Setup for money making.

    Args:
        bot (commands.Bot): Dizznem Bot
    """
    await bot.add_cog(MoneyMaking(bot))
