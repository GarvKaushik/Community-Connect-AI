from __future__ import annotations

import logging
import os

import aiohttp

logger = logging.getLogger(__name__)

TELEGRAM_TIMEOUT = aiohttp.ClientTimeout(total=5)

_missing_config_logged = False


async def notify_help_request(
    *,
    request_id: int,
    name: str | None,
    phone: str,
    category: str | None,
    location: str | None,
    summary: str,
    programs: list[str],
) -> bool:
    """Send a new help request to the volunteer Telegram chat. Never raises; returns
    whether it was sent."""
    program_lines = (
        "\n".join(f"{index}. {program}" for index, program in enumerate(programs, start=1))
        or "No verified match found."
    )
    follow_up = (
        "Verify eligibility and help the user with the application."
        if programs
        else "Find suitable support and call the user back."
    )
    return await _send(
        "NEW COMMUNITY ASSISTANCE REQUEST\n"
        f"Request #{request_id}\n\n"
        f"Category:\n{(category or 'not identified').replace('_', ' ').title()}\n\n"
        f"Location:\n{location or 'not given'}\n\n"
        f"Request:\n{summary}\n\n"
        f"Potential programs:\n{program_lines}\n\n"
        f"Required follow-up:\n{follow_up}\n\n"
        f"Contact: {name or 'name not given'}, {phone}"
    )


async def _send(text: str) -> bool:
    global _missing_config_logged

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        if not _missing_config_logged:
            logger.warning(
                "TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set; notifications disabled"
            )
            _missing_config_logged = True
        return False

    try:
        async with aiohttp.ClientSession(timeout=TELEGRAM_TIMEOUT) as session:
            async with session.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            ) as response:
                if response.status != 200:
                    logger.warning(
                        "telegram notification failed",
                        extra={"status": response.status, "body": await response.text()},
                    )
                    return False
    except Exception:
        logger.exception("telegram notification failed")
        return False

    return True
