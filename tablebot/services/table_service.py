from __future__ import annotations

import random

import numpy as np
import pandas as pd

from tablebot.constants import COLOR_PALETTES, CT_MAP, DISTINCT_COLORS, FFA_COLOR_PALETTES
from tablebot.models import TableState
from tablebot.rendering.text import get_table_image, text_to_image
from tablebot.services import edit_service, room_service
from tablebot.storage.state_store import load_state, save_state
from tablebot.utils.tags import assign_tags_to_groups, get_tag_similarity_matrix, greedy_grouping


def get_points(position_list: list[int], room_size: int = -1) -> list[int]:
    if room_size == -1:
        room_size = len(position_list)
    point_table = {
        2: [15, 7],
        3: [15, 8, 2],
        4: [15, 9, 4, 1],
        5: [15, 9, 5, 2, 1],
        6: [15, 10, 6, 3, 1, 0],
        7: [15, 10, 7, 5, 3, 1, 0],
        8: [15, 11, 8, 6, 4, 2, 1, 0],
        9: [15, 11, 8, 6, 4, 3, 2, 1, 0],
        10: [15, 12, 10, 8, 6, 4, 3, 2, 1, 0],
        11: [15, 12, 10, 8, 6, 5, 4, 3, 2, 1, 0],
        12: [15, 12, 10, 8, 7, 6, 5, 4, 3, 2, 1, 0],
    }
    return [point_table[room_size][pos - 1] if pos and 1 <= pos <= room_size else 0 for pos in position_list]


def identify_custom_track(track_name: str) -> str:
    return CT_MAP.get(str(track_name), str(track_name))


def process_race(all_players: pd.DataFrame, race_df: pd.DataFrame, room_code: str, points_to_off_results_players: int = 0) -> pd.DataFrame:
    race_df = race_df.copy()
    race_df["room_id"] = room_code
    track = identify_custom_track(str(race_df["track"].iloc[0]))
    race_df["track"] = track
    match_id = str(race_df["match_id"].iloc[0])
    room_size = len(race_df["friend_code"].unique().tolist())
    race_df["lag_start"] = pd.to_numeric(race_df["lag_start"], errors="coerce").fillna(0)
    race_df["finish_time_parsed"] = pd.to_timedelta("0:" + race_df["finish_time"].replace("", pd.NA), errors="coerce")
    race_df = race_df.sort_values("finish_time_parsed", na_position="last").drop(columns=["finish_time_parsed"])
    race_df["placement"] = range(1, len(race_df) + 1)
    race_df["dc_status"] = np.where(race_df["finish_time"] == "—", "on_results", "no")
    race_df.loc[race_df["finish_time"] == "—", "placement"] = room_size
    race_df["points"] = get_points(race_df["placement"].tolist(), room_size)

    on_results = race_df["friend_code"].tolist()
    off_results = all_players[~all_players["friend_code"].isin(on_results)].copy()
    off_results["lag_start"] = None
    off_results["conn_fail"] = None
    off_results["finish_time"] = None
    off_results["track"] = track
    off_results["match_id"] = match_id
    off_results["room_id"] = room_code
    off_results["placement"] = -1
    off_results["dc_status"] = "before"
    off_results["points"] = points_to_off_results_players
    off_results = off_results[["friend_code", "lag_start", "conn_fail", "finish_time", "mii_name", "track", "match_id", "room_id", "placement", "dc_status", "points"]]
    return pd.concat([race_df, off_results], ignore_index=True)


def guess_tags_from_players(all_players: pd.DataFrame, team_size: int, num_teams: int) -> tuple[bool, pd.DataFrame | str]:
    if len(all_players) < 1:
        return False, "No players found."
    if team_size == 1:
        out = all_players.copy()
        out["tag_guess"] = "FFA"
        return True, out
    mii_names = all_players["mii_name"].fillna("").tolist()
    sim_matrix = get_tag_similarity_matrix(mii_names, team_size)
    groups = greedy_grouping(sim_matrix, team_size, num_teams)
    tags = assign_tags_to_groups(mii_names, groups, team_size)
    out = all_players.copy()
    out["tag_guess"] = [tags.get(i, "Unknown Tag") for i in range(len(mii_names))]
    return True, out


