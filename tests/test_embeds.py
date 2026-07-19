"""Tests for utils/misc/embeds.py."""

from discord import Embed
from utils.misc.embeds import extract_embed_text, extract_message_embed_text


class TestExtractEmbedText:
    """Tests for extract_embed_text."""

    def test_empty_embed_returns_empty_string(self) -> None:
        """Test that an embed with no text returns an empty string."""
        assert extract_embed_text(Embed()) == ""

    def test_extracts_title(self) -> None:
        """Test that the title is extracted."""
        embed: Embed = Embed(title="Breaking News")
        assert extract_embed_text(embed) == "Breaking News"

    def test_extracts_description(self) -> None:
        """Test that the description is extracted."""
        embed: Embed = Embed(description="Something happened today.")
        assert extract_embed_text(embed) == "Something happened today."

    def test_extracts_title_and_description_in_order(self) -> None:
        """Test that title comes before description."""
        embed: Embed = Embed(title="Title", description="Description")
        assert extract_embed_text(embed) == "Title\nDescription"

    def test_extracts_fields(self) -> None:
        """Test that fields are extracted as name: value pairs."""
        embed: Embed = Embed()
        embed.add_field(name="Score", value="42")
        embed.add_field(name="Rank", value="1st")
        assert extract_embed_text(embed) == "Score: 42\nRank: 1st"

    def test_extracts_footer(self) -> None:
        """Test that footer text is extracted."""
        embed: Embed = Embed(title="Title")
        embed.set_footer(text="Footer text")
        assert extract_embed_text(embed) == "Title\nFooter text"

    def test_extracts_author_name(self) -> None:
        """Test that the author name is extracted first."""
        embed: Embed = Embed(title="Title")
        embed.set_author(name="Some Author")
        assert extract_embed_text(embed) == "Some Author\nTitle"

    def test_full_embed_order(self) -> None:
        """Test extraction order: author, title, description, fields, footer."""
        embed: Embed = Embed(title="Title", description="Desc")
        embed.set_author(name="Author")
        embed.add_field(name="Field", value="Value")
        embed.set_footer(text="Footer")
        assert extract_embed_text(embed) == "Author\nTitle\nDesc\nField: Value\nFooter"

    def test_skips_whitespace_only_parts(self) -> None:
        """Test that whitespace-only parts are skipped."""
        embed: Embed = Embed(title="   ", description="Real text")
        assert extract_embed_text(embed) == "Real text"


class TestExtractMessageEmbedText:
    """Tests for extract_message_embed_text."""

    def test_no_embeds_returns_empty_string(self) -> None:
        """Test that an empty embed list returns an empty string."""
        assert extract_message_embed_text([]) == ""

    def test_joins_multiple_embeds(self) -> None:
        """Test that multiple embeds are joined with newlines."""
        first: Embed = Embed(title="First")
        second: Embed = Embed(title="Second")
        assert extract_message_embed_text([first, second]) == "First\nSecond"

    def test_skips_empty_embeds(self) -> None:
        """Test that embeds with no text are skipped."""
        empty: Embed = Embed()
        titled: Embed = Embed(title="Only me")
        assert extract_message_embed_text([empty, titled]) == "Only me"
