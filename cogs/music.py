import asyncio
import datetime
import itertools
import re
import time

import async_timeout
import discord
import wavelink
from discord.ext import commands

import config


RURL = re.compile(r"https?:\/\/(?:www\.)?.+")
RSEEK = re.compile(
    r"^((?:(2[0-3]|[01]?[0-9]):)?(?:([0-5]?[0-9]):)?([0-5]?[0-9]))$")


class VoiceStateError(commands.CommandError):
    """Raised when a user's voice state is invalid."""

    def __init__(self, user: discord.User):
        self.user = user


class NotPrivilegedError(commands.CommandError):
    """Raised when a user executes a command when he doesn't have authority."""
    pass


class IncorrectChannelError(commands.CommandError):
    """Raised when a user executes a command outside of the sesssion channel."""

    def __init__(self, session_channel: discord.TextChannel):
        self.schannel = session_channel


class NoControllerError(commands.CommandError):
    """Raised when a controller doesn't exist for the a guild."""
    pass


class PhotonMusicController:

    def __init__(self, ctx: commands.Context):
        self.bot: commands.Bot = ctx.bot
        self.guild_id = ctx.guild.id
        self.channel = ctx.channel
        self.dj = ctx.author
        self.player: wavelink.Player = self.bot.wavelink.get_player(
            self.guild_id)

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()
        self.repeat = False
        self.prev_song = None

        self._controller_task: asyncio.Task = self.bot.loop.create_task(
            self._controller())
        self.destroyed = False  # Signals if the teardown has occured.

    async def _controller(self) -> None:
        await self.bot.wait_until_ready()
        await self.player.set_volume(40)

        while True:
            self.next.clear()
            if not self.repeat:
                try:
                    with async_timeout.timeout(300.0):
                        track = await self.queue.get()
                except asyncio.TimeoutError:
                    # Five minutes without any activity hence teardown.
                    await self.teardown()
            await self.player.play(track)
            self.prev_song = track
            await self.next.wait()

    async def teardown(self):
        """Disconnects the player and cancels internal tasks."""
        self._controller_task.cancel()
        await self.player.destroy()
        self.destroyed = True

    def has_authority(self, user) -> bool:
        """Checks if the user has authority to execute commands."""
        return user == self.dj or user.guild_permissions.ban_members

    def is_session_channel(self, channel) -> bool:
        """Checks if the user has executed the command in the session channel."""
        return channel == self.channel


