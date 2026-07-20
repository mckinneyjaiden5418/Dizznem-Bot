"""Tests for log.py."""

import logging

import log
import pytest


def test_set_up_logger_uses_append_filemode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the log file is opened in append mode, not truncated.

    Truncating on every start (the old "w" mode) destroys the log from
    whatever crash caused the restart, right when it's needed most.
    """
    captured: dict = {}

    def fake_basic_config(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(logging, "basicConfig", fake_basic_config)
    log.set_up_logger("test_module")

    assert captured["filemode"] == "a"
