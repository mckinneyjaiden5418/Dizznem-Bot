"""Tests for DizznemBot.on_ready in bot/bot.py."""

import pytest
from bot.bot import DizznemBot


class FakeChannel:
    """A minimal stand-in for a discord.TextChannel."""

    def __init__(self) -> None:
        """Initialize the fake channel."""
        self.sent_messages: list[str] = []

    async def send(self, content: str) -> None:
        """Record a sent message instead of hitting the network.

        Args:
            content (str): The message content.
        """
        self.sent_messages.append(content)


@pytest.fixture
def bot() -> DizznemBot:
    """Create a DizznemBot instance without connecting to Discord."""
    return DizznemBot()


class TestOnReady:
    """Tests for on_ready."""

    pytestmark = pytest.mark.asyncio

    async def test_missing_channel_does_not_raise(
        self,
        bot: DizznemBot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that a missing test channel is handled instead of crashing."""
        monkeypatch.setattr(bot, "get_channel", lambda _id: None)
        await bot.on_ready()  # should not raise

    async def test_sends_hello_when_channel_found(
        self,
        bot: DizznemBot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that Hello is sent to the test channel when it's found."""
        channel = FakeChannel()
        monkeypatch.setattr(bot, "get_channel", lambda _id: channel)
        await bot.on_ready()
        assert channel.sent_messages == ["Hello"]

    async def test_second_call_does_not_resend(
        self,
        bot: DizznemBot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that a second on_ready (e.g. gateway reconnect) doesn't resend."""
        channel = FakeChannel()
        monkeypatch.setattr(bot, "get_channel", lambda _id: channel)

        await bot.on_ready()
        await bot.on_ready()

        assert channel.sent_messages == ["Hello"]

    async def test_second_call_does_not_touch_get_channel(
        self,
        bot: DizznemBot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that a repeat on_ready short-circuits before looking up the channel."""
        calls: list[int] = []

        def fake_get_channel(channel_id: int) -> None:
            calls.append(channel_id)
            return None

        monkeypatch.setattr(bot, "get_channel", fake_get_channel)

        await bot.on_ready()
        await bot.on_ready()

        assert len(calls) == 1
