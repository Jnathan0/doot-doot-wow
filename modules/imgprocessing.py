import requests
import os
import discord
from datetime import datetime
from modules import config 
from modules.database import GetDB
from modules.errors import Image_Too_Large_Error

class ImageAttachment():
    def __init__(self, ctx, sound_id):
        self.ctx = ctx
        self.author_id = ctx.message.author.id
        self.attachment = self._get_image_attachment()
        self.filename = self.attachment.filename
        self.sound_id = sound_id
        self.filetype = self._get_image_filetype()

    def _get_image_filetype(self):
        if self.ctx.message.attachments[0].content_type.split('/')[1] == 'gif':
            return "gifs"
        return "images"

    def _get_image_attachment(self):
        if len(self.ctx.message.attachments) != 1:
            print("too many image attachments")
            # Implement custom error here
            return
        return self.ctx.message.attachments[0]

    def download_file(self):

        if self.attachment.size > config.image_size_limit:
            raise Image_Too_Large_Error
        file = requests.get(self.attachment.url)
        media_path = str(config.media_path+'/'+self.filetype+'/')

        # make a datetime.now() result into an int and append it to the filename 
        # to make the filename unique
        unique_filename = f'{int(datetime.now().strftime("%Y%m%d%H%M%S"))}{self.filename}'
        save_path = os.path.join(media_path, unique_filename)
        open(save_path, 'wb').write(file.content)

        db = GetDB(config.database_path)
        db.cursor.execute(f"DELETE FROM images WHERE sound_id=\"{self.sound_id}\"")
        db.cursor.execute("INSERT INTO images(sound_id, image_id, folder) VALUES(?,?,?)", (self.sound_id, unique_filename, self.filetype))
        db.commit()
        db.close()

    def delete_existing_image_file(self):
        """
        Deletes the associated image file from disk if it an entry exists in the database. 
        If there is no image, just returns. 
        """
        db = GetDB(config.database_path)
        try:
            image_data = db.cursor.execute(f"SELECT folder, image_id FROM images WHERE sound_id=\"{self.sound_id}\"").fetchall()[0]
            if image_data:
                folder = image_data[0]
                image_name = image_data[1]
                os.remove(f"{config.media_path}/{folder}/{image_name}")
                return
            else:
                return
        except IndexError as e:
            return