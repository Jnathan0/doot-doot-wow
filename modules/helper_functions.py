import datetime
import calendar
import subprocess
import sqlite3
import os
import asyncio
import discord
from pathlib import Path
from .database import GetDB
from .app_config import config


def restart_bot():
    os.system('. '+str(Path(__file__).resolve().parents[1])+'/DootRestart.sh')

def format_markdown(string):
    """
    Takes a string and formats them in discord markdown style using backticks.
    """
    return f"```\n{string}\n```"


def isLoud(savepath):
    """
    Parameters: 
        savepath - A filepath to an audio file 

    Takes a sound and returns bool if the sound is louder than the upper_limit.
    Makes a subprocess call to ffmpeg to get the mean volume. 
    """
    upper_limit = -8.0
    cmd = 'ffmpeg -i '+ savepath + ' -filter:a volumedetect -f null /dev/null 2>&1 | grep -oP \'mean_volume: \\K.([0-9]?\\d+(\\.\\d+))\''
    out = subprocess.getoutput(cmd)
    num = float(out.split()[0])
    if num >= upper_limit:
        return True
    else:
        return False


def checkExists(group, filename):
    """
    Function checks if a sound name already exists given a group.
    Group can be a specific group that already exists or the Root folder
    Returns boolean.
    """
    db = GetDB(config.database_path)
    data = db.cursor.execute(f"SELECT EXISTS(SELECT sound_name FROM sounds WHERE category_id=\"{group}\" ANd sound_name=\"{filename}\")").fetchall()
    db.close()

    for item in data:
        if item[0] == 1:
            return True
        else:
            return False


def checkGroup(group):
    """
    Function checks to see if a group name is already a sound ID, to elinminate multiple instances of the same folder name.
    Returns Boolean
    """
    db = GetDB(config.database_path)
    data = db.cursor.execute(f"SELECT EXISTS(SELECT sound_id FROM sounds WHERE sound_id=\"{group}\"").fetchall()
    db.close()
    for item in data:
        if item[0] == 1:
            return True
        else:
            return False

def check_dir(self, sounds_path):
    save_dir = os.path.join(sounds_path, self.group)
    save_path = os.path.join(save_dir, self.file[0])

    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
        self.new_folder = True

    return save_dir, save_path


def get_last_thursday():
    """ Returns the date of the last thursday of the current month"""
    cal = calendar.Calendar(firstweekday=calendar.MONDAY)
    today = datetime.datetime.today()
    year = today.year
    month = today.month
    monthcal = cal.monthdatescalendar(year, month)
    last_thursday = [day for week in monthcal for day in week if day.weekday() == calendar.THURSDAY and day.month == month][-1]
    return last_thursday

#############################
# PLAYCOUNT DB INTERACTIONS #
#############################

def increment_playcount(sound_id):
    """
    Function to increment the plays of a sound by +=1 

    Parameters:
        sound_id: the sound_id to increment the playcount 
    """
    conn = sqlite3.connect(config.database_path)
    c = conn.cursor()
    c.execute(f'''UPDATE sounds set plays=plays+1 WHERE sound_id="{sound_id}"''')
    conn.commit()
    c.close()


###############################
# QUICKSOUNDS DB INTERACTIONS #
###############################

def update_quicksound(member, number, sound, reverse):
    """
    Function to remove a quicksound associated with a discord user ID and a quicksound slot number, 
    and then update the entry with a new sound ID

    Parameters:
        - member: discord user ID number 
        - number: the quicksound slot to update 
        - sound: the sound ID to update the value to in the entry
        - reverse: numerical bool (1 or 0) signifying if the sound should be played in reverse
    """
    db = GetDB(config.database_path)
    db.cursor.execute(f"DELETE FROM quicksounds WHERE user_id={member} AND alias={number}")
    db.cursor.execute(f"INSERT INTO quicksounds (sound_id, user_id, alias, reverse) VALUES (?, ?, ?, ?)", (sound,member,number,reverse, ))
    db.commit()
    db.close()

#############################
# UPDATE RICKROLL PLAYCOUNT #
#############################

def update_rickroll(user_id):
    db = GetDB(config.database_path)
    db.cursor.execute(f"UPDATE rickroll SET plays=plays+1 WHERE user_id={user_id}")
    db.commit()
    db.close()

async def post_rickroll_update(ctx):
    file = discord.File(f"assets/static/rickroll.gif")
    await ctx.send(file=file, content = f"**{ctx.author.mention} just got rick rolled!\nThey've been rick rolled 42069 times!**")