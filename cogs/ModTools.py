import discord
import argparse
from discord.ext import commands
from modules import config, sounds
from modules.helper_functions import format_markdown, checkExists, checkGroup
from modules.database import GetDB
# import for buttons and dropdown UI
from discord_components import DiscordComponents, ComponentsBot, Button, Select, SelectOption

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
    
    @mod.group()
    @commands.guild_only()
    async def move(self, ctx, *, kwargs):
        """
        Moves a file to a different folder.

        arguments:
         -s, --sound)
            The full sound name to be moved
        -f, --folder)
            The destination folder that the sound is to moved into. 
            Default is no folder (root).
        
        Files can be:
        - A standalone sound
        - A sound inside of a folder

        Usage example (moving a sound `soundname` from one folder `folder-a` to another folder `folder-b`):
        > 'mod move -s soundname folder-a -f folder-b

        Usage example (moving a sound `yuh` that doesn't belong to a folder, into folder `dank-sounds`):
        > 'mod move -s yuh -f dank-sounds

        Usage example (moving a sound `fart long` into no folder), the resulting soundname will be `long`, since it is being moved out of a folder.
        > 'mode move -s fart long
        """
        parser = argparse.ArgumentParser()
        parser.add_argument("-s", "--sound", help="Sound name to move", nargs='+', required=True)
        parser.add_argument("-f", "--folder", help="Destination folder to move the sound into")
        member = ctx.message.author
        command_args = str(kwargs).split(' ')
        try:
            args = parser.parse_args(command_args)
            print(args)


            

        except argparse.ArgumentError as e:
            print(e)
            pass
        except argparse.ArgumentTypeError as e:
            print(e)
            pass
        except SystemExit:
            pass


        
    @commands.guild_only()
    @mod.group()
    async def delete(self, ctx, *, kwargs):
        """
        Delete a sound.
        If the sound is the only item inside of the folder, the folder will be deleted as well. 
        The sound must be one that the user has originally uploaded (users cannot delete other users sounds)..

        Usage example (Deleting a sound `yuh` that is not in a folder):
        > 'mod delete yuh

        Usage exapmle (Deleting a sound `long` that is inside of a folder `fart`):
        > 'mod delete fart long
        """
        # TODO: - check if the message author is the owner of the sound (discord id)
        #       - Remove sound from db and file system, use database transactions to rollback
        #       - Cleanup residual folders if they are empty after sound deletion 
        #       - Remove existing soundIDs from other tables (quicksounds, entry cache, entry sound tables)
        #       - Generate a message to send to members that use this sound for the above datastructures
        parser = argparse.ArgumentParser()
        parser.add_argument('sound', help="Sound name to delete", nargs='+')
        member = ctx.message.author
        command_args = str(kwargs).split(' ')
        try:
            args = parser.parse_args(command_args)
            print(args)
            if len(args.sound) == 1:
                sound_id = f"{args.sound[0]}"
                group = "root"
            else:
                sound_id = f"{args.sound[0]} {args.sound[1]}"
                group = args.sound[0]
            
            if checkExists(group, sound_id):
                db = GetDB(config.database_path)
                data = db.cursor.execute(f"SELECT EXISTS(SELECT sound_name FROM sounds WHERE ")
            else:
                await ctx.reply(format_markdown(f"Error: {sound_id} does not exist."), delete_after=10)


            
        except argparse.ArgumentError as e:
            print(e)
            pass
        except argparse.ArgumentTypeError as e:
            print(e)
            pass
        except SystemExit:
            pass

    @mod.group()
    @commands.guild_only()
    async def yodel(self, ctx, member: discord.Member):
        """
        Puts the mentioned user in the yodeling room.

        Usage example:
        > mod yodel @Owen Wilson Bot
        """
        if not ctx.message.mentions:
            await ctx.reply(format_markdown("You need to @ a user."))
            return
        if len(ctx.message.mentions) > 1:
            await ctx.reply(format_markdown("You can only banish one user to the yodeling room. Relax, satan."))
            return
        await member.move_to(channel=ctx.guild.get_channel(811024159806849064))
        return



    @mod.error # top level command error handing 
    async def permissions_role_error(self, ctx, error):
        if isinstance(error, commands.MissingRole):
            await ctx.send(format_markdown("Error: command requires 'owb' role to use."))

def setup(bot):
    bot.add_cog(ModTools(bot))