"""Tests for utils/money/steal.py."""

import pytest
from utils.money.steal import (
    FAIL_PENALTY_PERCENT,
    STEAL_PERCENT_RANGE,
    resolve_steal,
)


class TestResolveSteal:
    """Tests for resolve_steal."""

    def test_success_takes_percent_of_target_money(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that a successful steal takes a percentage of the target's money."""
        monkeypatch.setattr("utils.money.steal.random.random", lambda: 0.0)
        monkeypatch.setattr("utils.money.steal.random.uniform", lambda *_a: 0.20)

        success: bool
        amount: float
        success, amount = resolve_steal(stealer_money=1000.0, target_money=10_000.0)

        assert success is True
        assert amount == pytest.approx(2000.0)

    def test_failure_costs_percent_of_stealer_money(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that a failed steal costs the stealer a fixed percentage of their money."""
        monkeypatch.setattr("utils.money.steal.random.random", lambda: 0.99)

        success: bool
        amount: float
        success, amount = resolve_steal(stealer_money=1000.0, target_money=10_000.0)

        assert success is False
        assert amount == pytest.approx(1000.0 * FAIL_PENALTY_PERCENT)

    def test_success_amount_within_configured_range(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that the stolen amount always falls within STEAL_PERCENT_RANGE."""
        monkeypatch.setattr("utils.money.steal.random.random", lambda: 0.0)

        low, high = STEAL_PERCENT_RANGE
        for _ in range(20):
            _success, amount = resolve_steal(stealer_money=500.0, target_money=1000.0)
            assert low * 1000.0 <= amount <= high * 1000.0

    def test_returns_rounded_amount(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that returned amounts are rounded to 2 decimal places."""
        monkeypatch.setattr("utils.money.steal.random.random", lambda: 0.0)
        monkeypatch.setattr("utils.money.steal.random.uniform", lambda *_a: 0.123456)

        _success, amount = resolve_steal(stealer_money=1000.0, target_money=333.333)
        assert amount == round(amount, 2)
