import discord
import random
import asyncio
from modules import config
from modules.database import GetDB
from pathlib import Path
from discord.ext.commands import CommandNotFound
from discord.utils import get


class Player:
    def __init__(self):
        pass

    async def play(self, ctx, sound_object, reverse=False):
        if not ctx.author.voice:
            await ctx.send("`You are not in a voice channel`")
            return
        voice_channel = ctx.author.voice.channel

        try:
            if sound_object.media is not None:
                media_path_dict = {
                    "images": config.images_path,
                    "gifs": config.gifs_path
                }
                file = discord.File(str(f"{media_path_dict[sound_object.media_parent_folder]}/{sound_object.media}"))
                await ctx.send(file=file, delete_after=10)
        except:
            pass
        ##################################################################################################
        

        try:
            voice_channel = await voice_channel.connect()

        except discord.Forbidden:
            await ctx.send(
                "Command raised error \"403 Forbidden\". Please check if bot has permission to join and speak in voice "
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

        # There is a 1 in 500th chance that it
        # will do a rickroll instead of the desired sound
        random_chance = random.randint(1, 500)
        if random_chance == 1:
            source = discord.FFmpegOpusAudio(f"{config.sounds_path}/rickroll.mp3")

        else:
            try:
                if reverse == True:
                    source = discord.FFmpegOpusAudio(sound_object.path, options='-af areverse')
                    # source = discord.FFmpegOpusAudio(self.filename, options='-af acrusher=1:.45:52:0:log')
                    # source = discord.FFmpegOpusAudio(self.filename, options='-af equalizer=f=50:width_type=o:width=2:g=20') bass boost ear rape 
                    # source = discord.FFmpegOpusAudio(self.filename, options='-af areverse') reverse 
                else:
                    source = discord.FFmpegOpusAudio(sound_object.path)

                # source = discord.FFmpegOpusAudio(filename, options='-af areverse')

            # edge case: missing file error
            except FileNotFoundError:
                await ctx.send(
                    "There was an issue with playing sound: File Not Found. Its possible that host of bot forgot to copy "
                    "over a file. If this error occured on official bot please use D.github to report issue.")
        try:
            voice_channel.play(source)
            
        # catching most common errors that can occur while playing effects
        except discord.Forbidden:
            await ctx.send("There was issue playing a sound effect. please check if bot has speak permission")
            await voice_channel.disconnect()
            return

        except TimeoutError:
            await ctx.send(
                "There was a error while attempting to play the sound effect (Timeout) its possible that either discord "
                "API or bot host has latency or network issues. Please try again later, if issues will continue contact "
                "bot owner")
            await voice_channel.disconnect()
            return

        except Exception as e:
            await ctx.send(
                "There was an issue playing the sound. Please try again later. If issues will continue contact bot owner.")
            await voice_channel.disconnect()
            print(f'Error trying to play a sound: {e}')
            return

        while voice_channel.is_playing():
            await asyncio.sleep(1)

        voice_channel.stop()

        await voice_channel.disconnect()

player = Player()