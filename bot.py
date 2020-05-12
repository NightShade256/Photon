import logging

import aiohttp
import discord
import wavelink
from discord.ext import commands, tasks

__author__ = "Anish Jewalikar (__NightShade256__)"
__version__ = "1.3a"


extensions = [
    "cogs.admin",
    "cogs.notes",
    "cogs.utilities",
    "cogs.music",
    "cogs.moderation",
    "cogs.polls",
    "cogs.photon",
    "cogs.events"
]


async def _get_prefix(bot, msg):
    if msg.guild.id in bot.prefix_list:
        return bot.prefix_list[msg.guild.id]
    else:
        async with bot.database.acquire() as con:
            query = "SELECT prefix FROM guild WHERE guild_id = $1"
            precord = await con.fetchrow(query, msg.guild.id)
        if precord is None:
            prefix = "&"
        else:
            prefix = precord["prefix"]
        bot.prefix_list[msg.guild.id] = prefix
        return commands.when_mentioned_or(prefix)(bot, msg)


class Photon(commands.AutoShardedBot):

    def __init__(self, database_pool, event_loop):
        super().__init__(_get_prefix, loop=event_loop)
        self.library_version = discord.__version__
        self.prefix_list = {}
        self.database = database_pool
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
                    f"{ext} extension failed to load. EXCEPTION: {e}")

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
            await self.web.close()
            await self.database.close()
            await super().close()
            self.photon_log.info(
                "Shutdown attempt successful. Photon has been closed.")
        except Exception:
            self.photon_log.error(
                "Shutdown failed to occur gracefully.", exc_info=True)

    async def on_command_error(self, ctx, error):
        """Photon error handler."""

        if isinstance(error, commands.CommandOnCooldown):
            return await ctx.send(f"The command is on cooldown. Retry after **{error.retry_after:.2f}** seconds.")
        elif isinstance(error, commands.CommandInvokeError):
            if isinstance(error.original, wavelink.ZeroConnectedNodes):
                return await ctx.send("No Lavalink nodes are currently online. Please try again.")
            else:
                self.photon_log.error(
                    f"[ERROR] Command: {ctx.command.name} Exception: {error}")
