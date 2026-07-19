"""Embed text extraction utilities."""

from discord import Embed

MAX_EMBED_TEXT_LENGTH: int = 1500


def extract_embed_text(embed: Embed) -> str:
    """Flatten an embed's readable text into a single plain-text string.

    Pulls the author name, title, description, fields, and footer text
    from the embed, skipping any that are unset.

    Args:
        embed (Embed): The Discord embed to extract text from.

    Returns:
        str: The extracted text joined by newlines, or an empty string
        if the embed contains no readable text.
    """
    parts: list[str] = []

    if embed.author and embed.author.name:
        parts.append(embed.author.name)
    if embed.title:
        parts.append(embed.title)
    if embed.description:
        parts.append(embed.description)
    for field in embed.fields:
        name: str = (field.name or "").strip()
        value: str = (field.value or "").strip()
        if name and value:
            parts.append(f"{name}: {value}")
        elif name or value:
            parts.append(name or value)
    if embed.footer and embed.footer.text:
        parts.append(embed.footer.text)

    return "\n".join(part.strip() for part in parts if part.strip())


def extract_message_embed_text(embeds: list[Embed]) -> str:
    """Flatten all embeds on a message into one plain-text block.

    A single embed can hold up to 6000 characters across its fields, which
    would otherwise let one message dominate (or blow past) the summarize
    char budget. The combined result is capped at MAX_EMBED_TEXT_LENGTH.

    Args:
        embeds (list[Embed]): The message's embeds.

    Returns:
        str: Text from all embeds joined by newlines and capped in length,
        or an empty string if none contain readable text.
    """
    texts: list[str] = [extract_embed_text(embed) for embed in embeds]
    combined: str = "\n".join(text for text in texts if text)
    if len(combined) > MAX_EMBED_TEXT_LENGTH:
        combined = combined[:MAX_EMBED_TEXT_LENGTH].rstrip() + "…"
    return combined
