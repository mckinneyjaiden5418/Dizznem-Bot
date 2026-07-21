"""User related code."""

import asyncio
import atexit
import sqlite3
from pathlib import Path
from typing import Any, Self

from log import logger

DB_PATH: Path = Path("data/users.db")

USER_CACHE: dict[int, "User"] = {}
SAVE_INTERVAL: int = 60


def init_db() -> None:
    """Initialize database if not done so already."""
    logger.info("Initiating database...")

    DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                money REAL DEFAULT 0,
                prestige INTEGER DEFAULT 0,
                level INTEGER DEFAULT 0,
                message_count INTEGER DEFAULT 0
            )
        """,
        )

    logger.info("Database initialized.")


class User:
    """User class containing user information."""

    def __init__(
        self,
        id: int,  # noqa: A002 -- disabled for clarity, (I prefer id over user_id since user implied).
        name: str,
        money: float,
        prestige: int,
        level: int,
        message_count: int,
    ) -> None:
        """Initialize a user.

        Args:
            id (int): Discord user ID.
            name (str): Discord username.
            money (float): Money count.
            prestige (int): Prestige count.
            level (int): Current level.
            message_count (int): Number of messages sent.
        """
        self._initialized: bool = (
            False  # This is so __setattr__ doesn't get triggered during init.
        )
        self.id: int = id
        self.name: str = name
        self.money: float = money
        self.prestige: int = prestige
        self.level: int = level
        self.message_count: int = message_count
        self.dirty: bool = False
        self._initialized = True

    def __setattr__(self, key: str, value: Any) -> None:
        """Mark users as dirty whenever an attribute changes.

        Args:
            key (str): Attribute name being set.
            value (Any): New value being assigned to attribute.
        """
        if getattr(self, "_initialized", False) and key not in {
            "dirty",
            "_initialized",
        }:
            object.__setattr__(self, "dirty", True)
        object.__setattr__(self, key, value)

    @classmethod
    def from_db(cls, user_id: int) -> Self | None:
        """Load a user from the database.

        Args:
            user_id (int): Discord user ID.

        Returns:
            User | None: User instance if found, otherwise None.
        """
        with sqlite3.connect(DB_PATH) as conn:
            cursor: sqlite3.Cursor = conn.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,),
            )
            row: Any = cursor.fetchone()

        if row is None:
            return None

        return cls(*row)

    @classmethod
    def create_if_not_exists(cls, user_id: int, username: str) -> "User":
        """Create a new user if they don't exist in the database.

        Args:
            user_id (int): Discord user ID.
            username (str): Discord username.

        Returns:
            User: The existing or newly created user instance.
        """
        if user_id in USER_CACHE:
            return USER_CACHE[user_id]

        user: User | None = cls.from_db(user_id=user_id)
        if user is None:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    "INSERT INTO users (id, name) VALUES (?, ?)",
                    (user_id, username),
                )
                conn.commit()
            user = cls.from_db(user_id)

        USER_CACHE[user_id] = user  # pyright: ignore[reportArgumentType]
        return user  # pyright: ignore[reportReturnType]

    def save(self) -> None:
        """Save user's current state to database."""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                UPDATE users
                SET name = ?, money = ?, prestige = ?, level = ?, message_count = ?
                WHERE id = ?
                """,
                (
                    self.name,
                    self.money,
                    self.prestige,
                    self.level,
                    self.message_count,
                    self.id,
                ),
            )
            conn.commit()
        self.dirty = False

    def level_up_if_able(self) -> bool:
        """Level up user if they have required message count.

        Returns:
            bool: Level up successful.
        """
        required_messages: float = 2 * (self.level**2) + (50 * self.level) + 100
        if self.message_count >= required_messages:
            self.level += 1
            return True
        return False

    def __repr__(self) -> str:
        """__repr__ for object.

        Returns:
            str: All user information.
        """
        return (
            f"<User id={self.id} name={self.name!r} "
            f"money={self.money} level={self.level} prestige={self.prestige} "
            f"messages={self.message_count} unsaved={self.dirty}>"
        )


async def autosave() -> None:
    """Periodically save all unsaved users to the database."""
    while True:
        dirty_users: list[User] = [u for u in USER_CACHE.values() if u.dirty]
        if dirty_users:
            logger.debug("Saving unsaved users.")
            for user in dirty_users:
                user.save()
        await asyncio.sleep(SAVE_INTERVAL)


def save_all_users() -> None:
    """Save all users to database when shutting down bot."""
    for user in USER_CACHE.values():
        if user.dirty:
            user.save()
    logger.info("All users saved.")


atexit.register(save_all_users)
