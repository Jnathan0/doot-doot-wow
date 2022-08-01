"""
Supporting functions for interacting with persistent data stores and caches
for the MODTOOLS cog
"""
from tokenize import String
from .helper_functions import GetDB
from .app_config import config

def check_author(member_id: int, sound_name: str, category_id: str) -> bool:
    """
    Parameters: discord.Member.id, sound_id

    Checks in the sounds database if the sound_id's author is equal to member_id
    Returns: bool
    """
    db = GetDB(config.database_path)
    db.set_row_factory(lambda cursor, row: row[0:1])
    data = db.cursor.execute(f"SELECT EXISTS(SELECT * FROM sounds WHERE author_id={member_id} AND sound_name=\"{sound_name}\" AND category_id=\"{category_id}\")").fetchone()
    if data[0] != 1:
        return False
    else:
        return True
