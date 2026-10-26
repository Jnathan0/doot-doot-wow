# Doot Doot!

Doot Doot is a discord bot for playing sound files in a voice channel. Users can upload files to the bot and query stats. Metadata is cached using Redis and persistent data is stored using sqlite3. 


# Docker 

## Docker Environment Variables

This is a table of environment variables that can be set before running the container.
It includes the ENV VAR name, description and default value and type. 
Environment Variables that are (required) need values in order for the app to run.

|  Env Var name            |Description          |Default Value                |Type  |
|----------------|-------------------------------|-----------------------------|------|
|TOKEN (required)|The discord api token for your bot |NONE            |	  STRING|
|PREFIX        |The command prefix to call commands            |'            |STRING      |
|SUB_CMD_SEP          |The command separator for subcommands|Space (aka " ")|STRING      |
|REDIS_ADDRESS|Endpoint address for the redis cache| Localhost| IP ADDRESS OR URL
|REDIS_PORT| The port number to access the redis cache| 6379|INT
|REDIS_CHARSET|The supported charset to use with the redis cache| UTF-8|STRING
|SOUNDS_PATH| A path to specify the parent directory that contains all sound files|/sounds|STRING
|GIFS_PATH| A path to specify the parent directory that contains all the .gif files|/gifs|STRING
|IMAGES_PATH| A path to specify the parent directory that contains all static images|/images|STRING
|VIDEOS_PATH| A path to specify the parent directory that contains all video files|/videos|STRING
|DATABASE_PATH| A path to specify the parent directory that contains the sqlite3 .db file for sounds|/db|STRING
|METADATA_DB_PATH| A path to specify the parent directory that contains the sqlite3 .db file for persistent app metadata|/db|STRING
|OWB_ID (required)| The discord role id (recommended) or role name of the role allowed to use `/add` (uploading sounds), `/restart` and `'mod`. Server admins and the bot owner can always use them. Leave it blank (`" "`) to allow only admins and the owner|None|STRING or INT
|OWNER_IDS| Comma separated discord user ids allowed to use the `/admin` commands. When empty, the owner (or team) of the discord application is used|empty|STRING
|LOG_CHANNEL (reqiured)| The discord channel ID that the bot posts log events to|NONE|INT
|REVERSE_CHAR| The character that is used after a sound command to play the sound in reverse| - |STRING|
|IMAGE_SIZE_LIMIT| The maximum image size (in bytes) that can be uploaded to the app| 800000 (8 MB)|INT
|REDIS_DUMP_DIR| The path that contains the .rdb file to load into redis-server during app start|/db|PATH
|REDIS_DUMPFILE| The filename with .rdb extension to load into redis-server for persistent cache data| dump.rdb|STRING


# Getting Started

