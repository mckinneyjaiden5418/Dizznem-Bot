"""Help text utility."""

from discord.ext import commands

CATEGORY_MAP: dict[str, str] = {
    "Money": "💰 Economy",
    "MoneyMaking": "💰 Economy",
    "Stocks": "💰 Economy",
    "YouTube": "🎵 Music",
    "Games": "🎮 Games",
    "UserInfo": "👤 Profile",
    "AI": "🤖 AI",
    "Misc": "ℹ️ Misc",
    "Admin": "🛠️ Admin",
}

CATEGORY_ORDER: list[str] = [
    "💰 Economy",
    "🎵 Music",
    "🎮 Games",
    "👤 Profile",
    "🤖 AI",
    "ℹ️ Misc",
    "🛠️ Admin",
]

ADMIN_CATEGORY: str = "🛠️ Admin"
MAX_FIELD_LENGTH: int = 1000


def build_help_categories(
    bot: commands.Bot,
    is_admin: bool,
) -> dict[str, list[str]]:
    """Group bot commands into display categories.

    Args:
        bot (commands.Bot): The bot instance.
        is_admin (bool): Whether to include the admin-only category.

    Returns:
        dict[str, list[str]]: Category label -> list of formatted command lines.
    """
    categories: dict[str, list[str]] = {}
    for cmd in sorted(bot.commands, key=lambda c: c.name):
        cog_name: str = cmd.cog_name or "Misc"
        category: str = CATEGORY_MAP.get(cog_name, "ℹ️ Misc")
        if category == ADMIN_CATEGORY and not is_admin:
            continue

        description: str = cmd.description or cmd.help or "No description."
        categories.setdefault(category, []).append(f"**${cmd.name}** — {description}")

    return categories


def chunk_lines(lines: list[str], max_length: int = MAX_FIELD_LENGTH) -> list[str]:
    """Group lines into chunks that each fit within an embed field's length limit.

    Args:
        lines (list[str]): Lines to group.
        max_length (int): Max characters per chunk.

    Returns:
        list[str]: Newline-joined chunks, each under max_length.
    """
    chunks: list[str] = []
    current: list[str] = []
    current_length: int = 0

    for line in lines:
        if current and current_length + len(line) + 1 > max_length:
            chunks.append("\n".join(current))
            current = []
            current_length = 0
        current.append(line)
        current_length += len(line) + 1

    if current:
        chunks.append("\n".join(current))

    return chunks
