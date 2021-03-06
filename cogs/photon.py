import datetime
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
        uptime = humanize.naturaldelta(datetime.datetime.utcnow() - self.bot.start_time)

        # Building the embed.
        embed = discord.Embed(title="About Photon", description=desc,
                              colour=discord.Color.dark_teal())
        embed.set_thumbnail(url=url)
        resource_usage = f'{memory_usage}\n{cpu_usage:.2f}% CPU'
        embed.add_field(name='**• Resource Usage:**', value=resource_usage)
        embed.add_field(name='**• Server Count:**', value=guilds)
        embed.add_field(name='**• Unique Users:**', value=unique_users)
        embed.add_field(name="**• Commands Executed:**", value=self.bot.commands_completed)
        embed.add_field(name="**• Uptime:**", value=uptime)
        embed.add_field(name="**• Bot Version:**", value=self.bot.bot_version)
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
    @commands.cooldown(1, 30.0, commands.BucketType.guild)
    async def _welcome_set(self, ctx: commands.Context):
        """Set the current channel as the welcome/leave channel."""

        await self.bot.database.update_welcome_channel(ctx.guild.id, ctx.channel.id)
        await ctx.send("The current channel was set as the welcome/leave channel.")

    @_welcome.command(name="disable")
    @commands.has_guild_permissions(ban_members=True)
    @commands.cooldown(1, 30.0, commands.BucketType.guild)
    async def _welcome_disable(self, ctx: commands.Context):
        """Disables the welcome and leave messages."""

        await self.bot.database.update_welcome_channel(ctx.guild.id, None)
        await ctx.send("Welcome and Leave messages are now disabled.")

    @commands.command(name="prefix")
    @commands.has_guild_permissions(ban_members=True)
    @commands.cooldown(1, 60.0, commands.BucketType.guild)
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

    @commands.command(name="invite")
    async def _invite(self, ctx: commands.Context):
        """Get the invite link for the bot."""
        app_info = await self.bot.application_info()
        client_id = app_info.id

        fmt = "**You can invite me by clicking [here](" \
              f"https://discord.com/oauth2/authorize?client_id={client_id}" \
              "&permissions=1341652806&scope=bot).**"

        embed = discord.Embed(description=fmt, colour=discord.Colour.dark_teal())
        embed.set_footer(text=f"Requested by {ctx.author.name}.", icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    @commands.command(name="vote")
    async def _vote(self, ctx: commands.Context):
        """Voting information for the bot."""
        app_info = await self.bot.application_info()
        client_id = app_info.id

        fmt = "You can show your support for the bot by voting through the following links:\n\n" \
              f"**top.gg**:\nhttps://top.gg/bot/{client_id}\n\n" \
              f"**discordbotlist**:\nhttps://discordbotlist.com/bots/photon"

        embed = discord.Embed(description=fmt, colour=discord.Colour.dark_teal())
        embed.set_footer(text=f"Requested by {ctx.author.name}.", icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    @tasks.loop(minutes=15.0)
    async def discord_bot_list(self):
        """Posts the bot statistics to DBL fifteen minutes."""

        await self.bot.wait_until_ready()
        self.bot.photon_log.info("Trying to post statistics to DBL.")

        try:
            api_key = config.bot_lists["dbl"]
        except Exception:
            return

        app_info = await self.bot.application_info()
        client_id = app_info.id
        api_url = f"https://discordbotlist.com/api/v1/bots/{client_id}/stats"

        payload = {
            "users": len(self.bot.users),
            "guilds": len(self.bot.guilds)
        }

        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json"
        }

        async with self.bot.web.post(api_url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                self.bot.photon_log.info(
                    "Encountered API error while posting to stats to DBL.")
            else:
                self.bot.photon_log.info("Posted stats to DBL.")

        self.iterations += 1


def setup(bot: Photon):
    bot.add_cog(PhotonCog(bot))
