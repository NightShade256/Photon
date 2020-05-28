import asyncio

import asyncpg

import config
from bot import Photon
from utils import db

try:
    import uvloop
    uvloop_present = True
except ImportError:
    uvloop_present = False


async def fetch_database_helper(event_loop):
    pool = await asyncpg.create_pool(dsn=config.core["postgres_dsn"], loop=event_loop)
    helper = db.DatabaseHelper(pool)
    await helper.ensure_tables()
    return helper


def main():
    if uvloop_present:
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    loop = asyncio.get_event_loop()
    helper = loop.run_until_complete(fetch_database_helper(loop))
    bot = Photon(helper, loop)
    bot.run(config.core["token"])


if __name__ == "__main__":
    main()
