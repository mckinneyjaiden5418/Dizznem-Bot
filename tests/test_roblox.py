"""Tests for utils/money/roblox.py."""

from datetime import UTC, datetime, timedelta

import pytest
import utils.money.roblox as roblox_util
from utils.money.roblox import (
    ROGUE_QUESTIONS,
    CharacterEntry,
    GameCache,
    build_entries,
    check_answer,
    clear_cache,
    fetch_category_members,
    fetch_image_url,
    get_cache,
    nicknames,
    populate_cache_blocking,
    question,
    resolve_image_blocking,
    set_cache,
)


def make_entry(name: str, image_url: str | None = None) -> CharacterEntry:
    """Create a CharacterEntry for testing.

    Args:
        name (str): Character name.
        image_url (str | None): Optional image URL.

    Returns:
        CharacterEntry: Test entry.
    """
    return CharacterEntry(name=name, image_url=image_url)


def inject_cache(game: str, data: dict, age: timedelta = timedelta(hours=0)) -> None:
    """Inject a fake cache entry via the public set_cache helper.

    Args:
        game (str): "aba" or "rogue".
        data (dict): Category data to cache.
        age (timedelta): How old to make the cache entry.
    """
    set_cache(
        game,
        GameCache(data=data, cached_at=datetime.now(tz=UTC) - age),
    )


class TestCheckAnswer:
    """Tests for check_answer."""

    def test_correct_exact_answer(self) -> None:
        """Test that exact answers are recognized as correct."""
        assert check_answer("fischeran", "fischeran") is True

    def test_wrong_answer(self) -> None:
        """Test that an incorrect answer is rejected."""
        assert check_answer("fischeran", "goku") is False

    def test_case_insensitive(self) -> None:
        """Test that answer matching is case insensitive."""
        assert check_answer("fischeran", "FISCHERAN") is True

    def test_strips_whitespace(self) -> None:
        """Test that whitespace is ignored in answers."""
        assert check_answer("fischeran", "  fischeran  ") is True

    def test_nickname_resolves_correctly(self) -> None:
        """Test that nicknames resolve correctly to the expected answer."""
        assert check_answer("fischeran", "fisch") is True

    def test_wrong_nickname_fails(self) -> None:
        """Test that an incorrect nickname is rejected."""
        assert check_answer("fischeran", "pd") is False

    def test_partial_match_fails(self) -> None:
        """Test that an unrelated partial string is not accepted."""
        assert check_answer("Goku Black", "vege") is False

    def test_empty_user_answer(self) -> None:
        """Test that an empty string is not accepted."""
        assert check_answer("Goku", "") is False

    def test_short_exact_match_bypasses_length_check(self) -> None:
        """Test that short answers like '2B' pass if they exactly match."""
        assert check_answer("2B", "2b") is True

    def test_short_non_match_blocked_by_length_check(self) -> None:
        """Test that short guesses that don't exactly match are blocked."""
        assert check_answer("2B", "2c") is False


