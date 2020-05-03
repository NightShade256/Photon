import datetime
import functools

import discord
from discord.ext import commands


class Admin(commands.Cog):
    """Commands meant to be used only by the Bot admins."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)
    
    async def cog_command_error(self, ctx, error):
        """A mini error handler for this cog."""

        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(f"Please specify the **{error.param.name}** parameter.")

    @commands.command(name="reload", aliases=["re"])
    async def _reload(self, ctx, *, name: str):
        """Reloads the specified extension atomically.

        Example: If extension foo/test.py is to be reloaded, then 
        the name of specified should be foo.test"""

        try:
            self.bot.reload_extension(name)
            self.bot.photon_log.info(f"Reloaded extension {name}")
            await ctx.send("Reloaded the specified extension successfully.")
        except Exception as e:
            self.bot.photon_log.error(f"Failed to reload extension {name}")
            await ctx.send(f"Failed to reload the specified extension. Exception: {e}")

    @commands.command(name="load", aliases=["lo"])
    async def _load(self, ctx, *, name: str):
        """Loads the specified extension.

        Example: If extension foo/test.py is to be loaded, then 
        the name of specified should be foo.test"""

        try:
            self.bot.load_extension(name)
            self.bot.photon_log.info(f"Loaded extension {name}")
            await ctx.send("Loaded the specified extension successfully.")
        except Exception as e:
            self.bot.photon_log.error(f"Failed to load extension {name}")
            await ctx.send(f"Failed to load the specified extension. Exception: {e}")

    @commands.command(name="unload", aliases=["un"])
    async def _unload(self, ctx, *, name: str):
        """Unloads the specified extension.

        Example: If extension foo/test.py is to be unloaded, then 
        the name of specified should be foo.test"""

        try:
            self.bot.unload_extension(name)
            self.bot.photon_log.info(f"Unloaded extension {name}")
            await ctx.send("Unloaded the specified extension successfully.")
        except Exception as e:
            self.bot.photon_log.error(f"Failed to unload extension {name}")
            await ctx.send(f"Failed to unload the specified extension. Exception: {e}")

    @commands.command(name="exit", aliases=["shutdown", "quit"])
    async def _quit(self, ctx):
        """Initiates bot shutdown process."""

        await ctx.send("Photon is shutting down, have a nice day!")
        await self.bot.close()

    @commands.command(name="rdata")
    async def _rdata(self, ctx):
        """Regenerate database entry for the guild it is run in."""

        # Prewrite the queries.
        delete_query = "DELETE FROM guild WHERE guild_id = $1;"
        insert_query = "INSERT INTO guild VALUES ($1, $2, $3);"

        # Execute them.
        async with self.bot.database.acquire() as con:
            async with con.transaction():
                await con.execute(delete_query, ctx.guild.id)
                await con.execute(insert_query, ctx.guild.id, "&", None)

        await ctx.send("Regenerated database entry successfully.")


def setup(bot):
    bot.add_cog(Admin(bot))
