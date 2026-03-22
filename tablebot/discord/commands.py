from __future__ import annotations

from typing import Literal

import discord
from discord import app_commands

from tablebot.config import BASE_URL
from tablebot.constants import HELP_MAP, HELP_MESSAGE
from tablebot.rendering.text import image_to_file
from tablebot.services import edit_service, table_service
from tablebot.storage.state_store import state_exists
from tablebot.utils.formatting import parse_possible_mention


def _require_state(server_id: str, channel_id: str):
    if not state_exists(server_id, channel_id):
        raise FileNotFoundError("No table started in this channel.")
    return table_service.load_table_state(server_id, channel_id)


async def _send_interaction_message(interaction: discord.Interaction, content: str) -> None:
    if interaction.response.is_done():
        await interaction.edit_original_response(content=content, attachments=[])
    else:
        await interaction.response.send_message(content)


def register_commands(bot: discord.Client, tree: app_commands.CommandTree) -> None:
    @tree.command(name="vr", description="Verify Room")
    async def vr(interaction: discord.Interaction, player: str | None = None, image: Literal["True", "False"] = "False"):
        player = parse_possible_mention(player or str(interaction.user.id))
        await interaction.response.defer()
        success, vr_text, vr_image = table_service.verify_room(player)
        if not success:
            await interaction.edit_original_response(content=f"Error: {vr_text}")
            return
        if image == "True":
            buffer, filename = image_to_file(vr_image, "verify_room.png")
            await interaction.edit_original_response(content=None, attachments=[discord.File(buffer, filename=filename)])
        else:
            await interaction.edit_original_response(content=vr_text)

    @tree.command(name="sw", description="Start new War/Table")
    async def sw(
        interaction: discord.Interaction,
        format: Literal["FFA", "2v2", "3v3", "4v4", "5v5", "6v6"],
        num_teams: int,
        lookup: str | None = None,
        rxx: str | None = None,
        color_theme: str = "pastel",
    ):
        await interaction.response.defer()
        search_term = parse_possible_mention(lookup or str(interaction.user.id))
        server_id = str(interaction.guild.id)
        channel_id = str(interaction.channel.id)
        success, room_code_or_error = table_service.start_table(search_term, format, num_teams, server_id, channel_id, color_theme, rxx)
        if not success:
            await interaction.edit_original_response(content=f"Error: {room_code_or_error}")
            return
        state = table_service.load_table_state(server_id, channel_id)
        success, table_image, update_text, red_flags, _, edit_link = table_service.render_table(state)
        if not success:
            await interaction.edit_original_response(content=f"Error: {table_image}")
            return
        buffer, filename = image_to_file(table_image, "war_picture.png")
        lines = [
            f"Successfully started the {format} table with {num_teams} teams.",
            f"Room URL: {BASE_URL}/api/mkw_rr?id={room_code_or_error}",
            update_text,
        ]
        if red_flags:
            lines.append("")
            lines.extend(red_flags)
        await interaction.edit_original_response(content="\n".join(lines), attachments=[discord.File(buffer, filename=filename)])

    @tree.command(name="mergeroom", description="Merge existing table with new room")
    async def mergeroom(interaction: discord.Interaction, lookup: str | None = None, rxx: str | None = None):
        await interaction.response.defer()
        server_id = str(interaction.guild.id)
        channel_id = str(interaction.channel.id)
        state = _require_state(server_id, channel_id)
        success, message = table_service.merge_room(parse_possible_mention(lookup or str(interaction.user.id)), state, rxx)
        if success:
            table_service.save_table_state(server_id, channel_id, state)
        await interaction.edit_original_response(content=message if success else f"Error: {message}")

    @tree.command(name="wp", description="Display updated War/Table Picture")
    async def wp(interaction: discord.Interaction, by_race: Literal["True", "False"] = "False", distinct_color_table: Literal["True", "False"] = "False"):
        await interaction.response.defer()
        state = _require_state(str(interaction.guild.id), str(interaction.channel.id))
        success, table_image, update_text, red_flags, _, edit_link = table_service.render_table(state, by_race == "True", distinct_color_table == "True")
        if not success:
            await interaction.edit_original_response(content=f"Error: {table_image}")
            return
        buffer, filename = image_to_file(table_image, "war_picture.png")
        lines = [update_text]
        if red_flags:
            lines.extend(red_flags)
        await interaction.edit_original_response(content="\n".join(lines), attachments=[discord.File(buffer, filename=filename)])

    @tree.command(name="tt", description="Get Lorenzi Table Text")
    async def tt(interaction: discord.Interaction, by_race: Literal["True", "False"] = "False"):
        await interaction.response.defer()
        state = _require_state(str(interaction.guild.id), str(interaction.channel.id))
        await interaction.edit_original_response(content=table_service.get_tabletext(state, by_race == "True"))

    @tree.command(name="ap", description="List All Players who have been in room")
    async def ap(interaction: discord.Interaction):
        await interaction.response.defer()
        state = _require_state(str(interaction.guild.id), str(interaction.channel.id))
        await interaction.edit_original_response(content=table_service.get_allplayers(state))

    @tree.command(name="races", description="List all the races that have been played")
    async def races(interaction: discord.Interaction):
        await interaction.response.defer()
        state = _require_state(str(interaction.guild.id), str(interaction.channel.id))
        await interaction.edit_original_response(content=table_service.races_text(state))

    @tree.command(name="teams", description="List all the team tags in the room")
    async def teams(interaction: discord.Interaction):
        await interaction.response.defer()
        state = _require_state(str(interaction.guild.id), str(interaction.channel.id))
        await interaction.edit_original_response(content=table_service.teams_text(state))

    @tree.command(name="commands", description="List all the table edit commands that have been applied")
    async def commands_cmd(interaction: discord.Interaction):
        await interaction.response.defer()
        state = _require_state(str(interaction.guild.id), str(interaction.channel.id))
        await interaction.edit_original_response(content=table_service.commands_text(state))

    @tree.command(name="rr", description="List results of a race")
    async def rr(interaction: discord.Interaction, race_number: int = 9999, show_true_lag_start: Literal["True", "False"] = "False"):
        await interaction.response.defer()
        state = _require_state(str(interaction.guild.id), str(interaction.channel.id))
        await interaction.edit_original_response(content=table_service.race_result_text(state, max(1, race_number), show_true_lag_start == "True"))

    @tree.command(name="url", description="List Limitless room URLs")
    async def url(interaction: discord.Interaction):
        await interaction.response.defer()
        state = _require_state(str(interaction.guild.id), str(interaction.channel.id))
        num_rooms = int(state.metadata["num_rooms"].iloc[0])
        room_codes = [str(state.metadata[f"room_{index}_id"].iloc[0]) for index in range(1, num_rooms + 1)]
        urls = [f"{BASE_URL}/api/mkw_rr?id={room_code}" for room_code in room_codes]
        await interaction.edit_original_response(content="Room codes:\n" + "\n".join(room_codes) + "\n\nRoom URLs:\n" + "\n".join(urls))

    @tree.command(name="help", description="Get help with bot commands")
    async def help_cmd(interaction: discord.Interaction, command: str | None = None):
        await interaction.response.defer()
        await interaction.edit_original_response(content=HELP_MAP.get(command or "", HELP_MESSAGE))

    def _register_simple_toggle_command(name: str, description: str, undo_value: bool):
        @tree.command(name=name, description=description)
        async def toggle_command(interaction: discord.Interaction, command_id: int = 9999):
            await interaction.response.defer()
            server_id = str(interaction.guild.id)
            channel_id = str(interaction.channel.id)
            state = _require_state(server_id, channel_id)
            filtered = state.commands[state.commands["undo"] == (not undo_value)].copy()
            if len(filtered) < 1:
                await interaction.edit_original_response(content=f"No commands to {name} on this table.")
                return
            if command_id > int(filtered.iloc[-1]["command_id"]):
                command_id = int(filtered.iloc[-1]["command_id"])
            state.commands.loc[state.commands["command_id"] == command_id, "undo"] = undo_value
            _, error_log = table_service.apply_commands_and_save(server_id, channel_id, state)
            suffix = f"\nErrors:\n" + "\n".join(error_log) if error_log else ""
            await interaction.edit_original_response(content=f"Successfully updated command {command_id}.{suffix}")

    _register_simple_toggle_command("undo", "Undo a table edit command", True)
    _register_simple_toggle_command("redo", "Redo a table edit command", False)

    @tree.command(name="undoall", description="Undo all table edit commands")
    async def undoall(interaction: discord.Interaction):
        await interaction.response.defer()
        server_id = str(interaction.guild.id)
        channel_id = str(interaction.channel.id)
        state = _require_state(server_id, channel_id)
        state.commands["undo"] = True
        table_service.apply_commands_and_save(server_id, channel_id, state)
        await interaction.edit_original_response(content="Successfully marked all commands as undone.")

    @tree.command(name="redoall", description="Redo all table edit commands")
    async def redoall(interaction: discord.Interaction):
        await interaction.response.defer()
        server_id = str(interaction.guild.id)
        channel_id = str(interaction.channel.id)
        state = _require_state(server_id, channel_id)
        state.commands["undo"] = False
        table_service.apply_commands_and_save(server_id, channel_id, state)
        await interaction.edit_original_response(content="Successfully marked all commands as redone.")

    @tree.command(name="edittag", description="Change the name of a team's tag")
    async def edittag(interaction: discord.Interaction, current_tag: str, new_tag: str):
        await interaction.response.defer()
        server_id = str(interaction.guild.id)
        channel_id = str(interaction.channel.id)
        state = _require_state(server_id, channel_id)
        state.commands = edit_service.append_command(state.commands, "edittag", f"edittag {current_tag} {new_tag}", current_tag, new_tag)
        table_service.apply_commands_and_save(server_id, channel_id, state)
        await interaction.edit_original_response(content=f'Successfully changed team "{current_tag}" to "{new_tag}".')

    @tree.command(name="changetag", description="Change the tag of a player")
    async def changetag(interaction: discord.Interaction, player: str, new_tag: str):
        await interaction.response.defer()
        server_id = str(interaction.guild.id)
        channel_id = str(interaction.channel.id)
        state = _require_state(server_id, channel_id)
        success, player_id = table_service.map_player_input_to_player_id(player, state.all_players)
        if not success:
            await interaction.edit_original_response(content=str(player_id))
            return
        state.commands = edit_service.append_command(state.commands, "changetag", f"changetag {player_id} {new_tag}", player_id, new_tag)
        table_service.apply_commands_and_save(server_id, channel_id, state)
        await interaction.edit_original_response(content=f'Successfully changed player {player_id} to tag "{new_tag}".')

    @tree.command(name="teampen", description="Add Penalty amount to a team")
    async def teampen(interaction: discord.Interaction, team: str, amount: int):
        await interaction.response.defer()
        server_id = str(interaction.guild.id)
        channel_id = str(interaction.channel.id)
        state = _require_state(server_id, channel_id)
        state.commands = edit_service.append_command(state.commands, "teampen", f"teampen {team} {amount}", team, amount)
        table_service.apply_commands_and_save(server_id, channel_id, state)
        await interaction.edit_original_response(content=f'Successfully set the penalty for team "{team}".')

    @tree.command(name="sub", description="Sub a player in for another")
    async def sub(interaction: discord.Interaction, sub_in: str, sub_out: str, race: int):
        await interaction.response.defer()
        server_id = str(interaction.guild.id)
        channel_id = str(interaction.channel.id)
        state = _require_state(server_id, channel_id)
        success_in, sub_in_id = table_service.map_player_input_to_player_id(sub_in, state.all_players)
        success_out, sub_out_id = table_service.map_player_input_to_player_id(sub_out, state.all_players)
        success_race, match_id = edit_service.map_race_to_match_id(race, state.processed_races_dfs)
        if not success_in:
            await interaction.edit_original_response(content=str(sub_in_id))
            return
        if not success_out:
            await interaction.edit_original_response(content=str(sub_out_id))
            return
        if not success_race:
            await interaction.edit_original_response(content=str(match_id))
            return
        state.commands = edit_service.append_command(state.commands, "sub", f"sub {sub_in_id} {sub_out_id} {match_id}({race})", sub_in_id, sub_out_id, match_id)
        table_service.apply_commands_and_save(server_id, channel_id, state)
        await interaction.edit_original_response(content=f"Successfully subbed in player {sub_in_id} for player {sub_out_id} on race {race}.")

    @tree.command(name="removerace", description="Remove a race from the table")
    async def removerace(interaction: discord.Interaction, race: int):
        await interaction.response.defer()
        server_id = str(interaction.guild.id)
        channel_id = str(interaction.channel.id)
        state = _require_state(server_id, channel_id)
        success_race, match_id = edit_service.map_race_to_match_id(race, state.processed_races_dfs)
        if not success_race:
            await interaction.edit_original_response(content=str(match_id))
            return
        state.commands = edit_service.append_command(state.commands, "removerace", f"removerace {match_id}({race})", match_id)
        table_service.apply_commands_and_save(server_id, channel_id, state)
        await interaction.edit_original_response(content=f"Successfully removed race {race}.")

    @tree.command(name="insertrace", description="Insert a race onto the table")
    async def insertrace(interaction: discord.Interaction, race: int, placements: str, track: str = "Unknown Track"):
        await interaction.response.defer()
        server_id = str(interaction.guild.id)
        channel_id = str(interaction.channel.id)
        state = _require_state(server_id, channel_id)
        if race == 1:
            match_id_before = "1st race"
        else:
            success, match_id_before = edit_service.map_race_to_match_id(race - 1, state.processed_races_dfs)
            if not success:
                await interaction.edit_original_response(content=str(match_id_before))
                return
        player_ids = []
        for piece in [item.lstrip() for item in placements.split(",")]:
            success, player_id = table_service.map_player_input_to_player_id(piece, state.all_players)
            if not success:
                await interaction.edit_original_response(content=str(player_id))
                return
            player_ids.append(str(player_id))
        joined = ", ".join(player_ids)
        state.commands = edit_service.append_command(state.commands, "insertrace", f"insertrace {match_id_before}({race}) {joined}", match_id_before, joined, track)
        table_service.apply_commands_and_save(server_id, channel_id, state)
        await interaction.edit_original_response(content=f"Successfully inserted race {race}.")

    @tree.command(name="editrace", description="Edit finishing positions of a race")
    async def editrace(interaction: discord.Interaction, race: int, placements: str):
        await interaction.response.defer()
        server_id = str(interaction.guild.id)
        channel_id = str(interaction.channel.id)
        state = _require_state(server_id, channel_id)
        success_race, match_id = edit_service.map_race_to_match_id(race, state.processed_races_dfs)
        if not success_race:
            await interaction.edit_original_response(content=str(match_id))
            return
        player_ids = []
        for piece in [item.lstrip() for item in placements.split(",")]:
            success, player_id = table_service.map_player_input_to_player_id(piece, state.all_players)
            if not success:
                await interaction.edit_original_response(content=str(player_id))
                return
            player_ids.append(str(player_id))
        joined = ", ".join(player_ids)
        state.commands = edit_service.append_command(state.commands, "editrace", f"editrace {match_id}({race}) {joined}", match_id, joined)
        table_service.apply_commands_and_save(server_id, channel_id, state)
        await interaction.edit_original_response(content=f"Successfully edited race {race}.")

    @tree.command(name="cp", description="Change finish position of a player on a race")
    async def cp(interaction: discord.Interaction, player: str, race: int, position: int):
        await interaction.response.defer()
        server_id = str(interaction.guild.id)
        channel_id = str(interaction.channel.id)
        state = _require_state(server_id, channel_id)
        success_player, player_id = table_service.map_player_input_to_player_id(player, state.all_players)
        success_race, match_id = edit_service.map_race_to_match_id(race, state.processed_races_dfs)
        if not success_player:
            await interaction.edit_original_response(content=str(player_id))
            return
        if not success_race:
            await interaction.edit_original_response(content=str(match_id))
            return
        state.commands = edit_service.append_command(state.commands, "changeplace", f"cp {player_id} {match_id}({race}) {position}", player_id, match_id, position)
        table_service.apply_commands_and_save(server_id, channel_id, state)
        await interaction.edit_original_response(content=f"Successfully changed place for player {player_id} on race {race}.")

    @tree.command(name="edit", description="Change a player's score for a GP")
    async def edit(interaction: discord.Interaction, player: str, gp: int, score: int):
        await interaction.response.defer()
        server_id = str(interaction.guild.id)
        channel_id = str(interaction.channel.id)
        state = _require_state(server_id, channel_id)
        success_player, player_id = table_service.map_player_input_to_player_id(player, state.all_players)
        if not success_player:
            await interaction.edit_original_response(content=str(player_id))
            return
        state.commands = edit_service.append_command(state.commands, "edit", f"edit {player_id} {gp} {score}", player_id, gp, score)
        table_service.apply_commands_and_save(server_id, channel_id, state)
        await interaction.edit_original_response(content=f"Successfully edited player {player_id}'s GP {gp} to {score}.")

    @tree.command(name="gpedit", description="Change all players' scores for a GP")
    async def gpedit(interaction: discord.Interaction, gp: int, scores: str):
        await interaction.response.defer()
        server_id = str(interaction.guild.id)
        channel_id = str(interaction.channel.id)
        state = _require_state(server_id, channel_id)
        state.commands = edit_service.append_command(state.commands, "gpedit", f"gpedit {gp} {scores}", gp, scores)
        table_service.apply_commands_and_save(server_id, channel_id, state)
        await interaction.edit_original_response(content=f"Successfully edited GP {gp}.")

    @tree.command(name="changename", description="Change a player's display name on the table")
    async def changename(interaction: discord.Interaction, player: str, new_name: str):
        await interaction.response.defer()
        server_id = str(interaction.guild.id)
        channel_id = str(interaction.channel.id)
        state = _require_state(server_id, channel_id)
        success_player, player_id = table_service.map_player_input_to_player_id(player, state.all_players)
        if not success_player:
            await interaction.edit_original_response(content=str(player_id))
            return
        state.commands = edit_service.append_command(state.commands, "changename", f"changename {player_id} {new_name}", player_id, new_name)
        table_service.apply_commands_and_save(server_id, channel_id, state)
        await interaction.edit_original_response(content=f"Successfully changed player {player_id}'s name to {new_name}.")

    @tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        original_error = getattr(error, "original", error)
        if isinstance(original_error, FileNotFoundError):
            await _send_interaction_message(interaction, str(original_error))
            return
        raise error
