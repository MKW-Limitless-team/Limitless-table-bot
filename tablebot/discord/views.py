from __future__ import annotations

import time

import discord

from tablebot.rendering.text import image_to_file
from tablebot.services import table_service
from tablebot.utils.formatting import parse_possible_mention


class RefreshVerifyRoom(discord.ui.View):
    def __init__(self, player: str, image: bool, cooldown: int = 10):
        super().__init__(timeout=None)
        self.player = player
        self.image = image
        self.cooldown = cooldown
        self.last_pressed = 0.0

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.primary)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        now = time.time()
        if now - self.last_pressed < self.cooldown:
            await interaction.response.send_message(
                f"Please wait {round(self.cooldown - (now - self.last_pressed), 1)} seconds before refreshing again.",
                ephemeral=True,
            )
            return
        self.last_pressed = now
        player = parse_possible_mention(self.player)
        success, vr_text, vr_image = table_service.verify_room(player)
        if not success:
            await interaction.response.edit_message(content=f"Error: {vr_text}", attachments=[], view=self)
            return
        if self.image:
            buffer, filename = image_to_file(vr_image, "verify_room.png")
            await interaction.response.edit_message(content=None, attachments=[discord.File(buffer, filename=filename)], view=self)
        else:
            await interaction.response.edit_message(content=vr_text, attachments=[], view=self)


class RefreshWP(discord.ui.View):
    def __init__(self, by_race: bool, override_color: bool = False, cooldown: int = 10):
        super().__init__(timeout=None)
        self.by_race = by_race
        self.override_color = override_color
        self.cooldown = cooldown
        self.last_pressed = 0.0

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.primary)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        now = time.time()
        if now - self.last_pressed < self.cooldown:
            await interaction.response.send_message(
                f"Please wait {round(self.cooldown - (now - self.last_pressed), 1)} seconds before refreshing again.",
                ephemeral=True,
            )
            return

        self.last_pressed = now
        server_id = str(interaction.guild.id)
        channel_id = str(interaction.channel.id)

        try:
            state = table_service.load_table_state(server_id, channel_id)
        except FileNotFoundError:
            await interaction.response.edit_message(content="No table started in this channel.", attachments=[], view=self)
            return

        refresh_success, refresh_result = table_service.refresh_table_state(server_id, channel_id, state)
        if not refresh_success:
            await interaction.response.edit_message(content=f"Error: {refresh_result}", attachments=[], view=self)
            return

        success, table_image, update_text, red_flags, _, _ = table_service.render_table(state, self.by_race, self.override_color)
        if not success:
            await interaction.response.edit_message(content=f"Error: {table_image}", attachments=[], view=self)
            return

        buffer, filename = image_to_file(table_image, "war_picture.png")
        lines = [update_text]
        combined_red_flags = list(refresh_result) if isinstance(refresh_result, list) else []
        combined_red_flags.extend(red_flags)
        if combined_red_flags:
            lines.extend(combined_red_flags)
        await interaction.response.edit_message(content="\n".join(lines), attachments=[discord.File(buffer, filename=filename)], view=self)
