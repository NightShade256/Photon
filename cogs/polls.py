import asyncio

import discord
from discord.ext import commands


class Polls(commands.Cog):
    """Create polls in Discord. [GUILD ADMIN ONLY]"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_command_error(self, ctx: commands.Context, error):
        """A mini error handler for this cog."""
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(f"Please specify the {error.param.name} parameter.")
        elif isinstance(error, commands.BadArgument):
            return await ctx.send(f"Please specify a valid channel in which the poll should be published.")

    @commands.command(name="poll")
    @commands.has_guild_permissions(ban_members=True)
    @commands.cooldown(1, 120.0, commands.BucketType.guild)
    async def _poll(self, ctx, channel: discord.TextChannel, *, question: str):
        """Creates a poll.

        The poll is published in the channel provided by the user.
        The maximum options permissible in a poll is five."""

        info = await ctx.send('Specify the options one by one. Time limit per option is **1 minute**.')

        # Messages to delete before publishing the poll.
        messages = [info]
        # Options of the poll.
        options = []

        # A check for the message event.
        # It checks if a message is written by the invoker of the command or not.
        def check(m: discord.Message):
            return m.author == ctx.author and m.channel == ctx.channel and len(m.content) < 80

        for i in range(5):
            info2 = await ctx.send('You can specify a option or use `<publish>` to publish the poll.')

            # Wait for a message that satisfies the above check.
            try:
                option: discord.Message = await self.bot.wait_for(event='message', check=check, timeout=60.0)
            except asyncio.TimeoutError:

                # If options is empty, we can't publish the poll, hence we abort the process.
                if not options:
                    await ctx.channel.delete_messages(messages)
                    return await ctx.send('The current poll is being discarded due to inactivity for last one minute.')

                break

            if option.clean_content.startswith(f'<publish>'):
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


def setup(bot: commands.Bot):
    bot.add_cog(Polls(bot))