**System Package Requirements**
Please make sure these packages are installed before proceeding. 
* Python3.8 or higher 
* Sqlite3 (https://www.sqlite.org/download.html)
* Redis Server (https://redis.io/)
* FF-Mpeg (https://www.ffmpeg.org/download.html)

**Install python packages**
Navigate to the project directory and install the python package requirements:
`pip3 install -r requirements.txt`

**Directories**
##### _Media_
By default the app puts the `media` directory in the root directory of the project
The `media` directory contains the `sounds`, `gifs`, `images`, and `videos` sub directories.
You can optionally choose to specifiy your own path for `media` but the subdirectories must be contained in the `media` folder.

The directory structure is as follows:
`media/`.
| ____`sounds/`
| ____`images/`
| ____`videos/`
| ____`gifs/`


#### DB
The `db/` directory by default is in the root project directory.
You can specify in the `config.js` or as system environment variables the path for the `db/` directory. 
**NOTE**: The `.sql` files are by default located in the applications `db/` directory, and are used for setting up the sqlite3 databases for persistent data. 

**Getting config.json ready**
Make a copy of _config_example.json_ and rename it to _config.json_
The following keys in the _config.json_ file require these values:
* "token" 
	* (string) The API token obtained from discord
* "log_channel"
	* (int) The channel ID that logged events are posted to
* "prefix"
	* (char) The prefix to prepend to bot commands in order to call them 
	* The default is `'`
* "reverse_char"
	* (char) The character to flag the reversal of sounds during playback
	* The default is `-`
* "sounds_path"
	* (string) The path to the `media	`directory
	* The project by default includes the `media` directory with the required sub-directories
		* The path still needs to be specified before startup.
* "database_path"
	* (string) The path to the `db` directory
	* The project by default includes this directory in the root folder
* "sub_cmd_sep"
	* (char) The character that separates sub-commands that can be used for main commands
		* The default is a space
		* **warning**: Changing this value will result in undefined behaviour of the bot
* "owb_id"
	* (int) The discord role id that is used for elevated users
	* We reccomend making a custom discord role for privileged functions
* "redis"
	* "address"
		* The address of the redis server to use for caching
			* The default is `localhost`
	* "port"
		* The port to access the redis caching server on
			* The default is `6379`
	* "charset"
		* The charset type used for encoding with redis
			* The default is `utf-8`


## Create database files 

The database files need to be created.
Navigate to your `db/` directory and make sure `schema.sql` and `metadata_schema.sql` are in the directory
Create the sqlite3 database with the command:
`sqlite3 sounds.db < schema.sql`

And create the metadata database
`sqlite3 metadata.db < metadata_schema.sql`


## Running

Navigate to the directory that contains `main.py` and issue the command:
`python3.x main.py`
Where _x_ is the python 3 version you are using. 

# Command permissions

| Who | Commands |
|---|---|
| Bot owner (the discord application owner, or `OWNER_IDS`) | `/admin shutdown`, `/admin presence`, `/admin stats`, `/admin avatar` |
| Server admins (Administrator permission) and the bot owner | `/antispam …` |
| Members with the `OWB_ID` role, server admins and the bot owner | `/add`, `/restart`, `'mod` |
| Everyone | everything else |

`/admin` and `/antispam` are hidden in the client from members without the Administrator permission.
The checks also run when a command is used, so changing the command permissions in
Server Settings → Integrations can't let anyone else run them. Uses of `/admin` (and refused attempts) are posted to the log channel.

# Anti-spam (sound-spam timeout)

The bot can automatically stop a user from playing sounds for a while when they play sounds non-stop.
It is **off by default**: nothing is ever blocked until an admin runs `/antispam enable`.

A timeout only blocks the bot's sound commands (sound and folder names, `random`, quicksounds `1`/`2`/`3`).
The user can still chat and use voice, and entrance sounds still play.
While timed out, sound commands are deleted and the user gets a reminder at most once every 30 seconds.

**The rule:** a user is timed out when they play `max_plays` sounds within `window`, without a break of `reset_gap` or more
between plays. A break of `reset_gap` forgives the streak, so a few quick sounds followed by a pause never trip it.

| Setting | Default |
|---|---|
| Enabled | off |
| Rule | 10 plays within 3 minutes, a 30 second break resets the count |
| Timeout | 10 minutes |
| Escalation | ×2 for each timeout in the last day (10m → 20m → 40m …), capped at 1 week |
| Exempt | Members with the Administrator permission |
| Counted plays | sound and folder commands, `random`, quicksounds. Not commands sent while the bot is already playing |
| Notices | In the channel (deleted after 15s), plus the log channel |
| Discord timeout | off |

**Commands** (`/antispam …`, only visible to members with the Administrator permission, usable by them and the bot owner):

| Command | What it does |
|---|---|
| `status` | Show the settings and the number of active timeouts |
| `enable` / `disable` | Turn it on or off. Disabling pauses active timeouts, it does not lift them (use `pardon`) |
| `rule max_plays window_amount window_unit [reset_gap_amount reset_gap_unit]` | Set the trigger. A reset gap of `0` turns break forgiveness off |
| `duration amount unit` | Base timeout length |
| `escalation enabled [multiplier] [max_amount max_unit] [lookback_amount lookback_unit]` | Repeat offender settings |
| `counting [random] [quicksounds] [ignored_attempts]` | Which plays count. `ignored_attempts` counts commands sent while the bot is busy |
| `notify mode` | Where users are told: `channel`, `dm`, `both` or `none` |
| `options [exempt_admins] [log_channel] [discord_timeout]` | Exempt admins, log channel messages, and the optional Discord timeout |
| `exempt-role add/remove/list` | Roles that are never timed out |
| `reset-defaults` | Restore the defaults above (keeps it enabled or disabled), asks for confirmation |
| `timeout member amount unit [reason]` | Manually time a member out of sounds |
| `pardon member` | Lift a member's timeout |
| `active` | List active timeouts |
| `history member` | A member's last 10 timeouts |

Durations take an amount and a unit (seconds, minutes, hours, days or weeks). Timeouts can be up to 52 weeks.

**Discord timeout** (`/antispam options discord_timeout:True`, off by default) also applies Discord's own member timeout,
which mutes the user **server-wide** (text and voice), not just sounds. It needs the bot to have the Moderate Members
permission and a role above the user's, and Discord limits it to 4 weeks.

Settings and timeouts are stored in `metadata.db` (tables `antispam_settings` and `sound_timeouts`, see `app/db/antispam.sql`).
The tables are created automatically when the bot starts, and timeouts survive restarts.
Pardoned timeouts don't count toward escalation.
