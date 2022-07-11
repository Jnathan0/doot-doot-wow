import discord
import os
import re
from pathlib import Path
from discord.ext import commands
from modules import config, sounds, player
from modules.helper_functions import *
from modules.errors import *
from modules.aliases import DisplayablePath
from modules.metadata import update_metadata

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

    @commands.group(aliases=['1', '2', '3'])
    @commands.guild_only()
    async def quicksounds(self, ctx):
        """
        Assign a sound to numerical 1, 2 and 3 numbers as a shortcut to play a sound
        (Aka instead of typing a sound name out, just type the number)
        Example usage (for the slot 1 quicksound): `1`
        """
        await ctx.message.delete()
        command = ctx.message.content.split(config.prefix)[1]
        member = ctx.message.author.id
        if command in ['1','2','3']:
            server = ctx.message.guild.voice_client
            if server:
                return
            db = GetDB(config.database_path)
            db.cursor.execute(f"SELECT sound_id FROM quicksounds WHERE user_id={member} AND alias={command}")
            sound = db.cursor.fetchall()[0][0]
            db.close()
            if len(sound) == 0:
                await ctx.message.author.send(format_markdown(f"You dont have a sound set for slot {command}."))
                return
            else:

                await player.play(ctx, sounds.alias_dict[sound])
                config.sounds_queue.enqueue(increment_playcount, sound)
                config.worker_queue.enqueue(update_metadata, member, sound, call_type = "direct")

    @quicksounds.group()
    @commands.guild_only()
    async def info(self, ctx):
        """
        Get info on the current quicksounds set for the user
        Example Usage: `quicksounds info`
        """
        member = ctx.message.author.id
        db = GetDB(config.database_path)
        db.cursor.execute(f"SELECT alias,sound_id FROM QUICKSOUNDS WHERE user_id={member} ORDER BY alias")
        data = db.cursor.fetchall()
        embedvar = discord.Embed(title=f"{ctx.message.author.name}'s Quicksounds", color=0x00ff00)
        for item in data:
            embedvar.add_field(name=f"Slot {item[0]}", value=f"{item[1]}")
        await ctx.message.author.send(embed=embedvar)
        db.close()

    @quicksounds.group()
    @commands.guild_only()
    async def set(self ,ctx, *, argument):
        """
        Set a sound to a quicksound slot via UI prompt.
        Example Usage: `quicksounds set fart long`
        """
        member = ctx.message.author.id
        input_sound = str(argument).split(' ')
        if len(input_sound) == 2:
            group = input_sound[0]
            filename = input_sound[1]
        if len(input_sound) == 1:
            group = "root"
            filename = input_sound[0]

        message = await ctx.send(
            # What the fuck is this, javascript?
            "Select quicksound slot to add sound to.",
            components = [
                Select(
                    placeholder = "Select a quicksound slot.",
                    options = [ 
                        SelectOption(label = "1", value = 1),
                        SelectOption(label = "2", value = 2),
                        SelectOption(label = "3", value = 3)
                    ]
                )
            ])
        quicksound_slot = await self.bot.wait_for("select_option", timeout = 30.0)
        await message.delete()
        try:
            # obj = Quicksound(ctx, command)
            if not checkExists(group, filename):
                raise Sound_Not_Exist_Error

            config.worker_queue.enqueue(update_quicksound, member, int(quicksound_slot.values[0]), argument)

            # config.worker_queue.enqueue(update_quicksound, member, obj.number, obj.sound)
            await ctx.message.author.send(format_markdown(f"Quicksound {quicksound_slot.values[0]} updated to \"{argument}\"."))

            # await ctx.message.author.send(format_markdown(f"Quicksound {obj.number} updated to \"{obj.sound}\"."))

        except No_Argument_Error as e:
            await ctx.message.author.send(format_markdown(e))
            return

        except Slot_Out_Of_Bounds_Error as e:
            await ctx.message.author.send(format_markdown(e))
            return

        except Generic_Error as e:
            await ctx.message.author.send(format_markdown(e))
            return
        
        except Sound_Not_Exist_Error as e:
            await ctx.message.author.send(format_markdown(e))
            return

        except Error as e:
            await ctx.message.author.send(format_markdown("Something happened, please notify the bot owner."))
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
    bot.add_cog(SoundsUtils(bot))