# This file contains database interaction classes and 
# functions for updating and querying 
# data from the database
import sqlite3
from .app_config import config

class GetDB:
    """Class for setting up sqlite3 connection and cursor to a sqlite3 database"""
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
    
    def close(self):
        self.conn.close()
        
    def commit(self):
        self.conn.commit()

    def set_row_factory(self, arg):
        self.cursor.row_factory = arg