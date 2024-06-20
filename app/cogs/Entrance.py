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
    async def on_voice_state_update(self, member: discord.Member, before, after) -> None:
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
                filepath = random.choice(sounds.alias_dict[__holiday_map__[month_day]]).path
            else:
                db = GetDB(config.database_path)

                db.cursor.execute("SELECT sound_id, content_type FROM entrance WHERE user_id=?", (uid,))
                data = db.cursor.fetchall()
                sound = data[0][0]
                if len(sound) == 0:
                    return

                if data[0][1] == 'folder':
                    filepath = random.choice(sounds.alias_dict[sound]).path
                else:
                    filepath = sounds.alias_dict[sound].path
                db.close()
            await asyncio.sleep(.7) # Let slow client connections get their ears open before we connect and play sounds

            vc = await channel.connect()
            vc.play(discord.FFmpegOpusAudio(filepath))
            with audioread.audio_open(filepath) as f:
                #Start Playing
                while vc.is_playing():
                    await asyncio.sleep(f.duration)
            await vc.disconnect()

            # set a key:value pair of userid and entrance sound in the Redis cache and set it to expire in 3600 seconds (1 hour)
            with config.redis_connection.pipeline() as pipe:
                pipe.set(key, str(sound))
                pipe.expire(key, 3600)
                pipe.execute()
        elif vc_after is None:
            return
        else:
            return


async def setup(bot):
    await bot.add_cog(Entrance(bot))