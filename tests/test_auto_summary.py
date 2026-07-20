"""Tests for utils/misc/auto_summary.py."""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from utils.misc.auto_summary import (
    MAX_INTERVAL_HOURS,
    MIN_INTERVAL_HOURS,
    clamp_interval_hours,
    disable_auto_summary,
    enable_auto_summary,
    ensure_auto_summary_db,
    get_channel_config,
    get_due_channels,
    update_last_summary,
)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    """Create a temporary auto-summary database."""
    db_path: Path = tmp_path / "auto_summary.db"
    ensure_auto_summary_db(db_path)
    return db_path


def _set_last_summary(db_path: Path, channel_id: int, when: datetime) -> None:
    """Backdate a channel's last-summary timestamp directly in the DB."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE auto_summary_channels SET last_summary_at = ? WHERE channel_id = ?",
            (when.isoformat(), channel_id),
        )
        conn.commit()


class TestEnsureAutoSummaryDb:
    """Tests for ensure_auto_summary_db."""

    def test_creates_db_file(self, tmp_path: Path) -> None:
        """The database file is created."""
        db_path: Path = tmp_path / "auto_summary.db"
        ensure_auto_summary_db(db_path)
        assert db_path.exists()

    def test_second_call_does_not_wipe_data(self, db: Path) -> None:
        """Calling ensure_auto_summary_db again preserves existing rows."""
        enable_auto_summary(db, channel_id=1, interval_hours=6)
        ensure_auto_summary_db(db)
        assert get_channel_config(db, 1) is not None


class TestClampIntervalHours:
    """Tests for clamp_interval_hours."""

    def test_in_range_unchanged(self) -> None:
        """A value already in range passes through unchanged."""
        assert clamp_interval_hours(12) == 12

    def test_below_min_clamped_up(self) -> None:
        """Values below the minimum are clamped up."""
        assert clamp_interval_hours(0) == MIN_INTERVAL_HOURS

    def test_above_max_clamped_down(self) -> None:
        """Values above the maximum are clamped down."""
        assert clamp_interval_hours(9999) == MAX_INTERVAL_HOURS


class TestEnableAutoSummary:
    """Tests for enable_auto_summary."""

    def test_creates_config_for_channel(self, db: Path) -> None:
        """Enabling stores an interval for the channel."""
        enable_auto_summary(db, channel_id=42, interval_hours=6)
        config = get_channel_config(db, 42)
        assert config is not None
        assert config[0] == 6  # noqa: PLR2004

    def test_re_enabling_updates_interval(self, db: Path) -> None:
        """Enabling an already-enabled channel updates its interval."""
        enable_auto_summary(db, channel_id=42, interval_hours=6)
        enable_auto_summary(db, channel_id=42, interval_hours=12)
        config = get_channel_config(db, 42)
        assert config is not None
        assert config[0] == 12  # noqa: PLR2004

    def test_re_enabling_resets_last_summary_to_now(self, db: Path) -> None:
        """Re-enabling resets the last-summary timestamp so it isn't due yet."""
        enable_auto_summary(db, channel_id=42, interval_hours=6)
        _set_last_summary(db, 42, datetime.now(timezone.utc) - timedelta(hours=100))
        enable_auto_summary(db, channel_id=42, interval_hours=6)
        assert get_due_channels(db) == []

    def test_only_affects_the_given_channel(self, db: Path) -> None:
        """Enabling one channel doesn't create config for another."""
        enable_auto_summary(db, channel_id=1, interval_hours=6)
        assert get_channel_config(db, 2) is None


class TestDisableAutoSummary:
    """Tests for disable_auto_summary."""

    def test_returns_true_when_config_existed(self, db: Path) -> None:
        """Disabling a configured channel reports it existed."""
        enable_auto_summary(db, channel_id=42, interval_hours=6)
        assert disable_auto_summary(db, 42) is True

    def test_returns_false_when_nothing_to_disable(self, db: Path) -> None:
        """Disabling an unconfigured channel reports nothing existed."""
        assert disable_auto_summary(db, 999) is False

    def test_removes_config(self, db: Path) -> None:
        """Disabling removes the channel's config."""
        enable_auto_summary(db, channel_id=42, interval_hours=6)
        disable_auto_summary(db, 42)
        assert get_channel_config(db, 42) is None


class TestGetChannelConfig:
    """Tests for get_channel_config."""

    def test_returns_none_when_disabled(self, db: Path) -> None:
        """A channel with no config returns None."""
        assert get_channel_config(db, 1) is None

    def test_returns_interval_and_timestamp(self, db: Path) -> None:
        """An enabled channel's interval and timestamp are returned."""
        enable_auto_summary(db, channel_id=1, interval_hours=8)
        config = get_channel_config(db, 1)
        assert config is not None
        interval_hours, last_summary_at = config
        assert interval_hours == 8  # noqa: PLR2004
        assert isinstance(last_summary_at, str)


class TestGetDueChannels:
    """Tests for get_due_channels."""

    def test_freshly_enabled_channel_is_not_due(self, db: Path) -> None:
        """A channel enabled just now is not due for a summary."""
        enable_auto_summary(db, channel_id=1, interval_hours=6)
        assert get_due_channels(db) == []

    def test_channel_past_its_interval_is_due(self, db: Path) -> None:
        """A channel whose interval has elapsed is due."""
        enable_auto_summary(db, channel_id=1, interval_hours=6)
        _set_last_summary(db, 1, datetime.now(timezone.utc) - timedelta(hours=7))

        due = get_due_channels(db)

        assert len(due) == 1
        assert due[0][0] == 1

    def test_disabled_channels_are_never_due(self, db: Path) -> None:
        """Channels without a config are never returned."""
        assert get_due_channels(db) == []

    def test_only_returns_channels_past_their_own_interval(self, db: Path) -> None:
        """Each channel is checked against its own configured interval."""
        enable_auto_summary(db, channel_id=1, interval_hours=6)
        enable_auto_summary(db, channel_id=2, interval_hours=24)
        past_due: datetime = datetime.now(timezone.utc) - timedelta(hours=7)
        _set_last_summary(db, 1, past_due)
        _set_last_summary(db, 2, past_due)

        due_ids: list[int] = [channel_id for channel_id, *_ in get_due_channels(db)]

        assert due_ids == [1]


class TestUpdateLastSummary:
    """Tests for update_last_summary."""

    def test_marks_channel_as_no_longer_due(self, db: Path) -> None:
        """Updating the timestamp clears the due state."""
        enable_auto_summary(db, channel_id=1, interval_hours=6)
        _set_last_summary(db, 1, datetime.now(timezone.utc) - timedelta(hours=7))
        assert get_due_channels(db) != []

        update_last_summary(db, 1)

        assert get_due_channels(db) == []
