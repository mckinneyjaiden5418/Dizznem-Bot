"""Tests for utils/money/prediction_market.py."""

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from utils.money.prediction_market import (
    cancel_market,
    create_market,
    ensure_prediction_market_tables,
    get_market,
    get_market_pools,
    get_open_markets,
    get_user_bets,
    place_bet,
    resolve_market,
)

if TYPE_CHECKING:
    from user import User


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up a temporary prediction market database with a fresh user cache."""
    db_path: Path = tmp_path / "users.db"

    monkeypatch.setattr("user.DB_PATH", db_path)
    monkeypatch.setattr("user.USER_CACHE", {})

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

    ensure_prediction_market_tables(db_path)
    return db_path


def _insert_user(db: Path, user_id: int, username: str, money: float) -> None:
    """Insert a user directly into the users table."""
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO users (id, name, money) VALUES (?, ?, ?)",
            (user_id, username, money),
        )


@pytest.fixture
def funded_user(db: Path) -> tuple[Path, int, str]:
    """Insert a user with money and return (db_path, user_id, username)."""
    user_id: int = 999
    username: str = "karma"
    _insert_user(db, user_id, username, 1_000.0)
    return db, user_id, username


@pytest.fixture
def open_market(funded_user: tuple[Path, int, str]) -> tuple[Path, int]:
    """Create an open market and return (db_path, market_id)."""
    db, creator_id, _ = funded_user
    success, message = create_market(db, creator_id, "Will it rain tomorrow?")
    assert success is True
    market_id: int = int(message.split("**#")[1].split("**")[0])
    return db, market_id


class TestEnsurePredictionMarketTables:
    """Tests for ensure_prediction_market_tables."""

    def test_creates_prediction_markets_table(self, db: Path) -> None:
        """Test that the prediction_markets table is created."""
        with sqlite3.connect(db) as conn:
            tables: list[tuple[str]] = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'",
            ).fetchall()
        table_names: list[str] = [t[0] for t in tables]
        assert "prediction_markets" in table_names

    def test_creates_prediction_bets_table(self, db: Path) -> None:
        """Test that the prediction_bets table is created."""
        with sqlite3.connect(db) as conn:
            tables: list[tuple[str]] = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'",
            ).fetchall()
        table_names: list[str] = [t[0] for t in tables]
        assert "prediction_bets" in table_names


class TestCreateMarket:
    """Tests for create_market."""

    def test_successful_creation(self, funded_user: tuple) -> None:
        """Test that creating a market with a valid question succeeds."""
        db, user_id, _ = funded_user
        success, message = create_market(db, user_id, "Will it rain tomorrow?")
        assert success is True
        assert "Will it rain tomorrow?" in message

    def test_empty_question_fails(self, funded_user: tuple) -> None:
        """Test that creating a market with an empty question fails."""
        db, user_id, _ = funded_user
        success, message = create_market(db, user_id, "   ")
        assert success is False
        assert "empty" in message

    def test_question_too_long_fails(self, funded_user: tuple) -> None:
        """Test that creating a market with an overly long question fails."""
        db, user_id, _ = funded_user
        success, message = create_market(db, user_id, "a" * 201)
        assert success is False
        assert "characters or fewer" in message

    def test_market_is_open_by_default(self, funded_user: tuple) -> None:
        """Test that a newly created market defaults to open status."""
        db, user_id, _ = funded_user
        create_market(db, user_id, "Will it rain tomorrow?")
        markets: list[tuple[int, str, int]] = get_open_markets(db)
        assert len(markets) == 1


class TestGetOpenMarkets:
    """Tests for get_open_markets."""

    def test_empty_when_no_markets(self, db: Path) -> None:
        """Test that get_open_markets returns an empty list when none exist."""
        assert get_open_markets(db) == []

    def test_excludes_resolved_markets(self, open_market: tuple[Path, int]) -> None:
        """Test that resolved markets are excluded from open markets."""
        db, market_id = open_market
        resolve_market(db, market_id, "yes")
        assert get_open_markets(db) == []

    def test_excludes_cancelled_markets(self, open_market: tuple[Path, int]) -> None:
        """Test that cancelled markets are excluded from open markets."""
        db, market_id = open_market
        cancel_market(db, market_id)
        assert get_open_markets(db) == []


class TestPlaceBet:
    """Tests for place_bet."""

    def test_successful_bet(self, open_market: tuple[Path, int]) -> None:
        """Test that placing a valid bet succeeds."""
        db, market_id = open_market
        _insert_user(db, 1, "alice", 500.0)
        success, message = place_bet(db, 1, "alice", market_id, "yes", 100.0)
        assert success is True
        assert "YES" in message

    def test_invalid_side_fails(self, open_market: tuple[Path, int]) -> None:
        """Test that betting on an invalid side fails."""
        db, market_id = open_market
        _insert_user(db, 1, "alice", 500.0)
        success, message = place_bet(db, 1, "alice", market_id, "maybe", 100.0)
        assert success is False
        assert "yes" in message.lower()

    def test_non_positive_amount_fails(self, open_market: tuple[Path, int]) -> None:
        """Test that betting a non-positive amount fails."""
        db, market_id = open_market
        _insert_user(db, 1, "alice", 500.0)
        success, message = place_bet(db, 1, "alice", market_id, "yes", 0.0)
        assert success is False
        assert "greater than 0" in message

    def test_nonexistent_market_fails(self, db: Path) -> None:
        """Test that betting on a nonexistent market fails."""
        success, message = place_bet(db, 1, "alice", 9999, "yes", 100.0)
        assert success is False
        assert "does not exist" in message

    def test_insufficient_funds_fails(self, open_market: tuple[Path, int]) -> None:
        """Test that betting more than the user's balance fails."""
        db, market_id = open_market
        _insert_user(db, 1, "broke", 10.0)
        success, message = place_bet(db, 1, "broke", market_id, "yes", 100.0)
        assert success is False
        assert "Insufficient" in message

    def test_deducts_money_on_bet(self, open_market: tuple[Path, int]) -> None:
        """Test that the user's balance is reduced after placing a bet."""
        from user import USER_CACHE  # noqa: PLC0415

        db, market_id = open_market
        _insert_user(db, 1, "alice", 500.0)
        place_bet(db, 1, "alice", market_id, "yes", 100.0)

        user: User = USER_CACHE[1]
        assert user.money == pytest.approx(400.0)

    def test_cannot_bet_on_resolved_market(self, open_market: tuple[Path, int]) -> None:
        """Test that betting on an already-resolved market fails."""
        db, market_id = open_market
        resolve_market(db, market_id, "yes")
        success, message = place_bet(db, 1, "alice", market_id, "yes", 100.0)
        assert success is False
        assert "no longer open" in message

    def test_pools_reflect_bets(self, open_market: tuple[Path, int]) -> None:
        """Test that market pools update after bets are placed."""
        db, market_id = open_market
        _insert_user(db, 1, "alice", 500.0)
        _insert_user(db, 2, "bob", 500.0)
        place_bet(db, 1, "alice", market_id, "yes", 100.0)
        place_bet(db, 2, "bob", market_id, "no", 50.0)

        yes_total, no_total = get_market_pools(db, market_id)
        assert yes_total == pytest.approx(100.0)
        assert no_total == pytest.approx(50.0)


