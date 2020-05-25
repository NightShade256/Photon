import asyncio
import datetime
import re
import time

import discord
import humanize
from discord.ext import commands

from structs import hiddenpoll

RTIME: re.Pattern = re.compile(
    r"^((?:(2[0-3]|[01]?[0-9]):)?(?:([0-5]?[0-9])))$")


class Polls(commands.Cog):
    """Create polls in Discord. [GUILD ADMIN ONLY]"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.hidden_polls = {}
        self.tasks = {}

    async def cog_command_error(self, ctx: commands.Context, error):
        """A mini error handler for this cog."""
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(f"Please specify the **{error.param.name}** parameter.")
        elif isinstance(error, commands.BadArgument):
            if ctx.command.name == "poll":
                return await ctx.send(
                    "Please specify a valid channel in which the poll should be published.")
            else:
                return await ctx.send("The argument provided is of an invalid type.")
        else:
            self.bot.photon_log.error(
                f"[ERROR] Command: {ctx.command.name}, Exception: {error}.")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Hidden poll hook handler."""

        if payload.member.bot or payload.message_id not in self.hidden_polls:
            return

        coro = (self.hidden_polls[payload.message_id]).event_hook
        await coro(payload)

    async def poll_timeout(self, poll_id: int, time_limit: int):
        """Task that cancels the poll on timeout."""

        await asyncio.sleep(time_limit)
        ctr: hiddenpoll.PollController = self.hidden_polls[poll_id]
        await ctr.finish_poll()
        await ctr.message.clear_reactions()
        self.tasks.pop(poll_id)
        self.hidden_polls.pop(poll_id)
        await self.export_to_database(datetime.datetime.utcnow(), ctr)

    async def export_to_database(self, end: datetime.datetime, ctr: hiddenpoll.PollController):
        """Export the finished poll's votes and other stats to the database."""

        query = "INSERT INTO polls VALUES ($1, $2, $3, $4, $5, $6, $7);"

        votes = []
        options = []
        for emoji, option in ctr.options:
            votes.append(ctr.votes.retrieve(emoji))
            options.append(option)

        async with self.bot.database.acquire() as con:
            async with con.transaction():
                await con.execute(query,
                                  ctr.message.id,
                                  ctr.ctx.guild.id,
                                  ctr.question,
                                  ctr.start,
                                  end,
                                  votes,
                                  options)

    @commands.command(name="poll")
    @commands.has_guild_permissions(ban_members=True)
    @commands.cooldown(1, 120.0, commands.BucketType.guild)
    async def _poll(self, ctx, channel: discord.TextChannel, *, question: str):
        """Create a poll.

        The poll is published in the channel provided by the user.
        The maximum options permissible in a poll is five."""

        info = await ctx.send(
            "Specify the options one by one. Time limit per option is **1 minute**.")

        # Messages to delete before publishing the poll.
        messages = [info]
        # Options of the poll.
        options = []

        # A check for the message event.
        # It checks if a message is written by the invoker of the command or not.
        def check(m: discord.Message):
            return m.author == ctx.author and m.channel == ctx.channel and len(m.content) < 80

        for i in range(5):
            info2 = await ctx.send(
                "You can specify a option or use `<publish>` to publish the poll.")

            # Wait for a message that satisfies the above check.
            try:
                option: discord.Message = await self.bot.wait_for(
                    event='message', check=check, timeout=60.0)
            except asyncio.TimeoutError:

                # If options is empty, we can't publish the poll, hence we abort the process.
                if not options:
                    await ctx.channel.delete_messages(messages)
                    return await ctx.send(
                        "The poll is being discarded due to inactivity for last one minute.")

                break

            if option.clean_content.startswith('<publish>'):
                messages.extend((option, info2))
                break

            options.append((chr(0x1f1e6 + i), option.clean_content))
            opt_add = await ctx.send("Option added.")
            messages.extend((opt_add, option, info2))

        # Try to delete the messages sent by the user to construct the poll.
        try:
            await ctx.channel.delete_messages(messages)
        except Exception:
            pass

        description = '\n\n'.join(
            [f'{emoji} {option}' for emoji, option in options])

        # Create a new embed for our poll.
        poll_embed = discord.Embed(
            title=question, description=description, colour=0x7A25A8)
        poll_embed.set_footer(
            text=f"Asked by {ctx.author.name}.", icon_url=ctx.author.avatar_url)

        # Send the embed in the channel requested by the user.
        poll_msg: discord.Message = await channel.send(embed=poll_embed)

        # Add the reactions to the message.
        for emoji, _ in options:
            await poll_msg.add_reaction(emoji)

        await ctx.send("Poll successfully created.", delete_after=5.0)

    @commands.group(name="apoll")
    async def _apoll(self, ctx: commands.Context):
        """Group of commands to create and view anonymous polls.

        You the command without any subcommand to view ongoing anonymous polls.
        Use the subcommand history to view previous anonymous polls."""

        if ctx.invoked_subcommand is None:
            ongoing_apolls = [poll for poll in self.hidden_polls.values(
            ) if poll.ctx.guild.id == ctx.guild.id]
            if not ongoing_apolls:
                return await ctx.send("There are no ongoing anonymous polls, "
                                      "you can create one through "
                                      f"`{ctx.prefix}apoll new`.")

            fmt = [
                f"**[{ongoing.message.id}]** `{ongoing.question}`" for ongoing in ongoing_apolls]
            fmt = "\n".join(fmt)

            embed = discord.Embed(title="Ongoing Anonymous Polls",
                                  description=fmt,
                                  colour=discord.Colour.dark_teal())

            embed.set_footer(text=f"Requested by {ctx.author.name}.",
                             icon_url=ctx.author.avatar_url)

            await ctx.send(embed=embed)

    @_apoll.command(name="new")
    @commands.has_guild_permissions(ban_members=True)
    @commands.cooldown(1, 600.0, commands.BucketType.guild)
    async def _apoll_new(self, ctx, time_limit, channel: discord.TextChannel, *, question: str):
        """Create a new anonymous poll.

        The format for time limit is HH:MM
        where HH is for hours and MM is for minutes respectively.
        You can drop the HH part if you want a short poll.

        A poll can only be held for a maximum of 1 day."""

        if not RTIME.match(time_limit):
            return await ctx.send("Invalid time format used.")

        time_fmt_dict = {
            0: "%M",
            1: "%H:%M"
        }

        fmt = time_fmt_dict[time_limit.count(":")]
        parsed_time = time.strptime(time_limit, fmt)
        total_seconds = (parsed_time.tm_min * 60) + \
            (parsed_time.tm_hour * 3600)
        info = await ctx.send(
            "Specify the options one by one. Time limit per option is **1 minute**.")

        # Messages to delete before publishing the poll.
        messages = [info]
        # Options of the poll.
        options = []

        # A check for the message event.
        # It checks if a message is written by the invoker of the command or not.
        def check(m: discord.Message):
            return m.author == ctx.author and m.channel == ctx.channel and len(m.content) < 80

        for i in range(5):
            info2 = await ctx.send(
                "You can specify a option or use `<publish>` to publish the poll.")

            # Wait for a message that satisfies the above check.
            try:
                option: discord.Message = await self.bot.wait_for(
                    event='message', check=check, timeout=60.0)
            except asyncio.TimeoutError:

                # If options is empty, we can't publish the poll, hence we abort the process.
                if not options:
                    await ctx.channel.delete_messages(messages)
                    return await ctx.send(
                        "The poll is being discarded due to inactivity for last one minute.")

                break

            if option.clean_content.startswith("<publish>"):
                messages.extend((option, info2))
                break

            options.append((chr(0x1f1e6 + i), option.clean_content))
            opt_add = await ctx.send("Option added.")
            messages.extend((opt_add, option, info2))

        # Try to delete the messages sent by the user to construct the poll.
        try:
            await ctx.channel.delete_messages(messages)
        except Exception:
            pass
        poll_ctr = hiddenpoll.PollController(question, options, ctx)
        message_id = await poll_ctr.publish(channel, total_seconds)
        self.hidden_polls[message_id] = poll_ctr
        self.tasks[message_id] = self.bot.loop.create_task(
            self.poll_timeout(message_id, total_seconds))
        await ctx.send("Poll successfully created.", delete_after=5.0)

    @_apoll.command(name="view")
    @commands.has_guild_permissions(ban_members=True)
    @commands.cooldown(1, 60.0, commands.BucketType.guild)
    async def _apoll_view(self, ctx, poll_id: int):
        """View the results of an ongoing anonymous poll.

        The poll_id can be gotten from using the
        apoll command without any subcommands."""

        if poll_id not in self.hidden_polls:
            return await ctx.send("No poll with the specified poll ID found.")

        poll_ctr: hiddenpoll.PollController = self.hidden_polls[poll_id]

        if poll_ctr.ctx.guild.id != ctx.guild.id:
            return

        result_embed = poll_ctr.construct_result_embed()
        result_embed.set_footer(text=f"Requested by {ctx.author.name}.",
                                icon_url=ctx.author.avatar_url)

        await ctx.send(embed=result_embed)

    @_apoll.command(name="stop")
    @commands.has_guild_permissions(ban_members=True)
    @commands.cooldown(1, 60.0, commands.BucketType.guild)
    async def _apoll_stop(self, ctx, poll_id: int):
        """Stops an ongoing poll prematurely."""

        if poll_id not in self.hidden_polls and poll_id not in self.tasks:
            return await ctx.send("No poll with the specified poll ID found.")

        poll_ctr: hiddenpoll.PollController = self.hidden_polls[poll_id]

        if poll_ctr.ctx.guild.id != ctx.guild.id:
            return
        await poll_ctr.finish_poll()
        await poll_ctr.message.clear_reactions()
        self.hidden_polls.pop(poll_id)
        task: asyncio.Task = self.tasks.pop(poll_id)
        task.cancel()
        await self.export_to_database(datetime.datetime.utcnow(), poll_ctr)
        await ctx.send("The anonymous poll has been prematurely ended.")

    @_apoll.command(name="history")
    @commands.has_guild_permissions(ban_members=True)
    @commands.cooldown(1, 20.0, commands.BucketType.guild)
    async def _apoll_history(self, ctx, poll_id: int = None):
        """Fetch information about past anonymous polls.

        If this command is called without any arguments then
        a list of past polls is fetched.

        If this command is called with a poll ID then the
        results of the poll with that specific poll ID
        are fetched.

        In a future update, polls older than 2 months will
        be automatically be deleted from the database."""

        if poll_id is None:
            query = "SELECT * FROM polls WHERE guild_id = $1;"
            async with self.bot.database.acquire() as con:
                async with con.transaction():
                    past_polls = await con.fetch(query, ctx.guild.id)

            if not past_polls:
                return await ctx.send(
                    "There seem to be **no** past anonymous polls in this server.")

            fmt = []
            for poll in past_polls:
                fmt.append(f"**[{poll['poll_id']}]** `{poll['question']}`")
            fmt = "\n".join(fmt)
            embed = discord.Embed(title="Past Anonymous Polls",
                                  description=fmt,
                                  colour=discord.Colour.dark_teal())

            return await ctx.send(embed=embed)

        query = "SELECT * FROM polls WHERE poll_id = $1 AND guild_id = $2;"
        async with self.bot.database.acquire() as con:
            async with con.transaction():
                past_poll = await con.fetchrow(query, poll_id, ctx.guild.id)

        if past_poll is None:
            return await ctx.send("There was not past poll with the above poll ID in this guild.")

        fmt = []
        counter = 0x1f1e6

        for amt, option in zip(past_poll['votes'], past_poll['options']):
            fmt.append(f"{chr(counter)} `{option}` **{amt}**")
            counter += 1
        fmt = "\n\n".join(fmt)

        embed = discord.Embed(title=past_poll["question"],
                              description=fmt,
                              colour=discord.Colour.dark_teal())

        embed.set_footer(text=f"Requested by {ctx.author.name}.",
                         icon_url=ctx.author.avatar_url)

        embed.set_author(name=f"Poll ID: {poll_id}")
        end = humanize.naturaldate(past_poll['end_time'])
        embed.add_field(name="Ended", value=end.title())
        await ctx.send(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Polls(bot))
