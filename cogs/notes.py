import asyncio
import io

import discord
from discord.ext import commands


class Notes(commands.Cog):
    """
    Commands that allow users to take down notes.
    Notes can be retrieved by a user in any server.
    A user can have 125 notes.
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="add")
    async def _nadd(self, ctx, *, title: str = None):
        """Adds a note under the user's ID to the database."""
        if title is None:
            return await ctx.send("Please specify a title during the invocation of the command.")
        if len(title) > 40:
            return await ctx.send("The length of the title is too long. Max Limit: 40 chars.")

        limit_query = f"SELECT note_id FROM notes WHERE user_id = $1;"
        async with self.bot.database.acquire() as con:
            notes = await con.fetch(limit_query, ctx.author.id)

        if len(notes) == 125:
            return await ctx.send("Users can only create **125** notes.")
        
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
        query = "INSERT INTO notes VALUES (DEFAULT, $1, $2, $3)"
        async with self.bot.database.acquire() as con:
            async with con.transaction():
                await con.execute(query, ctx.author.id, title, content)
        self.bot.photon_log.info(
            f"[NOTE CREATE] USER_ID {ctx.author.id} USER_NAME: {ctx.author.name}")
        await ctx.send("Note successfully added.")

    @commands.command(name="list")
    async def _nlist(self, ctx, page: int = 1):
        """Lists the notes of the user invoking the command. Specify a page number to open that page."""
        query = "SELECT note_id, title FROM notes WHERE user_id = $1"
        async with self.bot.database.acquire() as con:
            notes = await con.fetch(query, ctx.author.id)
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
                    embed = discord.Embed(
                        title=f"Notes of {ctx.author.name} (Page No. {page})", description=body, colour=0xD9771C)
                    pages.append(embed)
                    break
            if len(notes) == 0:
                break
        if len(pages) < page:
            return await ctx.send(f"Page {page} does not exist.")
        await ctx.send(embed=pages[page - 1])

    @commands.command(name="delete")
    async def _ndelete(self, ctx, note_id: int = None):
        """Deletes the note belonging to the user with the specified note ID."""
        query = "DELETE FROM notes WHERE user_id = $1 AND note_id = $2 RETURNING title;"
        if note_id is None:
            return await ctx.send("Please specify the note ID of the note you want to delete.")
        async with self.bot.database.acquire() as con:
            async with con.transaction():
                row = await con.fetchrow(query, ctx.author.id, note_id)
        if row is None:
            return await ctx.send("No note with the specified note ID was found. Please try again.")
        self.bot.photon_log.info(
            f"[NOTE DELETE] NOTE_ID: {note_id} USER_ID {ctx.author.id} USER_NAME: {ctx.author.name}")
        await ctx.send(f"Note with **TITLE: {row['title']}** and **ID: {note_id}** was successfully removed.")

    @commands.command(name="view")
    async def _nview(self, ctx, note_id: int = None):
        """View the note belonging to the user with the specified note ID."""
        query = """SELECT content, title FROM notes WHERE user_id = $1 AND note_id = $2"""
        async with self.bot.database.acquire() as con:
            row = await con.fetchrow(query, ctx.author.id, note_id)
        if row is None:
            return await ctx.send("No note with the specified note ID was found. Please try again.")
        embed = discord.Embed(
            title=f"[{note_id}] {row['title']}", description=row["content"], colour=0xD9771C)
        embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    @commands.command(name="file")
    async def _nfile(self, ctx, note_id: int = None):
        """Converts the note into a .txt file which can then be downloaded."""
        query = """SELECT content, title FROM notes WHERE user_id = $1 AND note_id = $2"""
        async with self.bot.database.acquire() as con:
            row = await con.fetchrow(query, ctx.author.id, note_id)
        if row is None:
            return await ctx.send("No note with the specified note ID was found. Please try again.")
        stream = io.BytesIO(bytes(row["content"], "utf-8"))
        file = discord.File(stream, f"{row['title']}.txt")
        await ctx.send(file=file)
        self.bot.photon_log.info(
            f"[NOTE UPLOAD] NOTE_ID: {note_id} USER_ID: {ctx.author.id} USER_NAME: {ctx.author.name}")


def setup(bot):
    bot.add_cog(Notes(bot))
