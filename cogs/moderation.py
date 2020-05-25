import discord
from discord.ext import commands


class Moderation(commands.Cog):
    """Commands relating to server moderation."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_command_error(self, ctx, error):
        """Mini error handler for this cog."""
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(f"Please specify the **{error.param.name}** parameter.")
        elif isinstance(error, commands.BadArgument):
            if ctx.command.name in ("ban", "kick", "unban"):
                return await ctx.send("Could not find the user.")
            else:
                return await ctx.send("Please provide a valid amount of messages to delete.")
        else:
            self.bot.photon_log.error(f"[ERROR] Command: {ctx.command.name}, Exception: {error}.")

    @commands.command(name="prune", aliases=["purge"])
    @commands.has_guild_permissions(manage_messages=True, read_message_history=True)
    async def _prune(self, ctx, amount: int):
        """Delete specifed amount of messages in a channel.

        Actually the command in certain cases is NOT able to delete the amount
        of messages specifed, (because the amount is too large, etc) but
        instead deletes the maximum it can under that limit."""

        try:
            messages = await ctx.channel.purge(limit=(amount+1))
        except (discord.Forbidden, discord.HTTPException):
            return await ctx.send(
                "The bot doesn't have proper permissions or there was HTTP request failure."
            )
        await ctx.send(
            f"\N{WASTEBASKET} **{len(messages) - 1} messages** deleted from <#{ctx.channel.id}>.",
            delete_after=5.0
        )

    @commands.command(name="kick")
    @commands.has_guild_permissions(kick_members=True)
    async def _kick(self, ctx, user: discord.Member, *, reason: str = None):
        """Kicks the specified user from the server."""

        try:
            await user.kick(reason=reason)
        except (discord.Forbidden, discord.HTTPException):
            return await ctx.send("The bot couldn't kick the user.")
        await ctx.send("The user was successfully kicked.")

    @commands.command(name="ban")
    @commands.has_guild_permissions(ban_members=True)
    async def _ban(self, ctx, user: discord.Member, days: int = 1, *, reason: str = None):
        """Bans the specified user from the server."""

        try:
            await user.ban(reason=reason, delete_message_days=days)
        except (discord.Forbidden, discord.HTTPException):
            return await ctx.send("The bot couldn't ban the user.")
        await ctx.send("The user was successfully banned.")

    @commands.command(name="unban")
    @commands.has_guild_permissions(ban_members=True)
    async def _unban(self, ctx, user_id: int, *, reason: str = None):
        """Unbans the specified user from the server."""

        try:
            bans = await ctx.guild.bans()
            user = [member for member in bans if member.user.id == user_id]
            if not user:
                return await ctx.send("Could not find a user with that ID that is banned.")
            await ctx.guild.unban(user[0].user, reason=reason)
        except (discord.Forbidden, discord.HTTPException):
            return await ctx.send("The bot couldn't unban the user.")
        await ctx.send("The user was successfully unbanned.")

    @commands.command(name="softban")
    @commands.has_guild_permissions(ban_members=True)
    async def _softban(self, ctx, user: discord.Member, *, reason: str = None):
        """Softbans a specified user.

        This command essentially bans a user and then unbans him immediately,
        deleting his messages from the previous seven days in the process."""

        try:
            await ctx.guild.ban(user, reason=reason, delete_message_days=7)
            await user.unban(reason=f"[PHOTON] Softban command - {ctx.author.name}")
        except (discord.Forbidden, discord.HTTPException):
            return await ctx.send("The bot couldn't softban the user.")
        await ctx.send("The user was successfully softbanned.")


def setup(bot: commands.Bot):
    bot.add_cog(Moderation(bot))
