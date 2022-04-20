"""
This Cog handles the uploading of media to be stored into the file system,
and handles the insertion of database entries for the attributes of the media. 
"""
import asyncio
import requests
import os
from datetime import date
from modules import config, sounds, Sound
from modules.errors import *
from modules.helper_functions import *
from modules.database import *
from modules.imgprocessing import ImageAttachment
from discord.ext import commands

class Media(commands.Cog, commands.Command):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.guild_only()
    @commands.has_role(config.owb_id)#decorator to see if whoever requested the command has the role specified, takes roleid argument in int or string form. 
    async def add(self, ctx):
        '''Upload a sound file and add it to the library.\nCommand will be filename w/o file extension (ex. \'airhorn).\nYou can add to group like: 'add wow'''
        command = ctx.message.content.split(config.prefix)[1]

        print(ctx.message.attachments[0].content_type.split('/')[0])
        print(ctx.message.attachments[0].content_type.split('/'))
        if ctx.message.attachments[0].content_type.split('/')[0] == "image":
            try:
                sound_id = command.split("add ")[1]
                if sound_id not in sounds.alias_dict:
                    await ctx.message.author.send(format_markdown(f"The sound '{sound_id}' does not exist, so you cannot add an image for it."))
                    await ctx.message.delete()
                image = ImageAttachment(ctx, sound_id)
                # image.delete_existing_image_file()
                image.download_file()
                await ctx.message.author.send(format_markdown(f"Added image {image.filename} to sound {command.split('add ')[1]}"))
                await ctx.message.delete()

                sounds.update_sounds()
                self.bot.reload_extension(f"cogs.Player")
                return
            except Image_Too_Large_Error as e:
                print(e)
                return


        #TODO: The code below should be refactored into its own module 
        new_dir = False
        uid = ctx.message.author.id
        attachment = ctx.message.attachments[0]
        url = attachment.url
        downloaded_file = requests.get(url)
        filename = attachment.filename
        if len(command.split(config.sub_cmd_sep)) == 2:
            group = command.split(config.sub_cmd_sep)[1]
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
                    await ctx.send(format_markdown(f"The sound name \'{sound_name}\' is a reserved command, please change the sound name and retry."))
                    return

        if checkExists(mygroup, sound_name):
            await ctx.send(format_markdown(f"Sound name \"{sound_name}\" already exists for this folder. Please try naming it something else."))
            return             

        save_dir = os.path.join(config.sounds_path, group)
        save_path = os.path.join(save_dir, filename)
        
        if not os.path.exists(save_dir):
            new_dir = True
            os.makedirs(save_dir)

        open(save_path, 'wb').write(downloaded_file.content)
        if isLoud(save_path):
            os.remove(save_path)
            await ctx.send(format_markdown("ERROR: fUnNy bEcAuSe LoUd. Sound too loud, please choose a different file"))
            return

        confirmation_msg = ''

        if new_dir:
            confirmation_msg = f"{ctx.author.mention}\nYou are about to add sound: ```\"{sound_name}\"```\nThis will create a new folder with the name: ```{mygroup}```\nReact with ✅ to confirm. React with ❌ to cancel"
        confirmation_msg = f"{ctx.author.mention}\nYou are about to add sound: ```\"{sound_name}\"```\nTo the folder: ```{mygroup}```\nReact with ✅ to confirm. React with ❌ to cancel"

        msg = await ctx.send(confirmation_msg)
        await msg.add_reaction('✅')
        await msg.add_reaction('❌')
        
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ['✅','❌']

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout = 60.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send(format_markdown("You have waited too long to react, sound upload aborted."))
            os.remove(save_path)
            return
        
        if str(reaction) == '✅':
            await msg.delete()
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
        
            await ctx.send(format_markdown(f'added {filename}, updating list'))
            self.bot.reload_extension(f"cogs.Player")
        if str(reaction) == '❌':
            os.remove(save_path)
            await ctx.message.author.send(format_markdown("Process cancelled"))
            await msg.delete()
            await ctx.message.delete()
            return
   





    
    @add.error #error handaling for the add function
    async def upload_error(self,ctx,error):
        if isinstance(error, commands.MissingRole):#if .has_role returns with MissingRole error, send message
            await ctx.send(format_markdown("Cannot restart, \'owb\' role required"))
        if isinstance(error, Image_Too_Large_Error):
            await ctx.send(error)
        if isinstance(error, Error):
            await ctx.send(error)

def setup(bot):
    bot.add_cog(Media(bot))