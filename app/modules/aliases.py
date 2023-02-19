#app wide object that stores and updates sound aliases and folders during runtime

import os
from pathlib import Path
from .app_config import config 
from .database import GetDB

class Sound:
    def __init__(self, sound_id = None, path = None,  media = None, media_parent_folder = None):
        self.sound_id = sound_id
        self.path = path
        self.media = media 
        self.media_parent_folder = media_parent_folder

class SoundsInfo:
    """
    Object that manages data structure to hold alias and category information, to be accessed by application functions at runtime 

    Parameters:
        sounds_path - Static path to the sounds/ directory 

    """
    def __init__(self, sounds_path):
        self.sounds_path = sounds_path
        self.alias_dict, self.category_list = self.getAliasInfo()
        self.aliases = list(self.alias_dict.keys())

    # This function needs a big ole' refactor 
    def getAliasInfo(self):
        alias_dict = {}
        category_list = []

        with os.scandir(self.sounds_path) as root_dir:
            for item in root_dir:
                if item.is_file():
                    sound_id = str(item.name.split('.')[0])
                    path = item.path
                    db = GetDB(config.database_path)
                    db.set_row_factory(lambda cursor, row: row[0:2])
                    media = db.cursor.execute(f"SELECT image_id, folder FROM images WHERE sound_id=\"{sound_id}\"").fetchone()
                    media_parent_folder = None
                    media_name = None
                    if media is not None:
                        media_name = f"{media[0]}"
                        media_parent_folder = f"{media[1]}"
                    sound_object = Sound(sound_id = sound_id, path = path, media = media_name, media_parent_folder = media_parent_folder)
                    alias_dict[sound_object.sound_id] = sound_object
                    db.close()

                if item.is_dir():
                    alias_dict[item.name] = []
                    category_list.append(item.name)
                    with os.scandir(item.path) as subdir:
                        for file in subdir:
                            sound_name = str(file.name.split('.')[0])
                            path = file.path
                            sound_id = item.name + " " + sound_name
                            db = GetDB(config.database_path)
                            db.set_row_factory(lambda cursor, row: row[0:2])
                            media = db.cursor.execute(f"SELECT image_id, folder FROM images WHERE sound_id=\"{sound_id}\"").fetchone()
                            if media is not None:
                                media = f"{media[1]}/{media[0]}"
                            sound_object = Sound(sound_id = sound_id, path = path, media = media)
                            alias_dict[sound_object.sound_id] = sound_object
                            alias_dict[item.name].append(sound_object)
                            db.close()
        
        return alias_dict, category_list

    def update_sounds(self):
        # maybe just change this into an insert into the alias_dict instead of rebuilding the whole thing?
        self.alias_dict, self.category_list = self.getAliasInfo()
        self.aliases = list(self.alias_dict.keys())











class DisplayablePath(object):
    display_filename_prefix_middle = '├──'
    display_filename_prefix_last = '└──'
    display_parent_prefix_middle = '    '
    display_parent_prefix_last = '│   '

    def __init__(self, path, parent_path, is_last):
        self.path = Path(str(path))
        self.parent = parent_path
        self.is_last = is_last
        if self.parent:
            self.depth = self.parent.depth + 1
        else:
            self.depth = 0

    @property
    def displayname(self):
        if self.path.is_dir():
            return self.path.name + '/'
        return self.path.name

    @classmethod
    def make_tree(cls, root, parent=None, is_last=False, criteria=None):
        root = Path(str(root))
        criteria = criteria or cls._default_criteria

        displayable_root = cls(root, parent, is_last)
        yield displayable_root

        children = sorted(list(path
                               for path in root.iterdir()
                               if criteria(path)),
                          key=lambda s: str(s).lower())
        count = 1
        for path in children:
            is_last = count == len(children)
            if path.is_dir():
                yield from cls.make_tree(path,
                                         parent=displayable_root,
                                         is_last=is_last,
                                         criteria=criteria)
            else:
                yield cls(path, displayable_root, is_last)
            count += 1

    @classmethod
    def _default_criteria(cls, path):
        return True

    @property
    def displayname(self):
        if self.path.is_dir():
            return self.path.name + '/'
        return self.path.name

    def displayable(self):
        if self.parent is None:
            return self.displayname

        _filename_prefix = (self.display_filename_prefix_last
                            if self.is_last
                            else self.display_filename_prefix_middle)

        parts = ['{!s} {!s}'.format(_filename_prefix,
                                    self.displayname)]

        parent = self.parent
        while parent and parent.parent is not None:
            parts.append(self.display_parent_prefix_middle
                         if parent.is_last
                         else self.display_parent_prefix_last)
            parent = parent.parent

        return ''.join(reversed(parts))


sounds = SoundsInfo(config.sounds_path)