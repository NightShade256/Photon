import asyncio
import functools

import discord
from discord.ext import commands

# pylint: disable=import-error
from utils import canvas


class Events(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.lock = asyncio.Lock()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Welcome/Leave message handler."""

        # Acquire database connection and fetch guild entry.
        async with self.bot.database.acquire() as con:
            row = await con.fetchrow(
                "SELECT welcome FROM guild WHERE guild_id = $1", member.guild.id)
        if row is None:
            return

        # Get channel and check if it is None.
        channel = self.bot.get_channel(int(row["welcome"])) if row["welcome"] is not None else None
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

        # Acquire database connection and fetch guild entry.
        async with self.bot.database.acquire() as con:
            row = await con.fetchrow(
                "SELECT welcome FROM guild WHERE guild_id = $1", member.guild.id)
        if row is None:
            return

        # Get channel and check if it is None.
        channel = self.bot.get_channel(int(row["welcome"])) if row["welcome"] is not None else None
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

        # Create the guild row directly.
        query = "INSERT INTO guild VALUES ($1, $2, $3);"
        async with self.bot.database.acquire() as con:
            async with con.transaction():
                await con.execute(query, guild.id, "&", None)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        """Deletes the database entry of the concerned guild."""

        # Delete the guild row directly.
        query = "DELETE FROM guild WHERE guild_id = $1;"
        async with self.bot.database.acquire() as con:
            async with con.transaction():
                await con.execute(query, guild.id)


def setup(bot):
    bot.add_cog(Events(bot))
