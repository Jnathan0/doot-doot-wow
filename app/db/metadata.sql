CREATE TABLE IF NOT EXISTS "timeseries"
(
[entry_id] NVARCHAR(128) NOT NULL,
[sound_id] NVARCHAR(64) NOT NULL,
[sound_folder] NVARCHAR(64) NOT NULL,
[timestamp] FLOAT NOT NULL,
[day] INTEGER NOT NULL,
[month] INTEGER NOT NULL,
[year] INTEGER NOT NULL,
[call_type] NVARCHAR(16),
[user_id] INTEGER NOT NULL
);
CREATE UNIQUE INDEX timeseries_entry_timestamp on timeseries (entry_id, timestamp);
