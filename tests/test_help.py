"""Tests for utils/misc/help.py."""

from types import SimpleNamespace
from typing import Any

from utils.misc.help import ADMIN_CATEGORY, build_help_categories, chunk_lines


def make_command(
    name: str,
    cog_name: str | None,
    description: str = "A command.",
    help_text: str | None = None,
) -> Any:  # noqa: ANN401
    """Create a fake discord.py command for testing.

    Args:
        name (str): Command name.
        cog_name (str | None): Owning cog's class name.
        description (str): Command description.
        help_text (str | None): Fallback help text.

    Returns:
        Any: A stand-in object with the attributes build_help_categories reads.
    """
    return SimpleNamespace(
        name=name,
        cog_name=cog_name,
        description=description,
        help=help_text,
    )


def make_bot(commands_list: list[Any]) -> Any:  # noqa: ANN401
    """Create a fake bot exposing a commands list.

    Args:
        commands_list (list[Any]): Fake commands.

    Returns:
        Any: A stand-in object with a .commands attribute.
    """
    return SimpleNamespace(commands=commands_list)


class TestBuildHelpCategories:
    """Tests for build_help_categories."""

    def test_groups_by_category(self) -> None:
        """Test that commands are grouped into their mapped category."""
        bot: Any = make_bot(
            [
                make_command("daily", "MoneyMaking"),
                make_command("play", "YouTube"),
            ],
        )
        categories: dict[str, list[str]] = build_help_categories(bot, is_admin=False)
        assert any("daily" in line for line in categories["💰 Economy"])
        assert any("play" in line for line in categories["🎵 Music"])

    def test_unknown_cog_falls_back_to_misc(self) -> None:
        """Test that commands from an unmapped cog land in Misc."""
        bot: Any = make_bot([make_command("mystery", "SomeNewCog")])
        categories: dict[str, list[str]] = build_help_categories(bot, is_admin=False)
        assert any("mystery" in line for line in categories["ℹ️ Misc"])

    def test_admin_category_hidden_for_non_admin(self) -> None:
        """Test that admin commands are excluded for non-admins."""
        bot: Any = make_bot([make_command("addmoney", "Admin")])
        categories: dict[str, list[str]] = build_help_categories(bot, is_admin=False)
        assert ADMIN_CATEGORY not in categories

    def test_admin_category_shown_for_admin(self) -> None:
        """Test that admin commands are included for admins."""
        bot: Any = make_bot([make_command("addmoney", "Admin")])
        categories: dict[str, list[str]] = build_help_categories(bot, is_admin=True)
        assert any("addmoney" in line for line in categories[ADMIN_CATEGORY])

    def test_uses_help_as_description_fallback(self) -> None:
        """Test that .help is used when .description is empty."""
        bot: Any = make_bot(
            [make_command("foo", "Misc", description="", help_text="Help text.")],
        )
        categories: dict[str, list[str]] = build_help_categories(bot, is_admin=False)
        assert "Help text." in categories["ℹ️ Misc"][0]

    def test_uses_no_description_fallback(self) -> None:
        """Test that a generic fallback is used with no description or help."""
        bot: Any = make_bot([make_command("foo", "Misc", description="")])
        categories: dict[str, list[str]] = build_help_categories(bot, is_admin=False)
        assert "No description." in categories["ℹ️ Misc"][0]

    def test_sorted_alphabetically(self) -> None:
        """Test that commands within a category are alphabetically sorted."""
        bot: Any = make_bot(
            [make_command("zeta", "Misc"), make_command("alpha", "Misc")],
        )
        categories: dict[str, list[str]] = build_help_categories(bot, is_admin=False)
        names: list[str] = categories["ℹ️ Misc"]
        assert names[0].startswith("**$alpha**")
        assert names[1].startswith("**$zeta**")

    def test_no_cog_falls_back_to_misc(self) -> None:
        """Test that a command with no cog lands in Misc."""
        bot: Any = make_bot([make_command("orphan", None)])
        categories: dict[str, list[str]] = build_help_categories(bot, is_admin=False)
        assert any("orphan" in line for line in categories["ℹ️ Misc"])


class TestChunkLines:
    """Tests for chunk_lines."""

    def test_single_chunk_when_short(self) -> None:
        """Test that short lines are combined into a single chunk."""
        assert chunk_lines(["a", "b", "c"], max_length=1000) == ["a\nb\nc"]

    def test_splits_when_exceeding_max_length(self) -> None:
        """Test that lines are split once the max length would be exceeded."""
        lines: list[str] = ["x" * 60, "y" * 60]
        chunks: list[str] = chunk_lines(lines, max_length=100)
        assert chunks == ["x" * 60, "y" * 60]

    def test_empty_list_returns_empty(self) -> None:
        """Test that an empty input returns an empty output."""
        assert chunk_lines([]) == []

    def test_oversized_single_line_kept_alone(self) -> None:
        """Test that a single line longer than max_length isn't dropped or split."""
        line: str = "z" * 200
        assert chunk_lines([line], max_length=100) == [line]
