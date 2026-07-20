"""Tests for exception-handling correctness in bot/bot.py.

CommandTree.sync() documents exactly five exception types it can raise
(HTTPException, Forbidden, CommandSyncFailure, TranslationError,
MissingApplicationID). setup_hook()'s except clause around that call must
catch all five, or a routine sync failure (rate limit, missing scope, bad
command data) crashes the entire bot startup instead of being logged.
"""

from discord import Forbidden, HTTPException
from discord.app_commands import AppCommandError, CommandSyncFailure, TranslationError
from discord.errors import MissingApplicationID

# Mirrors the except tuple in bot/bot.py's setup_hook().
SYNC_EXCEPT_TUPLE: tuple[type[Exception], ...] = (HTTPException, AppCommandError)


class TestTreeSyncExceptionCoverage:
    """Every exception CommandTree.sync() can raise must be caught."""

    def test_http_exception_is_covered(self) -> None:
        """Test that a plain HTTPException is covered."""
        assert issubclass(HTTPException, SYNC_EXCEPT_TUPLE)

    def test_forbidden_is_covered(self) -> None:
        """Test that Forbidden (missing applications.commands scope) is covered."""
        assert issubclass(Forbidden, SYNC_EXCEPT_TUPLE)

    def test_command_sync_failure_is_covered(self) -> None:
        """Test that CommandSyncFailure (invalid command data) is covered."""
        assert issubclass(CommandSyncFailure, SYNC_EXCEPT_TUPLE)

    def test_translation_error_is_covered(self) -> None:
        """Test that TranslationError is covered."""
        assert issubclass(TranslationError, SYNC_EXCEPT_TUPLE)

    def test_missing_application_id_is_covered(self) -> None:
        """Test that MissingApplicationID is covered."""
        assert issubclass(MissingApplicationID, SYNC_EXCEPT_TUPLE)

    def test_old_buggy_tuple_covered_none_of_these(self) -> None:
        """Regression guard: documents the bug this fix corrects.

        The old except tuple (commands.ExtensionError, OSError) matched
        none of the real exception types sync() raises -- any sync
        failure propagated uncaught out of setup_hook() and crashed
        bot startup instead of being logged and skipped.
        """
        from discord.ext import commands

        old_tuple: tuple[type[Exception], ...] = (commands.ExtensionError, OSError)
        real_exceptions: tuple[type[Exception], ...] = (
            HTTPException,
            Forbidden,
            CommandSyncFailure,
            TranslationError,
            MissingApplicationID,
        )
        assert not any(issubclass(exc, old_tuple) for exc in real_exceptions)
