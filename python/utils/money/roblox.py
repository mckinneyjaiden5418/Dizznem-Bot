"""Roblox util."""

import asyncio
import random
from datetime import UTC, datetime, timedelta
from typing import TypedDict

import requests
from rapidfuzz import fuzz

ABA_BASE: str = "https://animebattlearenaaba.fandom.com"
ROGUE_BASE: str = "https://rogue-lineage.fandom.com"

ABA_CATEGORIES: dict[str, str] = {
    "character": "Characters",
}

ROGUE_CATEGORIES: dict[str, str] = {
    "race": "Races",
    "artifact": "Artifacts",
    "creature": "Creatures",
}

ROGUE_QUESTIONS: dict[str, str] = {
    "race": "What race is this?",
    "artifact": "What artifact is this?",
    "creature": "What creature is this?",
}

_CATEGORY_PAGE_FILTER: set[str] = {
    "Races",
    "Artifacts",
    "Creatures",
    "Characters",
    "Creatures (Khei)",
    "Khei Artifacts",
}

CACHE_TTL: timedelta = timedelta(hours=24)

FUZZY_THRESHOLD: int = 80
MIN_ANSWER_LENGTH: int = 4


class CharacterEntry(TypedDict):
    """A single wiki character entry."""

    name: str
    image_url: str | None


class GameCache(TypedDict):
    """Cached wiki data for a game."""

    data: dict[str, list[CharacterEntry]]
    cached_at: datetime


_cache: dict[str, GameCache] = {}


def set_cache(game: str, entry: GameCache) -> None:
    """Set a cache entry for a game. Intended for use in tests.

    Args:
        game (str): "aba" or "rogue".
        entry (GameCache): Cache entry to store.
    """
    _cache[game] = entry


def get_cache(game: str) -> GameCache | None:
    """Get the cache entry for a game. Intended for use in tests.

    Args:
        game (str): "aba" or "rogue".

    Returns:
        GameCache | None: Cached entry, or None if not present.
    """
    return _cache.get(game)


def clear_cache() -> None:
    """Clear all cached wiki data. Intended for use in tests."""
    _cache.clear()


def api_get(wiki_base: str, params: dict) -> dict:
    """Make a single MediaWiki API GET request.

    Args:
        wiki_base (str): Base URL of the wiki.
        params (dict): Query parameters.

    Returns:
        dict: Parsed JSON response.

    Raises:
        requests.HTTPError: On non-2xx responses.
        requests.Timeout: If the request exceeds 10 seconds.
    """
    params.setdefault("format", "json")
    params.setdefault("action", "query")
    response = requests.get(
        f"{wiki_base}/api.php",
        params=params,
        timeout=10,
        headers={"User-Agent": "DizznemBot/1.0 (Discord bot; contact via Discord)"},
    )
    response.raise_for_status()
    return response.json()


def fetch_category_members(wiki_base: str, category: str) -> list[str]:
    """Return all article titles in a wiki category, handling pagination.

    Args:
        wiki_base (str): Base URL of the wiki.
        category (str): Category name without the 'Category:' prefix.

    Returns:
        list[str]: Page titles belonging to that category.
    """
    titles: list[str] = []
    params: dict = {
        "list": "categorymembers",
        "cmtitle": f"Category:{category}",
        "cmlimit": "500",
        "cmtype": "page",
        "cmnamespace": "0",
    }

    while True:
        data: dict = api_get(wiki_base, params)
        members: list[dict] = data.get("query", {}).get("categorymembers", [])
        titles.extend(m["title"] for m in members)

        cont: str | None = data.get("continue", {}).get("cmcontinue")
        if not cont:
            break
        params["cmcontinue"] = cont

    return titles


def fetch_image_url(wiki_base: str, title: str) -> str | None:
    """Fetch the URL for a wiki page's lead image at native resolution.

    The original image is preferred over a thumbnail: requesting a
    thumbnail wider than the source makes Fandom upscale it, which is
    what made some trivia images blurry.

    Args:
        wiki_base (str): Base URL of the wiki.
        title (str): Exact page title.

    Returns:
        str | None: Image URL, or None if the page has no image.
    """
    data: dict = api_get(
        wiki_base,
        {
            "prop": "pageimages",
            "titles": title,
            "piprop": "original|thumbnail",
            "pithumbsize": "800",
            "pilicense": "any",
        },
    )
    pages: dict = data.get("query", {}).get("pages", {})
    for page in pages.values():
        original: dict | None = page.get("original")
        if original:
            return original["source"]
        thumbnail: dict | None = page.get("thumbnail")
        if thumbnail:
            return thumbnail["source"]
    return None


def build_entries(wiki_base: str, category: str) -> list[CharacterEntry]:
    """Build a list of character entries for a category with no images yet.

    Images are resolved lazily on first pick rather than upfront, to avoid
    making 190+ API calls on the first command use.

    Args:
        wiki_base (str): Base URL of the wiki.
        category (str): Category name without the 'Category:' prefix.

    Returns:
        list[CharacterEntry]: One entry per character, image_url starts as None.
    """
    titles: list[str] = fetch_category_members(wiki_base, category)
    return [
        CharacterEntry(name=t, image_url=None)
        for t in titles
        if t not in _CATEGORY_PAGE_FILTER
    ]


