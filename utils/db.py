from datetime import datetime
from typing import Union

import asyncpg
import discord

from structs.hiddenpoll import PollController


class DatabaseHelper:
    def __init__(self, pool: asyncpg.pool.Pool):
        self.pool = pool

    async def ensure_tables(self) -> None:
        """Ensure that important tables are present.

        Current Tables: guild, polls, notes."""

        table_query = """
            CREATE TABLE IF NOT EXISTS guild(
                guild_id bigint PRIMARY KEY,
                prefix varchar(5) DEFAULT '&',
                welcome bigint
            );

            CREATE TABLE IF NOT EXISTS polls(
                poll_id bigint PRIMARY KEY,
                guild_id bigint,
                question varchar(2000),
                start_time timestamp with time zone,
                end_time timestamp with time zone,
                votes integer[],
                options varchar(2000)[]
            );

            CREATE TABLE IF NOT EXISTS notes(
                note_id bigserial PRIMARY KEY,
                user_id bigint,
                title varchar(40),
                content varchar(2000)
            );"""

        async with self.pool.acquire() as con:
            async with con.transaction():
                await con.execute(table_query)

    async def create_guild_entry(self, guild: discord.Guild) -> None:
        """Create a entry for a guild in the database."""

        query_stub = "INSERT INTO guild VALUES ($1, $2, $3);"

        async with self.pool.acquire() as con:
            async with con.transaction():
                await con.execute(query_stub, guild.id, "&", None)

    async def delete_guild_entry(self, guild: discord.Guild) -> None:
        """Delete a guild entry in the database."""

        query_stub = "DELETE FROM guild WHERE guild_id = $1;"

        async with self.pool.acquire() as con:
            async with con.transaction():
                await con.execute(query_stub, guild.id)

    async def get_welcome_channel(self, guild: discord.Guild) -> Union[int, None]:
        """Check if welcome/leave logging is enabled in the guild and return the channel id."""

        query_stub = "SELECT welcome FROM guild WHERE guild_id = $1;"

        async with self.pool.acquire() as con:
            async with con.transaction():
                row = await con.fetchrow(query_stub, guild.id)

        # If the guild entry is not present, silently ignore it.
        if row is None:
            return None

        return row["welcome"]

    async def update_welcome_channel(self, guild_id: int, channel_id: int) -> None:
        """Updates the welcome channel of a guild."""

        query_stub = "UPDATE guild SET welcome = $1 WHERE guild_id = $2;"

        async with self.pool.acquire() as con:
            async with con.transaction():
                await con.execute(query_stub, channel_id, guild_id)

    async def update_prefix(self, guild_id: int, prefix: str) -> None:
        """Updates the prefix of a guild."""

        query_stub = "UPDATE guild SET prefix = $1 WHERE guild_id = $2;"

        async with self.pool.acquire() as con:
            async with con.transaction():
                await con.execute(query_stub, prefix, guild_id)

    async def fetch_prefix(self, guild_id: int) -> str:
        """Fetches a prefix."""

        query_stub = "SELECT prefix FROM guild WHERE guild_id = $1;"

        async with self.pool.acquire() as con:
            row = await con.fetchrow(query_stub, guild_id)

        return row

    async def is_allowed_notes(self, user_id, is_premium) -> bool:
        """Check if the user is allowed to create to any more notes."""

        query_stub = "SELECT note_id FROM notes WHERE user_id = $1;"

        async with self.pool.acquire() as con:
            async with con.transaction():
                notes = await con.fetch(query_stub, user_id)

        # Set note limit for the user depending upon the premium status.
        notes_limit = 150 if is_premium else 50

        if len(notes) == notes_limit:
            return False

        return True

    async def insert_note(self, title: str, content: str, user_id: int) -> int:
        """Inserts a note into the database and returns the note id."""

        query_stub = "INSERT INTO notes VALUES (DEFAULT, $1, $2, $3) RETURNING note_id;"

        async with self.pool.acquire() as con:
            async with con.transaction():
                row = await con.fetchrow(query_stub, user_id, title, content)

        return row["note_id"]

    async def fetch_notes(self, user_id: int) -> list:
        """Fetches the notes of a given user."""

        query_stub = "SELECT note_id, title FROM notes WHERE user_id = $1;"

        async with self.pool.acquire() as con:
            async with con.transaction():
                rows = await con.fetch(query_stub, user_id)

        return rows

    async def delete_note(self, note_id: int, user_id: int) -> Union[str, None]:
        """Deletes a given note from the database."""

        query_stub = (
            "DELETE FROM notes WHERE user_id = $1 AND note_id = $2 RETURNING title;"
        )

        async with self.pool.acquire() as con:
            async with con.transaction():
                row = await con.fetchrow(query_stub, user_id, note_id)

        if row is None:
            return None

        return row["title"]

    async def fetch_note(self, user_id: int, note_id: int) -> Union[list, None]:
        """Fetches a given note."""

        query_stub = (
            "SELECT content, title FROM notes WHERE user_id = $1 AND note_id = $2;"
        )

        async with self.pool.acquire() as con:
            async with con.transaction():
                row = await con.fetchrow(query_stub, user_id, note_id)

        return row

    async def insert_poll(self, end: datetime, ctr: PollController) -> None:
        """Export the finished poll's votes and other stats to the database."""

        query_stub = "INSERT INTO polls VALUES ($1, $2, $3, $4, $5, $6, $7);"

        votes = []
        options = []
        for emoji, option in ctr.options:
            votes.append(ctr.votes.retrieve(emoji))
            options.append(option)

        async with self.pool.acquire() as con:
            async with con.transaction():
                await con.execute(
                    query_stub,
                    ctr.message.id,
                    ctr.ctx.guild.id,
                    ctr.question,
                    ctr.start,
                    end,
                    votes,
                    options,
                )

    async def fetch_polls(self, guild_id: int) -> list:
        """Fetch past polls of a guild."""

        query_stub = "SELECT * FROM polls WHERE guild_id = $1;"

        async with self.pool.acquire() as con:
            async with con.transaction():
                rows = await con.fetch(query_stub, guild_id)

        return rows

    async def fetch_poll(self, poll_id: int, guild_id: int) -> Union[list, None]:
        """Fetches a given poll."""

        query_stub = "SELECT * FROM polls WHERE poll_id = $1 AND guild_id = $2;"

        async with self.pool.acquire() as con:
            async with con.transaction():
                row = await con.fetchrow(query_stub, poll_id, guild_id)

        return row

    async def close_database_pool(self) -> None:
        """Closes the internal database pool."""
        await self.pool.close()