class TestResolveMarket:
    """Tests for resolve_market."""

    def test_nonexistent_market_raises(self, db: Path) -> None:
        """Test that resolving a nonexistent market raises ValueError."""
        with pytest.raises(ValueError, match="does not exist"):
            resolve_market(db, 9999, "yes")

    def test_invalid_outcome_raises(self, open_market: tuple[Path, int]) -> None:
        """Test that resolving with an invalid outcome raises ValueError."""
        db, market_id = open_market
        with pytest.raises(ValueError, match="yes"):
            resolve_market(db, market_id, "maybe")

    def test_already_resolved_market_raises(self, open_market: tuple[Path, int]) -> None:
        """Test that resolving an already-resolved market raises ValueError."""
        db, market_id = open_market
        resolve_market(db, market_id, "yes")
        with pytest.raises(ValueError, match="not open"):
            resolve_market(db, market_id, "yes")

    def test_winner_takes_losing_pool_proportionally(self, open_market: tuple[Path, int]) -> None:
        """Test that winners split the losing pool proportional to their stake."""
        from user import USER_CACHE  # noqa: PLC0415

        db, market_id = open_market
        _insert_user(db, 1, "alice", 500.0)
        _insert_user(db, 2, "bob", 500.0)
        _insert_user(db, 3, "carol", 500.0)
        place_bet(db, 1, "alice", market_id, "yes", 100.0)
        place_bet(db, 2, "bob", market_id, "yes", 300.0)
        place_bet(db, 3, "carol", market_id, "no", 200.0)

        settlements = resolve_market(db, market_id, "yes")

        settlement_by_user: dict[int, tuple[float, float]] = {
            user_id: (stake, payout) for user_id, stake, payout in settlements
        }
        # Total pool is 600, split between alice/bob (100/400 and 300/400 of the yes pool).
        assert settlement_by_user[1][1] == pytest.approx(150.0)  # 100 * (600/400)
        assert settlement_by_user[2][1] == pytest.approx(450.0)  # 300 * (600/400)
        assert 3 not in settlement_by_user

        alice: User = USER_CACHE[1]
        bob: User = USER_CACHE[2]
        carol: User = USER_CACHE[3]
        assert alice.money == pytest.approx(500.0 - 100.0 + 150.0)
        assert bob.money == pytest.approx(500.0 - 300.0 + 450.0)
        assert carol.money == pytest.approx(500.0 - 200.0)

    def test_refunds_everyone_when_no_winning_bets(self, open_market: tuple[Path, int]) -> None:
        """Test that all bettors are refunded when nobody bet on the winning side."""
        from user import USER_CACHE  # noqa: PLC0415

        db, market_id = open_market
        _insert_user(db, 1, "alice", 500.0)
        place_bet(db, 1, "alice", market_id, "no", 100.0)

        settlements = resolve_market(db, market_id, "yes")

        assert settlements == [(1, 100.0, 100.0)]
        alice: User = USER_CACHE[1]
        assert alice.money == pytest.approx(500.0)

    def test_market_removed_from_open_list_after_resolution(
        self,
        open_market: tuple[Path, int],
    ) -> None:
        """Test that a resolved market no longer appears as open."""
        db, market_id = open_market
        resolve_market(db, market_id, "yes")
        market: tuple | None = get_market(db, market_id)
        assert market is not None
        assert market[3] == "resolved"
        assert market[4] == "yes"


