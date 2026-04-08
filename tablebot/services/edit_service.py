from __future__ import annotations

import numpy as np
import pandas as pd

from tablebot.constants.colors import COLOR_PALETTES


def append_command(commands: pd.DataFrame, command: str, description: str, *params: object) -> pd.DataFrame:
    padded = list(params[:4]) + [None] * max(0, 4 - len(params))
    new_row = {
        "command_id": len(commands) + 1,
        "command": command,
        "undo": False,
        "parameter_1": padded[0],
        "parameter_2": padded[1],
        "parameter_3": padded[2],
        "parameter_4": padded[3],
        "command_description": description,
    }
    return pd.concat([commands, pd.DataFrame([new_row])], ignore_index=True)


def map_race_to_match_id(race_input: int, processed_races_dfs: list[pd.DataFrame]) -> tuple[bool, str]:
    if race_input < 1 or race_input > len(processed_races_dfs):
        return False, f"Invalid race number {race_input}."
    return True, str(processed_races_dfs[race_input - 1].iloc[0]["match_id"])


def map_match_id_to_race_num(match_id: str, processed_races_dfs: list[pd.DataFrame]) -> tuple[bool, int | str]:
    for index, race in enumerate(processed_races_dfs):
        if str(race["match_id"].iloc[0]) == str(match_id):
            return True, index + 1
    return False, f"Unknown match_id: {match_id}"


def get_insertion_index(
    before_id: str,
    original_positions: dict[str, int],
    removed_positions: set[int],
    processed_races_dfs: list[pd.DataFrame],
) -> tuple[bool, int | str]:
    if before_id.lower() == "1st race":
        return True, 0

    if before_id in original_positions:
        orig_idx = original_positions[before_id]
        removed_before = sum(1 for pos in removed_positions if pos <= orig_idx)
        return True, (orig_idx - removed_before) + 1

    for idx, df in enumerate(processed_races_dfs):
        if str(df["match_id"].iloc[0]) == before_id:
            return True, idx

    return False, f"Unknown prior match_id: {before_id}"


def build_new_race_df(
    all_players_raw: pd.DataFrame,
    player_ids_in_position_order: str,
    new_match_id: str,
    get_points_func,
    points_to_off_results_players: int = 0,
    track: str = "Unknown",
) -> pd.DataFrame:
    player_ids = [item.strip() for item in player_ids_in_position_order.split(",")]
    local_players = all_players_raw.copy()
    local_players["player_event_id"] = local_players["player_event_id"].astype(str)
    players_in_room = local_players[local_players["player_event_id"].isin(player_ids)].copy()
    ordered = players_in_room.set_index("player_event_id").loc[player_ids].reset_index()
    room_size = len(ordered["friend_code"].unique().tolist())
    if "profile_id" not in ordered.columns:
        ordered["profile_id"] = ""
    if "mii_data" not in ordered.columns:
        ordered["mii_data"] = ""

    race_df = pd.DataFrame(
        {
            "profile_id": ordered["profile_id"],
            "mii_data": ordered["mii_data"],
            "friend_code": ordered["friend_code"],
            "lag_start": 0,
            "conn_fail": "—",
            "finish_time": "—",
            "mii_name": ordered["mii_name"],
            "track": track,
            "match_id": new_match_id,
            "room_id": "Inserted Race",
            "placement": list(range(1, len(ordered) + 1)),
            "dc_status": "no",
        }
    )
    race_df["points"] = get_points_func(race_df["placement"].tolist(), room_size)

    off_results = local_players[~local_players["player_event_id"].isin(player_ids)].copy()
    off_results["lag_start"] = None
    off_results["conn_fail"] = None
    off_results["finish_time"] = None
    off_results["track"] = track
    off_results["match_id"] = new_match_id
    off_results["room_id"] = "Inserted Race"
    off_results["placement"] = -1
    off_results["dc_status"] = "before"
    off_results["points"] = points_to_off_results_players
    if "profile_id" not in off_results.columns:
        off_results["profile_id"] = ""
    if "mii_data" not in off_results.columns:
        off_results["mii_data"] = ""
    off_results = off_results[["profile_id", "mii_data", "friend_code", "lag_start", "conn_fail", "finish_time", "mii_name", "track", "match_id", "room_id", "placement", "dc_status", "points"]]

    return pd.concat([race_df, off_results], ignore_index=True)


