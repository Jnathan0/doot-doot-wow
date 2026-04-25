import discord
import random
import asyncio
from modules import config

_FFMPEG_BEFORE_OPTS = '-nostdin -hide_banner -loglevel error'
_FFMPEG_OPTS = '-vn'


def _make_source(sound_object, reverse):
    # 1-in-500 chance of a rickroll instead of the requested sound
    if random.randint(1, 500) == 1:
        return discord.FFmpegOpusAudio(
            f"{config.sounds_path}/rickroll.mp3",
            before_options=_FFMPEG_BEFORE_OPTS,
            options=_FFMPEG_OPTS,
        )
    opts = f'-af areverse {_FFMPEG_OPTS}' if reverse else _FFMPEG_OPTS
    return discord.FFmpegOpusAudio(
        sound_object.path,
        before_options=_FFMPEG_BEFORE_OPTS,
        options=opts,
    )


async def _maybe_send_media(ctx, sound_object):
    try:
        if sound_object.media is not None:
            media_path_dict = {
                "images": config.images_path,
                "gifs": config.gifs_path,
            }
            file = discord.File(f"{media_path_dict[sound_object.media_parent_folder]}/{sound_object.media}")
            await ctx.send(file=file, delete_after=10)
    except Exception:
        pass


class Player:
    def __init__(self):
        pass

    async def play(self, ctx, sound_object, reverse=False):
        if not ctx.author.voice:
            await ctx.send("`You are not in a voice channel`")
            return
        voice_channel = ctx.author.voice.channel

        # Start ffmpeg before connecting so it warms up during the Discord handshake.
        try:
            source = _make_source(sound_object, reverse)
        except FileNotFoundError:
            await ctx.send(
                "There was an issue with playing sound: File Not Found. Its possible that host of bot forgot to copy "
                "over a file. If this error occured on official bot please use D.github to report issue.")
            return

        try:
            voice_client, _ = await asyncio.gather(
                voice_channel.connect(),
                _maybe_send_media(ctx, sound_object),
            )
        except discord.Forbidden:
            await ctx.send(
                'Command raised error "403 Forbidden". Please check if bot has permission to join and speak in voice '
                "channel")
            return
        except TimeoutError:
            await ctx.send(
                "There was an error while joining channel (Timeout). It's possible that either Discord API or bot host "
                "has latency/connection issues. Please try again later if issues will continue contact bot owner.")
            return
        except discord.ClientException:
            await ctx.send("I am already playing a sound! Please wait to the current sound is done playing!")
            return
        except Exception as e:
            await ctx.send(
                "There was an error processing your request. Please try again. If issues will continue contact bot owner.")
            print(f'Error trying to join a voicechannel: {e}')
            return

        done = asyncio.Event()
        loop = asyncio.get_running_loop()

        try:
            voice_client.play(source, after=lambda _: loop.call_soon_threadsafe(done.set))
        except discord.Forbidden:
            await ctx.send("There was issue playing a sound effect. please check if bot has speak permission")
            asyncio.create_task(voice_client.disconnect())
            return
        except TimeoutError:
            await ctx.send(
                "There was a error while attempting to play the sound effect (Timeout) its possible that either discord "
                "API or bot host has latency or network issues. Please try again later, if issues will continue contact "
                "bot owner")
            asyncio.create_task(voice_client.disconnect())
            return
        except Exception as e:
            await ctx.send(
                "There was an issue playing the sound. Please try again later. If issues will continue contact bot owner.")
            asyncio.create_task(voice_client.disconnect())
            print(f'Error trying to play a sound: {e}')
            return

        await done.wait()
        asyncio.create_task(voice_client.disconnect())


player = Player()
