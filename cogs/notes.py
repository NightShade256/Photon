import asyncio
import io

import discord
from discord.ext import commands
from bot import Photon


class Notes(commands.Cog):
    """
    Commands that allow users to take down notes.
    Notes can be retrieved by a user in any server.
    A user can have 125 notes.
    """

    def __init__(self, bot: Photon):
        self.bot = bot

    async def cog_command_error(self, ctx, error):
        """Mini error handler for this cog."""

        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(f"Please provide the **{error.param.name}** parameter.")
        elif isinstance(error, commands.BadArgument):
            if ctx.command.name == "list":
                return await ctx.send("Please provide a valid integer only.")
            else:
                return await ctx.send("Please provide a valid Note ID.")
        else:
            self.bot.photon_log.error(f"[ERROR] Command: {ctx.command.name}, Exception: {error}.")

    @commands.command(name="add")
    @commands.cooldown(1, 15.0, commands.BucketType.user)
    async def _nadd(self, ctx, *, title: str):
        """Adds a note under the user's ID to the database."""

        if len(title) > 40:
            return await ctx.send("The length of the title is too long. Max Limit: 40 chars.")

        is_allowed = await self.bot.database.is_allowed_notes(ctx.author.id, False)

        if not is_allowed:
            return await ctx.send("Users can only create **50** notes.")

        await ctx.send("**Time Limit: 10 minutes, Character Limit: 2000 chars.**")
        await ctx.send("Enter content of the note below this message:")

        def check_add(m):
            return m.author == ctx.author

        try:
            msg = await self.bot.wait_for(
                "message", check=check_add, timeout=600.0)
        except asyncio.TimeoutError:
            return await ctx.send("Time limit of 10 minutes reached. Please try again.")

        content = str(msg.content)
        await self.bot.database.insert_note(title, content, ctx.author.id)
        await ctx.send("Note successfully added.")

    @commands.command(name="list")
    @commands.cooldown(1, 7.0, commands.BucketType.user)
    async def _nlist(self, ctx, page: int = 1):
        """Lists the notes of the user invoking the command.

        Specify a page number to open that page."""

        notes = await self.bot.database.fetch_notes(ctx.author.id)
        if len(notes) == 0:
            return await ctx.send("You have not created any notes.")
        page_trigger = 4000
        pages = []
        while True:
            body = ""
            for _ in range(len(notes)):
                body += f"• **[{notes[0]['note_id']}]** {notes[0]['title']}\n"
                notes.pop(0)
                if (len(body) > page_trigger) or (len(body) < page_trigger and len(notes) == 0):
                    embed = discord.Embed(title=f"Notes of {ctx.author.name} (Page No. {page})",
                                          description=body,
                                          colour=discord.Colour.dark_teal())
                    embed.set_footer(text=f"Requested by {ctx.author.name}.",
                                     icon_url=ctx.author.avatar_url)
                    pages.append(embed)
                    break
            if len(notes) == 0:
                break
        if len(pages) < page:
            return await ctx.send(f"Page {page} does not exist.")
        await ctx.send(embed=pages[page - 1])

    @commands.command(name="delete")
    @commands.cooldown(1, 15.0, commands.BucketType.user)
    async def _ndelete(self, ctx, note_id: int):
        """Deletes the note belonging to the user with the specified note ID."""

        title = await self.bot.database.delete_note(note_id, ctx.author.id)
        if title is None:
            return await ctx.send(
                "No note with the specified note ID was found. Please try again.")
        await ctx.send(
            f"Note with **Title:** `{title}` and **ID:** `{note_id}` was removed.")

    @commands.command(name="view")
    @commands.cooldown(1, 15.0, commands.BucketType.user)
    async def _nview(self, ctx, note_id: int):
        """View the note belonging to the user with the specified note ID."""

        row = await self.bot.database.fetch_note(ctx.author.id, note_id)
        if row is None:
            return await ctx.send(
                "No note with the specified note ID was found. Please try again.")
        embed = discord.Embed(title=f"[{note_id}] {row['title']}",
                              description=row["content"],
                              colour=discord.Colour.dark_teal())
        embed.set_footer(text=f"Requested by {ctx.author.name}.",
                         icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    @commands.command(name="file")
    @commands.cooldown(1, 15.0, commands.BucketType.user)
    async def _nfile(self, ctx, note_id: int):
        """Converts the note into a .txt file which can then be downloaded."""

        row = await self.bot.database.fetch_note(ctx.author.id, note_id)
        if row is None:
            return await ctx.send(
                "No note with the specified note ID was found. Please try again.")
        stream = io.BytesIO(bytes(row["content"], "utf-8"))
        file = discord.File(stream, f"{row['title']}.txt")
        await ctx.send(file=file)


def setup(bot: Photon):
    bot.add_cog(Notes(bot))