def process_commands(
    metadata: pd.DataFrame,
    commands: pd.DataFrame,
    all_players_raw: pd.DataFrame,
    raw_races_dfs: list[pd.DataFrame],
    get_points_func,
) -> tuple[bool, pd.DataFrame, list[pd.DataFrame], list[str]]:
    error_log: list[str] = []
    fmt = int(metadata["format"].iloc[0])
    selected_palette = str(metadata["color_theme"].iloc[0])
    points_to_off_results = 3 if fmt == 5 else 0

    active_commands = commands[(commands["undo"] != True) & (commands["undo"] != "True")].copy()
    processed_all_players = all_players_raw.copy()
    processed_all_players["player_event_id"] = processed_all_players["player_event_id"].astype(int)
    processed_races_dfs = [df.copy() for df in raw_races_dfs]
    original_positions = {str(df["match_id"].iloc[0]): idx for idx, df in enumerate(raw_races_dfs)}

    remove_df = active_commands[active_commands["command"] == "removerace"].copy()
    match_ids_to_remove = remove_df["parameter_1"].astype(str).tolist() if not remove_df.empty else []
    removed_positions = {original_positions[mid] for mid in match_ids_to_remove if mid in original_positions}

    insert_df = active_commands[active_commands["command"] == "insertrace"].copy()
    inserted_positions: list[int] = []
    insert_counter = 1
    for _, row in insert_df.iterrows():
        success, insertion_index = get_insertion_index(str(row["parameter_1"]), original_positions, removed_positions, processed_races_dfs)
        if not success:
            error_log.append(f"Error on: {row['command_id']}: {row['command_description']} - {insertion_index}")
            continue
        idx_post_removal = int(insertion_index)
        removed_before = sum(1 for pos in removed_positions if pos < idx_post_removal)
        inserted_before = sum(1 for ins in inserted_positions if ins <= idx_post_removal)
        idx_current = idx_post_removal + removed_before + inserted_before
        new_race_df = build_new_race_df(
            processed_all_players,
            str(row["parameter_2"]),
            f"inserted{insert_counter}",
            get_points_func,
            points_to_off_results_players=points_to_off_results,
            track=str(row["parameter_3"]),
        )
        processed_races_dfs.insert(idx_current, new_race_df)
        inserted_positions.append(idx_post_removal)
        insert_counter += 1

    if match_ids_to_remove:
        processed_races_dfs = [df for df in processed_races_dfs if str(df["match_id"].iloc[0]) not in match_ids_to_remove]

    tag_commands = active_commands[active_commands["command"].isin(["edittag", "changetag"])].copy()
    processed_all_players["tag_guess"] = processed_all_players["tag_guess"].astype("string")
    for _, row in tag_commands.iterrows():
        if row["command"] == "edittag":
            old_tag = str(row["parameter_1"])
            new_tag = str(row["parameter_2"])
            processed_all_players.loc[processed_all_players["tag_guess"] == old_tag, "tag_guess"] = new_tag
        elif row["command"] == "changetag":
            player_id = int(row["parameter_1"])
            new_tag = str(row["parameter_2"])
            tag_to_color = (
                processed_all_players.groupby("tag_guess")["team_color"]
                .agg(lambda x: x.dropna().mode().iloc[0] if not x.dropna().empty else None)
                .to_dict()
            )
            chosen_color = tag_to_color.get(new_tag)
            if chosen_color is None:
                palette = COLOR_PALETTES.get(selected_palette, COLOR_PALETTES["pastel"])
                used_colors = {color for color in tag_to_color.values() if color}
                available = [color for color in palette if color not in used_colors]
                chosen_color = available[0] if available else palette[0]
            processed_all_players.loc[processed_all_players["player_event_id"] == player_id, "tag_guess"] = new_tag
            processed_all_players.loc[processed_all_players["tag_guess"] == new_tag, "team_color"] = chosen_color

    sub_df = active_commands[active_commands["command"] == "sub"].copy()
    for _, row in sub_df.iterrows():
        success, race_num = map_match_id_to_race_num(str(row["parameter_3"]), processed_races_dfs)
        if not success:
            error_log.append(f"Error on: {row['command_id']}: {row['command_description']} - {race_num}")
            continue
        in_id = int(row["parameter_1"])
        out_id = int(row["parameter_2"])
        processed_all_players.loc[processed_all_players["player_event_id"] == in_id, ["subbed_in_on", "subbed_in_for"]] = [race_num, out_id]
        processed_all_players.loc[processed_all_players["player_event_id"] == out_id, "subbed_out_on"] = race_num

    id_to_fc = processed_all_players.set_index(processed_all_players["player_event_id"].astype(int))["friend_code"]

    for _, row in active_commands.iterrows():
        command = str(row["command"])
        if command == "changename":
            processed_all_players.loc[processed_all_players["player_event_id"] == int(row["parameter_1"]), "changed_name"] = str(row["parameter_2"])
        elif command == "teampen":
            processed_all_players.loc[processed_all_players["tag_guess"] == str(row["parameter_1"]), "teampen"] = int(row["parameter_2"])
        elif command == "editrace":
            match_id = str(row["parameter_1"])
            player_ids = [int(item.strip()) for item in str(row["parameter_2"]).split(",")]
            for idx, race in enumerate(processed_races_dfs):
                if str(race["match_id"].iloc[0]) != match_id:
                    continue
                ordered_fcs = id_to_fc.reindex(player_ids).tolist()
                all_fcs = processed_all_players["friend_code"].tolist()
                not_in_room = [fc for fc in all_fcs if fc not in set(ordered_fcs)]
                final_order = ordered_fcs + not_in_room
                reindexed = race.set_index("friend_code", drop=False).reindex(final_order)
                reindexed = reindexed.fillna(
                    {
                        "placement": -1,
                        "points": 0,
                        "dc_status": "before",
                        "match_id": match_id,
                        "track": race["track"].iloc[0],
                        "room_id": race["room_id"].iloc[0],
                    }
                )
                placements = list(range(1, len(player_ids) + 1)) + [-1] * (len(reindexed) - len(player_ids))
                reindexed["placement"] = placements
                reindexed["points"] = np.where(reindexed["placement"] > 0, get_points_func(reindexed["placement"].tolist(), len(player_ids)), points_to_off_results)
                processed_races_dfs[idx] = reindexed.reset_index(drop=True)
                break
        elif command == "changeplace":
            player_id = int(row["parameter_1"])
            match_id = str(row["parameter_2"])
            new_position = int(row["parameter_3"])
            target_fc = id_to_fc[player_id]
            for idx, race in enumerate(processed_races_dfs):
                if str(race["match_id"].iloc[0]) != match_id:
                    continue
                race = race.copy()
                current_position = int(race.loc[race["friend_code"] == target_fc, "placement"].iloc[0])
                current_max = int(race["placement"].max())
                if new_position < 0:
                    adjustment = race[race["placement"] > current_position]["friend_code"].tolist()
                    race["placement"] = np.where(race["friend_code"].isin(adjustment), race["placement"] - 1, race["placement"])
                    race["placement"] = np.where(race["friend_code"] == target_fc, -1, race["placement"])
                    race["dc_status"] = np.where(race["friend_code"] == target_fc, "before", race["dc_status"])
                else:
                    if current_position < 0:
                        race["placement"] = np.where(race["placement"] >= new_position, race["placement"] + 1, race["placement"])
                        current_max += 1
                    else:
                        race["placement"] = np.where((race["placement"] >= new_position) & (race["placement"] < current_position), race["placement"] + 1, race["placement"])
                        race["placement"] = np.where((race["placement"] <= new_position) & (race["placement"] > current_position), race["placement"] - 1, race["placement"])
                    race["placement"] = np.where(race["friend_code"] == target_fc, new_position, race["placement"])
                    race["dc_status"] = np.where(race["friend_code"] == target_fc, "no", race["dc_status"])
                room_size = int((race["placement"] > 0).sum())
                race = race.sort_values(by=["placement"], key=lambda col: np.where(col == -1, np.inf, col)).reset_index(drop=True)
                race["points"] = np.where(race["placement"] > 0, get_points_func(race["placement"].tolist(), room_size), points_to_off_results)
                processed_races_dfs[idx] = race
                break

    for _, row in active_commands.iterrows():
        command = str(row["command"])
        if command not in {"edit", "gpedit"}:
            continue
        if command == "edit":
            player_id = int(row["parameter_1"])
            gp_num = int(row["parameter_2"])
            score = int(row["parameter_3"])
            start_race = (gp_num - 1) * 4 + 1
            end_race = min(start_race + 3, len(processed_races_dfs))
            fc = id_to_fc[player_id]
            for race_num in range(start_race, end_race + 1):
                processed_races_dfs[race_num - 1]["points"] = np.where(
                    processed_races_dfs[race_num - 1]["friend_code"] == fc,
                    score if race_num == start_race else 0,
                    processed_races_dfs[race_num - 1]["points"],
                )
        elif command == "gpedit":
            gp_num = int(row["parameter_1"])
            scores = [int(item.strip()) for item in str(row["parameter_2"]).split(",")]
            ordered_players = processed_all_players.sort_values("player_event_id")
            while len(scores) < len(ordered_players):
                scores.append(0)
            score_map = dict(zip(ordered_players["friend_code"].tolist(), scores))
            start_race = (gp_num - 1) * 4 + 1
            end_race = min(start_race + 3, len(processed_races_dfs))
            for fc in ordered_players["friend_code"].tolist():
                for race_num in range(start_race, end_race + 1):
                    processed_races_dfs[race_num - 1]["points"] = np.where(
                        processed_races_dfs[race_num - 1]["friend_code"] == fc,
                        score_map[fc] if race_num == start_race else 0,
                        processed_races_dfs[race_num - 1]["points"],
                    )

    processed_all_players["mii_name"] = processed_all_players["mii_name"].fillna("Unknown")
    processed_all_players["changed_name"] = processed_all_players["changed_name"].fillna("—")
    processed_all_players["display_name"] = np.where(
        (processed_all_players["changed_name"] != "—") & processed_all_players["changed_name"].notna(),
        processed_all_players["changed_name"],
        processed_all_players["mii_name"],
    )
    processed_all_players["display_name"] = processed_all_players["display_name"].fillna("Unknown")

    return True, processed_all_players, processed_races_dfs, error_log
