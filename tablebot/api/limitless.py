from __future__ import annotations

from typing import Any

import requests

from tablebot.config import BASE_URL, DEFAULT_TIMEOUT_SECONDS


def fetch_groups() -> list[dict[str, Any]]:
    response = requests.get(f"{BASE_URL}/api/groups", timeout=DEFAULT_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def fetch_room_race_results(room_code: str) -> dict[str, Any]:
    response = requests.get(f"{BASE_URL}/api/mkw_rr", params={"id": room_code}, timeout=DEFAULT_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def fetch_pinfo(pid: int) -> dict[str, Any]:
    response = requests.post(f"{BASE_URL}/api/pinfo", json={"pid": int(pid)}, timeout=DEFAULT_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()