def _base_metadata(server_id: str, channel_id: str, fmt: int, num_teams: int, color_theme: str, room_code: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "server_id": str(server_id),
                "channel_id": str(channel_id),
                "format": int(fmt),
                "num_teams": int(num_teams),
                "color_theme": color_theme,
                "num_rooms": 1,
                "room_1_id": room_code,
            }
        ]
    )


def _empty_commands_df() -> pd.DataFrame:
    return pd.DataFrame(columns=["command_id", "command", "undo", "parameter_1", "parameter_2", "parameter_3", "parameter_4", "command_description"])


def _parse_format(fmt: str) -> int:
    lookup = {"ffa": 1, "1": 1, "1v1": 1, "2": 2, "2v2": 2, "3": 3, "3v3": 3, "4": 4, "4v4": 4, "5": 5, "5v5": 5, "6": 6, "6v6": 6}
    value = lookup.get(str(fmt).lower())
    if value is None:
        raise ValueError(f"Unknown format: {fmt}")
    return value


def _create_all_players(races_dfs: list[pd.DataFrame], fmt: int, num_teams: int, color_theme: str) -> pd.DataFrame:
    all_players = pd.concat(races_dfs, ignore_index=True)[["friend_code", "mii_name"]].drop_duplicates(subset="friend_code", keep="last")
    success, tagged = guess_tags_from_players(races_dfs[0][["friend_code", "mii_name"]].copy(), fmt, num_teams)
    if success is not True:
        raise ValueError(str(tagged))
    all_players = pd.merge(all_players, tagged[["friend_code", "tag_guess"]], on="friend_code", how="left")
    if fmt == 1:
        all_players["tag_guess"] = all_players["tag_guess"].fillna("FFA")
    else:
        all_players["tag_guess"] = all_players["tag_guess"].fillna("Unknown Tag")

    palette = COLOR_PALETTES.get(color_theme, COLOR_PALETTES["pastel"])
    tags = all_players["tag_guess"].unique().tolist()
    tag_to_color = {tag: palette[index % len(palette)] for index, tag in enumerate(tags)}
    all_players["team_color"] = all_players["tag_guess"].map(tag_to_color)
    all_players = all_players.sort_values(by=["tag_guess", "mii_name"]).reset_index(drop=True)
    all_players["subbed_in_for"] = None
    all_players["subbed_in_on"] = None
    all_players["subbed_out_on"] = None
    all_players["player_event_id"] = np.arange(1, len(all_players) + 1)
    all_players["teampen"] = 0
    all_players["changed_name"] = "—"
    all_players["display_name"] = all_players["mii_name"]
    return all_players


def start_table(search_term: str | None, fmt: str, num_teams: int, server_id: str, channel_id: str, color_theme: str = "pastel", rxx: str | None = None) -> tuple[bool, str]:
    format_int = _parse_format(fmt)
    room_code = rxx
    if room_code is None:
        success, _, room_code = room_service.find_room_code(search_term or "")
        if success is not True:
            return False, str(_)

    success, races_or_error = room_service.get_races_from_room(str(room_code))
    if success is not True:
        return False, str(races_or_error)

    races_dfs = races_or_error
    if color_theme not in COLOR_PALETTES:
        color_theme = random.choice(list(COLOR_PALETTES.keys()))

    all_players = _create_all_players(races_dfs, format_int, num_teams, color_theme)
    all_players_raw = all_players.copy()
    raw_races = [process_race(all_players_raw, race_df, str(room_code), 3 if format_int == 5 else 0) for race_df in races_dfs]
    processed = [df.copy() for df in raw_races]
    metadata = _base_metadata(server_id, channel_id, format_int, num_teams, color_theme, str(room_code))
    state = TableState(
        metadata=metadata,
        all_players_raw=all_players_raw,
        all_players=all_players,
        commands=_empty_commands_df(),
        raw_races_dfs=raw_races,
        processed_races_dfs=processed,
    )
    save_state(server_id, channel_id, state)
    return True, f"{room_code}"


