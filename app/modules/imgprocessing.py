import requests
import os
import discord
from datetime import datetime
from modules import config 
from modules.database import GetDB
from modules.errors import Image_Too_Large_Error

class ImageAttachment():
    def __init__(self, attachment: discord.Attachment, sound_id: str):
        self.attachment = attachment
        self.sound_id = sound_id
        self.filetype = self._get_image_filetype()
        self.base_path_map = {
            "gifs": config.gifs_path,
            "images": config.images_path
        }

    def _get_image_filetype(self):
        if self.attachment.content_type.split('/')[1] == 'gif':
            return "gifs"
        return "images"


    def download_file(self, file_bytes):

        # if self.attachment.size > config.image_size_limit:
        #     raise Image_Too_Large_Error

        media_path = str(f"{self.base_path_map[self.filetype]}/")

        # make a datetime.now() result into an int and append it to the filename 
        # to make the filename unique
        unique_filename = f'{int(datetime.now().strftime("%Y%m%d%H%M%S"))}{self.attachment.filename}'
        save_path = os.path.join(media_path, unique_filename)
        open(save_path, 'wb').write(file_bytes)

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
                os.remove(f"{self.base_path_map[folder]}/{image_name}")
                return
            else:
                return
        except IndexError as e:
            return
        except FileNotFoundError as e:
            pass
