"""
This file contains all the functionality that are used for async task queueing,
handed off to an rq worker via redis queues to be completed.
"""
from .helper_functions import *
from .database import *
from .app_config import config
import redis
import datetime
import time
from redis import Redis


##########################
# REDIS METADATA CACHING #
##########################

def update_metadata(user_id, sound_id, call_type):
    ts = int(time.time() * 1000) # convert a UNIX timestamp by moving the decimal and making it into an integer
    key = "plays:metadata"
    # determine if the parent folder of a sound is a category or from the root folder 
    if len(sound_id.split(' ')) > 1:
        folder = sound_id.split(' ')[0]
    else:
        folder = "root"
    config.redis_metadata.xadd(name = str(key), fields = {"sound_id": sound_id, "folder": folder, "timestamp": ts, "user_id": user_id, "call_type": call_type}, id = ts)


####################################################
# STORING METADATA FROM REDIS TO PERMANANT STORAGE #
####################################################


def store_metadata():
    """
    Function calls a redis database to get the values of a redis stream older than 1 hour ago.
    Then for each value in the stream, stores the data to a database.
    """
    metadata = redis.StrictRedis('localhost', 6379, db = 1, charset = "utf-8", decode_responses = True)
    today = datetime.datetime.today().date()
    yesterday = today - datetime.timedelta(days = 1)
    result = metadata.xrange(name = str(yesterday), min = "-", max = "+")
    if not result:
        return
    else:
        for item in result:
            store_tuple(item)


def store_tuple(tuple):
    # injest the tuple from redis and assign values to local variables for feeding into SQL query
    entry_id = tuple[0]
    sound_id = tuple[1]['sound_id']
    sound_folder = tuple[1]['sound_folder']
    timestamp = int(tuple[1]['timestamp'])/1000 # convert the timestamp back into a UNIX supported float value
    user_id = tuple[1]['user_id']
    call_type = tuple[1]['call_type']

    # get a datetime object from a UNIX timestamp and generate the day, month, and year values of the timestamp
    dt = datetime.datetime.fromtimestamp(timestamp)
    day = dt.date().day
    month = dt.date().month
    year = dt.date().year

    # insert into database
    db = GetDB(config.metadata_path)
    db.cursor.execute(f"INSERT INTO timeseries (entry_id, sound_id, sound_folder, timestamp, day, month, year, call_type, user_id", (entry_id, sound_id, sound_folder, timestamp, day, month, year, call_type, user_id))
    db.commit()
    db.close()