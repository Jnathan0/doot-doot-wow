-- Sound-spam timeout tables, created in metadata.db by TimeoutStore.ensure_schema() when the AntiSpam cog loads.
-- Idempotent: safe to run on every start.

-- One row per guild, only written once an admin changes a setting (no row = defaults, feature off).
CREATE TABLE IF NOT EXISTS antispam_settings (
    guild_id                    BIGINT  PRIMARY KEY,
    enabled                     INTEGER NOT NULL DEFAULT 0,
    max_plays                   INTEGER NOT NULL DEFAULT 10,
    window_seconds              INTEGER NOT NULL DEFAULT 180,
    reset_gap_seconds           INTEGER NOT NULL DEFAULT 30,
    timeout_seconds             INTEGER NOT NULL DEFAULT 600,
    escalation_enabled          INTEGER NOT NULL DEFAULT 1,
    escalation_multiplier       REAL    NOT NULL DEFAULT 2.0,
    escalation_lookback_seconds INTEGER NOT NULL DEFAULT 86400,
    max_timeout_seconds         INTEGER NOT NULL DEFAULT 604800,
    exempt_role_ids             TEXT    NOT NULL DEFAULT '',     -- comma-separated snowflakes
    exempt_administrators       INTEGER NOT NULL DEFAULT 1,
    count_random                INTEGER NOT NULL DEFAULT 1,
    count_quicksounds           INTEGER NOT NULL DEFAULT 1,
    count_ignored_attempts      INTEGER NOT NULL DEFAULT 0,
    notify_mode                 TEXT    NOT NULL DEFAULT 'channel',
    log_to_log_channel          INTEGER NOT NULL DEFAULT 1,
    apply_discord_timeout       INTEGER NOT NULL DEFAULT 0,
    updated_at                  BIGINT,
    updated_by                  BIGINT
);

-- Shared contract with the stats/reports plan (it reads this table), keep column names stable.
CREATE TABLE IF NOT EXISTS sound_timeouts (
    id               INTEGER PRIMARY KEY,      -- SQLite rowid alias
    guild_id         BIGINT  NOT NULL,
    user_id          BIGINT  NOT NULL,
    reason           TEXT    NOT NULL,         -- 'auto' | 'manual'
    issued_by        BIGINT,                   -- NULL when automatic
    started_at       BIGINT  NOT NULL,         -- unix epoch seconds, UTC
    expires_at       BIGINT  NOT NULL,         -- unix epoch seconds, UTC
    revoked_at       BIGINT,
    revoked_by       BIGINT,
    trigger_plays    INTEGER,                  -- plays counted when tripped (auto only)
    trigger_window_s INTEGER,                  -- window in force when tripped (auto only)
    note             TEXT
);
CREATE INDEX IF NOT EXISTS idx_sound_timeouts_user    ON sound_timeouts (guild_id, user_id, started_at);
CREATE INDEX IF NOT EXISTS idx_sound_timeouts_expires ON sound_timeouts (guild_id, expires_at);
