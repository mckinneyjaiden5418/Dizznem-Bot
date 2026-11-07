"""Tests for main.py."""

import sqlite3
from pathlib import Path

import pytest
from main import handle_sigterm
from user import User


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary database for each test."""
    db_path: Path = tmp_path / "users.db"
    monkeypatch.setattr("user.DB_PATH", db_path)
    monkeypatch.setattr("user.USER_CACHE", {})

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
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
    return db_path


class TestHandleSigterm:
    """Tests for handle_sigterm."""

    def test_saves_dirty_users_before_exiting(
        self,
        db: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that unsaved changes are flushed to disk before exit."""
        user: User = User.create_if_not_exists(user_id=1, username="karma")
        user.money = 5_000
        assert user.dirty is True

        monkeypatch.setattr("sys.exit", lambda *_a: (_ for _ in ()).throw(SystemExit))

        with pytest.raises(SystemExit):
            handle_sigterm(15, None)

        with sqlite3.connect(db) as conn:
            row: tuple = conn.execute(
                "SELECT money FROM users WHERE id = 1",
            ).fetchone()
        assert row[0] == 5_000  # noqa: PLR2004

    def test_exits_after_saving(
        self,
        db: Path,  # noqa: ARG002 -- fixture sets up user.DB_PATH/USER_CACHE
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that the process is told to exit after saving."""
        exit_called: bool = False

        def fake_exit(code: int = 0) -> None:
            nonlocal exit_called
            exit_called = True
            assert code == 0

        monkeypatch.setattr("sys.exit", fake_exit)
        handle_sigterm(15, None)

        assert exit_called is True

    def test_no_dirty_users_still_exits_cleanly(
        self,
        db: Path,  # noqa: ARG002 -- fixture sets up user.DB_PATH/USER_CACHE
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that handling SIGTERM with no unsaved users doesn't error."""
        monkeypatch.setattr("sys.exit", lambda *_a: (_ for _ in ()).throw(SystemExit))

        with pytest.raises(SystemExit):
            handle_sigterm(15, None)