def merge_room(search_term: str | None, state: TableState, rxx: str | None = None) -> tuple[bool, str]:
    room_code = rxx
    if room_code is None:
        success, _, room_code = room_service.find_room_code(search_term or "")
        if success is not True:
            return False, str(_)
    existing = [state.metadata[f"room_{index}_id"].iloc[0] for index in range(1, int(state.metadata["num_rooms"].iloc[0]) + 1)]
    if room_code in existing:
        return False, f"Room {room_code} is already on the table."
    num_rooms = int(state.metadata["num_rooms"].iloc[0]) + 1
    state.metadata["num_rooms"] = num_rooms
    state.metadata[f"room_{num_rooms}_id"] = room_code
    return True, f"Successfully merged table with room {room_code}."


def load_table_state(server_id: str, channel_id: str) -> TableState:
    return load_state(server_id, channel_id)


def save_table_state(server_id: str, channel_id: str, state: TableState) -> None:
    save_state(server_id, channel_id, state)


def verify_room(search_term: str) -> tuple[bool, str, object]:
    success, rooms_or_error, room_code = room_service.find_room_code(search_term)
    if success is not True:
        return False, str(rooms_or_error), None
    success, races_or_error = room_service.get_races_from_room(str(room_code))
    track_list = []
    if success is True:
        track_list = [identify_custom_track(df["track"].iloc[0]) for df in races_or_error]
    room_df = room_service.build_verify_room_dataframe(str(room_code))
    output = room_vr_df_to_text(room_df, f"Limitless Room\nRoom {room_code}: {len(track_list)} races played", track_list)
    return True, f"```{output}```", text_to_image(output)


def room_vr_df_to_text(df: pd.DataFrame, title: str, list_of_tracks: list[str]) -> str:
    discord_ids = df["discord_id"].fillna("").astype(str).tolist()
    longest_discord = max(10, len(max(discord_ids, key=len)) + 1 if discord_ids else 10)
    header = f"{title}\n\n{'Role':<3} {'ConnF':<5} {'Mii Name':<11} {'Discord ID':<{longest_discord}} {'Friend Code':<15} {'VR'}\n"
    header += "-" * len(header)
    lines = [header]
    for _, row in df.iterrows():
        lines.append(
            f"{row['role']:<3} {row['conn_fail']:<5} {row['mii_name']:<11} {str(row['discord_id']):<{longest_discord}} {row['friend_code']:<15} {row['vr']}"
        )
    if list_of_tracks:
        lines.append("")
        lines.append(f"{len(list_of_tracks)} races played:")
        lines.extend([f"{index + 1}: {track}" for index, track in enumerate(list_of_tracks)])
    return "\n".join(lines)


def create_table_text_df(all_players: pd.DataFrame, processed_races: list[pd.DataFrame]) -> pd.DataFrame:
    table_df = all_players[all_players["subbed_in_on"].isnull()].copy()
    table_df["table_name"] = table_df["display_name"]
    table_df["table_name"] = table_df["table_name"].str.replace("/", "", regex=False).str.replace("#", "", regex=False)
    table_df["tag_guess"] = table_df["tag_guess"].str.replace("#", "", regex=False)
    table_df = table_df[["player_event_id", "tag_guess", "team_color", "teampen", "table_name", "friend_code"]].copy()
    for index, race_df in enumerate(processed_races, start=1):
        points = []
        for _, row in table_df.iterrows():
            fc = row["friend_code"]
            race_points = race_df.loc[race_df["friend_code"] == fc, "points"]
            points.append(int(race_points.iloc[0]) if len(race_points) else 0)
        table_df[f"race_{index}_scores"] = points
    return table_df


