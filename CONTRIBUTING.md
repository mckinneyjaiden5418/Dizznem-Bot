# Contributing to Dizznem Bot

Thanks for your interest in contributing! Please read through this guide before opening a PR or issue.

## Table of Contents
- [Requirements](#requirements)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [Running Tests](#running-tests)
- [Adding a Cog](#adding-a-cog)
- [Code Guidelines](#code-guidelines)
- [Pull Request Process](#pull-request-process)

---

## Requirements

- Python 3.12+
- FFmpeg *(optional — required only for the YouTube cog; the cog will fail to load without it)*
- libopus *(optional — required only for the YouTube cog)*

---

## Getting Started

This project uses a devcontainer for a consistent development environment. It's the recommended way to work on the bot.

1. Clone the repo
```bash
   git clone https://github.com/mckinneyjaiden5418/Dizznem-Bot.git
   cd Dizznem-Bot
```

2. Open in VS Code and reopen in the devcontainer when prompted.
   Dependencies from `requirements.txt` are installed automatically via `postCreateCommand`.

3. Copy `.env.example` to `.env` inside the `python/` directory and fill in your values.
```bash
   cp python/.env.example python/.env
```

> The bot will not run without a valid `DISCORD_BOT_TOKEN`.

### Installing System Dependencies *(YouTube cog only)*

If you want the YouTube cog to load, install FFmpeg and libopus:

```bash
sudo apt-get update && sudo apt-get install ffmpeg libopus0 libopus-dev -y
```

If FFmpeg is unavailable via apt (e.g. in a dev container), use the static build:

```bash
wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-armhf-static.tar.xz
tar xf ffmpeg-release-armhf-static.tar.xz
sudo mv ffmpeg-*-armhf-static/ffmpeg /usr/local/bin/ffmpeg
rm -rf ffmpeg-*
```

> Use `arm64` instead of `armhf` for 64-bit Raspberry Pi OS, or `amd64` for x86.

### Installing Python Dependencies

```bash
pip install -r python/requirements.txt --break-system-packages
```

---

## Environment Variables

The `.env` file lives inside the `python/` directory.

| Variable | Required | Description |
| -------- | -------- | ----------- |
| `DISCORD_BOT_TOKEN` | ✅ | Your Discord bot token |
| `DISCORD_BOT_TAG` | ❌ | Trigger word for AI chat (e.g. `dizznem`) |
| `TEST_CHANNEL_ID` | ❌ | Channel the bot says hello in on startup |
| `INSPIRATION_CHANNEL_ID` | ❌ | Target channel for daily inspiration messages |
| `QOTD_CHANNEL_ID` | ❌ | Target channel for QOTD store item |
| `ADMIN_ID` | ❌ | Discord user ID with admin command access |
| `AI_API_KEY` | ❌ | DeepSeek API key for AI chat feature |

> The Reddit cog requires a Reddit API key — see [reddit.com/prefs/apps](https://reddit.com/prefs/apps) to set one up.

---

## Project Structure
python/
├── main.py               # Entry point
├── user.py               # User class, DB logic, autosave
├── bot/
│   ├── bot.py            # DizznemBot class
│   └── cogs/             # All cogs live here
│       ├── misc/
│       ├── money/
│       └── moderation/
└── utils/                # Helpers used by cogs
    ├── misc/
    ├── money/
    ├── moderation/
    ├── general.py
    └── numbers.py

Databases are stored in `data/` at the repo root and are never committed.

---

## Running Tests

All tests use `tmp_path` and `monkeypatch` — they never touch the real databases in `data/`.

```bash
pytest -v
```

- Tests live in `tests/`
- `conftest.py` handles `sys.path` setup
- `pytest.ini` sets `asyncio_mode=auto`

**Please make sure all tests pass before opening a PR.** The PR template includes a checklist item for this. CI will also run pytest automatically on every push and pull request.

---

## Adding a Cog

Cogs are auto-loaded via `rglob("*.py")` — no manual registration needed.

1. Copy `python/bot/cogs/_template.py` and rename it to your cog's name.
2. Fill in your cog class and commands.
3. Use `@commands.hybrid_command` so commands work as both prefix and slash commands.
4. That's it — the bot will pick it up automatically on next startup.

---

## Code Guidelines

**Economy / User system**
- Always modify money via `user.money += x` — never write raw SQL to the `money` column.
  Raw SQL bypasses the dirty flag and the autosave loop will miss the change.
- Use `User.create_if_not_exists(user_id, username)` to get a user anywhere in the codebase.

**Async**
- Wrap all blocking calls (requests, yfinance, yt-dlp, wiki API) in `asyncio.to_thread`.
- Use `run_coroutine_threadsafe` when scheduling async work from a non-async thread (e.g. FFmpeg callbacks).

**Caching**
- Use module-level dicts with a `CACHE_TTL` for external API data (see `roblox.py` for the pattern).
- Expose cache helpers (`set_cache` / `get_cache` / `clear_cache`) so tests can inject data without triggering real API calls.

**General**
- Keep utility logic in `utils/` and Discord-facing command logic in `cogs/`.
- Format all money values through `format_number()` before displaying them.
- Validate user input (see `validate_quote()` in `inspiration.py` for an example).

---

## Pull Request Process

1. Branch off `main` with a descriptive branch name, e.g. `feature/stock-alerts` or `fix/gamble-cooldown`.
2. Fill out the PR template fully, including the pytest checklist item.
3. Keep PRs focused — one feature or fix per PR where possible.
4. A PR that breaks existing tests will not be merged.
