import discord
import pandas as pd
import traceback
import re
from typing import Optional
from datetime import date
from dateutil.relativedelta import relativedelta
from discord import app_commands
from discord.ext import commands
from modules import config, sounds
from modules.database import *
from modules.helper_functions import *
from modules.menus import ButtonMenu

class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    group = app_commands.Group(
        name="stats", 
        description="Example Usage: `/stats`"
    )
    
    @group.command(name="top")
    async def stats_top_command(self, interaction: discord.Interaction) -> None:
        """
        View the all-time top 10 played sounds.
        """
        try:
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
            await interaction.response.send_message(format_markdown(message))
            db.close()
            return


        except Exception as e:
            await interaction.response.send_message(format_markdown("ERROR: Sound file does not exist, please try using a specific sound if you think it does."), delete_after=5)
            return

    @group.command(name="sound")
    async def stats_sound_command(self, interaction: discord.Interaction, sound: str) -> None:
        """
        View the play count, author, and date added of a specific sound
        """
        if sound.lower() in ['hour', 'day', 'week', 'month', 'new']:
            return
        db = GetDB(config.database_path)
        db.cursor.execute("SELECT * FROM sounds WHERE sound_id=\""+sound+"\"")
        info = db.cursor.fetchall()
        user = await self.bot.fetch_user(info[0][3]) # Make the bot get a user object from the discord api, argument is unique user ID
        username = user.name
        embedvar = discord.Embed(title=f"{info[0][1]}", color=0x00ff00)
        embedvar.add_field(name="Plays", value=f"{str(info[0][4])}", inline=True)
        embedvar.add_field(name="Author", value=f"{username}", inline=True)
        embedvar.add_field(name="Date Created", value=f"{info[0][5]}", inline=False)
        embedvar.add_field(name="Parent Folder", value=f"{info[0][2]}", inline=True)
        await interaction.response.send_message(embed=embedvar)
        db.close()
        return
            
    @group.command(name="user")
    async def stats_user_command(self, interaction: discord.Interaction, user: str) -> None:
        # get the member IDs in the string
        matches = re.findall(r"<@!?([0-9]{15,20})>", user) # returns list of strings
        members = [interaction.guild.get_member(int(match)) for match in matches]
        for member in members:
            try:
                db = GetDB(config.database_path)
                db.cursor.execute("SELECT SUM(plays), COUNT(sound_id) FROM sounds WHERE author_id=\""+str(member.id)+"\"")
                info = db.cursor.fetchall()
                message = "User "+str(member.name)+" has added "+str(info[0][1])+" sounds with "+str(info[0][0])+" total plays!"
                db.cursor.execute("SELECT sound_id, plays FROM sounds WHERE author_id=\""+str(member.id)+"\" ORDER BY plays DESC LIMIT 10;")
                info = db.cursor.fetchall()
                message += "\n\n-------------------\n|TOP PLAYED SOUNDS|\n-------------------\n\n"
                i = 1
                print(info)
                for x in info:
                    message+=str(i)+") "+x[0]+" | Plays: "+str(x[1])+"\n"
                    i+=1
                await interaction.response.send_message(format_markdown(message))
                db.close()
        
            except Exception as e:
                print(e)
                await interaction.response.send_message(format_markdown(f"User {member.name} not found, they have not uploaded any sounds to the bot yet."))    


            # except Exception as e:
            #     await interaction.response.send_message(format_markdown("ERROR: Sound file does not exist, please try using a specific sound if you think it does."), delete_after=5)
            #     return

    @group.command(name="new")
    async def stats_new_subcommand(self, interaction: discord.Interaction) -> None:
        """
        Displays all the new sounds added from one month ago until today.
        Example Usage:
            `stats new`
        """
        try:
            mydate = date.today()
            last_month = mydate - relativedelta(months=+1)
            day_string = last_month.strftime("%Y-%m-%d")
            today_string = mydate.strftime("%Y-%m-%d")

            db = GetDB(config.database_path)
            db.cursor.execute("SELECT sound_id, date FROM sounds WHERE \"date\" >= ? ORDER BY date ASC", [day_string])
            info = db.cursor.fetchall()

            embeds = []
            message = f"---- SOUNDS ADDED FROM {day_string} - {today_string} ----"
            for item in info:
                line = f"| Date: {item[1]} | Name: {item[0]} |\n"
                if (len(message)+len(line)) > 1850:
                    embeds.append(format_markdown(message))
                    message = ""
                    message += line
                else:
                    message+=line
            if message:
                embeds.append(format_markdown(message))
            db.close()

            await interaction.response.send_message(content=embeds[0], view=ButtonMenu(embeds, 600))

        except Exception as e:
            print(e)
            await interaction.response.send_message((format_markdown("ERROR: Something broke for this specific command, maybe it will get fixed.")))
            return