class Music(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._controllers = {}
        self.node_online = False

        if not hasattr(bot, "wavelink"):
            self.bot.wavelink = wavelink.Client(self.bot)

        self.bot.loop.create_task(self.start_nodes())

    async def start_nodes(self):
        await self.bot.wait_until_ready()

        # Destroy nodes on reload
        if self.bot.wavelink.nodes:
            previous = self.bot.wavelink.nodes.copy()
            for node in previous.values():
                await node.destroy()

        # Initiate nodes
        for settings in config.nodes.values():
            node = await self.bot.wavelink.initiate_node(**settings)
            node.set_hook(self.on_event_hook)
        self.node_online = True

    async def on_event_hook(self, event):
        if isinstance(event, (wavelink.TrackEnd, wavelink.TrackException)):
            ctr: PhotonMusicController = self._controllers.get(
                event.player.guild_id)
            ctr.next.set()

    def get_controller(self, ctx: commands.Context) -> PhotonMusicController:
        """Fetches the controller associated with the guild.

        If an existing controller is found it returns that. But if the
        controller is destroyed or there is none then it creates a new one
        and returns that."""

        ctr = self._controllers.get(ctx.guild.id, None)
        if ctr is not None and not ctr.destroyed:
            return ctr
        else:
            ctr = PhotonMusicController(ctx)
            self._controllers[ctx.guild.id] = ctr
            return ctr

    def is_ctr_present(self, guild_id: int) -> bool:
        """Checks if a controller is present or present but destroyed."""
        ctr = self._controllers.get(guild_id, None)
        if ctr is None or ctr.destroyed:
            return False
        return True

    async def cog_before_invoke(self, ctx):
        """Checks it the user is connected to a voice channel or not."""

        if not self.node_online:
            return await ctx.send("Please wait for a second and allow the music nodes to come online.")

        exempted_commands = ("np", "queue")
        if ctx.author.voice is None and ctx.command.name not in exempted_commands:
            raise VoiceStateError(ctx.author)

    async def cog_command_error(self, ctx, error):
        """A error handler for the cog."""

        if isinstance(error, VoiceStateError):
            return await ctx.send(
                f"{ctx.author.mention}, please connect to a voice channel before using the command.")
        elif isinstance(error, NotPrivilegedError):
            return await ctx.send(
                f"{ctx.author.mention}, someone else is listening to music right. Please wait for them to finish.")
        elif isinstance(error, IncorrectChannelError):
            return await ctx.send(
                f"{ctx.author.mention}, please go to the session channel {error.schannel.mention}.")
        elif isinstance(error, NoControllerError):
            return await ctx.send(
                "Please use `join` or `play` commands first.")
        elif isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(
                f"{ctx.author.mention}, please provide the **{error.param.name}** parameter.")
        elif isinstance(error, wavelink.ZeroConnectedNodes):
            return await ctx.send("No Lavalink Nodes are currently online."
                                  "Please wait and try again."
                                  "They should come online in a few minutes.")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Listener that fires when voice state updates in a guild."""

        # Get controller for the guild and check if it is destroyed.
        ctr: PhotonMusicController = self._controllers.get(
            member.guild.id, None)
        if ctr is None or ctr.destroyed:
            return

        if not ctr.dj == member or member.bot:
            return

        # Swap the DJ is the DJ has left.
        if after.channel is None:
            channel: discord.VoiceChannel = self.bot.get_channel(
                int(ctr.player.channel_id))
            for m in channel.members:
                if m.bot:
                    pass
                else:
                    ctr.dj = m
                    return await ctr.channel.send(f"{ctr.dj.mention}, is now the new DJ for the session.")

        # Teardown as no one is in the voice channel.
        await ctr.teardown()
        await ctr.channel.send("The DJ has left the voice channel. Ending the current session.")

    @commands.command(name="join", aliases=["connect"])
    async def _join(self, ctx: commands.Context):
        """Photon joins the channel to which you are connected.

        This command has two effects:
        1) Music commands can only be used in the channel where this is invoked.
        2) Only the person who used the command and people with ban members
           permission is allowed to use the music commands, until the bot disconnects
           from the voice channel.
        """

        channel = ctx.author.voice.channel
        ctr = self.get_controller(ctx)

        # Check if the user has authority
        if not ctr.has_authority(ctx.author):
            raise NotPrivilegedError()

        await ctr.player.connect(channel.id)
        await ctx.send(f"⚓ Connected to {channel.mention} and bound to {ctx.channel.mention}.")

    @commands.command(name="play")
    async def _play(self, ctx: commands.Context, *, query: str):
        """Photon plays the song/audio requested by the user.

        The user can provide either the URL to the song or the song name.
        If the user provides a YouTube playlist URL only the first 20 songs
        will be added to the queue."""

        # Check if the user has authority to use the command.
        ctr: PhotonMusicController = self.get_controller(ctx)
        if not ctr.has_authority(ctx.author):
            raise NotPrivilegedError()
        # Check if the user is in the session channel.
        if not ctr.is_session_channel(ctx.channel):
            raise IncorrectChannelError(ctr.channel)

        # If the player is not connected to a voice channel, do so.
        if not ctr.player.is_connected:
            await ctx.invoke(self._join)

        # Check if the query is URL or not, and get tracks.
        if not RURL.match(query):
            query = f"ytsearch:{query}"
        tracks = await self.bot.wavelink.get_tracks(query)

        # If no results came up, abort.
        if not tracks:
            return await ctx.send("No search results came up for the query.")

        # If it is a playlist, add first 20 songs to the queue.
        if isinstance(tracks, wavelink.TrackPlaylist):
            await ctx.send(f"Adding {min(len(tracks.tracks), 50)} items from the playlist to the queue.")
            for track in tracks.tracks[:20]:
                await ctr.queue.put(track)
        else:
            track = tracks[0]
            await ctr.queue.put(track)
            await ctx.send(f"🎵 Added **{str(track)}** to the queue.")

    @commands.command(name="volume", aliases=["vol"])
    async def _volume(self, ctx: commands.Context, vol: int):
        """Change the player's volume to the desired quantity."""

        # Check if a controller is present. This is essentially to
        # eliminate a condition where if a person first uses any command other than
        # join or play and then disconnects or goes offline then the bot doesn't respond
        # to any other music commands by people without ban members permission.
        if not self.is_ctr_present(ctx.guild.id):
            raise NoControllerError()

        # Get the controller and check authority.
        ctr = self.get_controller(ctx)
        if not ctr.has_authority(ctx.author):
            raise NotPrivilegedError()
        if not ctr.is_session_channel(ctx.channel):
            raise IncorrectChannelError(ctr.channel)

        # Done to prevent invalid volume arguments.
        vol = min(max(vol, 0), 100)
        # Note current volume to use the correct emoji.
        current_volume = ctr.player.volume
        await ctr.player.set_volume(vol)
        if vol > current_volume:
            emoji = "🔊"
        else:
            emoji = "🔉"
        await ctx.send(f"{emoji} The player's volume has been changed to **{vol}%**")

    @commands.command(name="pause")
    async def _pause(self, ctx: commands.Context):
        """Pause the player."""

        # See comment on volume command.
        if not self.is_ctr_present(ctx.guild.id):
            raise NoControllerError()

        # Get the controller and check authority.
        ctr = self.get_controller(ctx)
        if not ctr.has_authority(ctx.author):
            raise NotPrivilegedError()
        if not ctr.is_session_channel(ctx.channel):
            raise IncorrectChannelError(ctr.channel)

        # Check if the player is playing anything or not.
        if not ctr.player.is_playing:
            return await ctx.send("The player is currently not playing anything.")

        # Check if the player is already paused.
        if ctr.player.is_paused:
            return await ctx.send("The player is already paused.")

        await ctr.player.set_pause(True)
        await ctx.send("⏸️ The player is now paused.")

    @commands.command(name="resume")
    async def _resume(self, ctx: commands.Context):
        """Resume the player from a paused state."""

        # See comment on volume command.
        if not self.is_ctr_present(ctx.guild.id):
            raise NoControllerError()

        # Get the controller and check authority.
        ctr = self.get_controller(ctx)
        if not ctr.has_authority(ctx.author):
            raise NotPrivilegedError()
        if not ctr.is_session_channel(ctx.channel):
            raise IncorrectChannelError(ctr.channel)

        # Check if the player is playing anything or not.
        if not ctr.player.is_playing:
            return await ctx.send("The player is currently not playing anything.")

        # Check if the player is not paused.
        if not ctr.player.is_paused:
            return await ctx.send("The player is already unpaused.")

        await ctr.player.set_pause(False)
        await ctx.send("▶️ The player is now unpaused.")

    @commands.command(name="queue", aliases=["q"])
    async def _queue(self, ctx: commands.CommandError):
        """Lists the next five upcoming songs."""

        # See comment on volume command.
        if not self.is_ctr_present(ctx.guild.id):
            raise NoControllerError()

        # Check if the user is in session channel.
        ctr = self.get_controller(ctx)
        if not ctr.is_session_channel(ctx.channel):
            raise IncorrectChannelError(ctr.channel)

        # Check if the player is not playing anything
        if not ctr.player.current or not ctr.queue._queue:
            return await ctx.send("No songs are currently queued up.")

        # Construct the embed
        upcoming = list(itertools.islice(ctr.queue._queue, 0, 5))
        base = "\n".join(f"**• `{song}`**" for song in upcoming)
        embed = discord.Embed(
            title="Upcoming:", description=base, colour=discord.Colour.dark_teal())

        # Send the embed.
        await ctx.send(embed=embed)

    @commands.command(name="skip")
    async def _skip(self, ctx: commands.Context):
        """Skips the current track."""

        # See comment on volume command.
        if not self.is_ctr_present(ctx.guild.id):
            raise NoControllerError()

        # Check if the user has authority
        ctr = self.get_controller(ctx)
        if not ctr.has_authority(ctx.author):
            raise NotPrivilegedError()
        if not ctr.is_session_channel(ctx.channel):
            raise IncorrectChannelError(ctr.channel)

        # Skip the current song.
        await ctr.player.stop()
        await ctx.send("⏩ The current song has been skipped.")

    @commands.command(name="stop", aliases=["leave"])
    async def _stop(self, ctx: commands.Context):
        """Stops the player, and disconnects from the voice channel."""

        # See comment on volume command.
        if not self.is_ctr_present(ctx.guild.id):
            raise NoControllerError()

        # Check if user has authority.
        ctr = self.get_controller(ctx)
        if not ctr.has_authority(ctx.author):
            raise NotPrivilegedError()
        if not ctr.is_session_channel(ctx.channel):
            raise IncorrectChannelError(ctr.channel)

        # Teardown the controller.
        await ctr.teardown()
        await ctx.send("⏹️ Photon has left the voice channel.")

    @commands.command(name="np")
    async def _np(self, ctx: commands.Context):
        """Display details about the track that is currently being played."""

        # See comment on volume command.
        if not self.is_ctr_present(ctx.guild.id):
            raise NoControllerError()

        # Check if user is in session channel.
        ctr = self.get_controller(ctx)
        if not ctr.is_session_channel(ctx.channel):
            raise IncorrectChannelError(ctr.channel)

        # Check if the player is playing anything or not.
        if not ctr.player.is_playing:
            return await ctx.send("No track is currently being played.")

        # elapsed seconds in the track
        elapsed = int((ctr.player.position) / 1000)

        # Beautify the time deltas
        current = ctr.player.current
        lenb = datetime.timedelta(seconds=(current.length/1000))
        elab = datetime.timedelta(seconds=int(elapsed))

        # Calculate the amount of emojis needed
        elap_ej = int(((elapsed * 1000) / current.length) * 10)
        left_ej = 10 - elap_ej
        base_str = f"{elab} <"
        for _ in range(elap_ej):
            base_str += "◻️ "
        for _ in range(left_ej):
            base_str += "◼️ "
        base_str = (base_str.strip()) + f"> {lenb}"
        embed = discord.Embed(title=current.title,
                              colour=discord.Colour.dark_teal())
        embed.add_field(name="**• Uploader:**", value=current.author)
        embed.add_field(name="**• Duration:**", value=base_str, inline=False)
        if current.thumb is not None:
            embed.set_thumbnail(url=current.thumb)
        await ctx.send(embed=embed)

    @commands.command(name="repeat")
    async def _repeat(self, ctx: commands.Context):
        """Switches on/off single track repeat."""

        # See comment on volume command
        if not self.is_ctr_present(ctx.guild.id):
            raise NoControllerError()

        # Check if user has authority
        ctr = self.get_controller(ctx)
        if not ctr.has_authority(ctx.author):
            raise NotPrivilegedError()
        if not ctr.is_session_channel(ctx.channel):
            raise IncorrectChannelError(ctr.channel)

        ctr.repeat = not ctr.repeat
        mode = "on" if ctr.repeat else "off"
        await ctx.send(f"🔂 Switched **{mode}** single track repeat.")

    @commands.command(name="seek")
    async def _seek(self, ctx: commands.Context, position: str):
        """Seek to the given position.

        Formats accepted:
        1) SS
        2) MM:SS
        3) HH:MM:SS

        You cannot omit the colon (:) in options 2 and 3."""

        # See comment on volume command
        if not self.is_ctr_present(ctx.guild.id):
            raise NoControllerError()

        # Check if user has authority
        ctr = self.get_controller(ctx)
        if not ctr.has_authority(ctx.author):
            raise NotPrivilegedError()
        if not ctr.is_session_channel(ctx.channel):
            raise IncorrectChannelError(ctr.channel)

        # Check if the postion provided is of valid format.
        if not RSEEK.match(position):
            return await ctx.send(f"Invalid format used. Please see `{ctx.prefix}help seek` for more.")

        # Define a dict which we will use to determine the format to parse the position.
        fmt_dict = {
            0: "%S",
            1: "%M:%S",
            2: "%H:%M:%S"
        }

        # Parse the position parameter.
        fmt = fmt_dict[position.count(":")]
        stime = time.strptime(position, fmt)
        pos = (stime.tm_sec) + (stime.tm_min * 60) + (stime.tm_hour * 3600)
        pos *= 1000

        # If the seek time is greater than the length of track, skip it.
        if pos > ctr.player.current.length:
            return await ctx.invoke(self._skip)

        # Seek the track.
        await ctr.player.seek(pos)
        string = "the beginning" if pos == 0 else position
        await ctx.send(f"↔️ Seeked the track to **{string}**.")

    @commands.command(name="eq", aliases=["equalizer"])
    async def _eq(self, ctx: commands.Context, eq_name: str):
        """Change the equalizer of the player.

        Permissible options are:
        1) boost (bass boost),
        2) piano (emphasis on vocals),
        3) metal (for rock/metal songs),
        4) flat (default).

        The equalizer takes about three seconds to change.
        """

        # See comment on volume command
        if not self.is_ctr_present(ctx.guild.id):
            raise NoControllerError()

        # Check if user has authority
        ctr = self.get_controller(ctx)
        if not ctr.has_authority(ctx.author):
            raise NotPrivilegedError()
        if not ctr.is_session_channel(ctx.channel):
            raise IncorrectChannelError(ctr.channel)

        # A list of permissible equalizers.
        eq_list = {
            "boost": wavelink.Equalizer.boost(),
            "flat": wavelink.Equalizer.flat(),
            "metal": wavelink.Equalizer.metal(),
            "piano": wavelink.Equalizer.piano()
        }

        # Check if the equalizer provided is in the list.
        if not eq_name.lower() in eq_list:
            return await ctx.send(
                f"Invalid equalizer name provided. See `{ctx.prefix}help eq` for a list of options.")

        # Change the equalizer.
        await ctr.player.set_eq(eq_list[eq_name])
        await ctx.send(f"🎚️ Changed the equalizer to **{eq_name.lower()}**.")

    @commands.command(name="swap")
    async def _swap(self, ctx: commands.Context, user: discord.Member):
        """Swap the DJ.

        You can swap the DJ to a person who is in the voice channel
        with you."""

        # See comment on volume command
        if not self.is_ctr_present(ctx.guild.id):
            raise NoControllerError()

        # Check if user has authority
        ctr = self.get_controller(ctx)
        if not ctr.has_authority(ctx.author):
            raise NotPrivilegedError()
        if not ctr.is_session_channel(ctx.channel):
            raise IncorrectChannelError(ctr.channel)

        # Check if the member is connected to the voice channel.
        members = (self.bot.get_channel(int(ctr.player.channel_id))).members
        if user not in members:
            return await ctx.send("The member is not in the current voice channel.")

        # Check if the user is attempting to assign DJ status to himself.
        if user == ctr.dj:
            return await ctx.send("You are already the DJ.")

        # Check if the user is assigning DJ status to a bot or Photon itself.
        if len(members) <= 2 or user.bot:
            return await ctx.send("You cannot assign the DJ role to a bot or Photon itself.")

        ctr.dj = user
        await ctx.send(f"{user.mention} is now the new DJ.")


def setup(bot: commands.Bot):
    bot.add_cog(Music(bot))
