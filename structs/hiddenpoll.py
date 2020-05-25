import asyncio
import collections
import datetime

import discord
from discord.ext import commands


class VotesCounter:

    def __init__(self, options: list):
        self._votes = collections.Counter()
        for option in options:
            self._votes[option] = 0
        self._ledger = []

    def increment(self, option: str, user_id: int) -> None:
        """Increment the vote count for the given option by one."""
        if user_id in self._ledger:
            return
        self._votes[option] += 1
        self._ledger.append(user_id)

    def retrieve(self, option: str) -> int:
        """Retrieve the vote count for the given option."""
        return self._votes[option]


class PollController:
    """A anonymous poll controller.

    Arguments
    ----------
    question : str
        The poll question.
    options : list
        The list of options.
    """

    def __init__(self, question: str, options: list, ctx: commands.Context):
        self.question = question
        self.options = options
        self.exempted = [emoji for emoji, _ in options]
        self.ctx = ctx
        self.embed: discord.Embed = None
        self.votes = VotesCounter(self.exempted)
        self._lock = asyncio.Lock()
        self.message: discord.Message = None
        self.start: datetime.datetime = None

    def construct_embed(self, time_limit) -> None:
        """Method that constructs the embed."""

        description = "\n\n".join(
            [f"{emoji} {option}" for emoji, option in self.options])

        temp_embed = discord.Embed(title=self.question,
                                   description=description,
                                   colour=discord.Colour.dark_green())

        temp_embed.set_footer(text=f"Asked by {self.ctx.author.name}.",
                              icon_url=self.ctx.author.avatar_url)

        temp_embed.add_field(name="**Status**", value="Ongoing")

        self.start = datetime.datetime.utcnow()
        etime = self.start + datetime.timedelta(seconds=time_limit)
        fmt_time = etime.strftime("%d/%m/%Y %H:%M:%S")
        temp_embed.add_field(name="**Ending at**", value=fmt_time + " UTC")
        self.embed = temp_embed

    def construct_result_embed(self) -> discord.Embed:
        """Method that constructs the result embed."""
        fmt = [f"**{self.question}**"]
        for emoji, option in self.options:
            amt = self.votes.retrieve(emoji)
            fmt.append(f"{emoji} `{option}` **{amt}**")

        fmt = "\n\n".join(fmt)

        embed = discord.Embed(title="Results",
                              description=fmt,
                              colour=discord.Colour.dark_teal())

        embed.set_author(name=f"Poll ID: {self.message.id}")

        embed.set_footer(text=f"Asked by {self.ctx.author.name}.",
                         icon_url=self.ctx.author.avatar_url)

        return embed

    async def finish_poll(self) -> None:
        """Updates the poll embed on finish."""

        result = self.construct_result_embed()
        self.embed = result
        await self.message.edit(embed=self.embed)

    async def publish(self, channel: discord.TextChannel, time_limit: int) -> int:
        """Publish the poll to the given channel."""

        if self.embed is None:
            self.construct_embed(time_limit)
        message: discord.Message = await channel.send(embed=self.embed)
        for emoji, _ in self.options:
            await message.add_reaction(emoji)

        self.message = message
        return message.id

    async def event_hook(self, payload: discord.RawReactionActionEvent):
        """Hook that gets called when a reaction is added on the poll."""

        if payload.emoji.is_custom_emoji():
            return await self.message.clear_reaction(payload.emoji)
        elif payload.emoji.name not in self.exempted:
            return await self.message.clear_reaction(payload.emoji)
        async with self._lock:
            self.votes.increment(payload.emoji.name, payload.member.id)
        await self.message.remove_reaction(payload.emoji, payload.member)
