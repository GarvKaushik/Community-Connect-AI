from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

DATABASE_PATH = Path(__file__).with_name("data") / "communityconnect.db"
MIN_PHONE_DIGITS = 7
MAX_PHONE_DIGITS = 15

_PLACEHOLDER_PATTERN = re.compile(r"^[\[<{(].*[\]>})]$")
_PLACEHOLDER_WORDS = frozenset(
    {"name", "full name", "user", "phone", "phone number", "number", "unknown", "none",
     "null", "n/a", "na", "xxx", "john doe", "jane doe", "test user"}
)


def _is_placeholder(value: str) -> bool:
    return bool(_PLACEHOLDER_PATTERN.match(value)) or value.lower() in _PLACEHOLDER_WORDS


def initialize() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(_connect()) as connection, connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS help_requests (
                id INTEGER PRIMARY KEY,
                name TEXT,
                phone TEXT NOT NULL,
                category TEXT,
                location TEXT,
                summary TEXT NOT NULL,
                programs TEXT NOT NULL,
                language TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'NEW',
                created_at TEXT NOT NULL
            )
            """
        )


def validate_phone(phone: str) -> str:
    clean_phone = " ".join(phone.split())
    if not clean_phone or _is_placeholder(clean_phone):
        raise ValueError("A real phone number is required so a volunteer can call back. Ask for it.")
    digits = re.sub(r"\D", "", clean_phone)
    if not MIN_PHONE_DIGITS <= len(digits) <= MAX_PHONE_DIGITS:
        raise ValueError(
            f"A phone number needs {MIN_PHONE_DIGITS} to {MAX_PHONE_DIGITS} digits. Ask them to repeat it."
        )
    return clean_phone


def save_request(
    *,
    name: str | None,
    phone: str,
    summary: str,
    category: str | None,
    location: str | None,
    programs: list[str],
    language: str,
) -> int:
    """Validate and store a request for human help. Raises ValueError with a message the
    agent can act on, so a bad tool call fails loudly instead of saving bad data."""
    clean_name = " ".join((name or "").split()) or None
    if clean_name and (_is_placeholder(clean_name) or len(re.findall(r"[^\W\d_]", clean_name)) < 2):
        raise ValueError("That name looks like a placeholder. Ask for their real name, or leave it empty.")

    clean_phone = validate_phone(phone)

    clean_summary = " ".join(summary.split())
    if not clean_summary:
        raise ValueError("Add a short summary of what the person needs.")

    with closing(_connect()) as connection, connection:
        cursor = connection.execute(
            """
            INSERT INTO help_requests
                (name, phone, category, location, summary, programs, language, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                clean_name,
                clean_phone,
                category,
                location,
                clean_summary,
                json.dumps(programs, ensure_ascii=False),
                language,
                dt.datetime.now(dt.UTC).isoformat(),
            ),
        )
        return int(cursor.lastrowid)


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DATABASE_PATH, timeout=5)
