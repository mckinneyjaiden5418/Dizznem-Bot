"""Tic-Tac-Toe game helpers."""

WINNING_LINES: tuple[tuple[int, int, int], ...] = (
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
)


def get_winner(board: list[str | None]) -> str | None:
    """Return the winning mark, if a player has completed a line.

    Args:
        board: Nine board cells containing "X", "O", or None.

    Returns:
        The winning mark, or None when no player has won.
    """
    for first, second, third in WINNING_LINES:
        mark: str | None = board[first]
        if mark is not None and mark == board[second] == board[third]:
            return mark
    return None


def is_draw(board: list[str | None]) -> bool:
    """Return whether a board is full with no winner.

    Args:
        board: Nine board cells containing "X", "O", or None.

    Returns:
        True when every cell is occupied and neither player has won.
    """
    return all(cell is not None for cell in board) and get_winner(board) is None
