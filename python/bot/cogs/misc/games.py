"""Interactive Dizzle game commands."""

from bot.bot import DizznemBot
from discord import ButtonStyle, Interaction, Member, Message
from discord.ext import commands
from discord.ui import Button, View
from utils.misc.tictactoe import get_winner, is_draw

TIC_TAC_TOE_TIMEOUT: int = 300


class TicTacToeButton(Button):
    """A clickable Tic-Tac-Toe board cell."""

    def __init__(self, index: int) -> None:
        """Initialize a board cell.

        Args:
            index: The zero-based board position.
        """
        super().__init__(
            label="\u200b",
            style=ButtonStyle.secondary,
            row=index // 3,
        )
        self.index: int = index

    async def callback(self, interaction: Interaction) -> None:
        """Place the current player's mark in this cell."""
        view: TicTacToeView = self.view  # type: ignore[assignment]
        await view.play(interaction, self)


class TicTacToeView(View):
    """A two-player Tic-Tac-Toe board."""

    def __init__(self, player_x: Member, player_o: Member) -> None:
        """Initialize a game board.

        Args:
            player_x: The command invoker, who plays X first.
            player_o: The challenged player, who plays O.
        """
        super().__init__(timeout=TIC_TAC_TOE_TIMEOUT)
        self.players: dict[str, Member] = {"X": player_x, "O": player_o}
        self.board: list[str | None] = [None] * 9
        self.current_mark: str = "X"
        self.message: Message | None = None

        for index in range(9):
            self.add_item(TicTacToeButton(index))

    @property
    def current_player(self) -> Member:
        """Return the player whose turn it is."""
        return self.players[self.current_mark]

    def _disable_board(self) -> None:
        """Disable all board cells after a game ends."""
        for child in self.children:
            child.disabled = True  # type: ignore[union-attr]

    async def play(self, interaction: Interaction, button: TicTacToeButton) -> None:
        """Apply one legal move and update the board message.

        Args:
            interaction: The button interaction.
            button: The selected board cell.
        """
        if interaction.user.id not in {player.id for player in self.players.values()}:
            await interaction.response.send_message(
                "This is not your Dizzle board, bro.",
                ephemeral=True,
            )
            return
        if interaction.user.id != self.current_player.id:
            await interaction.response.send_message(
                "Hold your horses - it is not your turn yet.",
                ephemeral=True,
            )
            return
        if self.board[button.index] is not None:
            await interaction.response.send_message(
                "That square is already claimed.",
                ephemeral=True,
            )
            return

        self.board[button.index] = self.current_mark
        button.label = self.current_mark
        button.style = ButtonStyle.success if self.current_mark == "X" else ButtonStyle.danger
        button.disabled = True

        winner: str | None = get_winner(self.board)
        if winner is not None:
            self._disable_board()
            await interaction.response.edit_message(
                content=f"{self.players[winner].mention} wins. Dizzle certified.",
                view=self,
            )
            return
        if is_draw(self.board):
            self._disable_board()
            await interaction.response.edit_message(
                content="It is a draw. Both of you cooked, apparently.",
                view=self,
            )
            return

        self.current_mark = "O" if self.current_mark == "X" else "X"
        await interaction.response.edit_message(
            content=f"{self.current_player.mention}'s turn ({self.current_mark}).",
            view=self,
        )

    async def on_timeout(self) -> None:
        """Disable the board after five minutes of inactivity."""
        self._disable_board()
        if self.message is not None:
            await self.message.edit(
                content="Tic-Tac-Toe timed out. The board has been retired.",
                view=self,
            )


class Games(commands.Cog):
    """Interactive Dizzle game commands."""

    def __init__(self, bot: DizznemBot) -> None:
        """Initialize Games.

        Args:
            bot: The Dizznem Bot instance.
        """
        self.bot: DizznemBot = bot

    @commands.hybrid_command(
        name="tictactoe",
        description="Challenge someone to Tic-Tac-Toe",
        aliases=["ttt"],
    )
    async def tictactoe(self, ctx: commands.Context, opponent: Member) -> None:
        """Start a Tic-Tac-Toe game.

        Args:
            ctx: The command context.
            opponent: The member challenged to play O.
        """
        if opponent.id == ctx.author.id:
            await ctx.send("You cannot challenge yourself.", ephemeral=True)
            return
        if opponent.bot:
            await ctx.send("Bots do not play Tic-Tac-Toe. They have scripts to write.", ephemeral=True)
            return

        player_x: Member = ctx.author  # type: ignore[assignment]
        view: TicTacToeView = TicTacToeView(player_x, opponent)
        message: Message = await ctx.send(
            f"{player_x.mention} is X. {opponent.mention} is O. "
            f"{player_x.mention}'s turn (X).",
            view=view,
        )
        view.message = message


async def setup(bot: DizznemBot) -> None:
    """Load the Games cog.

    Args:
        bot: The Dizznem Bot instance.
    """
    await bot.add_cog(Games(bot))
