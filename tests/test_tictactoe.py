"""Tests for Tic-Tac-Toe game helpers."""

import pytest
from utils.misc.tictactoe import get_winner, is_draw


@pytest.mark.parametrize(
    ("board", "winner"),
    [
        (["X", "X", "X", None, None, None, None, None, None], "X"),
        ([None, None, None, "O", "O", "O", None, None, None], "O"),
        (["X", None, None, "X", None, None, "X", None, None], "X"),
        (["O", None, None, None, "O", None, None, None, "O"], "O"),
    ],
)
def test_get_winner_returns_completed_line(
    board: list[str | None],
    winner: str,
) -> None:
    """Rows, columns, and diagonals produce a winner."""
    assert get_winner(board) == winner


def test_get_winner_returns_none_without_completed_line() -> None:
    """An unfinished board has no winner."""
    assert get_winner(["X", "O", None, None, None, None, None, None, None]) is None


def test_is_draw_requires_full_board_without_winner() -> None:
    """A full non-winning board is a draw."""
    board: list[str | None] = ["X", "O", "X", "X", "O", "O", "O", "X", "X"]
    assert is_draw(board) is True


def test_is_draw_rejects_winning_board() -> None:
    """A full board with a winner is not a draw."""
    board: list[str | None] = ["X", "X", "X", "O", "O", "X", "O", "X", "O"]
    assert is_draw(board) is False
