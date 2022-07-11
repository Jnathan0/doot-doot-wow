import json
import os
import redis
import sys
from pathlib import Path
from rq import Queue 
from redis import Redis
from modules.errors import *

#TODO:
# - Refactor the config object creation to be created in main and then added as an attribute to the bot "client" class

__all__ = ('config')

# See example_config.json and README.md for descriptions and examples of keys and values for required. 
required = [
            'token', 
            'prefix', 
            'sub_cmd_sep', 
            'reverse_char',
            'database_folder_path',
            'media_path',
            'owb_id',
            'image_size_limit'
            ]
defaults_map = {
    "token": None,
    "prefix": "'",
    "sub_cmd_sep": ' ',
    "redis_address": "localhost",
    "redis_port": 6379,
    "redis_charset": "utf-8",
    "sounds_path": "/sounds",
    "gifs_path": "/gifs",
    "images_path": "/images",
    "videos_path": "/videos",
    "database_path": "/db",
    "metadata_db_path": "/db",
    "owb_id": None,
    "log_channel": None,
    "reverse_char": "-",
    "image_size_limit": 800000,
}

# List of cogs to load into the bot
__extensions__ = [
    'Admin',
    'Player',
    'Basics',
    'SoundsUtils',
    'Stats',
    'Media',
    'Entrance',
    'ModTools',
    'Help'
]

class AppConfig():
    """
    Class for setting up application configuration at runtime. 

    Attributes:
        _config - The config file handler for the app's config.json
        extensions - The list of cogs that are to be loaded into the bot at runtime

        required - This is a list of the required attributes, who's values need to be read from the config.json.
                   If the entry is missing in config.json, the program will attempt to retrive the value from a environment variable of the same name, assumed to be set.
                   If there is neither, program will throw an error. 

        database_path - static path to the .db file in a file system

        media pathing:
            sounds_path - path to sounds/ directory in a file system
            gifs_path - path to gifs/ directory in a file system
            meme_path - path to images/ directory in a file system 
            videos_path - path to videos/ directory in a file system

        conections for redis caching:
            redis_connection - returned redis cache connection object from _create_redis_connection()
            redis_metadata - returned redis cache connection obejct from _create_redis_metadata_connection()
                             defaults metadata database on redis as "1" 

        redis queues:
            sounds_queue - Queue object for sounds worker 
            worker_queue - Queue object for generic worker 
            metadata_queue - Queue object for metadata woker 
    """
    def __init__(self):
        self._config = self._get_config()
        # Lazily set each attribute in "required" as an object attribute
        for item in defaults_map.keys(): 
            setattr(self, item, self._get_attribute_value(item))
        self.extensions = __extensions__
        self._validate_paths()
        self.metadata_db_path = self._validate_metadata_db_path()
        self.database_path = self._validate_sounds_db_path()

        # connections to redis for caching 
        self.redis_connection = self._create_redis_connection()
        self.redis_metadata = self._create_redis_metadata_connection()

        # connections to redis queues for RQ
        self.sounds_queue = self._create_sounds_queue()
        self.worker_queue = self._create_worker_queue()
        self.metadata_queue = self._create_metadata_queue()

    def _get_config(self):
        base_path = str(Path(__file__).resolve().parents[1])
        config_path = base_path+"/config.json"
        try:
            config_file = open(config_path, 'r')
        except FileNotFoundError as e: #TODO: make this into a custom error
            print(f"Warning: No config file found at path: {base_path}")
            return None
        return json.loads(config_file.read())

    def _get_attribute_value(self, attribute_name):
        """
        Takes an attribute name, looks it up in the config for its value.
        If there is no value in the config, it looks for an environment variable of the same name.
        If that is not found it throws error. 
        
        """
        try:
            value = self._config[attribute_name]
            if (value == "") or (value == None):
                value = os.getenv(attribute_name.upper(), default = defaults_map[attribute_name])
                if value is None:
                    raise Config_Key_Not_Exist_Error(attribute_name)
            print(f"Value for {attribute_name} is: {value}")
            return value

        except TypeError as e:
            value = os.getenv(attribute_name.upper(), default = defaults_map[attribute_name])
            if value is None:
                raise Config_Key_Not_Exist_Error(attribute_name)
            print(f"Value for {attribute_name} is: {value}")
            return value

        except Config_Key_Not_Exist_Error as e:
            print(f"{e}")
            sys.exit(1)

        except Error as e:
            print(f"{e}")
            sys.exit(1)

    def _validate_paths(self):
        paths = {
                "sounds path": self.sounds_path, 
                "gifs path":   self.gifs_path, 
                "videos path": self.videos_path, 
                "images path": self.images_path
                }
        for key,value in paths.items():
            try:
                if not os.path.isdir(value):
                    raise Directory_Not_Found_Error(message=f"Error: Required directory not found \"{key}\", please make sure this directory exists and is a valid config value.")
            except Directory_Not_Found_Error as e:
                sys.exit(1)

    def _validate_metadata_db_path(self):
        try:
            if not os.path.isfile(f"{str(self.metadata_db_path)}/metadata.db"):
                print("Metadata database file not found, creating database..")
                app_path = Path(__file__).resolve().parents[1]
                if not os.path.isfile(f"{app_path}/db/metadata.sql"):
                    print("File \"metadata.sql\" not found, required to create the metadata database.\nExiting...")
                    sys.exit(1)
                os.system(f"/bin/bash -c \"cd {str(self.metadata_db_path)} && /usr/bin/sqlite3 metadata.db < {app_path}/db/metadata.sql\"")
                return f"{str(self.database_path)}/metadata.db"
            return f"{str(self.database_path)}/metadata.db"
       
        except Exception as e:
            print(e)
            sys.exit(1)

    def _validate_sounds_db_path(self):
        try:
            if not os.path.isfile(f"{str(self.database_path)}/sounds.db"):
                print("Sounds database file not found, creating database..")
                app_path = Path(__file__).resolve().parents[1]
                if not os.path.isfile(f"{app_path}/db/sounds.sql"):
                    print("File \"sounds.sql\" not found, required to create the sounds database.\nExiting...")
                    sys.exit(1)
                os.system(f"/bin/bash -c \"cd {str(self.database_path)} && /usr/bin/sqlite3 sounds.db < {app_path}/db/sounds.sql\"")
                return f"{str(self.database_path)}/sounds.db"
            return f"{str(self.database_path)}/sounds.db"
        
        except Exception as e:
            print(e)
            sys.exit(1)


    def _create_redis_connection(self):
        try:
            address = self.redis_address
            port = self.redis_port
            charset = self.redis_charset
            return redis.StrictRedis(address, port, db = 0, charset = charset)
        except Exception as e:
            print(f"EXCEPTION: {e}")
            sys.exit(1)


    def _create_redis_metadata_connection(self):
        try:
            address = self.redis_address
            port = self.redis_port
            charset = self.redis_charset
            return redis.StrictRedis(address, port, db = 1, charset = charset, decode_responses = True)
        except Exception as e:
            print(f"EXCEPTION: \n{e}")
            sys.exit(1)

    def _create_sounds_queue(self):
        return Queue('plays', connection=self.redis_connection)

    def _create_worker_queue(self):
        return Queue('generic_worker', connection=self.redis_connection)

    def _create_metadata_queue(self):
        return Queue('metadata', connection=self.redis_connection)

config = AppConfig()