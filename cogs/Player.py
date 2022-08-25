import random
import os
import asyncio
import random
from discord.ext import commands
from modules import config, sounds, player
from modules.metadata import update_metadata
from modules.helper_functions import *

class Player(commands.Cog, commands.Command):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=sounds.aliases, hidden=True)
    @commands.guild_only()
    async def master_command(self, ctx):
        server = ctx.message.guild.voice_client
        if server:
            return
        user_id = int(ctx.message.author.id)
        command = ctx.message.content.split(config.prefix)[1]
        reverse = False
        if command[-1] == config.reverse_char:
            command = command.split(str(config.sub_cmd_sep+config.reverse_char))[0]
            reverse = True
        sound_object = sounds.alias_dict[command]

        if isinstance(sound_object, list):
            sound_object = random.choice(sound_object)
            sound_id = sound_object.sound_id
            call_type = "random"
        else:
            sound_id = command
            call_type = "direct"
        
        # Rickroll logic
        random_chance = random.randint(1, 500)
        if random_chance == 1:
            await player.play(ctx, sounds.alias_dict['rickroll'], reverse = False)
            update_rickroll(user_id)
        else:
            await player.play(ctx, sound_object, reverse)
            config.worker_queue.enqueue(update_metadata, user_id, sound_id, call_type)
            config.sounds_queue.enqueue(increment_playcount, sound_id)


    @commands.command(aliases=['r'])
    @commands.guild_only()
    async def random(self, ctx):
        """
        Plays a random sound from the /sounds directory.
        Chooses a sound in the root of the /sounds directory or chooses a folder to pick a sound from.
        Deletes the calling message from discord.
        """
        await ctx.message.delete()
        server = ctx.message.guild.voice_client
        
        if server:
            return
        member = ctx.message.author.id
        command = ctx.message.content.split(config.prefix)[1]

        reverse = False
        if command[-1] == config.reverse_char:
            command = command.split(str(config.sub_cmd_sep+config.reverse_char))[0]
            reverse = True
        random_path = sounds.alias_dict[random.choice(list(sounds.alias_dict.keys()))]
        if isinstance(random_path, list):
            file_path = random.choice(random_path)
            sound_id = file_path.sound_id
            random_path = file_path
            config.sounds_queue.enqueue(increment_playcount, sound_id)
        else:
            sound_id = random_path.sound_id
            config.sounds_queue.enqueue(increment_playcount, sound_id)

        # Rickroll logic
        random_chance = random.randint(1, 500)
        random_chance = 1
        if random_chance == 1:
            await player.play(ctx, sounds.alias_dict['rickroll'], reverse = False)
            update_rickroll(member)
            await post_rickroll_update(ctx)
        else:
            msg = await ctx.send(format_markdown("Random sound: "+str(sound_id)))
            await player.play(ctx, random_path, reverse)
            config.worker_queue.enqueue(update_metadata, member, str(sound_id), call_type = "random")
            await asyncio.sleep(10)
            await msg.delete()


    @commands.command(aliases=[])
    @commands.guild_only()
    async def stop(self, ctx):
        """
        Stops the currently playing sound if there is one. 
        """
        await ctx.message.delete()
        server = ctx.message.guild.voice_client
        if server:
            await server.disconnect()
        else:
            await ctx.send(format_markdown("I am not in a voice channel.."))

def setup(bot):
    bot.add_cog(Player(bot))