"""
This file contains all the functionality that are used for async task queueing,
handed off to an rq worker via redis queues to be completed.
"""
from redis import Redis
from metadata import store_metadata

####################################################
# STORING METADATA FROM REDIS TO PERMANANT STORAGE #
####################################################
store_metadata()