"""Steal command utilities."""

import random

SUCCESS_CHANCE: float = 0.4
MIN_TARGET_BALANCE: float = 10_000.0
MIN_THIEF_BALANCE: float = 1_000.0
STEAL_PERCENT_RANGE: tuple[float, float] = (0.10, 0.25)
FAIL_PENALTY_PERCENT: float = 0.10


def resolve_steal(stealer_money: float, target_money: float) -> tuple[bool, float]:
    """Resolve a steal attempt against a target's balance.

    On success, the stealer takes a random percentage of the target's
    money. On failure, the stealer is caught and pays a flat percentage
    of their own money as a penalty.

    Args:
        stealer_money (float): The stealer's current balance.
        target_money (float): The target's current balance.

    Returns:
        tuple[bool, float]: (success, amount). On success, amount is
        moved from target to stealer. On failure, amount is deducted
        from the stealer only.
    """
    if random.random() < SUCCESS_CHANCE:  # noqa: S311
        percent: float = random.uniform(*STEAL_PERCENT_RANGE)  # noqa: S311
        return True, round(target_money * percent, 2)

    return False, round(stealer_money * FAIL_PENALTY_PERCENT, 2)