class TestNicknames:
    """Tests for nicknames."""

    def test_known_nickname_resolved(self) -> None:
        """Test that a known nickname resolves to the correct value."""
        assert nicknames("fisch") == "fischeran"

    def test_pd_resolves(self) -> None:
        """Test that 'pd' resolves to the expected item."""
        assert nicknames("pd") == "phoenix down"

    def test_wka_resolves(self) -> None:
        """Test that 'wka' resolves to the expected item."""
        assert nicknames("wka") == "amulet of the white king"

    def test_white_kings_amulet_resolves(self) -> None:
        """Test that 'white kings amulet' resolves to the expected item."""
        assert nicknames("white kings amulet") == "amulet of the white king"

    def test_ff_resolves(self) -> None:
        """Test that 'ff' resolves to the expected item."""
        assert nicknames("ff") == "fairfrozen"

    def test_philosophers_stone_alternate_spelling(self) -> None:
        """Test that alternate spellings resolve correctly."""
        assert nicknames("philosophers stone") == "philosopher's stone"

    def test_lannis_resolves(self) -> None:
        """Test that 'lannis' resolves to the expected item."""
        assert nicknames("lannis") == "lannis' amulet"

    def test_lannis_amulet_resolves(self) -> None:
        """Test that 'lannis amulet' resolves to the expected item."""
        assert nicknames("lannis amulet") == "lannis' amulet"

    def test_gdull_resolves(self) -> None:
        """Test that 'gdull' resolves to greater dullahan."""
        assert nicknames("gdull") == "greater dullahan"

    def test_greater_dull_resolves(self) -> None:
        """Test that 'greater dull' resolves to greater dullahan."""
        assert nicknames("greater dull") == "greater dullahan"

    def test_gnav_resolves(self) -> None:
        """Test that 'gnav' resolves to greater navaran."""
        assert nicknames("gnav") == "greater navaran"

    def test_redacted_resolves(self) -> None:
        """Test that 'redacted' resolves to evil eye."""
        assert nicknames("redacted") == "evil eye"

    def test_phoenix_clown_resolves(self) -> None:
        """Test that 'phoenix clown' resolves to phoenix down."""
        assert nicknames("phoenix clown") == "phoenix down"

    def test_mscroom_key_resolves(self) -> None:
        """Test that 'mscroom key' resolves to scroom key."""
        assert nicknames("mscroom key") == "scroom key"

    def test_ice_drag_resolves(self) -> None:
        """Test that 'ice drag' resolves to ice dragon."""
        assert nicknames("ice drag") == "ice dragon"

    def test_unknown_name_returns_itself(self) -> None:
        """Test that unknown valid names return themselves."""
        assert nicknames("fischeran") == "fischeran"

    def test_unknown_name_no_match(self) -> None:
        """Test that totally unknown names are returned unchanged."""
        assert nicknames("totallyrandom") == "totallyrandom"

    def test_case_insensitive_lookup(self) -> None:
        """Test that nickname lookup ignores case."""
        assert nicknames("FISCH") == "fischeran"

    def test_lava_serpent_alias(self) -> None:
        """Test that 'lava serpent' resolves to the proper alias."""
        assert nicknames("lava serpent") == "lava snake"

    def test_tundra_dragon_alias(self) -> None:
        """Test that 'tundra dragon' resolves to the proper alias."""
        assert nicknames("tundra dragon") == "ice dragon"

    def test_sigil_shrieker_variants(self) -> None:
        """Test that both sigil shrieker variants resolve correctly."""
        assert nicknames("sigil shrieker") == "sealed shrieker"
        assert nicknames("sigil shriekers") == "sealed shrieker"

    def test_mscroom_variants(self) -> None:
        """Test that both mscroom variants resolve correctly."""
        assert nicknames("mscroom") == "metascroom"
        assert nicknames("metal scroom") == "metascroom"


class TestCheckAnswerWithNicknames:
    """Integration tests for check_answer resolving nicknames."""

    def test_fisch_resolves(self) -> None:
        """Test that 'fisch' resolves to fischeran."""
        assert check_answer("fischeran", "fisch") is True

    def test_pd_resolves(self) -> None:
        """Test that 'pd' resolves to phoenix down."""
        assert check_answer("phoenix down", "pd") is True

    def test_mscroom_resolves(self) -> None:
        """Test that 'mscroom' resolves to metascroom."""
        assert check_answer("metascroom", "mscroom") is True

    def test_metal_scroom_resolves(self) -> None:
        """Test that 'metal scroom' resolves to metascroom."""
        assert check_answer("metascroom", "metal scroom") is True


