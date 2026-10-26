import discord
import argparse
import asyncio
from discord.ext import commands
from modules import config, sounds
from modules.helper_functions import format_markdown, checkExists, checkGroup
from modules.database import GetDB

class ModTools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group()
    @commands.guild_only()
    @commands.has_role(config.owb_id)
    async def mod(self, ctx):
        """
        Top level command to invoke subcommands for moderators
        """
        if ctx.invoked_subcommand is None:
            await ctx.send(format_markdown("You need to use a subcommand with this command"), delete_after=10)
    
    # @mod.group()
    # @commands.guild_only()
    # async def move(self, ctx, *, kwargs):
    #     """
    #     Moves a file to a different folder.

    #     arguments:
    #      -s, --sound)
    #         The full sound name to be moved
    #     -f, --folder)
    #         The destination folder that the sound is to moved into. 
    #         Default is no folder (root).
        
    #     Files can be:
    #     - A standalone sound
    #     - A sound inside of a folder

    #     Usage example (moving a sound `soundname` from one folder `folder-a` to another folder `folder-b`):
    #     > 'mod move -s soundname folder-a -f folder-b

    #     Usage example (moving a sound `yuh` that doesn't belong to a folder, into folder `dank-sounds`):
    #     > 'mod move -s yuh -f dank-sounds

    #     Usage example (moving a sound `fart long` into no folder), the resulting soundname will be `long`, since it is being moved out of a folder.
    #     > 'mode move -s fart long
    #     """
    #     parser = argparse.ArgumentParser()
    #     parser.add_argument("-s", "--sound", help="Sound name to move", nargs='+', required=True)
    #     parser.add_argument("-f", "--folder", help="Destination folder to move the sound into")
    #     member = ctx.message.author
    #     command_args = str(kwargs).split(' ')
    #     try:
    #         args = parser.parse_args(command_args)
    #         print(args)


            

    #     except argparse.ArgumentError as e:
    #         print(e)
    #         pass
    #     except argparse.ArgumentTypeError as e:
    #         print(e)
    #         pass
    #     except SystemExit:
    #         pass


        
    # @mod.group()
    # @commands.guild_only()
    # async def yodel(self, ctx, member: discord.Member):
    #     """
    #     Puts the mentioned user in the yodeling room.

    #     Usage example:
    #     > mod yodel @Owen Wilson Bot
    #     """
    #     if not ctx.message.mentions:
    #         await ctx.reply(format_markdown("You need to @ a user."))
    #         return
    #     if len(ctx.message.mentions) > 1:
    #         await ctx.reply(format_markdown("You can only banish one user to the yodeling room. Relax, satan."))
    #         return
    #     await member.move_to(channel=ctx.guild.get_channel(811024159806849064))
    #     return



    # @mod.error # top level command error handing 
    # async def permissions_role_error(self, ctx, error):
    #     if isinstance(error, commands.MissingRole):
    #         await ctx.send(format_markdown("Error: command requires 'owb' role to use."))

async def setup(bot):
    await bot.add_cog(ModTools(bot))