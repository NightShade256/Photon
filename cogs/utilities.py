import asyncio
import datetime
import random
import re
import textwrap

import aiohttp
import discord
import humanize
from discord.ext import commands, tasks

import config
from bot import Photon

RHTML = re.compile(r"<.*?>")


class Utilities(commands.Cog):
    """Commands to help simplify tasks."""

    def __init__(self, bot: Photon):
        self.bot = bot
        temp = """Please follow all advisories and guidelines issued by
               [WHO](https://bit.ly/2YC6pY0) and the government. We can
               beat the pandemic. All that is required on our part is to
               stay home and have a bit of faith in our goverment."""
        lines = temp.splitlines()
        lines = [textwrap.dedent(line) for line in lines]
        temp = " ".join(lines)
        self.advisory = temp
        self.total_data = None
        self.tests_done = None
        self.last_fetched = None
        self.data_ready = asyncio.Event()

        # pylint: disable=no-member
        self._fetch_data.start()

    async def cog_command_error(self, ctx, error):
        """A mini error handler for this cog."""

        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(f"Please specify the **{error.param.name}** parameter.")
        else:
            self.bot.photon_log.error(
                f"[ERROR] Command: {ctx.command.name}, Exception: {error}.")

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
        confirmed = f"{humanize.intcomma(state_data['confirmed'])} " \
                    f"[+{state_data['deltaconfirmed']}]"
        active = f"{humanize.intcomma(state_data['active'])}"
        recovered = f"{humanize.intcomma(state_data['recovered'])} " \
                    f"[+{state_data['deltarecovered']}]"
        deaths = f"{humanize.intcomma(state_data['deaths'])} [+{state_data['deltadeaths']}]"
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
                        value=humanize.intcomma(int(self.tests_done)))
        delta: datetime.timedelta = datetime.datetime.utcnow() - self.last_fetched
        fetched = humanize.naturaltime(delta)
        footer = f"Requested by {ctx.author.name}.\n" \
                 f"Data fetched from https://www.covid19india.org {fetched}"
        embed.set_footer(text=footer, icon_url=ctx.author.avatar_url)

        # Send the embed.
        await ctx.send(embed=embed)

    @_covindia.before_invoke
    async def _data_check(self, ctx):
        """Blocks the execution of the covindia command until data is ready."""
        await self.data_ready.wait()

    @commands.command(name="covid")
    @commands.cooldown(1, 15.0, commands.BucketType.user)
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
        embed = discord.Embed(title=f"COVID-19 Statistics for {area}",
                              description=self.advisory,
                              url="https://www.bing.com/covid",
                              colour=discord.Colour.dark_teal())
        embed.add_field(name="**• Confirmed Cases:**", value=humanize.intcomma(confirmed))
        embed.add_field(name="**• Active Cases:**", value=humanize.intcomma(active))
        embed.add_field(name="**• Recovered:**", value=humanize.intcomma(recovered))
        embed.add_field(name="**• Deaths:**", value=humanize.intcomma(deaths))
        embed.add_field(name="**• Approx. Death Rate:**", value=rate)
        embed.add_field(name="**• Last Updated On:**", value=last_update)

        footer = f"Requested by {ctx.author.name}. Data fetched from https://covid19.mathdro.id/"
        embed.set_footer(text=footer, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    @commands.command(name="random")
    @commands.cooldown(1, 20.0, commands.BucketType.user)
    async def _randomn(self, ctx, start: int = 0, end: int = 10):
        """Generates a random integer number between the two specified numbers."""
        if start > end:
            return await ctx.send(
                "The start of the range cannot be more than the end of the range.")
        number = await self.bot.loop.run_in_executor(None, random.randint, start, end)
        await ctx.send(f"**{number}** was chosen at random.")

    @commands.command(name="avatar")
    async def _avatar(self, ctx, *, user: discord.User = None):
        """Shows the profile picture of the user specified.

        By default it shows the avatar of the person invoking the command."""

        if user is None:
            user = ctx.author
        avatar_url = str(user.avatar_url_as(static_format="png", size=1024))
        embed = discord.Embed(colour=discord.Color.dark_teal())
        embed.set_footer(text=f"Requested by {ctx.author.name}.",
                         icon_url=ctx.author.avatar_url)
        embed.set_image(url=avatar_url)
        await ctx.send(embed=embed)

    @commands.command(name="pypi")
    @commands.cooldown(1, 10.0, commands.BucketType.user)
    async def _pypi(self, ctx, *, package_name: str):
        """Displays information about a package listed on PyPI."""

        # Define the URL we are going to make GET request to.
        api_url = f"https://pypi.org/pypi/{package_name}/json"
        ico = "https://raw.githubusercontent.com/nlhkabu/warehouse-ui/gh-pages/img/pypi-sml.png"

        # Make the GET request.
        async with self.bot.web.get(api_url) as resp:

            # If the status is non-200 tell the user to check the package name
            if resp.status != 200:
                return await ctx.send("Please check the package name and try again.")

            # Decode the JSON data.
            data = await resp.json()

        desc = f"```{data['info']['summary']}```\n"
        inst = f"`pip install {package_name}`"

        # Construct the Embed.
        embed = discord.Embed(title=package_name,
                              description=desc,
                              colour=discord.Colour.dark_teal())

        # Add embed fields.
        embed.add_field(name="**• Author**", value=str(data["info"]["author"]))
        embed.add_field(name="**• Latest Release**", value=str(data["info"]["version"]))

        if data["info"]["license"]:
            embed.add_field(name="**• License**", value=data["info"]["license"])

        # If home page isn't empty, make a embeded link.
        if data["info"]["home_page"]:
            fmt = f"[Click to visit!]({data['info']['home_page']})"
            embed.add_field(name="**• Home Page**", value=fmt)

        pypi_page = f"[Click to visit!]({data['info']['project_url']})"
        embed.add_field(name="**• PyPI Page**", value=pypi_page)
        embed.add_field(name="**• Install Using**", value=inst)

        footer = f"Requested by {ctx.author.name}.\n" \
                 "This bot is not affiliated with PyPI in anyway."

        embed.set_footer(text=footer,
                         icon_url=ctx.author.avatar_url)
        embed.set_thumbnail(url=ico)

        # Send the embed.
        await ctx.send(embed=embed)

    @commands.command(name="dictionary", aliases=["dict"])
    @commands.cooldown(1, 15.0, commands.BucketType.user)
    @commands.is_nfsw()
    async def _dictionary(self, ctx, *, word: str):
        """Get the meaning for an English word or phrase.

        If the examples sometimes say None don't panic.
        The bot uses an API which has less examples documented.
        In the future there will be a switch of APIs."""

        req_url = f"https://owlbot.info/api/v4/dictionary/{word}"
        headers = {
            "Authorization": f"Token {config.api_keys['owlapi']}"
        }

        async with self.bot.web.get(req_url, headers=headers) as resp:
            if resp.status != 200:
                return await ctx.send("Please check the entered word, and try again.")

            try:
                data = await resp.json()
            except aiohttp.ContentTypeError:
                return await ctx.send("Please check the entered word, and try again.")

        if data["pronunciation"] is not None:
            fmt = f"**Pronunciation:** `{data['pronunciation']}`\n"
        else:
            fmt = ""

        sorted_definitions: list = data["definitions"][:5]
        sorted_definitions.sort(key=lambda k: k["type"])

        current_type = None
        for count, definition in enumerate(sorted_definitions):

            if current_type is None or definition["type"] != current_type:
                current_type = definition["type"]
                fmt += f"\n***{current_type}***\n\n"
            example = str(RHTML.sub("", str(definition['example'])))
            fmt += f"{count+1}. *{definition['definition']}*\n"
            fmt += f"**Example:** `{example}`\n" if example != "None" else ""

        embed = discord.Embed(title=f"\U0001F4DA  {word.title()}",
                              description=fmt,
                              colour=discord.Colour.dark_teal())

        footer = f"Requested by {ctx.author.name}. " \
                 "Powered by owlbot.info API."

        image = data["definitions"][0]["image_url"]

        if image is not None:
            embed.set_thumbnail(url=image)

        embed.set_footer(text=footer, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    @commands.command(name="serverinfo", aliases=["si"])
    async def _serverinfo(self, ctx: commands.Context):
        """Gives information about the server in which it is invoked."""

        # Create a embed.
        embed = discord.Embed(title=ctx.guild.name,
                              colour=discord.Colour.dark_teal())

        # Add owner and guild id fields.
        embed.add_field(name="Owner", value=str(ctx.guild.owner.name))
        embed.add_field(name="Guild ID", value=ctx.guild.id)

        # Clean the voice region string and add that as a field.
        region = str(ctx.guild.region).replace("_", " ").title()
        region = region.replace("Us", "US").replace("Vip", "VIP")
        region = region.replace("-", " ")
        embed.add_field(name="Voice Region", value=region)

        # Count the number of emojis and animated emojis, and add a field.
        normal_emojis = len([x for x in ctx.guild.emojis if not x.animated])
        animated_emojis = len([x for x in ctx.guild.emojis if x.animated])
        emoji_fmt = f"Static: {normal_emojis}\n" \
                    f"Animated: {animated_emojis}"
        embed.add_field(name="Emojis", value=emoji_fmt)

        # Count the number of voice and text channels.
        channels = f"Text: {len(ctx.guild.text_channels)}\n" \
                   f"Voice: {len(ctx.guild.voice_channels)}"
        embed.add_field(name="Channels", value=channels)

        # Calculate members, bots and otherwise.
        users = len([x for x in ctx.guild.members if not x.bot])
        bots = len(ctx.guild.members) - users
        fmt = f"Users: {users}\n" \
              f"Bots: {bots}"
        embed.add_field(name="Members", value=fmt)

        embed.add_field(name="Roles", value=len(ctx.guild.roles))
        embed.add_field(name="Server Boosters", value=len(ctx.guild.premium_subscribers))

        # Clean verification level and add a field.
        verif = str(ctx.guild.verification_level).replace("_", " ").title()
        embed.add_field(name="Verification Level", value=verif)

        # Set the footer and thumbnail.
        embed.set_footer(text=f"Requested by {ctx.author.name}.",
                         icon_url=ctx.author.avatar_url)
        embed.set_thumbnail(url=ctx.guild.icon_url)

        # Send the embed.
        await ctx.send(embed=embed)

    @commands.command(name="userinfo", aliases=["ui"])
    async def _userinfo(self, ctx, user: discord.Member = None):
        """Gives information about a user."""
        if user is None:
            user = ctx.author

        # Create the embed.
        embed = discord.Embed(title=user.display_name,
                              colour=discord.Colour.dark_teal())

        embed.add_field(name="Username",
                        value=user.name+"#"+user.discriminator, inline=False)
        embed.add_field(name="User ID", value=user.id)
        embed.add_field(name="Bot", value=str(user.bot))
        boost = "Yes" if user.premium_since is not None else "No"
        embed.add_field(name="Server Booster", value=boost)

        delta_create = datetime.datetime.utcnow() - user.created_at
        create_fmt = f"{user.created_at.strftime('%d/%m/%Y %H:%M:%S')}\n" \
                     f"({humanize.naturaltime(delta_create)})"
        embed.add_field(name="Account Created", value=create_fmt)

        delta_join = datetime.datetime.utcnow() - user.joined_at
        join_fmt = f"{user.joined_at.strftime('%d/%m/%Y %H:%M:%S')}\n" \
                   f"({humanize.naturaltime(delta_join)})"
        embed.add_field(name="Joined Guild", value=join_fmt)

        roles = [x.mention for x in user.roles]
        roles.pop(0)
        roles_fmt = " ".join(roles)
        if not roles_fmt:
            roles_fmt = "None"
        embed.add_field(name="Roles", value=roles_fmt, inline=False)

        embed.set_thumbnail(url=user.avatar_url)
        embed.set_footer(text=f"Requested by {ctx.author.name}.",
                         icon_url=ctx.author.avatar_url)

        # Send the embed.
        await ctx.send(embed=embed)

    @commands.command(name="wikipedia", aliases=["wiki"])
    @commands.is_nsfw()
    @commands.cooldown(1, 7.0, commands.BucketType.user)
    async def _wikipedia(self, ctx, *, query: str):
        """Search Wikipedia for a given term."""

        params_search = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": f"""intitle:{query}~ OR intitle:"{query}"~""",
            "srlimit": 2,
            "srsort": "relevance",
            "srwhat": "text",
            "srqiprofile": "mlr-1024rs"
        }

        url = "https://en.wikipedia.org/w/api.php"

        async with self.bot.web.get(url, params=params_search) as resp:
            search_data = await resp.json()

        if not search_data["query"]["search"]:
            return await ctx.send("Please check the search term and try again.")

        title = search_data["query"]["search"][0]["title"]

        params_get = {
            "action": "query",
            "format": "json",
            "prop": "extracts|info|pageimages",
            "exsentences": 10,
            "exintro": "true",
            "explaintext": "true",
            "inprop": "url",
            "pithumbsize": 512,
            "redirects": 1,
            "formatversion": 2,
            "titles": title
        }

        async with self.bot.web.get(url, params=params_get) as resp:
            get_data = await resp.json()

        page = get_data["query"]["pages"][0]

        if page.get("missing", False):
            return await ctx.send("Please check the query and try again.")

        embed = discord.Embed(title=page["title"],
                              colour=discord.Colour.dark_teal())

        link = page["fullurl"]

        if page["extract"] == f"{page['title']} may refer to:":
            return await ctx.send("Your query is ambiguous. Please specify more details.")

        if len(page["extract"]) < 500:
            description = "".join(textwrap.wrap(page["extract"], len(page["extract"])))
        else:
            extract = page["extract"][:500]
            extract = "".join(textwrap.wrap(extract, len(extract)))
            description = f"{extract}...\n[Read More]({link})"

        if page.get("thumbnail", None) is not None:
            embed.set_image(url=page["thumbnail"]["source"])
        else:
            icon = "https://www.wikipedia.org/portal/wikipedia.org/" \
                   "assets/img/Wikipedia-logo-v2.png"
            embed.set_thumbnail(url=icon)

        embed.description = description
        embed.url = link
        embed.set_footer(text=f"Requested by {ctx.author.name}. Powered by Wikipedia API",
                         icon_url=ctx.author.avatar_url)

        await ctx.send(embed=embed)


def setup(bot: Photon):
    bot.add_cog(Utilities(bot))
