"""Main."""

import os

import json
from bot.bot import DizznemBot
from dotenv import load_dotenv
from log import logger
from user import init_db

load_dotenv()


def validate_env() -> bool:
    """Validate if .env file has required variable(s).

    Returns:
        bool: True if valid env.
    """
    required_vars: list[str] = ["DISCORD_BOT_TOKEN"]
    missing_vars: list[str] = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(
            f"Missing required environment variables: {', '.join(missing_vars)}",
        )
    return not missing_vars


def main() -> None:
    """Start bot."""
    logger.info("Starting Dizznem Bot...")
    if not validate_env():
        return

    init_db()

    try:
        bot: DizznemBot = DizznemBot()
        bot.run_bot()
    except Exception as e:
        logger.error(f"Dizznem Bot failed to start: {e}")
        raise


if __name__ == "__main__":
    main()
