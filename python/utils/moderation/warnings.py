"""Warning system database utilities.

This is the foundation moderation primitive -- persistent, per-guild warning
records that later Phase 2 features (automod, mute escalation, mod logs) can
build on top of.
"""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

WARNINGS_DB_PATH: Path = Path("data/warnings.db")

MAX_REASON_LENGTH: int = 500


class WarningRecord(TypedDict):
    """A single warning issued to a user."""

    id: int
    guild_id: int
    user_id: int
    moderator_id: int
    reason: str
    created_at: str


def ensure_warnings_db(db_path: Path) -> None:
    """Create warnings.db if it doesn't exist.

    Args:
        db_path (Path): Path to the SQLite database file.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
        )
        conn.commit()


def validate_reason(reason: str) -> tuple[bool, str]:
    """Validate a warning reason before storing it.

    Args:
        reason (str): The reason text to validate.

    Returns:
        tuple[bool, str]: (is_valid, error_message)
    """
    stripped: str = reason.strip()

    if not stripped:
        return False, "Reason cannot be empty."

    if len(stripped) > MAX_REASON_LENGTH:
        return (
            False,
            f"Reason is too long. Must be {MAX_REASON_LENGTH} characters or less.",
        )

    return True, ""


def add_warning(
    db_path: Path,
    guild_id: int,
    user_id: int,
    moderator_id: int,
    reason: str,
) -> WarningRecord:
    """Add a warning for a user.

    Args:
        db_path (Path): SQLite database path.
        guild_id (int): Discord guild ID the warning was issued in.
        user_id (int): Discord user ID being warned.
        moderator_id (int): Discord user ID of the moderator issuing the warning.
        reason (str): Reason for the warning.

    Returns:
        WarningRecord: The newly created warning record.
    """
    ensure_warnings_db(db_path)
    created_at: str = datetime.now(tz=UTC).isoformat()

    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.execute(
            """
            INSERT INTO warnings (guild_id, user_id, moderator_id, reason, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (guild_id, user_id, moderator_id, reason, created_at),
        )
        conn.commit()
        new_id: int = cursor.lastrowid  # type: ignore[assignment]

    return WarningRecord(
        id=new_id,
        guild_id=guild_id,
        user_id=user_id,
        moderator_id=moderator_id,
        reason=reason,
        created_at=created_at,
    )


def get_warnings(db_path: Path, guild_id: int, user_id: int) -> list[WarningRecord]:
    """Get all warnings for a user in a guild, oldest first.

    Args:
        db_path (Path): SQLite database path.
        guild_id (int): Discord guild ID.
        user_id (int): Discord user ID.

    Returns:
        list[WarningRecord]: The user's warnings, ordered oldest to newest.
    """
    ensure_warnings_db(db_path)
    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.execute(
            """
            SELECT id, guild_id, user_id, moderator_id, reason, created_at
            FROM warnings
            WHERE guild_id = ? AND user_id = ?
            ORDER BY id ASC
            """,
            (guild_id, user_id),
        )
        rows: list[tuple] = cursor.fetchall()

    return [
        WarningRecord(
            id=row[0],
            guild_id=row[1],
            user_id=row[2],
            moderator_id=row[3],
            reason=row[4],
            created_at=row[5],
        )
        for row in rows
    ]


def get_warning(db_path: Path, guild_id: int, warning_id: int) -> WarningRecord | None:
    """Get a single warning by ID within a guild.

    Args:
        db_path (Path): SQLite database path.
        guild_id (int): Discord guild ID the warning must belong to.
        warning_id (int): ID of the warning to fetch.

    Returns:
        WarningRecord | None: The warning if found, otherwise None.
    """
    ensure_warnings_db(db_path)
    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.execute(
            """
            SELECT id, guild_id, user_id, moderator_id, reason, created_at
            FROM warnings
            WHERE id = ? AND guild_id = ?
            """,
            (warning_id, guild_id),
        )
        row: tuple | None = cursor.fetchone()

    if row is None:
        return None

    return WarningRecord(
        id=row[0],
        guild_id=row[1],
        user_id=row[2],
        moderator_id=row[3],
        reason=row[4],
        created_at=row[5],
    )


def delete_warning(db_path: Path, guild_id: int, warning_id: int) -> bool:
    """Delete a specific warning by ID within a guild.

    Args:
        db_path (Path): SQLite database path.
        guild_id (int): Discord guild ID the warning must belong to.
        warning_id (int): ID of the warning to delete.

    Returns:
        bool: True if a warning was deleted, False if none matched.
    """
    ensure_warnings_db(db_path)
    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.execute(
            "DELETE FROM warnings WHERE id = ? AND guild_id = ?",
            (warning_id, guild_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def count_warnings(db_path: Path, guild_id: int, user_id: int) -> int:
    """Count how many warnings a user has in a guild.

    Args:
        db_path (Path): SQLite database path.
        guild_id (int): Discord guild ID.
        user_id (int): Discord user ID.

    Returns:
        int: Number of warnings on record.
    """
    ensure_warnings_db(db_path)
    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.execute(
            "SELECT COUNT(*) FROM warnings WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        return cursor.fetchone()[0]
