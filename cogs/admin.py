import contextlib
import io
import textwrap
import traceback

from discord.ext import commands


class Admin(commands.Cog):
    """Commands meant to be used only by the Bot admins."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._last_result = None

    def cleanup_code(self, content):
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        return content.strip('` \n')

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    async def cog_command_error(self, ctx, error):
        """A mini error handler for this cog."""

        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(f"Please specify the **{error.param.name}** parameter.")
        else:
            self.bot.photon_log.error(
                f"[ERROR] Command: {ctx.command.name}, Exception: {error}.")

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
            await ctx.send(f"Failed to reload the specified extension. Exception: {e.original}")

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
            await ctx.send(f"Failed to load the specified extension. Exception: {e.original}")

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
            await ctx.send(f"Failed to unload the specified extension. Exception: {e.original}")

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

    # Taken from Rapptz/RoboDanny.
    @commands.command(name="eval")
    async def _eval(self, ctx, *, code: str):
        """Evaluates a snippet of Python code."""

        # Define some environment vars for the function.
        env = {
            "bot": self.bot,
            "ctx": ctx,
            "channel": ctx.channel,
            "author": ctx.author,
            "guild": ctx.guild,
            "message": ctx.message,
            "_": self._last_result
        }

        env.update(globals())

        # Clean up the code and define our 'stdout'.
        cleaned_code = self.cleanup_code(code)
        stdout = io.StringIO()

        # Wrap the code into a async function.
        to_compile = f"async def func():\n{textwrap.indent(cleaned_code, '  ')}"

        # try to 'compile' the function.
        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')

        func = env["func"]
        try:
            with contextlib.redirect_stdout(stdout):
                ret = await func()
        except Exception:
            value = stdout.getvalue()
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue()
            await ctx.message.add_reaction("\U00002705")

            if ret is None:
                if value:
                    await ctx.send(f"```py\n{value}\n```")
            else:
                self._last_result = ret
                await ctx.send(f"```py\n{value}{ret}\n```")


def setup(bot: commands.Bot):
    bot.add_cog(Admin(bot))
