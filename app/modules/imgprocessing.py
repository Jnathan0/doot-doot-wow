import requests
import os
import discord
from datetime import datetime
from pathlib import Path
from modules import config 
from modules.database import GetDB
from modules.errors import Image_Too_Large_Error
from modules.paths import safe_child, UnsafePath

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
        else:
            return "images"


    def download_file(self, file_bytes):

        # if self.attachment.size > config.image_size_limit:
        #     raise Image_Too_Large_Error

        media_path = self.base_path_map[self.filetype]

        # make a datetime.now() result into an int and append it to the filename 
        # to make the filename unique. Only the base name of the upload is used so
        # the attachment filename cannot point outside of the media directory.
        unique_filename = f'{int(datetime.now().strftime("%Y%m%d%H%M%S"))}{Path(self.attachment.filename).name}'
        save_path = safe_child(media_path, unique_filename)
        with open(save_path, 'wb') as file:
            file.write(file_bytes)

        with GetDB(config.database_path) as db:
            db.cursor.execute("DELETE FROM images WHERE sound_id = ?", (self.sound_id,))
            db.cursor.execute("INSERT INTO images(sound_id, image_id, folder) VALUES(?,?,?)", (self.sound_id, unique_filename, self.filetype))
            db.commit()

    def delete_existing_image_file(self):
        """
        Deletes the associated image file from disk if it an entry exists in the database. 
        If there is no image, just returns. 
        """
        with GetDB(config.database_path) as db:
            image_data = db.cursor.execute("SELECT folder, image_id FROM images WHERE sound_id = ?", (self.sound_id,)).fetchone()
        if not image_data:
            return
        folder, image_name = image_data
        try:
            # values from the database are data, not trusted paths
            os.remove(safe_child(self.base_path_map[folder], image_name))
        except (KeyError, UnsafePath) as e:
            print(f"Refusing to delete image {image_name!r} in folder {folder!r} for sound {self.sound_id!r}: {e!r}")
        except FileNotFoundError as e:
            pass

