import discord
import os
import re
from pathlib import Path
from discord.ext import commands
from modules import config, sounds
from modules.helper_functions import *
from modules.errors import *
from modules.aliases import DisplayablePath

# import for buttons and dropdown UI
from discord_components import DiscordComponents, ComponentsBot, Button, Select, SelectOption


# This cog allows users to query the sounds and folders that the bot has and returns messages 
# based on the function they call

class SoundsUtils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.guild_only()
    async def sounds(self, ctx):
        """
        View a list of categories and their sounds
        Will DM you a output of sounds, folders, and the sounds in the folders.
        Example Usage: `sounds`
        """
        member = ctx.message.author
        if ctx.message.mentions:
            try:
                user = ctx.message.mentions[0].id
                username = await self.bot.fetch_user(user)
                await member.send(f"-------------- SOUNDS FOR {username} --------------")
                db = GetDB(config.database_path)
                db.cursor.execute("SELECT sound_id FROM sounds WHERE author_id=? ORDER BY sound_id ASC", [user])
                info = db.cursor.fetchall()
                db.close()
                message = ""
                for item in info:
                    line = f"{item[0]}\n"
                    if (len(message)+len(line)) > 1994:
                        await member.send(format_markdown(message))
                        message =""
                    else:
                        message += line
                await member.send(format_markdown(message))
                await member.send("--------------------------------------------------")

            
            except Exception as e:
                await ctx.reply(format_markdown("ERROR: Something broke for this command, maybe it will get fixed."))
                return
        else:
            paths = DisplayablePath.make_tree(Path(config.sounds_path))
            msg_limit = 2000
            size = 0
            message = []
            msg = "```"
            for path in paths:
                message.append(path.displayable())
            for i in range(0, len(message)):
                block = message[i]
                if size+(len(block)+4) <= msg_limit:
                    msg+=('\n'+block)
                    size += len(block)+4
                    if i == len(message)-1:
                        msg+="""```"""
                        await member.send(msg)
                elif size+len(block) > msg_limit:
                    msg+="""```"""
                    await member.send(msg)
                    msg="```"
                    size=0


    @commands.command()
    @commands.guild_only()
    async def folders(self, ctx):
        """
        View the different sound categories or 
        view all the sounds in a specific category by specifying the category
        Example usage: `folders borat`
        """
        command = ctx.message.content.split(config.prefix)[1]
        message = ""
        if len(command.split()) > 1:
            path = os.listdir(config.sounds_path+'/'+command.split()[1])
            message += "📁 There are "+str(len(path))+" sounds in the "+command.split()[1]+" folder:\n\n"
            for item in list(path):
                message+=os.path.splitext(item)[0]+'\n'
            await ctx.send(format_markdown(message))
            return
        
        await ctx.reply("current categories:")
        for item in sounds.category_list:
            message += "📁" + item + '\n'
        await ctx.send(format_markdown(message))

def setup(bot):
    bot.add_cog(SoundsUtils(bot))