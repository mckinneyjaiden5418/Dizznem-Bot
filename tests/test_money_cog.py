"""Regression tests for bot/cogs/money/money.py command signatures."""

import inspect

from bot.cogs.money.money import Money


class TestNetworthSignature:
    """Tests for the /networth command's parameter defaults."""

    def test_member_defaults_to_none(self) -> None:
        """member must default to None so /networth works with no argument.

        Regression test: member previously had no default, making the
        member argument required for both the slash command and $networth,
        so a user couldn't check their own net worth without tagging
        themselves. See /balance for the correct pattern.
        """
        sig: inspect.Signature = inspect.signature(Money.networth.callback)
        member_param: inspect.Parameter = sig.parameters["member"]
        assert member_param.default is None
