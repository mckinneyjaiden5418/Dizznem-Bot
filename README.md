# Dizznem Bot

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Version](https://img.shields.io/badge/version-2.3.1-blue)

> Last updated: v2.3.1

A Discord bot for the Dizznem community built with discord.py. Features an economy system, stock market, YouTube playback, trivia, leaderboards, and more.

---

## Features

- **Economy** — Balance, daily/weekly rewards, gambling, transfers, net worth
- **Stock Market** — Buy and sell stocks tied to real-world tickers via Yahoo Finance
- **Store** — Spend your money on fun server actions and prestige
- **Trivia** — General trivia, ABA trivia, and Rogue Lineage trivia for money
- **YouTube** — Play YouTube audio in voice channels with a queue system
- **Leaderboards** — Rankings by balance, net worth, prestige, and level
- **Profile & Levels** — Track messages, level up, and view your server rank
- **Inspiration** — Daily inspirational quotes sent automatically at 8 PM EST
- **AI Chat** — Talk to Dizznem Bot AI powered by DeepSeek
- **And more** — Additional commands and features available in the bot

---

## Setup

### Requirements

- Python 3.12+
- FFmpeg *(optional — required only for YouTube audio playback)*
- libopus *(optional — required only for YouTube audio playback)*

### Recommended: Dev Container

This project includes a devcontainer for a consistent development environment. If you're using VS Code with Docker installed:

1. Clone the repo and open it in VS Code
2. When prompted, click **Reopen in Container** (or open the Command Palette and run `Dev Containers: Reopen in Container`)
3. The container will build automatically and install all Python dependencies via `postCreateCommand`
4. Copy `.env.example` to `.env` inside the `python/` directory and fill in your values

> FFmpeg and libopus are **not** installed by the devcontainer. If you need the YouTube cog, install them manually — see the system dependencies step below.

### Manual Setup

#### 1. Clone the repo

```bash
git clone https://github.com/mckinneyjaiden5418/Dizznem-Discord-Bot.git
cd Dizznem-Discord-Bot
```

#### 2. Install system dependencies *(YouTube cog only)*

```bash
sudo apt-get update && sudo apt-get install ffmpeg libopus0 libopus-dev -y
```

If FFmpeg is unavailable via apt, use the static build:

```bash
wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-armhf-static.tar.xz
tar xf ffmpeg-release-armhf-static.tar.xz
sudo mv ffmpeg-*-armhf-static/ffmpeg /usr/local/bin/ffmpeg
rm -rf ffmpeg-*
```

> Use `arm64` instead of `armhf` for 64-bit Raspberry Pi OS, or `amd64` for x86.

#### 3. Install Python dependencies

```bash
pip install -r python/requirements.txt --break-system-packages
```

#### 4. Configure environment variables

Create a `.env` file inside the `python/` directory:

```bash
cd python
nano .env
```

Fill in the following:

```dotenv
DISCORD_BOT_TOKEN=        # Your Discord bot token
DISCORD_BOT_TAG=          # The trigger word for AI chat (e.g. dizznem)
TEST_CHANNEL_ID=          # Channel ID the bot sends a hello message to on startup
INSPIRATION_CHANNEL_ID=   # Channel ID for daily inspiration messages
QOTD_CHANNEL_ID=          # Channel ID for question of the day
ADMIN_ID=                 # Your Discord user ID for admin commands
AI_API_KEY=               # DeepSeek API key for AI chat feature
```

#### 5. Run the bot

```bash
python3 main.py
```

---

## Commands

### User Commands

| Command | Description |
|---|---|
| `$help` | List all commands |
| `$balance` | View your balance |
| `$networth` | View your net worth including stocks |
| `$daily` | Claim your daily reward |
| `$weekly` | Claim your weekly reward |
| `$gamble <amount>` | Gamble your money |
| `$give <user> <amount>` | Transfer money to another user |
| `$store` | Open the store |
| `$trivia` | Answer a trivia question for money |
| `$aba` | Anime Battle Arena trivia |
| `$roguelineage` | Rogue Lineage trivia |
| `$stockmarket` | View all stocks and their prices |
| `$buystock <stock>` | Buy shares of a stock |
| `$sellstock <stock>` | Sell shares of a stock |
| `$stocks` | View your stock portfolio |
| `$play <query>` | Play a YouTube video in VC |
| `$skip` | Skip the current song |
| `$pause` | Pause playback |
| `$resume` | Resume playback |
| `$stop` | Stop playback and disconnect |
| `$queue` | View the song queue |
| `$nowplaying` | Show the current song |
| `$leaderboard` | View server leaderboards |
| `$level` | View your level stats |
| `$profile` | View your full profile |
| `$sus` | See how sus someone is |
| `$inspiration` | Get an inspirational quote |
| `$count` | Increment the server count |
| `$tictactoe <user>` | Challenge someone to Tic-Tac-Toe |
| `$steal <user>` | Attempt to steal money from another user |

### Admin Commands

| `$setmoney <user> <amount>` | Set a user's balance to amount |
| `$addmoney <user> <amount>` | Add amount to user's balance |
| `$retirestock <stock>` | Force-liquidate a stock |
| `$resetcooldown <cooldown>` | Reset a given cooldown |

---

## Environment Notes

- `DISCORD_BOT_TAG` is the word that triggers the AI chat (e.g. if set to `dizznem`, saying `dizznem what's up` in chat will get a response)
- Stock prices update automatically when the US market opens each day via Yahoo Finance
- The AI feature uses the [DeepSeek API](https://platform.deepseek.com)

---

## License

This project is licensed under the [MIT License](LICENSE.md).

---

## Made by Karma SB
