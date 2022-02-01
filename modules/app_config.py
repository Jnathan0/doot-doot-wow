import json
import os
import redis
import sys
from redis import connection
from pathlib import Path
from rq import Queue 
from redis import Redis
from modules.errors import *

#TODO:
# - Change config attributes to get from the confi.js and refactor out the docker env reading

__all__ = ('config')

required = [
            'token', 
            'prefix', 
            'sub_cmd_sep', 
            'redis',
            'reverse_char',
            'database_folder_path',
            'media_path',
            'owb_id',
            'image_size_limit'
            ]

__extensions__ = [
    'Admin',
    'Player',
    'Basics',
    'SoundsUtils',
    'Stats',
    'Media',
    'Entrance',
    'ModTools'
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
        self.is_docker = self._is_in_container()
        self.extensions = __extensions__
        for item in required: 
            setattr(self, item, self._get_attribute_value(item))

        # database pathing
        self.database_path = self._get_database_paths()

        # media pathing
        self.sounds_path = self._get_media_paths("sounds")
        self.gifs_path = self._get_media_paths("gifs")
        self.meme_path = self._get_media_paths("images")
        self.videos_path = self._get_media_paths("videos")

        # connections to redis for caching 
        self.redis_connection = self._create_redis_connection()
        self.redis_metadata = self._create_redis_metadata_connection()

        # connections to redis queues for RQ
        self.sounds_queue = self._create_sounds_queue()
        self.worker_queue = self._create_worker_queue()
        self.metadata_queue = self._create_metadata_queue()
        
    def _is_in_container(self):
        return False
        # if os.environ.get("IS_DOCKER"):
        #     return True
        # else:
        #     return False

    def _get_config(self):
        base_path = str(Path(__file__).resolve().parents[1])
        config_path = base_path+"/config.json"
        try:
            config_file = open(config_path, 'r')
        except FileNotFoundError as e: #TODO: make this into a custom error
            print(f"ERROR: No config file found at path: {base_path}")
            sys.exit(1)
        return json.loads(config_file.read())

    def _get_attribute_value(self, attribute_name):
        if self.is_docker:
            try:
                value = os.environ[attribute_name.upper()]
                return value
            except KeyError as e:
                print(f"REQUIRED KEY: {e}\nNOT SET IN CONFIG.JSON OR OS ENVIRONMENT.") 
                sys.exit(1)
        value = self._config[attribute_name]
        return value

    def _get_media_paths(self, attribute_name):
        if self.is_docker:
            try:
                if not os.path.isdir(f"/{attribute_name}"):
                    raise Directory_Not_Found_Error(message=f"Error: Configuration directory not found: {attribute_name}")
                return str(f"/{attribute_name}")
            except Directory_Not_Found_Error as e:
                sys.exit(1)
        if self._config["paths"][attribute_name] != '':
            return str(self._config["paths"][attribute_name])
        else:
            return str(self.media_path)+f"{attribute_name}/"


    def _get_database_paths(self):
        try:
            if self.is_docker:
                if not os.path.isdir("/db"):
                    raise Directory_Not_Found_Error(message="Error: Configuration directory not found: /db")
                if not os.path.isfile("/db/sounds.db"):
                    if not os.path.isfile("/db/sounds.sql"):
                        raise File_Not_Found_Error(message="Error: Configuration file not found: sounds.sql")
                    print("No sounds.db file found, creating database file.")
                    os.system("cd /db && sqlite3 sounds.db < sounds.sql")
                # if not os.path.isfile("/db/metadata.db"):
                #     if not os.path.isfile("/db/metadata.sql"):
                #         raise File_Not_Found_Error(message="Error: Configuration file not found: metadata.sql")
                #     os.system("cd /db && sqilte3 metadata.db < metadata.sql")
                return "/db/sounds.db"
            
            if self._config["database_folder_path"] == '':
                raise KeyError
            if not os.path.isfile(self._config["database_folder_path"]+"sounds.db"):
                if not os.path.isfile(self._config["database_folder_path"]+"sounds.sql"):
                    raise File_Not_Found_Error(message="Error: Configuration file not found: sounds.sql")
                print("No sounds.db file found, creating database file.")
                os.system(f"cd {self._config['database_folder_path']} && sqilte3 sounds.db < sounds.sql")
            return self._config['database_folder_path']+"sounds.db"

        except File_Not_Found_Error as e:
            print(e)
            sys.exit(1)
        except Directory_Not_Found_Error as e:
            print(e)
            sys.exit(1)
        except KeyError as e:
            print("Value for 'database_folder_path' not found, please assign value for it in the config.js")
            sys.exit(1)
        except Error as e:
            print(e)




    def _create_redis_connection(self):
        if self.is_docker:
            try:
                address = os.environ.get("REDIS_ADDRESS")
                port = os.environ.get("REDIS_PORT")
                charset = os.environ.get("REDIS_CHARSET")
                return redis.StrictRedis(address, port, charset)
            except KeyError as e:
                print(e)
                sys.exit(1)

        return redis.StrictRedis(self.redis["address"], self.redis["port"], charset = self.redis["charset"])

    def _create_redis_metadata_connection(self):
        if self.is_docker:
            try:
                address = os.environ.get("REDIS_ADDRESS")
                port = os.environ.get("REDIS_PORT")
                charset = os.environ.get("REDIS_CHARSET")
                return redis.StrictRedis(address, port, charset)
            except KeyError as e:
                print(e)
                sys.exit(1)
        return redis.StrictRedis(self.redis["address"], self.redis["port"], db = 1, charset = self.redis["charset"], decode_responses = True)

    def _create_sounds_queue(self):
        return Queue('plays', connection=self.redis_connection)

    def _create_worker_queue(self):
        return Queue('generic_worker', connection=self.redis_connection)

    def _create_metadata_queue(self):
        return Queue('metadata', connection=self.redis_connection)




config = AppConfig()
