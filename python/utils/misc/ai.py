"""AI response utilities."""

import requests
from log import logger

SYSTEM_NOTE: str = """You are being used as a chatbot in a discord bot known as Dizznem bot.
You are to respond as if you are Dizznem bot AI.
Dizznem is a retired streamer who used to stream on Twitch.
Dizznem is now an AI content creator to make big money.
He is friends with Karma SB who made this bot.
Only include relevant information in your response, if nothing is relevant here, just ignore it.
Don't include any reference to this note in your response!"""

SUMMARY_SYSTEM_NOTE: str = """You are Dizznem Bot AI, summarizing a Discord channel conversation.
Summarize the conversation concisely and clearly.
Group related topics together if there are multiple distinct conversations.
Only include usernames if relevant to understanding the context.
Use short bullet points.
Keep the summary under 400 words."""


def get_ai_response(prompt: str, api_key: str, cache: list[dict]) -> str:
    """Get an AI response from DeepSeek.

    Args:
        prompt (str): The user's prompt.
        api_key (str): DeepSeek API key.
        cache (list[dict]): A list of previous messages for context.

    Returns:
        str: The AI response.
    """
    try:
        response: requests.Response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": SYSTEM_NOTE},
                    *cache,
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=15,
        )
        data: dict = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"].strip()
        logger.error(f"Unexpected DeepSeek API response: {data}")
        return (  # noqa: TRY300
            "I couldn't generate a response right now. Try again later."
        )
    except requests.Timeout:
        logger.error("DeepSeek API request timed out.")
        return "The request timed out. Try again later."
    except requests.RequestException as e:
        logger.exception("Error generating AI response.", exc_info=e)
        return "Something went wrong generating a response."


def get_ai_summary(message_block: str, api_key: str) -> str:
    """Summarize a block of Discord messages using DeepSeek.

    Args:
        message_block (str): Chronological plain-text block of channel messages.
        api_key (str): DeepSeek API key.

    Returns:
        str: The AI-generated summary, or an error string on failure.
    """
    try:
        response: requests.Response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": SUMMARY_SYSTEM_NOTE},
                    {
                        "role": "user",
                        "content": (
                            "Please summarize the following Discord messages:\n\n"
                            + message_block
                        ),
                    },
                ],
            },
            timeout=15,
        )
        data: dict = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"].strip()
        logger.error(f"Unexpected DeepSeek API response: {data}")
        return (  # noqa: TRY300
            "I couldn't generate a summary right now. Try again later."
        )
    except requests.Timeout:
        logger.error("DeepSeek summarize request timed out.")
        return "The request timed out. Try again later."
    except requests.RequestException as e:
        logger.exception("Error generating AI summary.", exc_info=e)
        return "Something went wrong generating a summary."
