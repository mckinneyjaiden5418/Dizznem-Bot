"""Tests for utils/money/store_views.py."""

import sqlite3
from pathlib import Path

import pytest
from user import User
from utils.money.stocks import ensure_stocks_tables
from utils.money.store_views import PrestigeConfirmView, StoreView


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up a temporary users database with a fresh user cache."""
    db_path: Path = tmp_path / "users.db"

    monkeypatch.setattr("user.DB_PATH", db_path)
    monkeypatch.setattr("user.USER_CACHE", {})
    monkeypatch.setattr("utils.money.store_views.USERS_DB_PATH", db_path)

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

    ensure_stocks_tables(db_path)
    return db_path


class TestStoreViewCheckBalance:
    """Tests for StoreView._check_balance."""

    def test_uses_live_balance_not_stale_snapshot(self, db: Path) -> None:
        """Test that a low live balance fails the check despite a rich snapshot."""
        user: User = User.create_if_not_exists(user_id=1, username="test")
        user.money = 5
        view: StoreView = StoreView(user_id=1, balance=999_999, prestige=0, bot=None)
        assert view._check_balance(10_000) is False  # noqa: SLF001

    def test_passes_when_live_balance_covers_cost(self, db: Path) -> None:
        """Test that a sufficient live balance passes the check."""
        user: User = User.create_if_not_exists(user_id=2, username="test")
        user.money = 50_000
        view: StoreView = StoreView(user_id=2, balance=0, prestige=0, bot=None)
        assert view._check_balance(10_000) is True  # noqa: SLF001

    def test_fails_when_live_balance_dropped_below_stale_snapshot(
        self,
        db: Path,
    ) -> None:
        """Test the exact stale-balance bug: snapshot said rich, live is now poor."""
        user: User = User.create_if_not_exists(user_id=3, username="test")
        user.money = 100_000
        view: StoreView = StoreView(user_id=3, balance=100_000, prestige=0, bot=None)
        # Balance drops elsewhere while this view is still open (e.g. gambling).
        user.money = 1_000
        assert view._check_balance(10_000) is False  # noqa: SLF001


class TestStoreViewDeduct:
    """Tests for StoreView._deduct."""

    pytestmark = pytest.mark.asyncio

    async def test_deducts_from_live_balance(self, db: Path) -> None:
        """Test that deduct subtracts from the user's live money, not the snapshot."""
        user: User = User.create_if_not_exists(user_id=4, username="test")
        user.money = 100
        view: StoreView = StoreView(user_id=4, balance=100, prestige=0, bot=None)
        await view._deduct(30)  # noqa: SLF001
        assert user.money == 70  # noqa: PLR2004

    async def test_deduct_cannot_be_tricked_by_stale_snapshot(self, db: Path) -> None:
        """Test that deducting twice against a stale snapshot doesn't double count."""
        user: User = User.create_if_not_exists(user_id=5, username="test")
        user.money = 50
        view: StoreView = StoreView(user_id=5, balance=999_999, prestige=0, bot=None)
        await view._deduct(30)  # noqa: SLF001
        assert user.money == 20  # noqa: PLR2004
        assert view.balance == 20  # noqa: PLR2004, SLF001


class TestPrestigeConfirmViewLiveCheck:
    """Tests for PrestigeConfirmView's live balance re-check on confirm."""

    pytestmark = pytest.mark.asyncio

    async def test_prestige_rejected_when_balance_dropped(self, db: Path) -> None:
        """Test that prestige is refused if the live balance no longer covers cost."""
        user: User = User.create_if_not_exists(user_id=6, username="test")
        user.money = 100_000_000
        view: PrestigeConfirmView = PrestigeConfirmView(
            user_id=6,
            bot=None,
            cost=100_000_000,
        )
        # Balance drops below the prestige cost before confirming.
        user.money = 1_000

        class FakeResponse:
            async def edit_message(self, **_kwargs: object) -> None:
                pass

        class FakeInteraction:
            response = FakeResponse()

        await view.confirm.callback(FakeInteraction())

        assert user.money == 1_000  # noqa: PLR2004 -- unchanged, not reset to 0
        assert user.prestige == 0

    async def test_prestige_succeeds_when_balance_still_covers_cost(
        self,
        db: Path,
    ) -> None:
        """Test that prestige still works normally when the balance is sufficient."""
        user: User = User.create_if_not_exists(user_id=7, username="test")
        user.money = 150_000_000
        view: PrestigeConfirmView = PrestigeConfirmView(
            user_id=7,
            bot=None,
            cost=100_000_000,
        )

        class FakeResponse:
            async def edit_message(self, **_kwargs: object) -> None:
                pass

        class FakeInteraction:
            response = FakeResponse()

        await view.confirm.callback(FakeInteraction())

        assert user.money == 0
        assert user.prestige == 1
