"""Tests for utils/moderation/warnings.py."""

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from utils.moderation.warnings import (
    MAX_REASON_LENGTH,
    WarningRecord,
    add_warning,
    count_warnings,
    delete_warning,
    ensure_warnings_db,
    get_warning,
    get_warnings,
    validate_reason,
)

GUILD_ID: int = 111
OTHER_GUILD_ID: int = 222
USER_ID: int = 555
MODERATOR_ID: int = 999


@pytest.fixture
def db(tmp_path: Path) -> Path:
    """Create a temporary warnings database for each test."""
    return tmp_path / "warnings.db"


class TestEnsureWarningsDb:
    """Tests for ensure_warnings_db."""

    def test_creates_table(self, db: Path) -> None:
        """Test that the warnings table is created."""
        ensure_warnings_db(db)
        with sqlite3.connect(db) as conn:
            cursor: sqlite3.Cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='warnings'",
            )
            assert cursor.fetchone() is not None

    def test_idempotent(self, db: Path) -> None:
        """Test that calling ensure_warnings_db twice does not error or wipe data."""
        ensure_warnings_db(db)
        add_warning(db, GUILD_ID, USER_ID, MODERATOR_ID, "spamming")
        ensure_warnings_db(db)
        assert count_warnings(db, GUILD_ID, USER_ID) == 1


class TestValidateReason:
    """Tests for validate_reason."""

    def test_valid_reason(self) -> None:
        """Test that a normal reason passes validation."""
        is_valid, message = validate_reason("Spamming in general chat")
        assert is_valid is True
        assert message == ""

    def test_empty_reason_rejected(self) -> None:
        """Test that an empty reason is rejected."""
        is_valid, message = validate_reason("")
        assert is_valid is False
        assert "empty" in message.lower()

    def test_whitespace_only_reason_rejected(self) -> None:
        """Test that a whitespace-only reason is rejected."""
        is_valid, message = validate_reason("   ")
        assert is_valid is False
        assert "empty" in message.lower()

    def test_too_long_reason_rejected(self) -> None:
        """Test that a reason over MAX_REASON_LENGTH is rejected."""
        is_valid, message = validate_reason("x" * (MAX_REASON_LENGTH + 1))
        assert is_valid is False
        assert "too long" in message.lower()

    def test_reason_at_max_length_accepted(self) -> None:
        """Test that a reason exactly at MAX_REASON_LENGTH is accepted."""
        is_valid, _message = validate_reason("x" * MAX_REASON_LENGTH)
        assert is_valid is True


class TestAddWarning:
    """Tests for add_warning."""

    def test_returns_warning_record(self, db: Path) -> None:
        """Test that add_warning returns a populated WarningRecord."""
        warning: WarningRecord = add_warning(db, GUILD_ID, USER_ID, MODERATOR_ID, "rule 1")
        assert warning["guild_id"] == GUILD_ID
        assert warning["user_id"] == USER_ID
        assert warning["moderator_id"] == MODERATOR_ID
        assert warning["reason"] == "rule 1"
        assert warning["id"] > 0

    def test_persists_to_database(self, db: Path) -> None:
        """Test that the warning is actually written to the database."""
        add_warning(db, GUILD_ID, USER_ID, MODERATOR_ID, "rule 1")
        with sqlite3.connect(db) as conn:
            row: Any = conn.execute("SELECT COUNT(*) FROM warnings").fetchone()
        assert row[0] == 1

    def test_ids_increment(self, db: Path) -> None:
        """Test that successive warnings get increasing IDs."""
        first: WarningRecord = add_warning(db, GUILD_ID, USER_ID, MODERATOR_ID, "first")
        second: WarningRecord = add_warning(db, GUILD_ID, USER_ID, MODERATOR_ID, "second")
        assert second["id"] > first["id"]


class TestGetWarnings:
    """Tests for get_warnings."""

    def test_returns_empty_list_when_none(self, db: Path) -> None:
        """Test that a user with no warnings gets an empty list."""
        assert get_warnings(db, GUILD_ID, USER_ID) == []

    def test_returns_all_warnings_for_user(self, db: Path) -> None:
        """Test that all warnings for a user are returned."""
        add_warning(db, GUILD_ID, USER_ID, MODERATOR_ID, "first")
        add_warning(db, GUILD_ID, USER_ID, MODERATOR_ID, "second")
        records: list[WarningRecord] = get_warnings(db, GUILD_ID, USER_ID)
        assert len(records) == 2  # noqa: PLR2004

    def test_ordered_oldest_first(self, db: Path) -> None:
        """Test that warnings come back in creation order."""
        add_warning(db, GUILD_ID, USER_ID, MODERATOR_ID, "first")
        add_warning(db, GUILD_ID, USER_ID, MODERATOR_ID, "second")
        records: list[WarningRecord] = get_warnings(db, GUILD_ID, USER_ID)
        assert records[0]["reason"] == "first"
        assert records[1]["reason"] == "second"

    def test_scoped_to_guild(self, db: Path) -> None:
        """Test that warnings from another guild are not returned."""
        add_warning(db, GUILD_ID, USER_ID, MODERATOR_ID, "here")
        add_warning(db, OTHER_GUILD_ID, USER_ID, MODERATOR_ID, "elsewhere")
        records: list[WarningRecord] = get_warnings(db, GUILD_ID, USER_ID)
        assert len(records) == 1
        assert records[0]["reason"] == "here"

    def test_scoped_to_user(self, db: Path) -> None:
        """Test that another user's warnings are not returned."""
        add_warning(db, GUILD_ID, USER_ID, MODERATOR_ID, "target")
        add_warning(db, GUILD_ID, MODERATOR_ID, USER_ID, "someone else")
        records: list[WarningRecord] = get_warnings(db, GUILD_ID, USER_ID)
        assert len(records) == 1
        assert records[0]["reason"] == "target"