def populate_cache_blocking(game: str) -> None:
    """Synchronously build and store the full cache entry for a game.

    Args:
        game (str): "aba" or "rogue".
    """
    if game == "aba":
        wiki_base: str = ABA_BASE
        categories: dict[str, str] = ABA_CATEGORIES
    else:
        wiki_base: str = ROGUE_BASE
        categories: dict[str, str] = ROGUE_CATEGORIES

    data: dict[str, list[CharacterEntry]] = {}
    for key, category_name in categories.items():
        data[key] = build_entries(wiki_base, category_name)

    _cache[game] = GameCache(data=data, cached_at=datetime.now(tz=UTC))


async def ensure_cache(game: str) -> None:
    """Ensure the cache for a game is populated and not stale.

    Args:
        game (str): "aba" or "rogue".
    """
    cached: GameCache | None = _cache.get(game)
    if cached is None or datetime.now(tz=UTC) - cached["cached_at"] > CACHE_TTL:
        await asyncio.to_thread(populate_cache_blocking, game)


def resolve_image_blocking(wiki_base: str, entry: CharacterEntry) -> str | None:
    """Fetch and cache the image URL for a single entry if not already set.

    Mutates entry["image_url"] in place so the same character skips the
    API call on subsequent picks.

    Args:
        wiki_base (str): Base URL of the wiki.
        entry (CharacterEntry): The character entry to resolve.

    Returns:
        str | None: The image URL, or None if none found.
    """
    if entry["image_url"] is None:
        entry["image_url"] = fetch_image_url(wiki_base, entry["name"])
    return entry["image_url"]


async def resolve_image(wiki_base: str, entry: CharacterEntry) -> str | None:
    """Async wrapper for resolve_image_blocking.

    Args:
        wiki_base (str): Base URL of the wiki.
        entry (CharacterEntry): The character entry to resolve.

    Returns:
        str | None: The image URL, or None if none found.
    """
    return await asyncio.to_thread(resolve_image_blocking, wiki_base, entry)


async def question(game: str) -> tuple[str | None, str, str]:
    """Get a random trivia question for the given game.

    Args:
        game (str): "aba" or "rogue".

    Returns:
        tuple[str | None, str, str]: Image URL, question text, and answer.

    Raises:
        ValueError: If game is not "aba" or "rogue".
        RuntimeError: If the fetched category has no entries.
    """
    if game not in ("aba", "rogue"):
        msg: str = f"Unknown game: {game!r}"
        raise ValueError(msg)

    await ensure_cache(game)

    wiki_base: str = ABA_BASE if game == "aba" else ROGUE_BASE
    cached_data: dict[str, list[CharacterEntry]] = _cache[game]["data"]

    if game == "aba":
        category_key: str = "character"
        trivia_question: str = "What character is this?"
    else:
        category_key: str = random.choice(list(ROGUE_CATEGORIES.keys()))  # noqa: S311
        trivia_question: str = ROGUE_QUESTIONS[category_key]

    entries: list[CharacterEntry] = cached_data[category_key]
    if not entries:
        msg: str = f"No entries found for category {category_key!r}"
        raise RuntimeError(msg)

    entry: CharacterEntry = random.choice(entries)  # noqa: S311
    image_url: str | None = await resolve_image(wiki_base, entry)

    return image_url, trivia_question, entry["name"]


def check_answer(answer: str, user_answer: str) -> bool:
    """Check if the user's answer matches the correct answer.

    Args:
        answer (str): Correct answer.
        user_answer (str): User's answer.

    Returns:
        bool: True if user answered correctly.
    """
    user_answer = user_answer.lower().strip()
    user_answer = nicknames(user_answer)
    answer = answer.lower()

    if user_answer == answer:
        return True

    if len(user_answer) < MIN_ANSWER_LENGTH:
        return False

    return fuzz.partial_ratio(user_answer, answer) >= FUZZY_THRESHOLD


def nicknames(name: str) -> str:
    """Get canonical name if a nickname was used.

    Args:
        name (str): Possible nickname.

    Returns:
        str: Nickname changed to correct answer if applicable.
    """
    nickname_map: dict[str, str] = {
        # ABA
        "ay": "ay (4th raikage)",
        "boa": "boa hancock",
        "hol": "hol horse",
        "b": "killer b",
        # Rogue Lineage - Races
        "fisch": "fischeran",
        "metal scroom": "metascroom",
        "mscroom": "metascroom",
        "greater dull": "greater dullahan",
        "gdull": "greater dullahan",
        "gdullahan": "greater dullahan",
        "greater nav": "greater navaran",
        "gnav": "greater navaran",
        "asc kasp": "ascended kasparan",
        "asc vind": "ascended vind",
        "kasp": "kasparan",
        "nav": "navaran",
        "cons": "construct",
        # Rogue Lineage - Artifacts
        "pd": "phoenix down",
        "phoenix clown": "phoenix down",
        "wka": "amulet of the white king",
        "white kings amulet": "amulet of the white king",
        "white king amulet": "amulet of the white king",
        "ff": "fairfrozen",
        "philo": "philosopher's stone",
        "philosophers stone": "philosopher's stone",
        "lannis": "lannis' amulet",
        "lannis amulet": "lannis' amulet",
        "sc": "spider cloak",
        "mscroom key": "scroom key",
        "metascroom key": "scroom key",
        # Rogue Lineage - Creatures
        "z scroom": "zombie scroom",
        "redacted": "evil eye",
        "sigil shrieker": "sealed shrieker",
        "sigil shriekers": "sealed shrieker",
        "lava serpent": "lava snake",
        "tundra dragon": "ice dragon",
        "ice drag": "ice dragon",
    }
    return nickname_map.get(name.lower(), name)
