"""Stock market utilities."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yfinance as yf
from log import logger
from user import User

USERS_DB_PATH: Path = Path("data/users.db")
WEEKDAY: int = 4  # 0 - 4 for Monday - Friday

STOCK_MAP: dict[str, str | None] = {
    "Dizznem": "TSLA",
    "Karma": "NVDA",
    "So6": "AAPL",
    "BigH": "MSFT",
    "Luffy": "NFLX",
    "Naruto": "SNY",
    "Ichigo": "INTC",
    "Goku": "DIS",
    "Subaru": "BTC-USD",
}

DEFAULT_PRICES: dict[str, float] = {
    "Dizznem": 10.00,
    "Karma": 5.00,
    "So6": 7.50,
    "BigH": 15.00,
    "Luffy": 8.00,
    "Naruto": 6.00,
    "Ichigo": 9.00,
    "Goku": 12.00,
    "Subaru": 20.00,
}


def ensure_stocks_tables(db_path: Path) -> None:
    """Create stock_prices and user_stocks tables if they don't exist.

    Args:
        db_path (Path): Path to users.db.
    """
    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_prices (
                name         TEXT PRIMARY KEY,
                price        REAL NOT NULL,
                open_price   REAL NOT NULL,
                last_updated TEXT NOT NULL
            )
            """,
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_stocks (
                user_id    INTEGER NOT NULL,
                stock_name TEXT NOT NULL,
                quantity   INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, stock_name)
            )
            """,
        )
        for name, price in DEFAULT_PRICES.items():
            cursor.execute(
                """
                INSERT OR IGNORE INTO stock_prices (name, price, open_price, last_updated)
                VALUES (?, ?, ?, ?)
                """,
                (name, price, price, datetime.now(timezone.utc).isoformat()),
            )
        conn.commit()


def is_market_open() -> bool:
    """Check if the US stock market is currently open.

    Returns:
        bool: True if the market is open.
    """
    now: datetime = datetime.now(timezone.utc)
    if now.weekday() > WEEKDAY:
        return False
    market_open: datetime = now.replace(hour=14, minute=30, second=0, microsecond=0)
    market_close: datetime = now.replace(hour=21, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close


def refresh_prices(db_path: Path) -> None:
    """Fetch latest prices from Yahoo Finance for mapped stocks.

    Args:
        db_path (Path): Path to users.db.
    """
    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.cursor()
        for name, ticker in STOCK_MAP.items():
            if ticker is None:
                continue
            try:
                data: yf.Ticker = yf.Ticker(ticker)
                info: Any = data.fast_info
                price: float = float(info.last_price)
                open_price: float = float(info.open)
                cursor.execute(
                    """
                    UPDATE stock_prices
                    SET price = ?, open_price = ?, last_updated = ?
                    WHERE name = ?
                    """,
                    (price, open_price, datetime.now(timezone.utc).isoformat(), name),
                )
            except (ValueError, AttributeError) as exc:
                logger.exception(
                    f"Failed to fetch price for {name} ({ticker})",
                    exc_info=exc,
                )
        conn.commit()


def get_all_prices(db_path: Path) -> list[tuple[str, float, float]]:
    """Get all stock names, current prices, and open prices.

    Args:
        db_path (Path): Path to users.db.

    Returns:
        list[tuple[str, float, float]]: List of (name, price, open_price).
    """
    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute("SELECT name, price, open_price FROM stock_prices")
        return cursor.fetchall()


def get_price(db_path: Path, stock_name: str) -> float | None:
    """Get the current price of a stock.

    Args:
        db_path (Path): Path to users.db.
        stock_name (str): Name of the stock.

    Returns:
        float | None: Current price, or None if stock doesn't exist.
    """
    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute("SELECT price FROM stock_prices WHERE name = ?", (stock_name,))
        row: tuple = cursor.fetchone()
    return row[0] if row else None


def get_user_balance(user_id: int, username: str) -> float:
    """Get a user's current money balance via the User cache.

    Args:
        user_id (int): Discord user ID.
        username (str): Discord username.

    Returns:
        float: User's current balance.
    """
    user: User = User.create_if_not_exists(user_id=user_id, username=username)
    return user.money


def get_user_stocks(db_path: Path, user_id: int) -> list[tuple[str, int, float]]:
    """Get all stocks owned by a user with current value.

    Args:
        db_path (Path): Path to users.db.
        user_id (int): Discord user ID.

    Returns:
        list[tuple[str, int, float]]: List of (stock_name, quantity, total_value).
    """
    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute(
            """
            SELECT us.stock_name, us.quantity, sp.price
            FROM user_stocks us
            JOIN stock_prices sp ON us.stock_name = sp.name
            WHERE us.user_id = ? AND us.quantity > 0
            """,
            (user_id,),
        )
        rows: list[tuple] = cursor.fetchall()
    return [(name, qty, qty * price) for name, qty, price in rows]


def buy_stock(
    db_path: Path,
    user_id: int,
    username: str,
    stock_name: str,
    quantity: int,
) -> tuple[bool, str]:
    """Buy stocks for a user, deducting from their money balance.

    Args:
        db_path (Path): Path to users.db.
        user_id (int): Discord user ID.
        username (str): Discord username.
        stock_name (str): Name of the stock to buy.
        quantity (int): Number of shares to buy.

    Returns:
        tuple[bool, str]: (success, message)
    """
    user: User = User.create_if_not_exists(user_id=user_id, username=username)

    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute("SELECT price FROM stock_prices WHERE name = ?", (stock_name,))
        row: tuple = cursor.fetchone()
        if row is None:
            return False, f"Stock `{stock_name}` does not exist."

        price: float = row[0]
        total_cost: float = price * quantity

        if user.money < total_cost:
            return (
                False,
                f"Insufficient funds. You need **${total_cost:,.2f}** but have **${user.money:,.2f}**.",  # noqa: E501
            )

        user.money -= total_cost

        cursor.execute(
            """
            INSERT INTO user_stocks (user_id, stock_name, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, stock_name) DO UPDATE SET quantity = quantity + ?
            """,
            (user_id, stock_name, quantity, quantity),
        )
        conn.commit()

    return True, f"Bought **{quantity}x {stock_name}** for **${total_cost:,.2f}**."


def sell_stock(
    db_path: Path,
    user_id: int,
    username: str,
    stock_name: str,
    quantity: int,
) -> tuple[bool, str]:
    """Sell stocks for a user, adding to their money balance.

    Args:
        db_path (Path): Path to users.db.
        user_id (int): Discord user ID.
        username (str): Discord username.
        stock_name (str): Name of the stock to sell.
        quantity (int): Number of shares to sell.

    Returns:
        tuple[bool, str]: (success, message)
    """
    user: User = User.create_if_not_exists(user_id=user_id, username=username)

    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute(
            "SELECT quantity FROM user_stocks WHERE user_id = ? AND stock_name = ?",
            (user_id, stock_name),
        )
        row: tuple = cursor.fetchone()
        if row is None or row[0] < quantity:
            owned: int = row[0] if row else 0
            return False, f"You only own **{owned}x {stock_name}**."

        cursor.execute("SELECT price FROM stock_prices WHERE name = ?", (stock_name,))
        price: float = cursor.fetchone()[0]
        total_value: float = price * quantity

        user.money += total_value

        cursor.execute(
            """
            UPDATE user_stocks SET quantity = quantity - ?
            WHERE user_id = ? AND stock_name = ?
            """,
            (quantity, user_id, stock_name),
        )
        conn.commit()

    return True, f"Sold **{quantity}x {stock_name}** for **${total_value:,.2f}**."


def liquidate_stock(db_path: Path, stock_name: str) -> list[tuple[int, int, float, float]]:
    """Force-sell every holder's shares of a stock at its current price.

    Intended to be run once, manually, right before a stock's underlying
    STOCK_MAP ticker is changed. Since a stock's price is the live ticker
    price with no continuity between tickers, repointing the ticker while
    people hold shares would instantly reprice their position for free
    (a windfall or a wipeout unrelated to any trade). Settling everyone
    at the pre-swap price first means the ticker change can't move
    anyone's money.

    Args:
        db_path (Path): Path to users.db.
        stock_name (str): Name of the stock to liquidate.

    Returns:
        list[tuple[int, int, float, float]]: (user_id, quantity, price, payout)
        for each holder settled, in no particular order. Empty if the
        stock currently has no holders.

    Raises:
        ValueError: If the stock does not exist.
    """
    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute("SELECT price FROM stock_prices WHERE name = ?", (stock_name,))
        row: tuple | None = cursor.fetchone()
        if row is None:
            msg: str = f"Stock `{stock_name}` does not exist."
            raise ValueError(msg)
        price: float = row[0]

        cursor.execute(
            "SELECT user_id, quantity FROM user_stocks WHERE stock_name = ? AND quantity > 0",  # noqa: E501
            (stock_name,),
        )
        holders: list[tuple[int, int]] = cursor.fetchall()

        settlements: list[tuple[int, int, float, float]] = []
        for user_id, quantity in holders:
            payout: float = price * quantity
            # Every holder already has a User row from buying in via $buystock,
            # so this always resolves the existing user rather than creating one.
            user: User = User.create_if_not_exists(user_id=user_id, username="")
            user.money += payout
            settlements.append((user_id, quantity, price, payout))

        cursor.execute("DELETE FROM user_stocks WHERE stock_name = ?", (stock_name,))
        conn.commit()

    return settlements
