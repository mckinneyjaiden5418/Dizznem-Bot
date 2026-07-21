"""Warning system moderation commands.

$warn / $warnings / $delwarn -- the foundation moderation primitive that
later Phase 2 features (automod, mute escalation, mod logs) build on top of.
"""

from bot.bot import DizznemBot
from discord import Color, Embed, Member
from discord.ext import commands
from log import logger  # noqa: F401
from utils.moderation.warnings import (
    WARNINGS_DB_PATH,
    WarningRecord,
    add_warning,
    count_warnings,
    delete_warning,
    get_warnings,
    validate_reason,
)

MAX_WARNINGS_DISPLAYED: int = 25


class Moderation(commands.Cog):
    """Warning system moderation commands."""

    def __init__(self, bot: DizznemBot) -> None:
        """Initialize Moderation.

        Args:
            bot (DizznemBot): Dizznem Bot.
        """
        self.bot: DizznemBot = bot

    @commands.hybrid_command(
        name="warn",
        description="Issue a persistent warning to a user (mod command).",
    )
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    async def warn(
        self,
        ctx: commands.Context,
        member: Member,
        *,
        reason: str,
    ) -> None:
        """Issue a persistent warning to a user.

        Args:
            ctx (commands.Context): Context.
            member (Member): Member to warn.
            reason (str): Reason for the warning.
        """
        if ctx.guild is None:
            return

        if member.bot:
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description="You cannot warn bots.",
                ),
                ephemeral=True,
            )
            return

        if member.id == ctx.author.id:
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description="You cannot warn yourself.",
                ),
                ephemeral=True,
            )
            return

        is_valid: bool
        error_message: str
        is_valid, error_message = validate_reason(reason)
        if not is_valid:
            await ctx.send(
                embed=Embed(title="Error", color=Color.red(), description=error_message),
                ephemeral=True,
            )
            return

        warning: WarningRecord = add_warning(
            WARNINGS_DB_PATH,
            guild_id=ctx.guild.id,
            user_id=member.id,
            moderator_id=ctx.author.id,
            reason=reason.strip(),
        )
        total: int = count_warnings(WARNINGS_DB_PATH, ctx.guild.id, member.id)

        embed: Embed = Embed(
            title="⚠️ User Warned",
            color=Color.orange(),
            description=(
                f"**{member.display_name}** has been warned by "
                f"**{ctx.author.display_name}**.\n\n"
                f"**Reason:** {warning['reason']}"
            ),
        )
        embed.set_footer(text=f"Warning ID: {warning['id']} • Total warnings: {total}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="warnings",
        description="View a user's warning history.",
    )
    @commands.guild_only()
    async def warnings_cmd(
        self,
        ctx: commands.Context,
        member: Member | None = None,
    ) -> None:
        """View a user's warning history.

        Viewing your own warnings is always allowed. Viewing someone else's
        requires the Moderate Members permission.

        Args:
            ctx (commands.Context): Context.
            member (Member | None): Member to view warnings for (defaults to self).
        """
        if ctx.guild is None:
            return

        target: Member = member or ctx.author  # pyright: ignore[reportAssignmentType]

        if target.id != ctx.author.id and not ctx.author.guild_permissions.moderate_members:
            await ctx.send(
                embed=Embed(
                    title="Missing Permissions",
                    color=Color.red(),
                    description="You do not have permission to view other users' warnings.",
                ),
                ephemeral=True,
            )
            return

        records: list[WarningRecord] = get_warnings(WARNINGS_DB_PATH, ctx.guild.id, target.id)

        if not records:
            await ctx.send(
                embed=Embed(
                    title="ℹ️ No Warnings",  # noqa: RUF001
                    color=Color.blue(),
                    description=f"**{target.display_name}** has no warnings on record.",
                ),
            )
            return

        shown: list[WarningRecord] = records[-MAX_WARNINGS_DISPLAYED:]
        lines: list[str] = [
            f"**#{record['id']}** — <@{record['moderator_id']}>\n{record['reason']}"
            for record in shown
        ]

        embed: Embed = Embed(
            title=f"⚠️ Warnings for {target.display_name}",
            color=Color.orange(),
            description="\n\n".join(lines),
        )
        footer: str = f"Total warnings: {len(records)}"
        if len(records) > MAX_WARNINGS_DISPLAYED:
            footer += f" (showing most recent {MAX_WARNINGS_DISPLAYED})"
        embed.set_footer(text=footer)
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="delwarn",
        description="Remove a specific warning by ID (mod command).",
    )
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    async def delwarn(self, ctx: commands.Context, warning_id: int) -> None:
        """Remove a specific warning by its ID.

        Args:
            ctx (commands.Context): Context.
            warning_id (int): ID of the warning to remove.
        """
        if ctx.guild is None:
            return

        deleted: bool = delete_warning(WARNINGS_DB_PATH, ctx.guild.id, warning_id)

        if not deleted:
            await ctx.send(
                embed=Embed(
                    title="Error",
                    color=Color.red(),
                    description=f"No warning with ID **{warning_id}** was found.",
                ),
                ephemeral=True,
            )
            return

        embed: Embed = Embed(
            title="✅ Warning Removed",
            color=Color.green(),
            description=f"Warning **#{warning_id}** has been removed.",
        )
        await ctx.send(embed=embed)


async def setup(bot: DizznemBot) -> None:
    """Setup for Moderation.

    Args:
        bot (DizznemBot): Dizznem Bot.
    """
    await bot.add_cog(Moderation(bot))
