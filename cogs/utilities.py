import asyncio
import datetime
import random
import textwrap

import discord
import humanize
from discord.ext import commands, tasks


class Utilities(commands.Cog):
    """Commands to help simplify tasks."""

    def __init__(self, bot):
        self.bot = bot
        temp = """Please follow all advisories and guidelines issued by [WHO](https://www.who.int/emergencies/diseases/novel-coronavirus-2019/advice-for-public) and the government. We can beat the pandemic. 
All that is required on our part is to stay home and have a bit of faith in our goverment."""
        self.advisory = textwrap.dedent(temp)
        self.total_data = None
        self.tests_done = None
        self.last_fetched = None
        self.data_ready = asyncio.Event()

        # pylint: disable=no-member
        self._fetch_data.start()

    # Done so as to not overwhelm the API.
    @tasks.loop(minutes=15.0)
    async def _fetch_data(self):
        """Updates COVID-19 data about India every 15 minutes."""
        # Fetch the data from the API.
        async with self.bot.web.get('https://api.covid19india.org/data.json') as req:
            data = await req.json()

        self.total_data = data['statewise']
        self.tests_done = data['tested'][-1]['totalsamplestested']
        self.last_fetched = datetime.datetime.utcnow()
        self.data_ready.set()

    def cog_unload(self):
        """Cancel the task of fetching data before cog unload."""

        # pylint: disable=no-member
        self._fetch_data.cancel()

    @commands.command(name="covindia")
    async def _covindia(self, ctx, *, state: str = "Total"):
        """
        Provides statistics related to the COVID-19 pandemic for India.

        You can also get individual stats for states by doing something like:
        [prefix]covindia Maharashtra
        """
        # Parse data to find the state.
        data = [x for x in self.total_data if (
            x['state'].lower() == state.lower() or x['statecode'] == state.upper())]

        # If no such state exists
        if not data:
            return await ctx.send('Invalid state name or state code.')

        # Pull data as prerequisite to build the embed.
        state_data = data[0]
        area = state_data['state'] if state != 'Total' else 'India'
        confirmed = f"{state_data['confirmed']} [+{state_data['deltaconfirmed']}]"
        active = f"{state_data['active']}"
        recovered = f"{state_data['recovered']} [+{state_data['deltarecovered']}]"
        deaths = f"{state_data['deaths']} [+{state_data['deltadeaths']}]"
        rate = '{:.2f}%'.format(
            ((int(state_data['deaths'])/int(state_data['confirmed']))*100))
        colour = discord.Color.dark_teal()

        # Build the embed.
        embed = discord.Embed(title=f'COVID-19 Statistics for {area}', description=self.advisory,
                              url='https://www.covid19india.org', colour=colour)
        embed.add_field(name='**• Confirmed Cases:**', value=confirmed)
        embed.add_field(name='**• Active Cases:**', value=active)
        embed.add_field(name='**• Recovered:**', value=recovered)
        embed.add_field(name='**• Deaths:**', value=deaths)
        embed.add_field(name='**• Approx. Death Rate:**', value=rate)
        embed.add_field(name='**• Last Updated On:**',
                        value=state_data['lastupdatedtime'])
        embed.add_field(name='**• Tests Done Nationally:**',
                        value=self.tests_done)
        delta: datetime.timedelta = datetime.datetime.utcnow() - self.last_fetched
        fetched = humanize.naturaltime(delta)
        footer = f"""Requested by {ctx.author.name}. Data fetched from https://www.covid19india.org {fetched}"""
        embed.set_footer(text=footer,
                         icon_url=ctx.author.avatar_url)

        # Send the embed.
        await ctx.send(embed=embed)

    @_covindia.before_invoke
    async def _data_check(self, ctx):
        """Blocks the execution of the covindia command until data is ready."""
        await self.data_ready.wait()

    @commands.command(name="covid")
    async def _covid(self, ctx, *, country: str = "all"):
        """Provides statistics related to COVID-19 for the world.

        You can also get individual stats for countries by doing something like:
        [prefix]covid Spain
        """
        if country.lower() in ("india", "in", "ind"):
            return await ctx.invoke(self.bot.get_command("covindia"))
        if country == "all":
            url = "https://covid19.mathdro.id/api"
            area = "the World"
        else:
            url = f"https://covid19.mathdro.id/api/countries/{country.lower()}"
            area = f"{country.upper()}"
        async with self.bot.web.get(url) as req:
            if req.status == 404:
                return await ctx.send("Country not found or the country doesn't have any cases.")
            data = await req.json()
        confirmed = data["confirmed"]["value"]
        recovered = data["recovered"]["value"]
        deaths = data["deaths"]["value"]
        active = confirmed - (recovered + deaths)
        rate = "{:.2f}%".format(((deaths/confirmed)*100))
        temp = data["lastUpdate"].split("T")
        last_update = f"{temp[0].replace('-', '/')} {temp[1][:8]}"
        embed = discord.Embed(
            title=f"COVID-19 Statistics for {area}", description=self.advisory, url="https://www.bing.com/covid", colour=0x1A93E1)
        embed.add_field(name="**• Confirmed Cases:**", value=confirmed)
        embed.add_field(name="**• Active Cases:**", value=active)
        embed.add_field(name="**• Recovered:**", value=recovered)
        embed.add_field(name="**• Deaths:**", value=deaths)
        embed.add_field(name="**• Approx. Death Rate:**", value=rate)
        embed.add_field(name="**• Last Updated On:**", value=last_update)
        embed.set_footer(
            text=f"Requested by {ctx.author.name}. Data fetched from https://covid19.mathdro.id/", icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    @commands.command(name="random")
    async def _randomn(self, ctx, start: int = 0, end: int = 10):
        """Generates a random integer number between the two specified numbers."""
        if start > end:
            return await ctx.send("The start of the range cannot be more than the end of the range.")
        number = await self.bot.loop.run_in_executor(None, random.randint, start, end)
        await ctx.send(f"**{number}** was chosen at random.")

    @commands.command(name="avatar")
    async def _avatar(self, ctx, *, user: discord.User = None):
        """Shows the profile picture of the user specified.

        By default it shows the avatar of the person invoking the command."""

        if user is None:
            user = ctx.author
        avatar_url = str(user.avatar_url_as(format="png", static_format="png", size=1024))
        embed = discord.Embed(colour=discord.Color.dark_teal())
        embed.set_image(url=avatar_url)
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Utilities(bot))
