"""Automatic channel summary scheduling utilities."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

MIN_INTERVAL_HOURS: int = 1
MAX_INTERVAL_HOURS: int = 168  # 1 week


def ensure_auto_summary_db(db_path: Path) -> None:
    """Create the auto-summary table if it doesn't exist.

    Args:
        db_path (Path): Path to the SQLite database file.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS auto_summary_channels (
                channel_id      INTEGER PRIMARY KEY,
                interval_hours  INTEGER NOT NULL,
                last_summary_at TEXT NOT NULL
            )
        """,
        )
        conn.commit()


def clamp_interval_hours(interval_hours: int) -> int:
    """Clamp an interval into [MIN_INTERVAL_HOURS, MAX_INTERVAL_HOURS].

    Args:
        interval_hours (int): The raw interval requested by the user.

    Returns:
        int: The clamped interval.
    """
    return max(MIN_INTERVAL_HOURS, min(interval_hours, MAX_INTERVAL_HOURS))


def enable_auto_summary(db_path: Path, channel_id: int, interval_hours: int) -> None:
    """Enable (or reconfigure) automatic summaries for a channel.

    The last-summary timestamp is reset to now, so the first automatic
    summary fires one interval from now rather than immediately.

    Args:
        db_path (Path): Path to the SQLite database file.
        channel_id (int): The channel to enable automatic summaries for.
        interval_hours (int): Hours between automatic summaries.
    """
    now: str = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO auto_summary_channels
                (channel_id, interval_hours, last_summary_at)
            VALUES (?, ?, ?)
            ON CONFLICT(channel_id) DO UPDATE SET
                interval_hours = excluded.interval_hours,
                last_summary_at = excluded.last_summary_at
            """,
            (channel_id, interval_hours, now),
        )
        conn.commit()


def disable_auto_summary(db_path: Path, channel_id: int) -> bool:
    """Disable automatic summaries for a channel.

    Args:
        db_path (Path): Path to the SQLite database file.
        channel_id (int): The channel to disable automatic summaries for.

    Returns:
        bool: True if a config existed and was removed, False otherwise.
    """
    with sqlite3.connect(db_path) as conn:
        cursor: sqlite3.Cursor = conn.execute(
            "DELETE FROM auto_summary_channels WHERE channel_id = ?",
            (channel_id,),
        )
        conn.commit()
        return cursor.rowcount > 0


def get_channel_config(db_path: Path, channel_id: int) -> tuple[int, str] | None:
    """Get the automatic summary config for a channel.

    Args:
        db_path (Path): Path to the SQLite database file.
        channel_id (int): The channel to look up.

    Returns:
        tuple[int, str] | None: (interval_hours, last_summary_at), or None if
        automatic summaries aren't enabled for this channel.
    """
    with sqlite3.connect(db_path) as conn:
        row: tuple | None = conn.execute(
            """
            SELECT interval_hours, last_summary_at
            FROM auto_summary_channels
            WHERE channel_id = ?
            """,
            (channel_id,),
        ).fetchone()
    return (row[0], row[1]) if row else None


def get_due_channels(db_path: Path) -> list[tuple[int, int, str]]:
    """Get all enabled channels whose automatic summary interval has elapsed.

    Args:
        db_path (Path): Path to the SQLite database file.

    Returns:
        list[tuple[int, int, str]]: (channel_id, interval_hours,
        last_summary_at) for every channel that is due for a summary.
    """
    now: datetime = datetime.now(timezone.utc)
    with sqlite3.connect(db_path) as conn:
        rows: list[tuple] = conn.execute(
            "SELECT channel_id, interval_hours, last_summary_at FROM auto_summary_channels",
        ).fetchall()

    due: list[tuple[int, int, str]] = []
    for channel_id, interval_hours, last_summary_at in rows:
        last: datetime = datetime.fromisoformat(last_summary_at)
        elapsed_hours: float = (now - last).total_seconds() / 3600
        if elapsed_hours >= interval_hours:
            due.append((channel_id, interval_hours, last_summary_at))
    return due


def update_last_summary(db_path: Path, channel_id: int) -> None:
    """Set a channel's last-summary timestamp to now.

    Args:
        db_path (Path): Path to the SQLite database file.
        channel_id (int): The channel to update.
    """
    now: str = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE auto_summary_channels SET last_summary_at = ? WHERE channel_id = ?",
            (now, channel_id),
        )
        conn.commit()
