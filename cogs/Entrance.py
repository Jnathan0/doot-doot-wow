import asyncio 
import discord
import audioread
import datetime
import random
from datetime import date, datetime
from discord.ext import commands
from modules.database import GetDB
from modules.app_config import config
from modules.player import player
from modules.errors import *
from modules.helper_functions import *
from modules.aliases import sounds

# mapping of mm/dd to holidays
# TODO: Refactor this in a less coupled way, shouldn't be hardcoding this. 
__holiday_map__ = { "12-24" : "christmas",
                    "12-25" : "christmas",
                    "12-31" : "newyears",
                    "01-01" : "newyears"}

class Entrance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before, after):
        """ 
        Plays a user defined sound from the sounds catalog when the user joins the voice channel from not being in one before.
        If the uesr hasn't been in the voice for more than an hour, the entry sound will play when they connect.
        If the user connects to the voice channel before 60 mins from their initial entry, the sound will not play.
        """
        if member.bot: #dont use this feature for bots entering the voice channel
            return

        vc_before = before.channel
        vc_after = after.channel
        if vc_before == vc_after:
            return

        if vc_before is None:
            uid = member.id
            key = str(f"entrance:{uid}")
            if config.redis_connection.exists(key):
                return
            
            channel = member.voice.channel

            month_day = datetime.today().strftime("%m-%d")
            if month_day in __holiday_map__.keys():
                sound = random.choice(sounds.alias_dict[__holiday_map__[month_day]]).sound_id
            else:
                db = GetDB(config.database_path)

                db.cursor.execute("SELECT sound_id FROM entrance WHERE user_id=?", (uid,))
                sound = db.cursor.fetchall()[0][0]
                if len(sound) == 0:
                    return


            await asyncio.sleep(.7) # Let slow client connections get their ears open before we connect and play sounds

            vc = await channel.connect()
            vc.play(discord.FFmpegPCMAudio(sounds.alias_dict[sound].path))
            with audioread.audio_open(sounds.alias_dict[sound].path) as f:
                #Start Playing
                while vc.is_playing():
                    await asyncio.sleep(f.duration)
            await vc.disconnect()
            db.close()

            # set a key:value pair of userid and entrance sound in the Redis cache and set it to expire in 3600 seconds (1 hour)
            with config.redis_connection.pipeline() as pipe:
                pipe.set(key, str(sound))
                pipe.expire(key, 3600)
                pipe.execute()
        elif vc_after is None:
            return
        else:
            return

    @commands.group()
    @commands.guild_only()
    async def entrance(self, ctx):
        """
        Plays a sound when you enter a voice channel to announce your entry. 
        Will not play unless you have been out of voice for more than an hour since your last entry has played.
        """

    @entrance.group()
    @commands.guild_only()
    async def set(self, ctx, *args):
        """
        Set a sound to play when you enter a voice channel.
        Sound only plays if its been more than an hour since it last played. 
        Example Usage: `entrance set fart long`
        """
        args = list(args)
        if len(args) == 0:
            group = 'root'
            filename = args[0]
            sound_id = filename
        if len(args) == 1:
            group = args[0]
            filename = args[1]
            sound_id = f"{group} {filename}"
        try:
            if not checkExists(group, filename):
                raise Sound_Not_Exist_Error
            member_id = ctx.message.author.id
            db = GetDB(config.database_path)
            db.cursor.execute("DELETE FROM entrance WHERE user_id=?",(member_id,))
            db.cursor.execute("INSERT INTO entrance(sound_id, user_id, last_seen) VALUES(?,?,?)", (sound_id, member_id, "NULL"))
            db.commit()
            await ctx.message.author.send(format_markdown(f"Set entry sound to: \"{sound_id}\" for User {ctx.message.author.name}"))
            db.close()
            return

        except Sound_Not_Exist_Error as e:
            await ctx.message.author.send(format_markdown(e))
            return
        except Error as e:
            await ctx.message.author.send(format_markdown("Something happened, please notify the bot owner."))
            return

    @entrance.group()
    @commands.guild_only()
    async def remove(self, ctx):
        """
        Remove the entry sound for the user. 
        This will disable a sound playing when the user enters a voice chat. 
        Example Usage: `entrance remove`
        """
        member_id = ctx.message.author.id
        db = GetDB(config.database_path)
        db.cursor.execute("DELETE FROM entrance WHERE user_id=?", (member_id,))
        db.commit()
        await ctx.message.author.send(format_markdown("Removed entry sound."))
        db.close()
        return

    @entrance.group()
    @commands.guild_only()
    async def info(self, ctx):
        """
        DMs the user the entrance sound they have set.
        Example Usage: `entrance info`
        """
        member_id = ctx.message.author.id
        db = GetDB(config.database_path)
        db.cursor.execute("SELECT sound_id FROM entrance WHERE user_id=?", (member_id,))
        data = db.cursor.fetchall()
        if len(data) == 0:
            await ctx.message.author.send(format_markdown("You don't have an entry sound set."))
            return
        else:
            await ctx.message.author.send(f"> {ctx.author.mention} your entrance sound is \"{data[0][0]}\"")
        db.close()

def setup(bot):
    bot.add_cog(Entrance(bot))