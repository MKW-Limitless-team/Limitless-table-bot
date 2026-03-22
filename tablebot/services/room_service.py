from __future__ import annotations

import pandas as pd
import requests

from tablebot.api import limitless
from tablebot.utils.formatting import created_ago_text, format_friend_code, format_milliseconds, parse_possible_mention


def find_room_by_player(rooms: list[dict], query: str) -> tuple[bool, str]:
    query_lower = query.strip().lower()
    matches = []
    for room in rooms:
        for player in room["players"]:
            if query_lower in str(player["friend_code"]).lower() or query_lower in str(player["mii_name"]).lower():
                matches.append(room)
                break
    room_codes = [room["room_code"] for room in matches]
    if len(room_codes) > 1:
        return False, f'I found multiple rooms matching "{query}". Use a more specific lookup.'
    if not room_codes:
        return False, f'I could not find any room containing "{query}".'
    return True, room_codes[0]


def get_rooms() -> list[dict]:
    rooms_json = limitless.fetch_groups()
    rooms = []
    for room in rooms_json:
        current_room = {
            "room_id": room["id"],
            "room_code": room["id"],
            "open_time": created_ago_text(str(room.get("created", ""))),
            "players": [],
        }
        role_counter = 1
        for _, pdata in room.get("players", {}).items():
            discord_id = ""
            pid = str(pdata.get("pid", ""))
            if pid:
                try:
                    pinfo = limitless.fetch_pinfo(int(pid))
                    discord_id = str(pinfo.get("User", {}).get("DiscordID", "") or "")
                except Exception:
                    discord_id = ""
            conn_fail = str(pdata.get("conn_fail", "—"))
            if conn_fail == "0":
                conn_fail = "—"
            elif conn_fail not in {"", "—"}:
                conn_fail = f"{conn_fail}.00"
            current_room["players"].append(
                {
                    "pid": pid,
                    "friend_code": str(pdata.get("fc", "")).strip(),
                    "role": str(role_counter),
                    "conn_fail": conn_fail,
                    "region": str(room.get("rk", "?")),
                    "mii_name": str(pdata.get("name", "")).strip() or "Unknown",
                    "vr": str(pdata.get("ev", "")).strip(),
                    "discord_id": discord_id,
                }
            )
            role_counter += 1
        rooms.append(current_room)
    return rooms


def find_room_code(query: str) -> tuple[bool, list[dict] | str, str | None]:
    lookup = parse_possible_mention(query)
    candidates = [lookup]
    rooms = get_rooms()
    for candidate in candidates:
        candidate_text = str(candidate).strip().lower()
        for room in rooms:
            for player in room["players"]:
                if (
                    candidate_text in str(player["friend_code"]).strip().lower()
                    or candidate_text in str(player["mii_name"]).strip().lower()
                    or (player.get("discord_id") and candidate_text == str(player["discord_id"]).strip().lower())
                ):
                    return True, rooms, room["room_code"]
    return False, f'I could not resolve a room for "{query}".', None


def get_races_from_room(room_code: str) -> tuple[bool, list[pd.DataFrame] | str]:
    try:
        results_json = limitless.fetch_room_race_results(room_code)
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code == 404:
            return False, f"I found the room {room_code}, but I couldn't find any completed races yet. Rerun this command after the first race has finished."
        return False, f"I couldn't load race results right now (HTTP {status_code or 'unknown'})."
    except requests.RequestException:
        return False, "I couldn't reach the Limitless race results API right now."

    rooms = get_rooms()
    room = next((room for room in rooms if room["room_code"] == room_code), None)
    player_map = {player["pid"]: player for player in (room["players"] if room else [])}

    races = []
    for race_id, race_data in results_json.get("results", {}).items():
        current = []
        course = None
        for player in race_data:
            profile_id = str(player.get("ProfileID") or player.get("profile_id") or player.get("pid") or "")
            room_player = player_map.get(profile_id, {})
            if not room_player and profile_id:
                try:
                    pinfo = limitless.fetch_pinfo(int(profile_id))
                except Exception:
                    pinfo = {}
            else:
                pinfo = {}

            course = player.get("CourseID", course)
            mii_name = (
                player.get("MiiName")
                or player.get("mii_name")
                or room_player.get("mii_name")
                or pinfo.get("User", {}).get("LastInGameSn")
                or "Unknown"
            )
            friend_code = (
                player.get("FriendCode")
                or player.get("friend_code")
                or room_player.get("friend_code")
                or ""
            )
            finish_time_ms = player.get("FinishTimeMs", player.get("FinishTime", player.get("finish_time_ms")))
            lag_ms = player.get("Delta", player.get("delta", 0))
            lag_seconds = round(float(lag_ms) / 1000.0, 2) if lag_ms not in (None, "") else 0.0
            current.append(
                {
                    "friend_code": format_friend_code(friend_code),
                    "lag_start": lag_seconds,
                    "conn_fail": room_player.get("conn_fail", "—"),
                    "finish_time": format_milliseconds(finish_time_ms),
                    "mii_name": mii_name,
                    "track": str(course or "Unknown"),
                    "match_id": f"match_{int(race_id)}",
                }
            )
        if current:
            races.append(pd.DataFrame(current))

    if not races:
        return False, "I found the room, but I couldn't find any completed races yet. Rerun this command after the first race has finished."

    races.sort(key=lambda df: int(str(df["match_id"].iloc[0]).replace("match_", "")))
    return True, races


def build_verify_room_dataframe(room_code: str) -> pd.DataFrame:
    rooms = get_rooms()
    room = next((room for room in rooms if room["room_code"] == room_code), None)
    if room is None:
        raise ValueError(f"Unknown room code: {room_code}")

    room_df = pd.DataFrame(room["players"])[["role", "conn_fail", "mii_name", "friend_code", "vr", "discord_id"]]
    return room_df
