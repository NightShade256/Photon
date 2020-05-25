import textwrap

import discord
import humanize
import psutil
from discord.ext import commands


class PhotonCog(commands.Cog, name="Photon"):
    """Find information related to Photon."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.process = psutil.Process()

    async def cog_command_error(self, ctx, error):
        """Mini error handler for this cog."""

        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send("Please provide a valid prefix string.")
        else:
            self.bot.photon_log.error(f"[ERROR] Command: {ctx.command.name}, Exception: {error}.")

    @commands.command(name="about")
    async def _about(self, ctx):
        """Get information about Photon."""

        # Retrieve the memory usage, dividing by 1024^2 to convert bytes to
        # mebibytes.
        memory_usage = humanize.naturalsize(
            self.process.memory_full_info().uss)
        # Retrieve the CPU usage
        cpu_usage = self.process.cpu_percent() / psutil.cpu_count()
        # Get the total server and users that photon serves
        guilds = len(self.bot.guilds)
        unique_users = sum(1 for x in self.bot.get_all_members())

        # As a prerequisite for building the embed.
        desc = """Photon is a multipurpose Discord bot that aims to be user friendly and fast.
                  It is **open source** under the **MIT license**.
                  You can find the source code [here](https://github.com/NightShade256/Photon)."""
        desc = " ".join([textwrap.dedent(x) for x in desc.splitlines()])
        desc = " ".join(textwrap.wrap(desc, len(desc)))
        url = 'https://www.python.org/static/community_logos/python-powered-w-200x80.png'

        # Building the embed.
        embed = discord.Embed(title="About Photon", description=desc,
                              colour=discord.Color.dark_teal())
        embed.set_thumbnail(url=url)
        resource_usage = f'{memory_usage}\n{cpu_usage:.2f}% CPU'
        embed.add_field(name='**• Resource Usage:**', value=resource_usage)
        embed.add_field(name='**• Server Count:**', value=guilds)
        embed.add_field(name='**• Unique Users:**', value=unique_users)
        embed.set_footer(
            text=f'Requested by {ctx.author.name}.', icon_url=ctx.author.avatar_url)

        # Send it!
        await ctx.send(embed=embed)

    @commands.command(name="welcome")
    @commands.has_guild_permissions(ban_members=True)
    @commands.cooldown(1, 120.0, commands.BucketType.guild)
    async def _welcome(self, ctx: commands.Context):
        """Enable or disable welcome and leave messages."""

        async with self.bot.database.acquire() as con:
            row = await con.fetchrow(
                "SELECT welcome FROM guild WHERE guild_id = $1;", ctx.guild.id)
            if row["welcome"] is None:
                channel_id = ctx.channel.id
            else:
                channel_id = None
            async with con.transaction():
                query = "UPDATE guild SET welcome = $1 WHERE guild_id = $2;"
                await con.execute(query, channel_id, ctx.guild.id)
        fmt = "enabled" if channel_id is not None else "disabled"
        await ctx.send(f"Welcome and Leave messages are now **{fmt}** in this channel.")

    @commands.command(name="prefix")
    @commands.has_guild_permissions(ban_members=True)
    @commands.cooldown(1, 120.0, commands.BucketType.guild)
    async def _prefix(self, ctx: commands.Context, *, prefix: str):
        """Change the prefix to your liking."""

        # Check if prefix is very large.
        if len(prefix) > 5:
            return await ctx.send("The prefix can only be five characters long.")

        # Update the prefix
        query = "UPDATE guild SET prefix = $1 WHERE guild_id = $2;"
        async with self.bot.database.acquire() as con:
            async with con.transaction():
                await con.execute(query, prefix, ctx.guild.id)

        self.bot.prefix_list[ctx.guild.id] = prefix
        await ctx.send(f"The prefix was successfully changed to **`{prefix}`**.")

    @commands.command(name="ping")
    async def _ping(self, ctx: commands.Context):
        """Check the bot's API/WS latency.

        This command is not that useful, but can help to determine
        if the bot is having network problems.
        """

        latency = self.bot.latency * 1000

        # Calculate the time
        message = await ctx.send("Calculating ping...")
        print(message.created_at)

        delta = (message.created_at - ctx.message.created_at).microseconds / 1000

        fmt = f"\U0001F493 **{latency:.2f}ms**\n" \
              f"\U00002194\U0000FE0F **{delta}ms**\n\n" \
              f"These values are only indicative in nature."

        await message.edit(content=fmt)


def setup(bot: commands.Bot):
    bot.add_cog(PhotonCog(bot))
