import asyncio
import functools

import discord
from discord.ext import commands

from bot import Photon
# pylint: disable=import-error
from utils import canvas


class Events(commands.Cog):

    def __init__(self, bot: Photon):
        self.bot = bot
        self.lock = asyncio.Lock()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Welcome/Leave message handler."""

        # Fetch the welcome channel id from the database.
        welcome_status = await self.bot.database.get_welcome_channel(member.guild)
        if welcome_status is None:
            return

        # Get channel and check if it is None.
        channel = self.bot.get_channel(int(welcome_status))
        if channel is None:
            return

        # Fetch avatar
        avatar = await (member.avatar_url_as(size=256)).read()

        # With lock make image.
        async with self.lock:
            func = functools.partial(canvas.welcome_leave_image, avatar, member, True)
            image = await self.bot.loop.run_in_executor(None, func)
        file_buffer = discord.File(image, "welcome.png")
        await channel.send(file=file_buffer)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Welcome/Leave message handler."""

        # Fetch the welcome channel id from the database.
        welcome_status = await self.bot.database.get_welcome_channel(member.guild)
        if welcome_status is None:
            return

        # Get channel and check if it is None.
        channel = self.bot.get_channel(int(welcome_status))
        if channel is None:
            return

        # Fetch avatar
        avatar = await (member.avatar_url_as(size=256)).read()

        # With lock make image.
        async with self.lock:
            func = functools.partial(canvas.welcome_leave_image, avatar, member, False)
            image = await self.bot.loop.run_in_executor(None, func)
        file_buffer = discord.File(image, "goodbye.png")
        await channel.send(file=file_buffer)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Creates database entry when Photon joins a guild."""

        await self.bot.database.create_guild_entry(guild)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        """Deletes the database entry of the concerned guild."""

        await self.bot.database.delete_guild_entry(guild)


def setup(bot: Photon):
    bot.add_cog(Events(bot))
