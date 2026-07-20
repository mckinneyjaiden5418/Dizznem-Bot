"""Logger setup."""

import logging


def set_up_logger(module_name: str) -> logging.Logger:
    """Set up logger.

    Args:
        module_name (str): Name of module.

    Returns:
        logging.Logger: Logger.
    """
    is_debug_mode: bool = False

    logging.basicConfig(
        level=logging.DEBUG if is_debug_mode else logging.INFO,
        filename="dizznem_bot.log",
        filemode="a",
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger: logging.Logger = logging.getLogger(module_name)
    logger.setLevel(logging.DEBUG if is_debug_mode else logging.INFO)

    console_handler: logging.StreamHandler[logging.TextIO] = ( # pyright: ignore[reportAttributeAccessIssue]
        logging.StreamHandler()
    )
    console_handler.setLevel(logging.DEBUG if is_debug_mode else logging.INFO)
    console_format = logging.Formatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    return logger


logger: logging.Logger = set_up_logger(__name__)
