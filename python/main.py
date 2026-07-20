"""Main."""

import os
import signal
import sys
from types import FrameType

from bot.bot import DizznemBot
from dotenv import load_dotenv
from log import logger
from user import init_db, save_all_users

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


def handle_sigterm(signum: int, frame: FrameType | None) -> None:  # noqa: ARG001
    """Flush unsaved user data to disk before the process is terminated.

    atexit handlers don't run on SIGTERM (the signal most process managers --
    systemd, Docker, etc. -- send to stop a process), so without this, any
    money/level/prestige changes made in the last SAVE_INTERVAL seconds would
    be silently lost on every restart.

    Args:
        signum (int): The signal number received.
        frame (FrameType | None): The current stack frame.
    """
    logger.info("Received SIGTERM, saving all users before exit...")
    save_all_users()
    sys.exit(0)


def main() -> None:
    """Start bot."""
    logger.info("Starting Dizznem Bot...")
    if not validate_env():
        return

    init_db()
    signal.signal(signal.SIGTERM, handle_sigterm)

    try:
        bot: DizznemBot = DizznemBot()
        bot.run_bot()
    except Exception as e:
        logger.error(f"Dizznem Bot failed to start: {e}")
        raise


if __name__ == "__main__":
    main()