def get_table_text_by_gp(table_df: pd.DataFrame, format_int: int, color_theme: str, override_color: bool = False, for_update: bool = False) -> str:
    race_columns = [col for col in table_df.columns if col.startswith("race_") and col.endswith("_scores")]
    output_lines = [f"#title {len(race_columns)} races"]
    grouped = table_df.groupby(["tag_guess", "team_color", "teampen"])
    if format_int == 1 and len(table_df) >= 10:
        palette = FFA_COLOR_PALETTES.get(color_theme, FFA_COLOR_PALETTES["honey"])
        for idx, (_, row) in enumerate(table_df.iterrows(), start=1):
            color = DISTINCT_COLORS[idx - 1] if override_color else palette[min(idx - 1, len(palette) - 1)]
            gp_scores = [sum(row[col] for col in race_columns[i : i + 4]) for i in range(0, len(race_columns), 4)]
            output_lines.append(f"\nFFA{idx} {color}")
            output_lines.append(f"{row['table_name']} {'|'.join(str(score) for score in gp_scores)}|")
        return "\n".join(output_lines)
    for color_index, ((tag, color, pen), group) in enumerate(grouped):
        if override_color:
            color = DISTINCT_COLORS[color_index % len(DISTINCT_COLORS)]
        if for_update:
            color = ""
        output_lines.append(f"\n{tag} {color}".rstrip())
        if int(pen) != 0:
            output_lines.append(f"Penalty {-abs(int(pen))}")
        for _, row in group.iterrows():
            gp_scores = [sum(row[col] for col in race_columns[i : i + 4]) for i in range(0, len(race_columns), 4)]
            output_lines.append(f"{row['table_name']} {'|'.join(str(score) for score in gp_scores)}|")
    return "\n".join(output_lines)


def render_table(state: TableState, by_race: bool = False, override_color: bool = False) -> tuple[bool, object, str, list[str], list[str], str]:
    table_df = create_table_text_df(state.all_players.copy(), state.processed_races_dfs)
    table_text = get_table_text_by_gp(table_df, int(state.metadata["format"].iloc[0]), str(state.metadata["color_theme"].iloc[0]), override_color=override_color, for_update=True)
    image, edit_link = get_table_image(table_text)
    update_text = f"{len(state.processed_races_dfs)} races tracked."
    errors = get_table_errors(state)
    return True, image, update_text, errors, [], edit_link


def get_tabletext(state: TableState, by_race: bool = False) -> str:
    table_df = create_table_text_df(state.all_players.copy(), state.processed_races_dfs)
    return get_table_text_by_gp(table_df, int(state.metadata["format"].iloc[0]), str(state.metadata["color_theme"].iloc[0]), for_update=True)


def get_allplayers(state: TableState) -> str:
    output = []
    for _, row in state.all_players.iterrows():
        output.append(f"{row['player_event_id']}. {row['mii_name']} - ({row['friend_code']})")
    return "\n".join(output)


def races_text(state: TableState) -> str:
    return "**Races:**\n" + "\n".join(f"{index + 1}: {race.iloc[0]['track']}" for index, race in enumerate(state.processed_races_dfs))


def teams_text(state: TableState) -> str:
    lines = ["**Team Tags:**"]
    for tag in state.all_players["tag_guess"].unique().tolist():
        lines.append(f"**{tag}**")
        for _, row in state.all_players[state.all_players["tag_guess"] == tag].iterrows():
            lines.append(f"     {row['mii_name']}")
        lines.append("")
    return "\n".join(lines)