class TestCancelMarket:
    """Tests for cancel_market."""

    def test_nonexistent_market_raises(self, db: Path) -> None:
        """Test that cancelling a nonexistent market raises ValueError."""
        with pytest.raises(ValueError, match="does not exist"):
            cancel_market(db, 9999)

    def test_already_resolved_market_raises(self, open_market: tuple[Path, int]) -> None:
        """Test that cancelling an already-resolved market raises ValueError."""
        db, market_id = open_market
        resolve_market(db, market_id, "yes")
        with pytest.raises(ValueError, match="not open"):
            cancel_market(db, market_id)

    def test_refunds_all_bettors(self, open_market: tuple[Path, int]) -> None:
        """Test that all bettors get their full stake back on cancellation."""
        from user import USER_CACHE  # noqa: PLC0415

        db, market_id = open_market
        _insert_user(db, 1, "alice", 500.0)
        _insert_user(db, 2, "bob", 500.0)
        place_bet(db, 1, "alice", market_id, "yes", 100.0)
        place_bet(db, 2, "bob", market_id, "no", 50.0)

        refunds = cancel_market(db, market_id)

        assert dict(refunds) == {1: 100.0, 2: 50.0}
        alice: User = USER_CACHE[1]
        bob: User = USER_CACHE[2]
        assert alice.money == pytest.approx(500.0)
        assert bob.money == pytest.approx(500.0)

    def test_market_status_is_cancelled(self, open_market: tuple[Path, int]) -> None:
        """Test that a cancelled market's status is updated."""
        db, market_id = open_market
        cancel_market(db, market_id)
        market: tuple | None = get_market(db, market_id)
        assert market is not None
        assert market[3] == "cancelled"


class TestGetUserBets:
    """Tests for get_user_bets."""

    def test_empty_when_no_bets(self, open_market: tuple[Path, int]) -> None:
        """Test that a user with no bets on a market returns an empty list."""
        db, market_id = open_market
        assert get_user_bets(db, market_id, 1) == []

    def test_aggregates_bets_by_side(self, open_market: tuple[Path, int]) -> None:
        """Test that multiple bets on the same side are aggregated together."""
        db, market_id = open_market
        _insert_user(db, 1, "alice", 500.0)
        place_bet(db, 1, "alice", market_id, "yes", 50.0)
        place_bet(db, 1, "alice", market_id, "yes", 25.0)

        bets = get_user_bets(db, market_id, 1)
        assert bets == [("yes", 75.0)]
