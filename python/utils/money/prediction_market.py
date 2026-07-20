"""Prediction market utilities.

Binary (yes/no) prediction markets, pari-mutuel style: bettors stake money on
either side while a market is open, and once an admin resolves it, the total
pool (both sides combined) is split among winners proportionally to their
stake. Money is deducted from a bettor's balance the moment they bet, so a
losing stake is simply never returned -- there's no separate escrow ledger to
reconcile.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from user import User

USERS_DB_PATH: Path = Path("data/users.db")
QUESTION_MAX_LENGTH: int = 200
VALID_SIDES: set[str] = {"yes", "no"}


def ensure_prediction_market_tables(db_path: Path) -> None:
    """Create prediction_markets and prediction_bets tables if they don't exist.

    Args:
        db_path (Path): Path to users.db.
    """
    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS prediction_markets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                question    TEXT NOT NULL,
                creator_id  INTEGER NOT NULL,
                status      TEXT NOT NULL DEFAULT 'open',
                outcome     TEXT,
                created_at  TEXT NOT NULL,
                resolved_at TEXT
            )
            """,
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS prediction_bets (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id  INTEGER NOT NULL,
                user_id    INTEGER NOT NULL,
                side       TEXT NOT NULL,
                amount     REAL NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (market_id) REFERENCES prediction_markets (id)
            )
            """,
        )
        conn.commit()


def create_market(db_path: Path, creator_id: int, question: str) -> tuple[bool, str]:
    """Create a new open prediction market.

    Args:
        db_path (Path): Path to users.db.
        creator_id (int): Discord user ID of the market creator.
        question (str): The yes/no question being predicted.

    Returns:
        tuple[bool, str]: (success, message)
    """
    question = question.strip()
    if not question:
        return False, "Question cannot be empty."
    if len(question) > QUESTION_MAX_LENGTH:
        return False, f"Question must be {QUESTION_MAX_LENGTH} characters or fewer."

    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO prediction_markets (question, creator_id, status, created_at)
            VALUES (?, ?, 'open', ?)
            """,
            (question, creator_id, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        market_id: int = cursor.lastrowid  # type: ignore[assignment]

    return True, f"Market **#{market_id}** created: {question}"


def get_market(db_path: Path, market_id: int) -> tuple | None:
    """Get a market by ID.

    Args:
        db_path (Path): Path to users.db.
        market_id (int): Market ID.

    Returns:
        tuple | None: (id, question, creator_id, status, outcome, created_at,
        resolved_at), or None if it doesn't exist.
    """
    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, question, creator_id, status, outcome, created_at, resolved_at
            FROM prediction_markets WHERE id = ?
            """,
            (market_id,),
        )
        return cursor.fetchone()


def get_open_markets(db_path: Path) -> list[tuple[int, str, int]]:
    """Get all open markets.

    Args:
        db_path (Path): Path to users.db.

    Returns:
        list[tuple[int, str, int]]: List of (id, question, creator_id).
    """
    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, question, creator_id FROM prediction_markets
            WHERE status = 'open' ORDER BY id DESC
            """,
        )
        return cursor.fetchall()


def get_market_pools(db_path: Path, market_id: int) -> tuple[float, float]:
    """Get the total amount staked on each side of a market.

    Args:
        db_path (Path): Path to users.db.
        market_id (int): Market ID.

    Returns:
        tuple[float, float]: (yes_total, no_total)
    """
    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute(
            """
            SELECT side, SUM(amount) FROM prediction_bets
            WHERE market_id = ? GROUP BY side
            """,
            (market_id,),
        )
        totals: dict[str, float] = dict(cursor.fetchall())

    return totals.get("yes", 0.0), totals.get("no", 0.0)


def get_user_bets(db_path: Path, market_id: int, user_id: int) -> list[tuple[str, float]]:
    """Get a user's total stake on each side of a market.

    Args:
        db_path (Path): Path to users.db.
        market_id (int): Market ID.
        user_id (int): Discord user ID.

    Returns:
        list[tuple[str, float]]: List of (side, total_amount).
    """
    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute(
            """
            SELECT side, SUM(amount) FROM prediction_bets
            WHERE market_id = ? AND user_id = ? GROUP BY side
            """,
            (market_id, user_id),
        )
        return cursor.fetchall()


