import discord
import asyncio
from discord.ext import commands
from modules import config, sounds, player
from modules.helper_functions import *
from modules.errors import *
from modules.metadata import update_metadata

# import for buttons and dropdown UI
from discord_components import DiscordComponents, ComponentsBot, Button, Select, SelectOption


# This cog allows users to query the sounds and folders that the bot has and returns messages 
# based on the function they call

class Quicksounds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
            db.cursor.execute(f"SELECT sound_id, reverse FROM quicksounds WHERE user_id={member} AND alias={command}")
            data = db.cursor.fetchall()[0]
            reverse = data[1]
            sound = data[0]
            db.close()
            if len(sound) == 0:
                await ctx.message.author.send(format_markdown(f"You dont have a sound set for slot {command}."))
                return
            else:

                await player.play(ctx, sounds.alias_dict[sound], reverse=reverse)
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
    async def set(self, ctx, *args):
        """
        Set a sound to a quicksound slot via UI prompt.
        Example Usage: `quicksounds set fart long`
        """
        member = ctx.message.author.id
        input = list(args)
        reverse_opt = 0 # use int for sqlite3 because bools end up as ints anyway
        # if the reverse option is found as the last input of the string, set reverse opt
        # and set input list to be without the option
        if input[-1] == '-':
            reverse_opt = 1 # use int for sqlite3 because bools end up as ints anyway
            input = input[:-1]
        if len(input) == 2:
            group = input[0]
            filename = input[1]
        if len(input) == 1:
            group = "root"
            filename = input[0]
        try:
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

            # obj = Quicksound(ctx, command)
            if not checkExists(group, filename):
                raise Sound_Not_Exist_Error

            sound_id = ' '.join(input)
            print(config.database_path)
            config.worker_queue.enqueue(update_quicksound, member, int(quicksound_slot.values[0]), sound_id, reverse_opt)

            # config.worker_queue.enqueue(update_quicksound, member, obj.number, obj.sound)
            message = f"Quicksound {quicksound_slot.values[0]} updated to \"{sound_id}\"."
            if reverse_opt:
                message = f"Quicksound {quicksound_slot.values[0]} updated to \"{sound_id}\", with reversed playback."
            await ctx.message.author.send(format_markdown(message))

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
        
        except asyncio.TimeoutError as e:
            await message.delete()
            return
                
def setup(bot):
    bot.add_cog(Quicksounds(bot))