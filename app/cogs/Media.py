"""
This Cog handles the uploading of media to be stored into the file system,
and handles the insertion of database entries for the attributes of the media. 
"""
import asyncio
import requests
import os
import discord
from typing import Optional
from datetime import date
from modules import config, sounds, Sound
from modules.errors import *
from modules.helper_functions import *
from modules.database import *
from modules.imgprocessing import ImageAttachment
from modules.media import ImageAddModal, SoundConfirmationDiag
from discord.ext import commands
from discord import app_commands

class Media(commands.Cog, commands.Command):
    def __init__(self, bot):
        self.bot = bot

    # @commands.command()
    # @commands.guild_only()
    # @commands.has_role(config.owb_id)#decorator to see if whoever requested the command has the role specified, takes roleid argument in int or string form. 
    # async def add(self, ctx):
    
    @app_commands.command(name='add')
    @app_commands.default_permissions(attach_files=True)
    # @app_commands.checks.has_role(config.owb_id)
    @app_commands.describe(folder='(Optional) folder to add sound to.', )
    async def add_command(self, interaction: discord.Interaction, attachment: discord.Attachment, folder: Optional[str]):
        """
        Upload a sound file and add it to the bots sound library.
        \nCommand will be filename w/o file extension (ex. `airhorn.mp3` will become `airhorn`).
        \n> Example Usage (adding a sound):\n upload a supported sound file named what you want the command name to be and then use the `add` command
        \n> (For example, the user uploads airhorn.mp3, then in the same message uses the `add` command. `airhorn.mp3` will become the `airhorn` command in the bot)
        \nA sound can be added to a folder, which can contain multiple sounds.
        \n> Example Usage (adding a sound to a folder):\n `add foldername soundname`
        """
        if attachment.content_type.split('/')[0] == 'image':
            image_add_modal = ImageAddModal()
            await interaction.response.send_modal(image_add_modal)
            await image_add_modal.wait()
            sound = str(image_add_modal.sound)
            try:
                if sound not in sounds.alias_dict:
                    return await image_add_modal.interaction.followup.send(format_markdown(f"The sound '{sound}' does not exist, so you cannot add an image for it."))
                image = ImageAttachment(attachment, sound)
                file_bytes = await attachment.read()
                image.delete_existing_image_file()
                image.download_file(file_bytes)
                try:
                    sounds.update_sounds()
                except Exception as e:
                    print(e)
                    return await image_add_modal.interaction.followup.send(format_markdown("An error occoured while updating the sounds catalog, if this persists please notify an admin."), ephemeral=True)
                await self.bot.reload_extension(f"cogs.Player")
                return await image_add_modal.interaction.followup.send(f"Image uploaded for sound \"{sound}\"")
            
            except Image_Too_Large_Error as e:
                # bitwise shift left to get MB 
                # see https://docs.python.org/3.3/reference/expressions.html?highlight=bitwise#shifting-operations
                return await image_add_modal.interaction.followup.send(format_markdown(f"Error: Image size cannot exceed {int(config.image_size_limit/(1<<20))} MB. "), ephemeral=True)
            
            except Exception as e:
                print(e)
                return await image_add_modal.interaction.followup.send(format_markdown("An error occoured while processing this command. If this persists please notify an admin."), ephemeral=True)

        #TODO: The code below should be refactored into its own module 
        new_dir = False
        uid = interaction.user.id
        downloaded_file = await attachment.read(use_cached=False)
        filename = attachment.filename
        if folder:
            group = folder
        else:
            group = ''
        mygroup = group
        sound_id = mygroup + ' ' + filename.split('.')[0]
        sound_name = filename.split('.')[0]
        if mygroup == '':
            mygroup = "root"
            sound_id = filename.split('.')[0]
        author_id = uid

        if mygroup == "root":
            for command in self.bot.commands:
                if str.lower(sound_name) == str.lower(command.name):
                    await interaction.response.send_message(format_markdown(f"The sound name \'{sound_name}\' is a reserved command, please change the sound name and retry."))
                    return

        if checkExists(mygroup, sound_name):
            await interaction.response.send_message(format_markdown(f"Sound name \"{sound_name}\" already exists for this folder. Please try naming it something else."))
            return             

        save_dir = os.path.join(config.sounds_path, group)
        save_path = os.path.join(save_dir, filename)
        
        if not os.path.exists(save_dir):
            new_dir = True
            os.makedirs(save_dir)

        open(save_path, 'wb').write(downloaded_file)
        if isLoud(save_path):
            os.remove(save_path)
            await interaction.response.send_message(format_markdown("ERROR: fUnNy bEcAuSe LoUd. Sound too loud, please choose a different file"))
            return

        if checkExceedsDurationLimit(save_path):
            os.remove(save_path)
            await interaction.response.send_message(format_markdown(f"ERROR: Duration of media playback exceeds limit of {config.media_duration_limit} second(s)"))
            return

        confirmation_msg = ''

        if new_dir:
            confirmation_msg = f"{interaction.user.mention}\nYou are about to add sound: ```\"{sound_name}\"```\nThis will create a new folder with the name: ```{mygroup}```"
        confirmation_msg = f"{interaction.user.mention}\nYou are about to add sound: ```\"{sound_name}\"```\nTo the folder: ```{mygroup}```"
        confirmation_view = SoundConfirmationDiag()
        await interaction.response.send_message(content=confirmation_msg, view=confirmation_view)
        await confirmation_view.wait()
        if confirmation_view.confirmed:
            mydate = date.today().strftime("%Y-%m-%d")
            db = GetDB(config.database_path)
            db.cursor.execute("INSERT OR IGNORE INTO categories (category_id) VALUES (\""+mygroup+"\")")
            db.commit()
            query = "INSERT INTO sounds (sound_id, sound_name, category_id, author_id, plays, date) VALUES (?,?,?,?,?,?);"
            mytuple = (sound_id, sound_name, mygroup, author_id, 0, mydate)
            db.cursor.execute(query, mytuple)
            db.commit()
            db.close()
            try:
                # # If sounds gets very large, insert into existing data structure 
                # sound_object = Sound(sound_id = sound_id, path = save_path)
                # sounds.alias_dict[sound_object.sound_id] = sound_object
                
                # rebuild the existing sounds datastructure from scratch
                # If performance is an issue, use the above commented code 
                sounds.update_sounds()
            except Exception as e:
                print(e)
            if mygroup == 'root':
                msg = f'added {sound_name}, updating list'
            else:
                msg = f'added {sound_id}, updating list'
            await confirmation_view.interaction.response.edit_message(content=format_markdown(msg), view=None)
            await self.bot.reload_extension(f"cogs.Player")
            return
        if not confirmation_view.confirmed:
            os.remove(save_path)
            await confirmation_view.interaction.response.edit_message(content=format_markdown("Process cancelled"), view=None)
            return


async def setup(bot):
    await bot.add_cog(Media(bot))