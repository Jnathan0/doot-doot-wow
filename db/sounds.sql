CREATE TABLE IF NOT EXISTS "authors"
(
[author_id] INTEGER PRIMARY KEY NOT NULL
);
CREATE TABLE IF NOT EXISTS "categories"
(
[category_id] NVARCHAR(220) PRIMARY KEY NOT NULL
);
CREATE TABLE IF NOT EXISTS "sounds"
(
[sound_id] NVARCHAR(220) NOT NULL,
[sound_name] NVARCHAR(220) NOT NULL,
[category_id] NVARCHAR(220) NOT NULL,
[author_id] INTEGER NOT NULL,
[plays] INTEGER,
[date] NVARCHAR(20),
FOREIGN KEY ([category_id]) REFERENCES "categories" ([category_id]) ON DELETE NO ACTION ON UPDATE NO ACTION,
FOREIGN KEY ([author_id]) REFERENCES "authors" ([author_id]) ON DELETE NO ACTION ON UPDATE NO ACTION
);
CREATE TABLE IF NOT EXISTS "entrance"(
[sound_id] NVARCHAR(220) NOT NULL,
[user_id] INTEGER NOT NULL,
[last_seen] NVARCHAR(80),
FOREIGN KEY ([sound_id]) REFERENCES "sounds" ([sound_id]) ON DELETE NO ACTION ON UPDATE NO ACTION
);
CREATE TABLE IF NOT EXISTS "quicksounds"
(
[sound_id] NVARCHAR(220) NOT NULL,
[user_id] INTEGER NOT NULL,
[alias] INTEGER,
FOREIGN KEY ([sound_id]) REFERENCES "sounds" ([sound_id]) ON DELETE NO ACTION ON UPDATE NO ACTION
);
CREATE TABLE IF NOT EXISTS "images"
(
[sound_id] NVARCHAR(220) NOT NULL,
[image_id] NVARCHAR(256) NOT NULL,
[folder]   NVARCHAR(220) NOT NULL,
FOREIGN KEY ([sound_id]) REFERENCES "sounds" ([sound_id]) ON DELETE NO ACTION ON UPDATE NO ACTION
);