# These commands are for checking aggregated, time-ranged stats from the Redis server #
# hourly, daily, weekly and monthly stats #
# Time is based on a rolling period from when the command is issued (i.e. 'daily' wil request stats 24 hours ago to current time) #

    @group.command(name="hour")
    async def stats_hour_subcommand(self, interaction: discord.Interaction) -> None:
        """
        Check the count of the played sounds from an hour until now

        Example Usage:
            `stats hour`
        """
        try:
            redis_metadata = config.redis_metadata
            # redis_metadata = redis.StrictRedis('localhost', 6379, db = 1, charset = "utf-8", decode_responses = True)
            stream_key = "plays:metadata"

            start_time = datetime.datetime.now() - datetime.timedelta(hours = 1)
            start_time = int(start_time.timestamp()*1000)


            query_result = redis_metadata.xrange(name = str(stream_key), min = start_time, max = "+")
            if not query_result:
                await interaction.response.send_message(format_markdown("Looks like there haven't been any sounds played within the last hour, time to get shitposting."))
                return

            dict_list = []
            for item in query_result:
                dict_list.append(item[1])
            foo = pd.DataFrame.from_dict(dict_list)
            bar = foo["sound_id"].value_counts()
            header = f"Sound Name          Plays\n-------------------------\n"
            await interaction.response.send_message(format_markdown(header + bar.head(n=10).to_string()))
            redis_metadata.close()

        except Exception as e:
            print(e)
            await interaction.response.send_message(format_markdown("Something happen"))
            return


    @group.command(name="day")
    async def stats_day_subcommand(self, interaction: discord.Interaction) -> None:
        """
        Check the count of the played sounds from 24 hours until now

        Example Usage:
            `stats day`
        """
        try:
            redis_metadata = config.redis_metadata
            # redis_metadata = redis.StrictRedis('localhost', 6379, db = 1, charset = "utf-8", decode_responses = True)
            stream_key = "plays:metadata"

            start_time = datetime.datetime.now() - datetime.timedelta(hours = 24)
            start_time = int(start_time.timestamp()*1000)


            query_result = redis_metadata.xrange(name = str(stream_key), min = start_time, max = "+")
            if not query_result:
                await interaction.response.send_message(format_markdown("Looks like there haven't been any sounds played within the day, time to get shitposting."))
                return

            dict_list = []
            for item in query_result:
                dict_list.append(item[1])
            foo = pd.DataFrame.from_dict(dict_list)
            bar = foo["sound_id"].value_counts()
            header = f"Sound Name          Plays\n-------------------------\n"
            await interaction.response.send_message(format_markdown(header + bar.head(n=10).to_string()))
            redis_metadata.close()

        except Exception as e:
            print(e)
            await interaction.response.send_message(format_markdown("Something happen"))
            return

    @group.command(name="week")
    async def stats_week_subcommand(self, interaction: discord.Interaction) -> None:
        """
        Check the count of the played sounds from 7 days ago until now

        Example Usage:
            `stats week`
        """
        try:
            redis_metadata = config.redis_metadata
            # redis_metadata = redis.StrictRedis('localhost', 6379, db = 1, charset = "utf-8", decode_responses = True)
            stream_key = "plays:metadata"

            start_time = datetime.datetime.now() - datetime.timedelta(hours = 168)
            start_time = int(start_time.timestamp()*1000)


            query_result = redis_metadata.xrange(name = str(stream_key), min = start_time, max = "+")
            if not query_result:
                await interaction.response.send_message(format_markdown("Looks like there haven't been any sounds played within the last week, time to get shitposting."))
                return

            dict_list = []
            for item in query_result:
                dict_list.append(item[1])
            foo = pd.DataFrame.from_dict(dict_list)
            bar = foo["sound_id"].value_counts()
            header = f"Sound Name          Plays\n-------------------------\n"
            await interaction.response.send_message(format_markdown(header + bar.head(n=10).to_string()))
            redis_metadata.close()

        except Exception as e:
            print(e)
            await interaction.response.send_message(format_markdown("Something happen"))
            return

    @group.command(name="month")
    async def stats_month_subcommand(self, interaction: discord.Interaction) -> None:
        """
        Check the count of the played sounds from the date from last month until now

        Example Usage:
            `stats month`
        """
        try:
            redis_metadata = config.redis_metadata
            # redis_metadata = redis.StrictRedis('localhost', 6379, db = 1, charset = "utf-8", decode_responses = True)
            stream_key = "plays:metadata"

            start_time = datetime.datetime.now() - datetime.timedelta(hours = 730)
            start_time = int(start_time.timestamp()*1000)


            query_result = redis_metadata.xrange(name = str(stream_key), min = start_time, max = "+")
            if not query_result:
                await interaction.response.send_message(format_markdown("Looks like there haven't been any sounds played within the last month, time to get shitposting."))
                return

            dict_list = []
            for item in query_result:
                dict_list.append(item[1])
            foo = pd.DataFrame.from_dict(dict_list)
            bar = foo["sound_id"].value_counts()
            header = f"Sound Name          Plays\n-------------------------\n"
            await interaction.response.send_message(format_markdown(header + bar.head(n=10).to_string()))
            redis_metadata.close()

        except Exception as e:
            print(e)
            await interaction.response.send_message(format_markdown("Something happen"))
            return

async def setup(bot):
    await bot.add_cog(Stats(bot))