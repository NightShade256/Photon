import logging

import aiohttp
import discord
import wavelink
from discord.ext import commands

from utils import db

__author__ = "Anish Jewalikar (__NightShade256__)"
__version__ = "1.7a"


extensions = [
    "cogs.admin",
    "cogs.notes",
    "cogs.utilities",
    "cogs.music",
    "cogs.moderation",
    "cogs.polls",
    "cogs.photon",
    "cogs.events",
    "cogs.fun"
]


async def _get_prefix(bot, msg):
    if msg.guild.id in bot.prefix_list:
        return bot.prefix_list[msg.guild.id]
    else:
        precord = await bot.database.fetch_prefix(msg.guild.id)
        if precord is None:
            prefix = "&"
        else:
            prefix = precord["prefix"]
        bot.prefix_list[msg.guild.id] = prefix
        return commands.when_mentioned_or(prefix)(bot, msg)


class Photon(commands.Bot):

    def __init__(self, db_helper, event_loop):
        super().__init__(_get_prefix, loop=event_loop)
        self.library_version = discord.__version__
        self.prefix_list = {}
        self.database: db.DatabaseHelper = db_helper
        self.web = aiohttp.ClientSession(loop=self.loop)
        log_string = "[PHOTON] Time: %(asctime)s Message: %(message)s"
        logging.basicConfig(format=log_string, datefmt="%d-%b-%y %H:%M:%S")
        self.photon_log = logging.getLogger("Photon")
        self.photon_log.setLevel(10)
        for ext in extensions:
            try:
                self.load_extension(ext)
                self.photon_log.info(f"{ext} extension successfully loaded.")
            except Exception as e:
                self.photon_log.error(
                    f"{ext} extension failed to load. EXCEPTION: {e.__cause__}")

    async def on_ready(self):
        self.photon_log.info(
            f"Photon is now ready. Guild Count: {len(self.guilds)}.")

    async def on_message(self, message):
        if message.guild is None:
            return
        await self.process_commands(message)

    def run(self, api_token):
        super().run(api_token, reconnect=True)

    async def close(self):
        self.photon_log.info("Shutdown attempt started.")
        try:
            await super().close()
            await self.web.close()
            await self.database.close()
            self.photon_log.info(
                "Shutdown attempt successful. Photon has been closed.")
        except Exception:
            self.photon_log.error(
                "Shutdown failed to occur gracefully.", exc_info=True)

    async def on_command_error(self, ctx: commands.Context, error):
        """Photon error handler."""

        if isinstance(error, commands.CommandOnCooldown):
            is_owner_sync = await self.is_owner(ctx.author)
            if is_owner_sync:
                return await ctx.reinvoke()

            return await ctx.send(
                f"The command is on cooldown. Retry after **{error.retry_after:.2f}** seconds.")

        elif isinstance(error, commands.CommandInvokeError):
            if isinstance(error.original, wavelink.ZeroConnectedNodes):
                return await ctx.send("No Lavalink nodes are currently online. Please try again.")
            else:
                self.photon_log.error(
                    f"[ERROR] Command: {ctx.command.name} Exception: {error}")
