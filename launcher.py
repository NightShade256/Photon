import asyncio

import asyncpg

import config
from bot import Photon

try:
    import uvloop
    uvloop_present = True
except ImportError:
    uvloop_present = False


async def fetch_pool(event_loop):
    return await asyncpg.create_pool(dsn=config.core["postgres_dsn"], loop=event_loop)


async def configure_database(pool):
    guild_table = """
        CREATE TABLE IF NOT EXISTS guild(
            guild_id bigint PRIMARY KEY,
            prefix varchar(5) DEFAULT '&',
            welcome bigint
        );
    """

    polls_table = """
        CREATE TABLE IF NOT EXISTS polls(
            poll_id bigint PRIMARY KEY,
            guild_id bigint,
            question varchar(2000),
            start_time timestamp with time zone,
            end_time timestamp with time zone,
            votes integer[],
            options varchar(2000)[]
        );
    """

    notes_table = """
        CREATE TABLE IF NOT EXISTS notes(
            note_id bigserial PRIMARY KEY,
            user_id bigint,
            title varchar(40),
            content varchar(2000)
        );
    """

    async with pool.acquire() as con:
        try:
            async with con.transaction():
                await con.execute(guild_table)
                await con.execute(notes_table)
                await con.execute(polls_table)
        except Exception:
            pass


def main():
    if uvloop_present:
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    loop = asyncio.get_event_loop()
    pool = loop.run_until_complete(fetch_pool(loop))
    loop.run_until_complete(configure_database(pool))
    bot = Photon(pool, loop)
    bot.run(config.core["token"])


if __name__ == "__main__":
    main()