def place_bet(
    db_path: Path,
    user_id: int,
    username: str,
    market_id: int,
    side: str,
    amount: float,
) -> tuple[bool, str]:
    """Place a bet on one side of a prediction market.

    Args:
        db_path (Path): Path to users.db.
        user_id (int): Discord user ID.
        username (str): Discord username.
        market_id (int): Market ID to bet on.
        side (str): "yes" or "no".
        amount (float): Amount to stake.

    Returns:
        tuple[bool, str]: (success, message)
    """
    side = side.strip().lower()
    if side not in VALID_SIDES:
        return False, "Side must be `yes` or `no`."

    if amount <= 0:
        return False, "Amount must be greater than 0."

    market: tuple | None = get_market(db_path, market_id)
    if market is None:
        return False, f"Market **#{market_id}** does not exist."

    status: str = market[3]
    if status != "open":
        return False, f"Market **#{market_id}** is no longer open for betting."

    # Check the bettor's own balance before touching it -- never derive the
    # required amount from anyone else's balance.
    user: User = User.create_if_not_exists(user_id=user_id, username=username)
    if user.money < amount:
        return (
            False,
            f"Insufficient funds. You need **${amount:,.2f}** but have **${user.money:,.2f}**.",  # noqa: E501
        )

    user.money -= amount

    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO prediction_bets (market_id, user_id, side, amount, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (market_id, user_id, side, amount, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()

    return True, f"Bet **${amount:,.2f}** on **{side.upper()}** for Market **#{market_id}**."


def resolve_market(
    db_path: Path,
    market_id: int,
    outcome: str,
) -> list[tuple[int, float, float]]:
    """Resolve a market and pay out the winning side from the full pool.

    Each winner receives their own stake back plus a share of the losing
    pool proportional to their stake in the winning pool. If nobody bet on
    the winning side, every bettor (both sides) is refunded their stake
    instead, since there's no one to award the pool to.

    Args:
        db_path (Path): Path to users.db.
        market_id (int): Market ID to resolve.
        outcome (str): "yes" or "no".

    Returns:
        list[tuple[int, float, float]]: (user_id, stake, payout) for each
        bettor paid out.

    Raises:
        ValueError: If the market doesn't exist, isn't open, or outcome is invalid.
    """
    outcome = outcome.strip().lower()
    if outcome not in VALID_SIDES:
        msg: str = "Outcome must be `yes` or `no`."
        raise ValueError(msg)

    market: tuple | None = get_market(db_path, market_id)
    if market is None:
        msg = f"Market #{market_id} does not exist."
        raise ValueError(msg)

    status: str = market[3]
    if status != "open":
        msg = f"Market #{market_id} is not open."
        raise ValueError(msg)

    yes_total, no_total = get_market_pools(db_path, market_id)
    total_pool: float = yes_total + no_total
    winning_total: float = yes_total if outcome == "yes" else no_total

    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.cursor()

        settlements: list[tuple[int, float, float]] = []
        if winning_total == 0:
            # No one backed the winning side -- refund everyone instead of
            # awarding an un-owned pool to nobody.
            cursor.execute(
                """
                SELECT user_id, SUM(amount) FROM prediction_bets
                WHERE market_id = ? GROUP BY user_id
                """,
                (market_id,),
            )
            for user_id, stake in cursor.fetchall():
                user: User = User.create_if_not_exists(user_id=user_id, username="")
                user.money += stake
                settlements.append((user_id, stake, stake))
        else:
            cursor.execute(
                """
                SELECT user_id, SUM(amount) FROM prediction_bets
                WHERE market_id = ? AND side = ? GROUP BY user_id
                """,
                (market_id, outcome),
            )
            for user_id, stake in cursor.fetchall():
                payout: float = stake * (total_pool / winning_total)
                user = User.create_if_not_exists(user_id=user_id, username="")
                user.money += payout
                settlements.append((user_id, stake, payout))

        cursor.execute(
            """
            UPDATE prediction_markets
            SET status = 'resolved', outcome = ?, resolved_at = ?
            WHERE id = ?
            """,
            (outcome, datetime.now(timezone.utc).isoformat(), market_id),
        )
        conn.commit()

    return settlements


def cancel_market(db_path: Path, market_id: int) -> list[tuple[int, float]]:
    """Cancel an open market and refund every bettor their stake.

    Args:
        db_path (Path): Path to users.db.
        market_id (int): Market ID to cancel.

    Returns:
        list[tuple[int, float]]: (user_id, refunded_amount) for each bettor refunded.

    Raises:
        ValueError: If the market doesn't exist or isn't open.
    """
    market: tuple | None = get_market(db_path, market_id)
    if market is None:
        msg: str = f"Market #{market_id} does not exist."
        raise ValueError(msg)

    status: str = market[3]
    if status != "open":
        msg = f"Market #{market_id} is not open."
        raise ValueError(msg)

    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute(
            """
            SELECT user_id, SUM(amount) FROM prediction_bets
            WHERE market_id = ? GROUP BY user_id
            """,
            (market_id,),
        )
        rows: list[tuple[int, float]] = cursor.fetchall()

        refunds: list[tuple[int, float]] = []
        for user_id, stake in rows:
            user: User = User.create_if_not_exists(user_id=user_id, username="")
            user.money += stake
            refunds.append((user_id, stake))

        cursor.execute(
            "UPDATE prediction_markets SET status = 'cancelled' WHERE id = ?",
            (market_id,),
        )
        conn.commit()

    return refunds
