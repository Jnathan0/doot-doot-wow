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
