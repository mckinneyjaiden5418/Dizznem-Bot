"""YouTube voice channel commands."""

import asyncio
import subprocess
import time
from collections import deque
from typing import TYPE_CHECKING

import yt_dlp
from bot.bot import DizznemBot
from discord import (
    ClientException,
    Color,
    Embed,
    FFmpegPCMAudio,
    Forbidden,
    Member,
    PCMVolumeTransformer,
    StageChannel,
    VoiceChannel,
    VoiceClient,
)
from discord.ext import commands, tasks
from log import logger

if TYPE_CHECKING:
    from yt_dlp.extractor.common import _InfoDict

YDL_OPTIONS: dict = {
    "format": "bestaudio[ext=m4a]/bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",  # noqa: S104
    "socket_timeout": 15,
    "retries": 2,
}

FFMPEG_OPTIONS: dict = {
    "options": "-vn -bufsize 512k",
}

AUTO_DISCONNECT_SECONDS: int = 300  # 5 minutes
MAX_QUEUE_DISPLAY: int = 10
MAX_EMBED_FIELD_LENGTH: int = 1000
MAX_TITLE_LENGTH: int = 50
FETCH_TIMEOUT_SECONDS: int = 30


class YouTube(commands.Cog):
    """YouTube voice channel commands."""

    def __init__(self, bot: DizznemBot) -> None:
        """Initialize the cog.

        Args:
            bot (DizznemBot): Dizznem Bot.
        """
        self.bot: DizznemBot = bot
        self.queue: deque[dict] = deque()
        self.current: dict | None = None
        self.voice_client: VoiceClient | None = None
        self._idle_time: int = 0
        self._ytdlp_proc: subprocess.Popen[bytes] | None = None
        self._auto_disconnect.start()

    def cog_unload(self) -> None:
        """Stop background tasks on unload."""
        self._auto_disconnect.cancel()
        self._kill_ytdlp()
        logger.debug("[yt] YouTube cog unloaded, auto_disconnect task cancelled")

    def _kill_ytdlp(self) -> None:
        """Kill the active yt-dlp process if one is running."""
        if self._ytdlp_proc is not None and self._ytdlp_proc.poll() is None:
            try:
                self._ytdlp_proc.kill()
                logger.debug(f"[yt] _kill_ytdlp: killed pid={self._ytdlp_proc.pid}")
            except ProcessLookupError:
                logger.debug("[yt] _kill_ytdlp: process already gone")
        self._ytdlp_proc = None

    async def _fetch_info(self, query: str) -> dict | None:
        """Fetch video info from YouTube.

        Args:
            query (str): Search query or URL.

        Returns:
            dict | None: Video info dict, or None if not found.
        """
        is_url: bool = query.startswith(("http://", "https://"))
        logger.debug(f"[yt] _fetch_info called | query={query!r} | is_url={is_url}")
        t_start: float = time.monotonic()

        def _extract() -> dict | None:
            logger.debug(f"[yt] _extract thread started | query={query!r}")
            t: float = time.monotonic()
            with yt_dlp.YoutubeDL(
                YDL_OPTIONS,  # pyright: ignore[reportArgumentType]
            ) as ydl:
                try:
                    search_query: str = query if is_url else f"ytsearch:{query}"
                    logger.debug(
                        f"[yt] yt-dlp extract_info start | search_query={search_query!r}",
                    )
                    info: _InfoDict = ydl.extract_info(search_query, download=False)
                    elapsed: float = time.monotonic() - t
                    logger.debug(f"[yt] yt-dlp extract_info done in {elapsed:.2f}s")
                    if is_url:
                        return info  # pyright: ignore[reportReturnType]
                    if info and "entries" in info and info["entries"]:
                        logger.debug(
                            f"[yt] search returned {len(info['entries'])} entries, using first", # pyright: ignore[reportArgumentType]
                        )
                        return info["entries"][0] # pyright: ignore[reportIndexIssue]
                    logger.debug("[yt] search returned no entries")
                    return None  # noqa: TRY300
                except (
                    yt_dlp.utils.DownloadError  # pyright: ignore[reportAttributeAccessIssue]
                ) as e:
                    logger.error(f"[yt] yt-dlp DownloadError: {e}")
                    return None

        try:
            result: dict | None = await asyncio.wait_for(
                asyncio.to_thread(_extract),
                timeout=FETCH_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            elapsed = time.monotonic() - t_start
            logger.error(
                f"[yt] _fetch_info TIMED OUT after {elapsed:.2f}s | query={query!r}",
            )
            return None

        elapsed = time.monotonic() - t_start
        if result is None:
            logger.debug(
                f"[yt] _fetch_info returned None in {elapsed:.2f}s | query={query!r}",
            )
        else:
            logger.debug(
                f"[yt] _fetch_info success in {elapsed:.2f}s | title={result.get('title')!r}",
            )
        return result

    def _play_next(self, ctx: commands.Context) -> None:  # noqa: C901, PLR0915
        """Play the next song in the queue."""
        logger.debug(
            f"[yt] _play_next called | queue_size={len(self.queue)} | voice_client={self.voice_client is not None}",  # noqa: E501
        )

        if not self.queue or not self.voice_client:
            logger.debug(
                "[yt] _play_next: queue empty or no voice_client, clearing current",
            )
            self.current = None
            return

        self.current = self.queue.popleft()
        logger.debug(
            f"[yt] _play_next: popped song | title={self.current.get('title')!r} | queue remaining={len(self.queue)}",  # noqa: E501
        )

        async def _start_playing() -> None:
            if self.current is None:
                logger.debug("[yt] _start_playing: self.current is None, aborting")
                return

            title: str = self.current.get("title", "unknown")
            webpage_url: str | None = self.current.get("webpage_url")

            if not webpage_url:
                logger.error(
                    f"[yt] _start_playing: no webpage_url for {title!r}, aborting",
                )
                self.current = None
                return

            if not self.voice_client:
                logger.error("[yt] _start_playing: no voice client, aborting")
                self.current = None
                return

            logger.debug(f"[yt] _start_playing: starting yt-dlp pipe for {title!r}")

            ytdlp_cmd: list[str] = [
                "yt-dlp",
                "--format",
                "bestaudio[ext=m4a]/bestaudio/best",
                "--no-playlist",
                "--quiet",
                "--no-warnings",
                "--no-part",
                "-o",
                "-",
                webpage_url,
            ]

            logger.debug(f"[yt] _start_playing: cmd={' '.join(ytdlp_cmd)}")

            def _start_proc() -> subprocess.Popen[bytes]:
                """Start yt-dlp process in a thread to avoid blocking the event loop."""
                return subprocess.Popen(  # noqa: S603
                    ytdlp_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )

            try:
                proc: subprocess.Popen[bytes] = await asyncio.to_thread(_start_proc)
                self._ytdlp_proc = proc
            except Exception as e:  # noqa: BLE001
                logger.error(
                    f"[yt] _start_playing: failed to start yt-dlp process: {e}",
                )
                self.current = None
                await ctx.send(
                    embed=Embed(
                        title="⚠️ Playback Failed",
                        color=Color.red(),
                        description=f"Couldn't start playback for **{title}**, skipping.",
                    ),
                )
                self._play_next(ctx)
                return

            logger.debug(
                f"[yt] _start_playing: yt-dlp process started | pid={proc.pid}",
            )

            def after_playing(error: Exception | None) -> None:
                if error:
                    logger.error(f"[yt] after_playing error: {error}")
                else:
                    logger.debug(f"[yt] after_playing: finished cleanly for {title!r}")
                self._kill_ytdlp()
                asyncio.run_coroutine_threadsafe(
                    self._send_next_playing(ctx),
                    self.bot.loop,
                )

            try:
                source: PCMVolumeTransformer[FFmpegPCMAudio] = PCMVolumeTransformer(
                    FFmpegPCMAudio(
                        proc.stdout,  # pyright: ignore[reportArgumentType]
                        pipe=True,
                        **FFMPEG_OPTIONS,
                    ),
                    volume=0.5,
                )
                logger.debug(
                    "[yt] _start_playing: FFmpegPCMAudio source created successfully",
                )
                logger.debug(f"[yt] calling voice_client.play() for {title!r}")
                self.voice_client.play(source, after=after_playing)
                logger.debug(f"[yt] voice_client.play() returned for {title!r}")
            except Exception as e:  # noqa: BLE001
                logger.error(f"[yt] _start_playing: failed to start playback: {e}")
                self._kill_ytdlp()
                self.current = None
                await ctx.send(
                    embed=Embed(
                        title="⚠️ Playback Failed",
                        color=Color.red(),
                        description=f"Couldn't play **{title}**, skipping.",
                    ),
                )
                self._play_next(ctx)

        asyncio.run_coroutine_threadsafe(_start_playing(), self.bot.loop)
        logger.debug(
            "[yt] _play_next: _start_playing scheduled via run_coroutine_threadsafe",
        )

    async def _send_next_playing(self, ctx: commands.Context) -> None:
        """Send now playing embed and advance the queue.

        Args:
            ctx (commands.Context): Context.
        """
        logger.debug(f"[yt] _send_next_playing called | queue_size={len(self.queue)}")

        just_finished: str | None = self.current.get("title") if self.current else None
        logger.debug(f"[yt] _send_next_playing: just finished={just_finished!r}")

        self._play_next(ctx)

        await asyncio.sleep(0.5)

        if self.current:
            logger.debug(
                f"[yt] _send_next_playing: sending Now Playing embed for {self.current.get('title')!r}",  # noqa: E501
            )
            embed: Embed = Embed(
                title="🎵 Now Playing",
                color=Color.red(),
                description=f"**[{self.current['title']}]({self.current['webpage_url']})**",
            )
            embed.set_thumbnail(url=self.current.get("thumbnail"))
            embed.add_field(
                name="Duration",
                value=_format_duration(self.current.get("duration", 0)),
                inline=True,
            )
            await ctx.send(embed=embed)
        else:
            logger.debug("[yt] _send_next_playing: queue empty, nothing to play next")

    @tasks.loop(seconds=30)
    async def _auto_disconnect(self) -> None:
        """Disconnect from VC if idle for too long."""
        if self.voice_client is None or not self.voice_client.is_connected():
            self._idle_time = 0
            return

        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self._idle_time = 0
            return

        self._idle_time += 30
        logger.debug(
            f"[yt] _auto_disconnect: idle_time={self._idle_time}s / {AUTO_DISCONNECT_SECONDS}s",
        )

        if self._idle_time >= AUTO_DISCONNECT_SECONDS:
            logger.debug("[yt] _auto_disconnect: idle threshold reached, disconnecting")
            self.queue.clear()
            self.current = None
            self._kill_ytdlp()
            await self.voice_client.disconnect()
            self.voice_client = None
            self._idle_time = 0
            logger.debug("[yt] _auto_disconnect: disconnected and state cleared")

    @_auto_disconnect.before_loop
    async def before_auto_disconnect(self) -> None:
        """Wait until bot is ready before starting the loop."""
        await self.bot.wait_until_ready()

    @commands.hybrid_command(name="play", description="Play a YouTube video in VC")
    async def play(self, ctx: commands.Context, *, query: str) -> None:
        """Play a YouTube video by title or URL.

        Args:
            ctx (commands.Context): Context.
            query (str): Video title or URL to search for.
        """
        logger.debug(f"[yt] play command invoked | user={ctx.author} | query={query!r}")

        if not isinstance(ctx.author, Member) or ctx.author.voice is None:
            logger.debug("[yt] play: author not in VC, aborting")
            await ctx.send(
                embed=Embed(
                    title="❌ Not in VC",
                    color=Color.red(),
                    description="You need to be in a voice channel to use this command.",
                ),
                ephemeral=True,
            )
            return

        await ctx.defer()
        logger.debug("[yt] play: deferred response, starting _fetch_info")

        t_total: float = time.monotonic()
        info: dict | None = await self._fetch_info(query)

        if info is None:
            logger.debug(f"[yt] play: _fetch_info returned None for query={query!r}")
            await ctx.send(
                embed=Embed(
                    title="❌ Not Found",
                    color=Color.red(),
                    description=f"Could not find a video for **{query}**.",
                ),
            )
            return

        logger.debug(
            f"[yt] play: info fetched | title={info.get('title')!r} | total so far={time.monotonic() - t_total:.2f}s",  # noqa: E501
        )

        voice_channel: VoiceChannel | StageChannel | None = ctx.author.voice.channel
        logger.debug(
            f"[yt] play: voice_channel={getattr(voice_channel, 'name', None)!r}",
        )

        try:
            if self.voice_client is None or not self.voice_client.is_connected():
                logger.debug("[yt] play: connecting to voice channel")
                self.voice_client = (
                    await voice_channel.connect()  # pyright: ignore[reportOptionalMemberAccess]
                )
                logger.debug("[yt] play: connected to voice channel")
            elif self.voice_client.channel != voice_channel:
                logger.debug(
                    f"[yt] play: moving from {self.voice_client.channel!r} to {voice_channel!r}",
                )
                await self.voice_client.move_to(voice_channel)
        except (TimeoutError, ClientException, Forbidden) as e:
            logger.error(f"[yt] play: failed to join voice channel: {e}")
            await ctx.send(
                embed=Embed(
                    title="❌ Couldn't Join Voice Channel",
                    color=Color.red(),
                    description="I couldn't connect to your voice channel. Check my "
                    "voice permissions and try again.",
                ),
            )
            return

        self.queue.append(info)
        logger.debug(f"[yt] play: appended to queue | queue_size={len(self.queue)}")

        if not self.voice_client.is_playing() and not self.voice_client.is_paused():
            logger.debug("[yt] play: not currently playing, calling _play_next")
            self._play_next(ctx)
            embed: Embed = Embed(
                title="🎵 Now Playing",
                color=Color.red(),
                description=f"**[{info['title']}]({info['webpage_url']})**",
            )
        else:
            logger.debug(
                f"[yt] play: already playing, added to queue at position #{len(self.queue)}",
            )
            embed = Embed(
                title="➕ Added to Queue",  # noqa: RUF001
                color=Color.og_blurple(),
                description=f"**[{info['title']}]({info['webpage_url']})**",
            )
            embed.add_field(
                name="Position",
                value=f"**#{len(self.queue)}** in queue",
                inline=True,
            )

        embed.set_thumbnail(url=info.get("thumbnail"))
        embed.add_field(
            name="Duration",
            value=_format_duration(info.get("duration", 0)),
            inline=True,
        )
        logger.debug(
            f"[yt] play: sending response embed | total command time={time.monotonic() - t_total:.2f}s",  # noqa: E501
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="skip", description="Skip the current song")
    async def skip(self, ctx: commands.Context) -> None:
        """Skip the current song.

        Args:
            ctx (commands.Context): Context.
        """
        logger.debug(
            f"[yt] skip command invoked | user={ctx.author} | is_playing={self.voice_client.is_playing() if self.voice_client else False}",  # noqa: E501
        )

        if self.voice_client is None or not self.voice_client.is_playing():
            await ctx.send(
                embed=Embed(
                    title="❌ Nothing Playing",
                    color=Color.red(),
                    description="There is nothing currently playing.",
                ),
                ephemeral=True,
            )
            return

        logger.debug(
            f"[yt] skip: stopping current song | title={self.current.get('title') if self.current else None!r}",  # noqa: E501
        )
        self._kill_ytdlp()
        self.voice_client.stop()
        await ctx.send(
            embed=Embed(
                title="⏭️ Skipped",
                color=Color.og_blurple(),
                description="Skipped the current song.",
            ),
        )

    @commands.hybrid_command(name="pause", description="Pause the current song")
    async def pause(self, ctx: commands.Context) -> None:
        """Pause the current song.

        Args:
            ctx (commands.Context): Context.
        """
        logger.debug(f"[yt] pause command invoked | user={ctx.author}")

        if self.voice_client is None or not self.voice_client.is_playing():
            await ctx.send(
                embed=Embed(
                    title="❌ Nothing Playing",
                    color=Color.red(),
                    description="There is nothing currently playing.",
                ),
                ephemeral=True,
            )
            return

        self.voice_client.pause()
        logger.debug("[yt] pause: paused")
        await ctx.send(
            embed=Embed(
                title="⏸️ Paused",
                color=Color.og_blurple(),
                description="Paused the current song.",
            ),
        )

    @commands.hybrid_command(name="resume", description="Resume the current song")
    async def resume(self, ctx: commands.Context) -> None:
        """Resume the current song.

        Args:
            ctx (commands.Context): Context.
        """
        logger.debug(f"[yt] resume command invoked | user={ctx.author}")

        if self.voice_client is None or not self.voice_client.is_paused():
            await ctx.send(
                embed=Embed(
                    title="❌ Nothing Paused",
                    color=Color.red(),
                    description="There is nothing currently paused.",
                ),
                ephemeral=True,
            )
            return

        self.voice_client.resume()
        logger.debug("[yt] resume: resumed")
        await ctx.send(
            embed=Embed(
                title="▶️ Resumed",
                color=Color.og_blurple(),
                description="Resumed the current song.",
            ),
        )

    @commands.hybrid_command(
        name="stop",
        description="Stop playback and clear the queue",
    )
    async def stop(self, ctx: commands.Context) -> None:
        """Stop playback, clear the queue and disconnect.

        Args:
            ctx (commands.Context): Context.
        """
        logger.debug(
            f"[yt] stop command invoked | user={ctx.author} | queue_size={len(self.queue)}",
        )

        self.queue.clear()
        self.current = None
        self._idle_time = 0
        self._kill_ytdlp()

        if self.voice_client:
            logger.debug("[yt] stop: disconnecting voice client")
            await self.voice_client.disconnect()
            self.voice_client = None
            logger.debug("[yt] stop: disconnected")

        await ctx.send(
            embed=Embed(
                title="⏹️ Stopped",
                color=Color.og_blurple(),
                description="Stopped playback and cleared the queue.",
            ),
        )

    @commands.hybrid_command(name="queue", description="View the current song queue")
    async def queue_cmd(self, ctx: commands.Context) -> None:
        """Show the current queue.

        Args:
            ctx (commands.Context): Context.
        """
        logger.debug(
            f"[yt] queue command invoked | user={ctx.author} | queue_size={len(self.queue)} | current={self.current.get('title') if self.current else None!r}",  # noqa: E501
        )

        if not self.current and not self.queue:
            await ctx.send(
                embed=Embed(
                    title="📋 Queue",
                    color=Color.og_blurple(),
                    description="The queue is empty.",
                ),
            )
            return

        embed: Embed = Embed(title="📋 Queue", color=Color.og_blurple())

        if self.current:
            title: str = self.current["title"]
            if len(title) > MAX_TITLE_LENGTH:
                title = title[: MAX_TITLE_LENGTH - 3] + "..."
            embed.add_field(
                name="🎵 Now Playing",
                value=f"**[{title}]({self.current['webpage_url']})**",
                inline=False,
            )

        if self.queue:
            queue_lines: list[str] = []
            total_length: int = 0
            for i, item in enumerate(self.queue):
                if i >= MAX_QUEUE_DISPLAY:
                    break
                title = item["title"]
                if len(title) > MAX_TITLE_LENGTH:
                    title = title[: MAX_TITLE_LENGTH - 3] + "..."
                line: str = f"`{i + 1}.` **[{title}]({item['webpage_url']})**"
                total_length += len(line) + 1  # +1 for newline
                if total_length > MAX_EMBED_FIELD_LENGTH:
                    queue_lines.append("*...and more*")
                    break
                queue_lines.append(line)

            embed.add_field(
                name="Up Next",
                value="\n".join(queue_lines),
                inline=False,
            )
            if len(self.queue) > MAX_QUEUE_DISPLAY:
                embed.set_footer(
                    text=f"...and {len(self.queue) - MAX_QUEUE_DISPLAY} more",
                )

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="nowplaying", description="Show the current song")
    async def nowplaying(self, ctx: commands.Context) -> None:
        """Show the currently playing song.

        Args:
            ctx (commands.Context): Context.
        """
        logger.debug(
            f"[yt] nowplaying command invoked | user={ctx.author} | current={self.current.get('title') if self.current else None!r}",  # noqa: E501
        )

        if not self.current:
            await ctx.send(
                embed=Embed(
                    title="❌ Nothing Playing",
                    color=Color.red(),
                    description="Nothing is currently playing.",
                ),
                ephemeral=True,
            )
            return

        embed: Embed = Embed(
            title="🎵 Now Playing",
            color=Color.red(),
            description=f"**[{self.current['title']}]({self.current['webpage_url']})**",
        )
        embed.set_thumbnail(url=self.current.get("thumbnail"))
        embed.add_field(
            name="Duration",
            value=_format_duration(self.current.get("duration", 0)),
            inline=True,
        )
        embed.add_field(
            name="Queue Length",
            value=f"**{len(self.queue)}** song(s) remaining",
            inline=True,
        )
        await ctx.send(embed=embed)


def _format_duration(seconds: int) -> str:
    """Format seconds into mm:ss or hh:mm:ss.

    Args:
        seconds (int): Duration in seconds.

    Returns:
        str: Formatted duration string.
    """
    seconds = int(seconds)
    hours: int
    remainder: int
    minutes: int
    secs: int
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02}:{secs:02}"
    return f"{minutes}:{secs:02}"


async def setup(bot: DizznemBot) -> None:
    """Load the cog.

    Args:
        bot (DizznemBot): Dizznem Bot.
    """
    await bot.add_cog(YouTube(bot))