class TestGetWarning:
    """Tests for get_warning."""

    def test_returns_matching_warning(self, db: Path) -> None:
        """Test that a warning is returned by ID."""
        created: WarningRecord = add_warning(db, GUILD_ID, USER_ID, MODERATOR_ID, "rule 1")
        fetched: WarningRecord | None = get_warning(db, GUILD_ID, created["id"])
        assert fetched is not None
        assert fetched["reason"] == "rule 1"

    def test_returns_none_when_missing(self, db: Path) -> None:
        """Test that None is returned for a non-existent warning ID."""
        ensure_warnings_db(db)
        assert get_warning(db, GUILD_ID, 12345) is None

    def test_returns_none_for_wrong_guild(self, db: Path) -> None:
        """Test that a warning cannot be fetched using the wrong guild ID."""
        created: WarningRecord = add_warning(db, GUILD_ID, USER_ID, MODERATOR_ID, "rule 1")
        assert get_warning(db, OTHER_GUILD_ID, created["id"]) is None


class TestDeleteWarning:
    """Tests for delete_warning."""

    def test_deletes_existing_warning(self, db: Path) -> None:
        """Test that deleting an existing warning returns True and removes it."""
        created: WarningRecord = add_warning(db, GUILD_ID, USER_ID, MODERATOR_ID, "rule 1")
        result: bool = delete_warning(db, GUILD_ID, created["id"])
        assert result is True
        assert get_warnings(db, GUILD_ID, USER_ID) == []

    def test_returns_false_for_missing_id(self, db: Path) -> None:
        """Test that deleting a non-existent warning ID returns False."""
        ensure_warnings_db(db)
        assert delete_warning(db, GUILD_ID, 99999) is False

    def test_does_not_delete_across_guilds(self, db: Path) -> None:
        """Test that a warning cannot be deleted using the wrong guild ID."""
        created: WarningRecord = add_warning(db, GUILD_ID, USER_ID, MODERATOR_ID, "rule 1")
        result: bool = delete_warning(db, OTHER_GUILD_ID, created["id"])
        assert result is False
        assert len(get_warnings(db, GUILD_ID, USER_ID)) == 1

    def test_only_deletes_targeted_warning(self, db: Path) -> None:
        """Test that deleting one warning leaves the others intact."""
        first: WarningRecord = add_warning(db, GUILD_ID, USER_ID, MODERATOR_ID, "first")
        second: WarningRecord = add_warning(db, GUILD_ID, USER_ID, MODERATOR_ID, "second")
        delete_warning(db, GUILD_ID, first["id"])
        remaining: list[WarningRecord] = get_warnings(db, GUILD_ID, USER_ID)
        assert len(remaining) == 1
        assert remaining[0]["id"] == second["id"]


class TestCountWarnings:
    """Tests for count_warnings."""

    def test_zero_when_none(self, db: Path) -> None:
        """Test that count is zero for a user with no warnings."""
        assert count_warnings(db, GUILD_ID, USER_ID) == 0

    def test_counts_correctly(self, db: Path) -> None:
        """Test that the count matches the number of warnings added."""
        add_warning(db, GUILD_ID, USER_ID, MODERATOR_ID, "one")
        add_warning(db, GUILD_ID, USER_ID, MODERATOR_ID, "two")
        add_warning(db, GUILD_ID, USER_ID, MODERATOR_ID, "three")
        assert count_warnings(db, GUILD_ID, USER_ID) == 3  # noqa: PLR2004

    def test_decrements_after_delete(self, db: Path) -> None:
        """Test that the count reflects a deleted warning."""
        first: WarningRecord = add_warning(db, GUILD_ID, USER_ID, MODERATOR_ID, "one")
        add_warning(db, GUILD_ID, USER_ID, MODERATOR_ID, "two")
        delete_warning(db, GUILD_ID, first["id"])
        assert count_warnings(db, GUILD_ID, USER_ID) == 1
