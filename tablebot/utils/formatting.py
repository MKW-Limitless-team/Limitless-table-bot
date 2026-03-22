from __future__ import annotations

import re
from datetime import datetime, timezone


def format_friend_code(friend_code: int | str) -> str:
    text = re.sub(r"\D", "", str(friend_code))
    if len(text) == 12:
        return f"{text[0:4]}-{text[4:8]}-{text[8:12]}"
    return str(friend_code)


def format_milliseconds(milliseconds: int | float | str | None) -> str:
    if milliseconds in (None, "", "—"):
        return "—"

    try:
        value = int(milliseconds)
    except (TypeError, ValueError):
        return str(milliseconds)

    minutes, remainder = divmod(value, 60_000)
    seconds, ms = divmod(remainder, 1_000)
    return f"{minutes}:{seconds:02d}.{ms:03d}"


def parse_possible_mention(value: str | int | None) -> str:
    if value is None:
        return ""

    text = str(value).strip()
    match = re.fullmatch(r"<@!?(\d+)>", text)
    if match:
        return match.group(1)
    return text


def created_ago_text(iso_ts: str) -> str:
    if not iso_ts:
        return ""

    normalized = iso_ts
    if "." in normalized:
        base, frac = normalized.split(".", 1)
        frac = frac.rstrip("Z")[:6]
        normalized = f"{base}.{frac}Z"

    try:
        dt = datetime.strptime(normalized, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return ""

    delta = datetime.now(timezone.utc) - dt
    minutes = int(delta.total_seconds() // 60)
    return f"(created {minutes} minutes ago)"
