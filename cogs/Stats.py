import discord
import pandas as pd
import traceback
from datetime import date
from dateutil.relativedelta import relativedelta
from discord.ext import commands
from modules import config, sounds
from modules.database import *
from modules.helper_functions import *

class Stats(commands.Cog, commands.Command):
    def __init__(self, bot):
        self.bot = bot

    @commands.group()
    @commands.guild_only()
    async def stats(self,ctx):
        """
        View the play count, author, and date added of a specific sound
        or the amount of sounds and plays for a user
        Example Usage: `stats`
        """
        command = ctx.message.content.split(config.prefix)[1]
        if command == "stats":
            db = GetDB(config.database_path)
            db.cursor.execute("SELECT COUNT(sound_id) FROM sounds")
            info = db.cursor.fetchall()
            message = "Total Sounds: " + str(info[0][0])+"\n"
            db.cursor.execute("SELECT sound_id, plays from sounds ORDER BY plays DESC LIMIT 10")
            info = db.cursor.fetchall()
            message += "\n----------------------\n|TOP 10 PLAYED SOUNDS|\n----------------------\n\n"
            i = 1
            for x in info:
                message+=str(i)+") "+x[0]+" | Plays: "+str(x[1])+"\n"
                i+=1
            await ctx.reply(format_markdown(message))
            db.close()
            return
            
        elif ctx.message.mentions: #Check if the argument is an @mention to a guild member
            try:
                user = ctx.message.mentions[0].id #Strip just the ID number from the mention string
                db = GetDB(config.database_path)
                db.cursor.execute("SELECT SUM(plays), COUNT(sound_id) FROM sounds WHERE author_id=\""+str(user)+"\"")
                info = db.cursor.fetchall()
                message = "User "+str(ctx.message.mentions[0])+" has added "+str(info[0][1])+" sounds with "+str(info[0][0])+" total plays!"
                db.cursor.execute("SELECT sound_id, plays FROM sounds WHERE author_id=\""+str(user)+"\" ORDER BY plays DESC LIMIT 10;")
                info = db.cursor.fetchall()
                message += "\n\n-------------------\n|TOP PLAYED SOUNDS|\n-------------------\n\n"
                i = 1
                for x in info:
                    message+=str(i)+") "+x[0]+" | Plays: "+str(x[1])+"\n"
                    i+=1
                await ctx.reply(format_markdown(message))
                db.close()
                return
            
            except Exception as e:
                await ctx.reply(format_markdown("ERROR: User not found, are you sure they have added anything to the bot?"))    
        else:
            try:
                sound_id = command.split("stats ")[1]
                if sound_id.lower() in ['hour', 'day', 'week', 'month', 'new']:
                    return
                db = GetDB(config.database_path)
                db.cursor.execute("SELECT * FROM sounds WHERE sound_id=\""+sound_id+"\"")
                info = db.cursor.fetchall()
                user = await self.bot.fetch_user(info[0][3]) # Make the bot get a user object from the discord api, argument is unique user ID
                username = user.name
                embedvar = discord.Embed(title=f"{info[0][1]}", color=0x00ff00)
                embedvar.add_field(name="Plays", value=f"{str(info[0][4])}", inline=True)
                embedvar.add_field(name="Author", value=f"{username}", inline=True)
                embedvar.add_field(name="Date Created", value=f"{info[0][5]}", inline=False)
                embedvar.add_field(name="Parent Folder", value=f"{info[0][2]}", inline=True)
                # message = info[0][1] + "\n\nDate Created: "+info[0][5]+"\nAuthor: "+username+"\nParent folder: "+info[0][2]+"\nPlays: "+str(info[0][4])
                await ctx.send(embed=embedvar)
                db.close()
                return

            except Exception as e:
                await ctx.send(format_markdown("ERROR: Sound file does not exist, please try using a specific sound if you think it does."), delete_after=5)
                return

    @stats.group()
    @commands.guild_only()
    async def new(self, ctx):
        """
        Displays all the new sounds added from one month ago until today.
        Example Usage:
            `stats new`
        """
        try:
            member = ctx.message.author

            mydate = date.today()
            last_month = mydate - relativedelta(months=+1)
            day_string = last_month.strftime("%Y-%m-%d")
            today_string = mydate.strftime("%Y-%m-%d")


            db = GetDB(config.database_path)
            db.cursor.execute("SELECT sound_id, date FROM sounds WHERE \"date\" >= ? ORDER BY date ASC", [day_string])
            info = db.cursor.fetchall()
            await member.send(f"------ SOUNDS ADDED FROM {day_string} - {today_string} ------")
            message = ""
            for item in info:
                line = f"| Date: {item[1]} | Name: {item[0]} |\n"
                if (len(message)+len(line)) > 1994:
                    await member.send(format_markdown(message))
                    message = ""
                    message += line
                else:
                    message+=line
            await member.send(format_markdown(message))
            await member.send("--------------------------")
            db.close()

        except Exception as e:
            print(e)
            print(traceback.format_exec())
            await ctx.send(format_markdown("ERROR: Something broke for this specific command, maybe it will get fixed."))
            return

