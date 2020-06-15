import textwrap

import discord
import humanize
import psutil
from discord.ext import commands, tasks

import config
from bot import Photon


class PhotonCog(commands.Cog, name="Photon"):
    """Find information related to Photon."""

    def __init__(self, bot: Photon):
        self.bot = bot
        self.process = psutil.Process()
        self.discord_bot_list.start()
        self.iterations = 0

    def cog_unload(self):
        self.discord_bot_list.cancel()

    async def cog_command_error(self, ctx, error):
        """Mini error handler for this cog."""

        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send("Please provide a valid prefix string.")
        else:
            self.bot.photon_log.error(
                f"[ERROR] Command: {ctx.command.name}, Exception: {error}.")

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
        unique_users = len(self.bot.users)

        # As a prerequisite for building the embed.
        desc = """Photon is a multipurpose Discord bot that aims to be user friendly and fast.
                  It is **open sourced** under the **MIT license**.
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

    @commands.group(name="welcome")
    @commands.has_guild_permissions(ban_members=True)
    @commands.cooldown(1, 10.0, commands.BucketType.guild)
    async def _welcome(self, ctx: commands.Context):
        """Subcommands to enable or disable welcome and leave messages.

        When used without a subcommand, this command shows the current status
        of the welcome and leave messages. That is if they are enabled it will
        show the channel in which they are enabled and if they are disabled it
        will show that they are disabled."""
        if ctx.invoked_subcommand is None and ctx.subcommand_passed is None:
            channel_id = await self.bot.database.get_welcome_channel(ctx.guild)
            if channel_id is None:
                return await ctx.send("Welcome and Leave messages are disabled in this server.")

            channel = self.bot.get_channel(channel_id)
            if channel is None:
                return await ctx.send("Welcome and Leave messages are disabled in this server.")

            await ctx.send(
                f"Welcome and leave messages are currently enabled in {channel.mention}.")
        elif ctx.invoked_subcommand is None and ctx.subcommand_passed is not None:
            return await ctx.send("That is not a valid subcommand!")

    @_welcome.command(name="set")
    @commands.has_guild_permissions(ban_members=True)
    @commands.cooldown(1, 60.0, commands.BucketType.guild)
    async def _welcome_set(self, ctx: commands.Context):
        """Set the current channel as the welcome/leave channel."""

        await self.bot.database.update_welcome_channel(ctx.guild.id, ctx.channel.id)
        await ctx.send("The current channel was set as the welcome/leave channel.")

    @_welcome.command(name="disable")
    @commands.has_guild_permissions(ban_members=True)
    @commands.cooldown(1, 60.0, commands.BucketType.guild)
    async def _welcome_disable(self, ctx: commands.Context):
        """Disables the welcome and leave messages."""

        await self.bot.database.update_welcome_channel(ctx.guild.id, None)
        await ctx.send("Welcome and Leave messages are now disabled.")

    @commands.command(name="prefix")
    @commands.has_guild_permissions(ban_members=True)
    @commands.cooldown(1, 120.0, commands.BucketType.guild)
    async def _prefix(self, ctx: commands.Context, *, prefix: str):
        """Change the prefix to your liking."""

        # Check if prefix is very large.
        if len(prefix) > 5:
            return await ctx.send("The prefix can only be five characters long.")

        # Update the prefix
        await self.bot.database.update_prefix(ctx.guild.id, prefix)

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

        delta = (message.created_at -
                 ctx.message.created_at).microseconds / 1000

        fmt = f"\U0001F493 **{latency:.2f}ms**\n" \
              f"\U00002194\U0000FE0F **{delta}ms**\n\n" \
              f"These values are only suggestive in nature."

        embed = discord.Embed(title="\U0001F3D3 Pong!",
                              description=fmt,
                              colour=discord.Colour.dark_teal())

        embed.set_footer(text=f"Requested by {ctx.author.name}.",
                         icon_url=ctx.author.avatar_url)

        await message.edit(content="", embed=embed)

    @tasks.loop(minutes=15.0)
    async def discord_bot_list(self):
        """Posts the bot statistics to DBL fifteen minutes."""

        self.bot.photon_log.info("Trying to post statistics to DBL.")

        try:
            api_key = config.bot_lists["dbl"]
        except Exception:
            return

        client_id = self.bot.user.id
        api_url = f"https://discordbotlist.com/api/v1/bots/{client_id}/stats"

        params = {
            "users": len(self.bot.users),
            "guilds": len(self.bot.guilds)
        }

        headers = {
            "Authorization": api_key
        }

        async with self.web.post(api_url, params=params, headers=headers) as resp:
            if resp.status != 200:
                self.bot.photon_log.info(
                    "Encountered API error while posting to stats to DBL.")
            else:
                self.bot.photon_log.info("Posted stats to DBL.")
        
        self.iterations += 1


def setup(bot: Photon):
    bot.add_cog(PhotonCog(bot))