def commands_text(state: TableState) -> str:
    if len(state.commands) < 1:
        return "No table edit commands added to the current table."
    output = ["Commands on the table:"]
    for _, row in state.commands.iterrows():
        prefix = f"{row['command_id']}. "
        if row["undo"] in (True, "True"):
            output.append(f"{prefix}UNDONE {row['command_description']}")
        else:
            output.append(f"{prefix}{row['command_description']}")
    return "\n".join(output)


def race_result_text(state: TableState, race_number: int = 9999, display_true_lag_start: bool = False) -> str:
    race_number = max(1, min(race_number, len(state.processed_races_dfs)))
    df = state.processed_races_dfs[race_number - 1].copy()
    df = df[df["placement"] >= 1].sort_values("placement")
    df["display_name"] = df["friend_code"].apply(
        lambda fc: state.all_players[state.all_players["friend_code"] == fc]["display_name"].iloc[0]
        if len(state.all_players[state.all_players["friend_code"] == fc]) else "Unknown"
    )
    if display_true_lag_start:
        df["lag_start_display"] = df["lag_start"]
    else:
        lag = df["lag_start"].abs()
        df["lag_start_display"] = np.where(lag >= 0.50, df["lag_start"], "—")
    longest_name = max(11, len(max(df["display_name"].tolist(), key=len)) + 1 if len(df) else 11)
    header = f"Race #{race_number}: {df.iloc[0]['track']} ({df.iloc[0]['match_id']})\n\n"
    header += f"{'Place':<6} {'Mii Name':<11} {'Display Name':<{longest_name}} {'Finish Time':<12} {'Lag Start':<9}\n"
    header += "-" * (50 + longest_name) + "\n"
    lines = [header]
    for _, row in df.iterrows():
        lines.append(f"{row['placement']:<6} {row['mii_name']:<11} {row['display_name']:<{longest_name}} {row['finish_time']:<12} {row['lag_start_display']:<9}")
    return "```" + "\n".join(lines) + "```"


def get_table_errors(state: TableState) -> list[str]:
    errors = []
    expected_players = int(state.metadata["format"].iloc[0]) * int(state.metadata["num_teams"].iloc[0])
    for idx, race_df in enumerate(state.processed_races_dfs, start=1):
        on_results = race_df[(race_df["placement"] > 0) & (race_df["finish_time"] != "—")]
        if len(on_results) < expected_players:
            errors.append(f"- Race #{idx} has {len(on_results)} players instead of {expected_players}.")
    return errors


def apply_commands_and_save(server_id: str, channel_id: str, state: TableState) -> tuple[bool, list[str]]:
    _, processed_all_players, processed_races_dfs, error_log = edit_service.process_commands(
        state.metadata,
        state.commands,
        state.all_players_raw,
        state.raw_races_dfs,
        get_points,
    )
    state.all_players = processed_all_players
    state.processed_races_dfs = processed_races_dfs
    save_state(server_id, channel_id, state)
    return True, error_log


def map_player_input_to_player_id(player_input: str, all_players_df: pd.DataFrame) -> tuple[bool, int | str]:
    try:
        as_int = int(player_input)
        if as_int in list(map(int, all_players_df["player_event_id"].tolist())):
            return True, as_int
    except (TypeError, ValueError):
        pass
    for column, label in [("changed_name", "changed name"), ("display_name", "display name"), ("mii_name", "mii name"), ("friend_code", "friend code")]:
        exact = all_players_df[all_players_df[column] == player_input]
        if len(exact) == 1:
            return True, int(exact.iloc[0]["player_event_id"])
        partial = all_players_df[all_players_df[column].astype(str).str.contains(str(player_input), regex=False, na=False)]
        if len(partial) == 1:
            return True, int(partial.iloc[0]["player_event_id"])
        if len(partial) > 1:
            return False, f'I found multiple players matching {label} "{player_input}", try using /ap number instead.'
    return False, f'I could not figure out which player "{player_input}" refers to.'