# These commands are for checking aggregated, time-ranged stats from the Redis server #
# hourly, daily, weekly and monthly stats #
# Time is based on a rolling period from when the command is issued (i.e. 'daily' wil request stats 24 hours ago to current time) #

    @stats.group()
    @commands.guild_only()
    async def hour(self, ctx):
        """
        Check the count of the played sounds from an hour until now

        Example Usage:
            `stats hour`
        """
        try:
            member = ctx.message.author
            redis_metadata = config.redis_metadata
            # redis_metadata = redis.StrictRedis('localhost', 6379, db = 1, charset = "utf-8", decode_responses = True)
            stream_key = "plays:metadata"

            start_time = datetime.datetime.now() - datetime.timedelta(hours = 1)
            start_time = int(start_time.timestamp()*1000)


            query_result = redis_metadata.xrange(name = str(stream_key), min = start_time, max = "+")
            if not query_result:
                await member.send(format_markdown("Looks like there haven't been any sounds played within the last hour, time to get shitposting."))
                return

            dict_list = []
            for item in query_result:
                dict_list.append(item[1])
            foo = pd.DataFrame.from_dict(dict_list)
            bar = foo["sound_id"].value_counts()
            header = f"Sound Name          Plays\n-------------------------\n"
            await ctx.reply(format_markdown(header + bar.head(n=10).to_string()))
            redis_metadata.close()

        except Exception as e:
            await ctx.reply(format_markdown("Something happen"))
            return


    @stats.group()
    @commands.guild_only()
    async def day(self, ctx):
        """
        Check the count of the played sounds from 24 hours until now

        Example Usage:
            `stats day`
        """
        try:
            member = ctx.message.author
            redis_metadata = config.redis_metadata
            # redis_metadata = redis.StrictRedis('localhost', 6379, db = 1, charset = "utf-8", decode_responses = True)
            stream_key = "plays:metadata"

            start_time = datetime.datetime.now() - datetime.timedelta(hours = 24)
            start_time = int(start_time.timestamp()*1000)


            query_result = redis_metadata.xrange(name = str(stream_key), min = start_time, max = "+")
            if not query_result:
                await member.send(format_markdown("Looks like there haven't been any sounds played within the day, time to get shitposting."))
                return

            dict_list = []
            for item in query_result:
                dict_list.append(item[1])
            foo = pd.DataFrame.from_dict(dict_list)
            bar = foo["sound_id"].value_counts()
            header = f"Sound Name          Plays\n-------------------------\n"
            await ctx.reply(format_markdown(header + bar.head(n=10).to_string()))
            redis_metadata.close()

        except Exception as e:
            await ctx.reply(format_markdown("Something happen"))
            return

    @stats.group()
    @commands.guild_only()
    async def week(self, ctx):
        """
        Check the count of the played sounds from 7 days ago until now

        Example Usage:
            `stats week`
        """
        try:
            member = ctx.message.author
            redis_metadata = config.redis_metadata
            # redis_metadata = redis.StrictRedis('localhost', 6379, db = 1, charset = "utf-8", decode_responses = True)
            stream_key = "plays:metadata"

            start_time = datetime.datetime.now() - datetime.timedelta(hours = 168)
            start_time = int(start_time.timestamp()*1000)


            query_result = redis_metadata.xrange(name = str(stream_key), min = start_time, max = "+")
            if not query_result:
                await member.send(format_markdown("Looks like there haven't been any sounds played within the last week, time to get shitposting."))
                return

            dict_list = []
            for item in query_result:
                dict_list.append(item[1])
            foo = pd.DataFrame.from_dict(dict_list)
            bar = foo["sound_id"].value_counts()
            header = f"Sound Name          Plays\n-------------------------\n"
            await ctx.reply(format_markdown(header + bar.head(n=10).to_string()))
            redis_metadata.close()

        except Exception as e:
            await ctx.reply(format_markdown("Something happen"))
            return

    @stats.group()
    @commands.guild_only()
    async def month(self, ctx):
        """
        Check the count of the played sounds from the date from last month until now

        Example Usage:
            `stats month`
        """
        try:
            member = ctx.message.author
            redis_metadata = config.redis_metadata
            # redis_metadata = redis.StrictRedis('localhost', 6379, db = 1, charset = "utf-8", decode_responses = True)
            stream_key = "plays:metadata"

            start_time = datetime.datetime.now() - datetime.timedelta(hours = 730)
            start_time = int(start_time.timestamp()*1000)


            query_result = redis_metadata.xrange(name = str(stream_key), min = start_time, max = "+")
            if not query_result:
                await member.send(format_markdown("Looks like there haven't been any sounds played within the last month, time to get shitposting."))
                return

            dict_list = []
            for item in query_result:
                dict_list.append(item[1])
            foo = pd.DataFrame.from_dict(dict_list)
            bar = foo["sound_id"].value_counts()
            header = f"Sound Name          Plays\n-------------------------\n"
            await ctx.reply(format_markdown(header + bar.head(n=10).to_string()))
            redis_metadata.close()

        except Exception as e:
            await ctx.reply(format_markdown("Something happen"))
            return

def setup(bot):
    bot.add_cog(Stats(bot))