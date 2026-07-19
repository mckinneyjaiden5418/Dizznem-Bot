"""Tests for DeepSeek request helpers."""

from types import SimpleNamespace

import pytest
import requests
import utils.misc.ai as ai_util


class TestGetAiResponse:
    """Tests for get_ai_response."""

    def test_returns_stripped_response_and_sends_context(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The prompt, cache, and system note are sent to DeepSeek."""
        captured: dict = {}

        def fake_post(*_args: object, **kwargs: object) -> object:
            captured.update(kwargs)
            return SimpleNamespace(
                json=lambda: {"choices": [{"message": {"content": "  W pfp.  "}}]},
            )

        monkeypatch.setattr(ai_util.requests, "post", fake_post)

        result: str = ai_util.get_ai_response(
            "who is dizznem?",
            "test-key",
            [{"role": "assistant", "content": "Previous"}],
        )

        assert result == "W pfp."
        assert captured["timeout"] == 15
        assert captured["headers"]["Authorization"] == "Bearer test-key"
        assert captured["json"]["messages"][-1] == {
            "role": "user",
            "content": "who is dizznem?",
        }

    def test_returns_fallback_for_unexpected_response(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An API response without choices returns a user-safe fallback."""
        monkeypatch.setattr(
            ai_util.requests,
            "post",
            lambda *_args, **_kwargs: SimpleNamespace(json=lambda: {}),
        )

        assert "couldn't generate" in ai_util.get_ai_response("hi", "key", [])

    def test_returns_timeout_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A timeout does not escape the utility."""
        monkeypatch.setattr(
            ai_util.requests,
            "post",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(requests.Timeout()),
        )

        assert "timed out" in ai_util.get_ai_response("hi", "key", [])

    def test_returns_request_error_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Other request failures do not escape the utility."""
        monkeypatch.setattr(
            ai_util.requests,
            "post",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(requests.RequestException()),
        )

        assert "Something went wrong" in ai_util.get_ai_response("hi", "key", [])


class TestGetAiSummary:
    """Tests for get_ai_summary."""

    def test_returns_stripped_summary_and_sends_block(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The summary prompt includes the supplied message block."""
        captured: dict = {}

        def fake_post(*_args: object, **kwargs: object) -> object:
            captured.update(kwargs)
            return SimpleNamespace(
                json=lambda: {"choices": [{"message": {"content": "  - Summary  "}}]},
            )

        monkeypatch.setattr(ai_util.requests, "post", fake_post)

        assert ai_util.get_ai_summary("Owen: W bot", "key") == "- Summary"
        assert "Owen: W bot" in captured["json"]["messages"][-1]["content"]
        assert captured["timeout"] == 15

    def test_returns_fallback_for_unexpected_response(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An API response without choices returns a user-safe fallback."""
        monkeypatch.setattr(
            ai_util.requests,
            "post",
            lambda *_args, **_kwargs: SimpleNamespace(json=lambda: {}),
        )

        assert "couldn't generate" in ai_util.get_ai_summary("messages", "key")

    def test_returns_timeout_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A timeout does not escape the utility."""
        monkeypatch.setattr(
            ai_util.requests,
            "post",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(requests.Timeout()),
        )

        assert "timed out" in ai_util.get_ai_summary("messages", "key")

    def test_returns_request_error_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Other request failures do not escape the utility."""
        monkeypatch.setattr(
            ai_util.requests,
            "post",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(requests.RequestException()),
        )

        assert "Something went wrong" in ai_util.get_ai_summary("messages", "key")
