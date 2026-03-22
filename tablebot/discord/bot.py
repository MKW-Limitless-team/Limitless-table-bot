from __future__ import annotations

import discord
from discord.ext import commands

from tablebot.config import CONFIG_PATH, TOKEN
from tablebot.discord.commands import register_commands


def build_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.messages = True
    bot = commands.Bot(command_prefix="%", intents=intents)

    @bot.event
    async def on_ready() -> None:
        await bot.tree.sync()
        print(f"Logged in as {bot.user}")

    register_commands(bot, bot.tree)
    return bot


def run() -> None:
    if not TOKEN:
        raise RuntimeError(f"Discord bot token is not set. Update {CONFIG_PATH}.")
    build_bot().run(TOKEN)