class TestFetchCategoryMembers:
    """Tests for fetch_category_members."""

    def test_single_page(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a single page of results is returned correctly."""
        payload: dict = {
            "query": {
                "categorymembers": [
                    {"title": "Goku", "ns": 0},
                    {"title": "Naruto Uzumaki", "ns": 0},
                ],
            },
        }
        monkeypatch.setattr(roblox_util, "api_get", lambda *_a, **_kw: payload)
        result: list[str] = fetch_category_members(
            "https://example.fandom.com",
            "Characters",
        )
        assert result == ["Goku", "Naruto Uzumaki"]

    def test_pagination(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that pagination tokens are followed correctly."""
        calls: list[dict] = []
        pages: list[dict] = [
            {
                "query": {"categorymembers": [{"title": "Goku", "ns": 0}]},
                "continue": {"cmcontinue": "token123"},
            },
            {
                "query": {"categorymembers": [{"title": "Vegeta", "ns": 0}]},
            },
        ]

        def fake_api(wiki_base: str, params: dict) -> dict:  # noqa: ARG001
            calls.append(dict(params))
            return pages[len(calls) - 1]

        monkeypatch.setattr(roblox_util, "api_get", fake_api)
        result: list[str] = fetch_category_members(
            "https://example.fandom.com",
            "Characters",
        )
        assert result == ["Goku", "Vegeta"]
        assert len(calls) == 2  # noqa: PLR2004
        assert calls[1].get("cmcontinue") == "token123"

    def test_empty_category(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that an empty category returns an empty list."""
        monkeypatch.setattr(
            roblox_util,
            "api_get",
            lambda *_a, **_kw: {"query": {"categorymembers": []}},
        )
        result: list[str] = fetch_category_members(
            "https://example.fandom.com",
            "Empty",
        )
        assert result == []


class TestFetchImageUrl:
    """Tests for fetch_image_url."""

    def test_returns_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a thumbnail URL is returned when present."""
        payload: dict = {
            "query": {
                "pages": {
                    "1": {"thumbnail": {"source": "https://img.example.com/goku.png"}},
                },
            },
        }
        monkeypatch.setattr(roblox_util, "api_get", lambda *_a, **_kw: payload)
        result: str | None = fetch_image_url("https://example.fandom.com", "Goku")
        assert result == "https://img.example.com/goku.png"

    def test_prefers_original_over_thumbnail(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that the native-resolution original wins over the thumbnail."""
        payload: dict = {
            "query": {
                "pages": {
                    "1": {
                        "original": {"source": "https://img.example.com/goku-full.png"},
                        "thumbnail": {"source": "https://img.example.com/goku-800.png"},
                    },
                },
            },
        }
        monkeypatch.setattr(roblox_util, "api_get", lambda *_a, **_kw: payload)
        result: str | None = fetch_image_url("https://example.fandom.com", "Goku")
        assert result == "https://img.example.com/goku-full.png"

    def test_no_thumbnail_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that None is returned when no thumbnail exists."""
        payload: dict = {"query": {"pages": {"1": {"title": "Goku"}}}}
        monkeypatch.setattr(roblox_util, "api_get", lambda *_a, **_kw: payload)
        result: str | None = fetch_image_url("https://example.fandom.com", "Goku")
        assert result is None

    def test_empty_pages_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that None is returned when pages dict is empty."""
        payload: dict = {"query": {"pages": {}}}
        monkeypatch.setattr(roblox_util, "api_get", lambda *_a, **_kw: payload)
        result: str | None = fetch_image_url("https://example.fandom.com", "Goku")
        assert result is None


class TestBuildEntries:
    """Tests for build_entries."""

    def test_entries_have_none_image(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that all entries are created with image_url as None."""
        monkeypatch.setattr(
            roblox_util,
            "fetch_category_members",
            lambda *_a: ["Goku", "Naruto Uzumaki"],
        )
        entries: list[CharacterEntry] = build_entries(
            "https://example.fandom.com",
            "Characters",
        )
        assert len(entries) == 2  # noqa: PLR2004
        assert all(e["image_url"] is None for e in entries)
        assert entries[0]["name"] == "Goku"
        assert entries[1]["name"] == "Naruto Uzumaki"

    def test_empty_category(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that an empty category returns an empty list."""
        monkeypatch.setattr(roblox_util, "fetch_category_members", lambda *_a: [])
        entries: list[CharacterEntry] = build_entries(
            "https://example.fandom.com",
            "Characters",
        )
        assert entries == []

    def test_filters_category_index_pages(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that category index pages are excluded from entries."""
        monkeypatch.setattr(
            roblox_util,
            "fetch_category_members",
            lambda *_a: ["Fischeran", "Races", "Artifacts", "Creatures", "Characters"],
        )
        entries: list[CharacterEntry] = build_entries(
            "https://example.fandom.com",
            "Races",
        )
        names: list[str] = [e["name"] for e in entries]
        assert "Fischeran" in names
        assert "Races" not in names
        assert "Artifacts" not in names
        assert "Creatures" not in names
        assert "Characters" not in names


class TestResolveImageBlocking:
    """Tests for resolve_image_blocking."""

    def test_fetches_when_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that an image is fetched and cached when not already set."""
        entry: CharacterEntry = make_entry("Goku")
        monkeypatch.setattr(
            roblox_util,
            "fetch_image_url",
            lambda *_a: "https://img.example.com/goku.png",
        )
        result: str | None = resolve_image_blocking("https://example.fandom.com", entry)
        assert result == "https://img.example.com/goku.png"
        assert entry["image_url"] == "https://img.example.com/goku.png"

    def test_skips_fetch_when_already_set(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that fetch_image_url is not called if image_url is already cached."""
        entry: CharacterEntry = make_entry(
            "Goku",
            image_url="https://cached.example.com/goku.png",
        )
        called: bool = False

        def should_not_be_called(*_a: object) -> None:
            nonlocal called
            called = True

        monkeypatch.setattr(roblox_util, "fetch_image_url", should_not_be_called)
        result: str | None = resolve_image_blocking("https://example.fandom.com", entry)
        assert result == "https://cached.example.com/goku.png"
        assert not called

    def test_handles_no_image(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that None is handled gracefully when the wiki has no image."""
        entry: CharacterEntry = make_entry("Unnamed")
        monkeypatch.setattr(roblox_util, "fetch_image_url", lambda *_a: None)
        result: str | None = resolve_image_blocking("https://example.fandom.com", entry)
        assert result is None
        assert entry["image_url"] is None


class TestPopulateCacheBlocking:
    """Tests for populate_cache_blocking."""

    def test_aba_populates_character_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that the aba cache is populated with a character key."""
        monkeypatch.setattr(
            roblox_util,
            "build_entries",
            lambda *_a: [make_entry("Goku"), make_entry("Naruto Uzumaki")],
        )
        clear_cache()
        populate_cache_blocking("aba")
        cached: GameCache | None = get_cache("aba")
        assert cached is not None
        assert "character" in cached["data"]
        assert len(cached["data"]["character"]) == 2  # noqa: PLR2004

    def test_rogue_populates_all_categories(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that the rogue cache is populated with all three category keys."""
        monkeypatch.setattr(
            roblox_util,
            "build_entries",
            lambda *_a: [make_entry("Fischeran")],
        )
        clear_cache()
        populate_cache_blocking("rogue")
        cached: GameCache | None = get_cache("rogue")
        assert cached is not None
        for key in ("race", "artifact", "creature"):
            assert key in cached["data"]

    def test_cache_timestamp_is_recent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that the cache timestamp is set to approximately now."""
        monkeypatch.setattr(roblox_util, "build_entries", lambda *_a: [])
        clear_cache()
        before: datetime = datetime.now(tz=UTC)
        populate_cache_blocking("aba")
        after: datetime = datetime.now(tz=UTC)
        cached: GameCache | None = get_cache("aba")
        assert cached is not None
        assert before <= cached["cached_at"] <= after


class TestQuestion:
    """Tests for question."""

    pytestmark = pytest.mark.asyncio

    async def test_aba_returns_correct_structure(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that question() returns the correct tuple structure for aba."""
        inject_cache(
            "aba",
            {"character": [make_entry("Goku", "https://img.example.com/goku.png")]},
        )

        async def fake_ensure(game: str) -> None:
            pass

        async def fake_resolve(_wiki: str, _entry: CharacterEntry) -> str:
            return "https://img.example.com/goku.png"

        monkeypatch.setattr(roblox_util, "ensure_cache", fake_ensure)
        monkeypatch.setattr(roblox_util, "resolve_image", fake_resolve)

        image_url: str | None
        trivia_question: str
        answer: str
        image_url, trivia_question, answer = await question("aba")
        assert trivia_question == "What character is this?"
        assert answer == "Goku"
        assert image_url == "https://img.example.com/goku.png"

    async def test_rogue_question_text_matches_category(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that rogue returns a valid question for whichever category is picked."""
        inject_cache(
            "rogue",
            {
                "race": [make_entry("Fischeran", "https://img.example.com/f.png")],
                "artifact": [
                    make_entry("Phoenix Down", "https://img.example.com/pd.png"),
                ],
                "creature": [
                    make_entry("Lava Snake", "https://img.example.com/ls.png"),
                ],
            },
        )

        async def fake_ensure(game: str) -> None:
            pass

        async def fake_resolve(_wiki: str, entry: CharacterEntry) -> str | None:
            return entry["image_url"]

        monkeypatch.setattr(roblox_util, "ensure_cache", fake_ensure)
        monkeypatch.setattr(roblox_util, "resolve_image", fake_resolve)

        for _ in range(20):
            _image_url: str | None
            trivia_question: str
            answer: str
            _image_url, trivia_question, answer = await question("rogue")
            assert trivia_question in ROGUE_QUESTIONS.values()
            assert isinstance(answer, str)

    async def test_invalid_game_raises(self) -> None:
        """Test that an invalid game name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown game"):
            await question("minecraft")

    async def test_cache_miss_triggers_populate(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that a missing cache entry triggers populate."""
        clear_cache()
        populate_called: bool = False

        async def fake_ensure(game: str) -> None:
            nonlocal populate_called
            populate_called = True
            inject_cache(
                game,
                {"character": [make_entry("Goku", "https://img.example.com/goku.png")]},
            )

        async def fake_resolve(wiki: str, entry: CharacterEntry) -> str:  # noqa: ARG001
            return "https://img.example.com/goku.png"

        monkeypatch.setattr(roblox_util, "ensure_cache", fake_ensure)
        monkeypatch.setattr(roblox_util, "resolve_image", fake_resolve)
        await question("aba")
        assert populate_called

    async def test_stale_cache_triggers_repopulate(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that a stale cache entry triggers repopulation."""
        inject_cache(
            "aba",
            {"character": [make_entry("Goku")]},
            age=timedelta(hours=25),
        )
        repopulate_called: bool = False

        async def fake_ensure(game: str) -> None:
            nonlocal repopulate_called
            repopulate_called = True
            inject_cache(
                game,
                {"character": [make_entry("Goku", "https://img.example.com/goku.png")]},
            )

        async def fake_resolve(wiki: str, entry: CharacterEntry) -> str:  # noqa: ARG001
            return "https://img.example.com/goku.png"

        monkeypatch.setattr(roblox_util, "ensure_cache", fake_ensure)
        monkeypatch.setattr(roblox_util, "resolve_image", fake_resolve)
        await question("aba")
        assert repopulate_called

    async def test_none_image_url_is_allowed(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that question() succeeds even when no image is available."""
        inject_cache("aba", {"character": [make_entry("Goku")]})

        async def fake_ensure(game: str) -> None:
            pass

        async def fake_resolve(_wiki: str, _entry: CharacterEntry) -> None:
            return None

        monkeypatch.setattr(roblox_util, "ensure_cache", fake_ensure)
        monkeypatch.setattr(roblox_util, "resolve_image", fake_resolve)

        image_url: str | None
        _trivia_question: str
        answer: str
        image_url, _trivia_question, answer = await question("aba")
        assert image_url is None
        assert answer == "Goku"
