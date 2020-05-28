import asyncio

import discord
from discord.ext import commands

from bot import Photon
# pylint: disable=import-error
from structs import ttc


class Fun(commands.Cog):
    """Commands related to enterainment."""

    def __init__(self, bot: Photon):
        self.bot = bot
        self.sessions = set()

    async def cog_command_error(self, ctx, error):
        """A mini error handler for this cog."""

        if isinstance(error, commands.BadArgument):
            return await ctx.send("Could not find the specified user.")
        elif isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(
                f"Please specify the **{error.param.name}** parameter.")
        else:
            self.bot.photon_log.error(
                f"[ERROR] Command: {ctx.command.name}, Exception: {error}.")

    @commands.command(name="ttc", aliases=["tictactoe"])
    async def _tictactoe(self, ctx, opponent: discord.Member = None):
        """Play a game of Tic-Tac-toe with your friend."""

        if ctx.channel.id in self.sessions:
            return await ctx.send(
                "There is already a game in progress in this channel.")

        if opponent is not None:

            if opponent.bot or opponent == ctx.author:
                return

            def check(m):
                cond = m.content.startswith("accept")
                return m.channel == ctx.channel and m.author == opponent and cond

            def check_first_player(m):
                try:
                    num = int(m.content)
                except ValueError:
                    return False
                cond = True if num <= 9 and num >= 0 else False
                return m.channel == ctx.channel and m.author == ctx.author and cond

            def check_second_player(m):
                try:
                    num = int(m.content)
                except ValueError:
                    return False
                cond = True if num <= 9 and num >= 0 else False
                return m.channel == ctx.channel and m.author == opponent and cond

            fmt = f"{opponent.mention}, **{ctx.author.name}** has " \
                "invited you to a game of Tic Tac Toe, \n" \
                "Type `accept` in the chat to start the game!"

            await ctx.send(fmt)
            try:
                msg = await self.bot.wait_for("message", check=check, timeout=60.0)
            except asyncio.TimeoutError:
                return await ctx.send(
                    "The opponent did not respond. The game will not start.")
            self.sessions.add(ctx.channel.id)
            board = ttc.TicTacToe()
            board_msg = await ctx.send(board.render_board())
            while True:
                try:
                    msg = await self.bot.wait_for(
                        "message", check=check_first_player, timeout=30.0)
                except asyncio.TimeoutError:
                    return await ctx.send(
                        "The challenger was inactive for thirty seconds.\n"
                        f"{opponent.mention} won!")

                is_legal = board.make_move(int(msg.content), ttc.Player.FIRST)
                if not is_legal:
                    return await ctx.send("Illegal Move! Stopping the game.")
                await msg.delete()
                await board_msg.edit(content=board.render_board())
                game_over = board.check_game_over()

                if game_over == ttc.Player.NONE:
                    return await ctx.send("Its a draw!")
                elif game_over == ttc.Player.FIRST:
                    return await ctx.send(f"{ctx.author.mention} won!")

                try:
                    msg = await self.bot.wait_for(
                        "message", check=check_second_player, timeout=30.0)
                except asyncio.TimeoutError:
                    return await ctx.send(
                        "The challenger was inactive for thirty seconds.\n"
                        f"{ctx.author.mention} won!")

                is_legal = board.make_move(int(msg.content), ttc.Player.SECOND)
                if not is_legal:
                    return await ctx.send("Illegal move! Stopping the game.")
                await msg.delete()
                await board_msg.edit(content=board.render_board())
                game_over = board.check_game_over()

                if game_over == ttc.Player.NONE:
                    return await ctx.send("Its a draw!")
                elif game_over == ttc.Player.SECOND:
                    return await ctx.send(f"{opponent.mention} won!")
        else:

            def check_author(m):
                try:
                    num = int(m.content)
                except ValueError:
                    return False
                cond = True if num <= 9 and num >= 0 else False
                return m.channel == ctx.channel and m.author == ctx.author and cond

            board = ttc.TicTacToe()
            board_msg = await ctx.send(board.render_board())
            self.sessions.add(ctx.channel.id)
            while True:
                try:
                    msg = await self.bot.wait_for(
                        "message", check=check_author, timeout=30.0)
                except asyncio.TimeoutError:
                    return await ctx.send(
                        "You were inactive for thirty seconds.\n"
                        "The Computer wins!")

                is_legal = board.make_move(int(msg.content), ttc.Player.FIRST)
                if not is_legal:
                    return await ctx.send("Illegal Move! Stopping the game.")

                await msg.delete()
                await board_msg.edit(content=board.render_board())
                game_over = board.check_game_over()

                if game_over == ttc.Player.NONE:
                    return await ctx.send("Its a draw!")

                # this will NEVER OCCUR! The AI is better always.
                # there can be a draw but never a win for the player.
                elif game_over == ttc.Player.FIRST:
                    return await ctx.send("You won!")

                board.make_move_AI()
                await board_msg.edit(content=board.render_board())
                game_over = board.check_game_over()

                if game_over == ttc.Player.NONE:
                    return await ctx.send("Its a draw!")
                elif game_over == ttc.Player.SECOND:
                    return await ctx.send("The Computer won!")

    @_tictactoe.after_invoke
    async def _cleanup_session_set(self, ctx):
        """Cleans up the session set after the game is done."""
        if ctx.channel.id in self.sessions:
            self.sessions.remove(ctx.channel.id)


def setup(bot: Photon):
    bot.add_cog(Fun(bot))
