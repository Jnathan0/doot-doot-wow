import discord
import os
import re
from typing import List
from typing import Optional
from pathlib import Path
from discord.ext import commands
from discord import ui
from discord import app_commands
from modules import config, sounds, player
from modules.menus import ButtonMenu
from modules.helper_functions import *
from modules.errors import *
from modules.aliases import DisplayablePath
from modules.metadata import update_metadata
from modules.quicksounds import Quicksound

# This cog allows users to query the sounds and folders that the bot has and returns messages 
# based on the function they call

class SoundsUtils(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    entrance_group = app_commands.Group(
        name="entrance",
        description="Example Usage: `/entrance`"
    )

    quicksounds_group = app_commands.Group(
        name="quicksounds",
        description="Example Usage: /quicksounds"
    )


    @app_commands.command(name="sounds")
    @app_commands.describe(user="@username")
    async def sounds_command(self, interaction: discord.Interaction, user: Optional[str]) -> None:
        """
        View a list of folders and their sounds
        """
        await interaction.response.defer(thinking=True)
        if user:
            matches = re.findall(r"<@!?([0-9]{15,20})>", user) # returns list of strings
            if not matches:
                await interaction.followup.send(format_markdown("No user mention was found, please mention a user for this option (e.x @Owen Wilson Bot)"), ephemeral=True)
                return
            if len(matches) != 1:
                await interaction.follwup.send(format_markdown(f"Error: too many user mentions, please only mention one user for this command"), ephemeral=True)
                return
            member = interaction.guild.get_member(int(matches[0]))
            try:
                user = member.id
                db = GetDB(config.database_path)
                db.cursor.execute(f"SELECT sound_id FROM sounds WHERE author_id={user} ORDER BY sound_id ASC")
                info = db.cursor.fetchall()
                db.close()
                pages = []
                message = f"----------- SOUNDS FOR {member.name} -----------\n"
                for item in info:
                    line = f"{item[0]}\n"
                    if (len(message)+len(line)) > 1994:
                        pages.append(format_markdown(message))
                        message = line
                    else:
                        message += line
                pages.append(format_markdown(message))
                await interaction.user.send(content=pages[0], view=ButtonMenu(pages, 600))
                
            except Exception as e:
                print(e)
                await interaction.followup.send(format_markdown("ERROR: Something broke for this command, maybe it will get fixed."), ephemeral=True)
                return

        else:
            paths = DisplayablePath.make_tree(Path(config.sounds_path))
            msg_limit = 1988
            size = 0
            message = []
            pages = []
            msg = ""
            for path in paths:
                message.append(path.displayable())
            for i in range(0, len(message)):
                block = message[i]
                if size+(len(block)+4) <= msg_limit:
                    msg+=('\n'+block)
                    size += len(block)+4
                    if i == len(message)-1:
                        pages.append(format_markdown(msg))
                elif size+len(block) > msg_limit:
                    pages.append(format_markdown(msg))
                    msg=""
                    size=0
            await interaction.user.send(content=pages[0], view=ButtonMenu(pages, 600))

        await interaction.delete_original_response()


    @app_commands.command(name="folders")
    @app_commands.describe(folder="(optional) folder to view sounds in")
    async def folders_command(self, interaction: discord.Interaction, folder: Optional[str]) -> None:
        """
        View all folders or specific sounds in a folder.
        """
        message = ""
        if folder:
            try:
                path = os.listdir(config.sounds_path+'/'+folder)
                message += "📁 There are "+str(len(path))+" sounds in the "+folder+" folder:\n\n"
                for item in list(path):
                    message+=os.path.splitext(item)[0]+'\n'
                await interaction.response.send_message(format_markdown(message))
                return
            except FileNotFoundError as e:
                await interaction.response.send_message(format_markdown(f"Error: folder \"{folder}\" not found."))
                return
        else:
            try:
                for item in sorted(sounds.category_list):
                    message += "📁" + item + '\n'
                await interaction.response.send_message(format_markdown(message))
                return
            except TypeError as e:
                print(e)
                await interaction.response.send_message(format_markdown(f"No folders found."))
                return
    ### discord only allows 25 or less options for slash commands so imma leave this commented out
    # @folders_command.autocomplete('folder')
    # async def folders_autocomplete(self, interaction: discord.Interaction, current: str,) -> List[app_commands.Choice[str]]:
    #     folders = sounds.category_list
    #     return [app_commands.Choice(name=folder, value=folder) for folder in folders if current.lower() in folder.lower()]

    @commands.command(aliases=['1', '2', '3'], hidden=True)
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

    @quicksounds_group.command(name="set")
    @app_commands.describe(sound="sound name to set to a quicksound slot")
    async def quicksounds_set_command(self, interaction: discord.Interaction, sound: str) -> None:
        """
        Set a sound to a quicksound slot via UI prompt.
        """
        input_sound = sound.split(' ')
        if len(input_sound) == 2:
            group = input_sound[0]
            filename = input_sound[1]
        if len(input_sound) == 1:
            group = "root"
            filename = input_sound[0]
        
        view = ui.View()
        view.add_item(Quicksound(group, filename, sound))
        await interaction.response.send_message("Select quicksound slot", view=view, ephemeral=True)

    @quicksounds_group.command(name="info")
    async def quicksounds_info_command(self, interaction: discord.Interaction) -> None:
        """
        Get info on the current quicksounds set for yourself
        """
        db = GetDB(config.database_path)
        db.cursor.execute(f"SELECT alias,sound_id FROM QUICKSOUNDS WHERE user_id={interaction.user.id} ORDER BY alias")
        data = db.cursor.fetchall()
        embedvar = discord.Embed(title=f"{interaction.user.name}'s Quicksounds", color=0x00ff00)
        for item in data:
            embedvar.add_field(name=f"Slot {item[0]}", value=f"{item[1]}")
        await interaction.response.send_message(embed=embedvar, ephemeral=True)
        db.close()


    @entrance_group.command(name="set")
    @app_commands.describe(sound="Full sound name to set as entry sound")
    @app_commands.describe(folder="Folder name to randomly pull from for entry sound")
    async def entrance_set_command(self, interaction: discord.Interaction, sound: Optional[str] = None, folder: Optional[str] = None) -> None:
        """
        Set an entrance sound based on a full soundname or a random sound from a specified folder
        """
        if (sound and folder):
            await interaction.response.send_message(format_markdown(f"Error cannot set SOUND and FOLDER, please choose one."), ephemeral=True)
            return
        if sound:
            db = GetDB(config.database_path)
            given_sound = sound.split(' ')
            group = 'root'
            sound_name = given_sound[0]

            if len(given_sound) == 2:
                group = given_sound[0]
                sound_name = given_sound[1]

            if not checkExists(group, sound_name):
                interaction.response.send_message(format_markdown(f"Error: Cannot set entrance, sound {sound} does not exist."), ephemeral=True)
                return
            try:
                db = GetDB(config.database_path)
                db.cursor.execute(f"DELETE FROM entrance WHERE user_id={interaction.user.id}")
                db.cursor.execute(f"INSERT INTO entrance(sound_id, user_id) VALUES(\"{sound}\",{interaction.user.id})")
                db.commit()
                await interaction.response.send_message(format_markdown(f"Set entry sound to: \"{sound}\" for User {interaction.user.name}"), ephemeral=True)
                db.close()
            except Exception as e:
                await interaction.response.send_message(format_markdown(f"Error: an error occoured attempting to set entry sound. Please contact an admin if this persists."))
                print(e)

        if folder:
            if not checkGroup(folder):
                await interaction.response.send_message(format_markdown(f"Error: Cannot set entrance, folder {folder} does not exist."), ephemeral=True)
                return
            try:
                db = GetDB(config.database_path)
                db.cursor.execute(f"DELETE FROM entrance WHERE user_id={interaction.user.id}")
                db.cursor.execute(f"INSERT INTO entrance(sound_id, user_id, content_type) VALUES(\"{folder}\",{interaction.user.id},\"folder\")")
                db.commit()
                await interaction.response.send_message(format_markdown(f"Set entry folder to: \"{folder}\" for User {interaction.user.name}"), ephemeral=True)
                db.close()
            except Exception as e:
                await interaction.response.send_message(format_markdown(f"Error: an error occoured attempting to set entry sound. Please contact an admin if this persists."))
                print(e)

    @entrance_group.command(name="info")
    async def entrance_info_command(self, interaction: discord.Interaction) -> None:
        """
        View currently set entrance sound for yourself.
        """
        db = GetDB(config.database_path)
        db.cursor.execute(f"SELECT sound_id, content_type FROM entrance WHERE user_id={interaction.user.id}")
        data = db.cursor.fetchall()
        db.close()
        if len(data) == 0:
            await interaction.response.send_message(format_markdown("You don't have an entry sound set."), ephemeral=True)
            return
        else:
            await interaction.response.send_message(f"{interaction.user.name} your entrance {data[0][1]} is:\n{format_markdown(data[0][0])}", ephemeral=True)

    @entrance_group.command(name="remove")
    async def entrance_remove_command(self, interaction: discord.Interaction) -> None:
        """
        Removes your entrance sound.
        """
        db = GetDB(config.database_path)
        db.cursor.execute(f"DELETE FROM entrance WHERE user_id={interaction.user.id}")
        db.commit()
        await interaction.response.send_message(format_markdown("Removed entry sound."), ephemeral=True)
        

async def setup(bot):
    await bot.add_cog(SoundsUtils(bot))