"""Tests for general utility helpers."""

import asyncio
from types import SimpleNamespace

from utils.general import get_user_answer, reset_cd


class TestResetCooldown:
    """Tests for reset_cd."""

    def test_does_nothing_without_a_command(self) -> None:
        """A context without a command should be accepted."""
        reset_cd(SimpleNamespace(command=None))

    def test_resets_the_current_command_cooldown(self) -> None:
        """The active command receives the context to reset."""
        calls: list[object] = []
        command: SimpleNamespace = SimpleNamespace(
            reset_cooldown=lambda ctx: calls.append(ctx),
        )
        ctx: SimpleNamespace = SimpleNamespace(command=command)

        reset_cd(ctx)

        assert calls == [ctx]


class TestGetUserAnswer:
    """Tests for get_user_answer."""

    async def test_returns_matching_message_content(self) -> None:
        """A matching reply is returned to the caller."""
        author: object = object()
        channel: object = object()
        ctx: SimpleNamespace = SimpleNamespace(author=author, channel=channel)
        reply: SimpleNamespace = SimpleNamespace(
            author=author,
            channel=channel,
            content="Dizzle answer",
        )

        class Bot:
            async def wait_for(self, _event: str, check: object, timeout: int) -> object:
                assert timeout == 15
                assert check(reply) is True
                assert check(SimpleNamespace(author=object(), channel=channel)) is False
                return reply

        assert await get_user_answer(Bot(), ctx) == "Dizzle answer"

    async def test_returns_none_after_timeout(self) -> None:
        """A timeout produces no answer."""
        ctx: SimpleNamespace = SimpleNamespace(author=object(), channel=object())

        class Bot:
            async def wait_for(self, *_args: object, **_kwargs: object) -> object:
                raise asyncio.TimeoutError

        assert await get_user_answer(Bot(), ctx, timeout=1) is None
