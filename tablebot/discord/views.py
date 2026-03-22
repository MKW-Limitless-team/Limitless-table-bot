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
