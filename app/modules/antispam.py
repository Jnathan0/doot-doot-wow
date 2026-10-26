"""
Sound-spam timeout.

Users who play sounds non-stop get blocked from the bot's sound commands for a while.
The rule: a user trips it by playing `max_plays` sounds within `window_seconds` with no
quiet gap of `reset_gap_seconds` or more between consecutive plays.

* PlayWindow / AntiSpamSettings / SoundGuard hold the logic and take injectable clocks,
  they don't import discord so they can be tested on their own.
* TimeoutStore persists settings and issued timeouts in metadata.db (db/antispam.sql).
* `guard` is the module-level singleton the Player / SoundsUtils / AntiSpam cogs share.
"""
import asyncio
import sqlite3
import time
from collections import deque
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from discord.ext import commands

from .app_config import config
from .database import GetDB
from .durations import humanize, UNIT_SECONDS

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "db" / "antispam.sql"

NOTIFY_MODES = ("channel", "dm", "both", "none")
MAX_TIMEOUT_SECONDS = 52 * UNIT_SECONDS["weeks"]
# discord caps Member.timeout() at 28 days
DISCORD_TIMEOUT_MAX_SECONDS = 4 * UNIT_SECONDS["weeks"]


class InvalidSetting(ValueError):
    """Raised with a user facing message when a setting is out of range."""
    pass


@dataclass(frozen=True)
class AntiSpamSettings:
    """Per guild settings. The defaults are what a guild with no settings row gets (feature off)."""
    enabled: bool = False
    max_plays: int = 10
    window_seconds: int = 180
    reset_gap_seconds: int = 30
    timeout_seconds: int = 600
    escalation_enabled: bool = True
    escalation_multiplier: float = 2.0
    escalation_lookback_seconds: int = 86400
    max_timeout_seconds: int = 604800
    exempt_role_ids: Tuple[int, ...] = ()
    exempt_administrators: bool = True
    count_random: bool = True
    count_quicksounds: bool = True
    count_ignored_attempts: bool = False
    notify_mode: str = "channel"
    log_to_log_channel: bool = True
    apply_discord_timeout: bool = False

    @classmethod
    def from_row(cls, row) -> "AntiSpamSettings":
        values = {}
        for field in fields(cls):
            if field.name not in row.keys() or row[field.name] is None:
                continue
            value = row[field.name]
            if field.name == "exempt_role_ids":
                value = tuple(int(role_id) for role_id in str(value).split(",") if role_id.strip())
            elif isinstance(field.default, bool):
                value = bool(value)
            values[field.name] = value
        return cls(**values)

    def to_row(self) -> dict:
        row = {}
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name == "exempt_role_ids":
                value = ",".join(str(role_id) for role_id in value)
            elif isinstance(value, bool):
                value = int(value)
            row[field.name] = value
        return row

    def validate(self) -> "AntiSpamSettings":
        """Returns self if every value is in range, otherwise raises InvalidSetting."""
        timeout_cap = DISCORD_TIMEOUT_MAX_SECONDS if self.apply_discord_timeout else MAX_TIMEOUT_SECONDS
        if not 2 <= self.max_plays <= 100:
            raise InvalidSetting("Max plays must be between 2 and 100.")
        if not 10 <= self.window_seconds <= UNIT_SECONDS["days"]:
            raise InvalidSetting("Window must be between 10s and 1d.")
        if not 0 <= self.reset_gap_seconds <= self.window_seconds:
            raise InvalidSetting(f"Reset gap must be between 0 (off) and the window ({humanize(self.window_seconds)}).")
        if not 1 <= self.timeout_seconds <= timeout_cap:
            raise InvalidSetting(f"Timeout must be between 1s and {humanize(timeout_cap)}"
                                 + (" while Discord timeouts are on." if self.apply_discord_timeout else "."))
        if not 1.0 <= self.escalation_multiplier <= 10.0:
            raise InvalidSetting("Escalation multiplier must be between 1.0 and 10.0.")
        if not 60 <= self.escalation_lookback_seconds <= MAX_TIMEOUT_SECONDS:
            raise InvalidSetting(f"Escalation lookback must be between 1m and {humanize(MAX_TIMEOUT_SECONDS)}.")
        if not self.timeout_seconds <= self.max_timeout_seconds <= timeout_cap:
            raise InvalidSetting(f"Max timeout must be between the base timeout ({humanize(self.timeout_seconds)}) "
                                 f"and {humanize(timeout_cap)}"
                                 + (" while Discord timeouts are on." if self.apply_discord_timeout else "."))
        if self.notify_mode not in NOTIFY_MODES:
            raise InvalidSetting(f"Notify mode must be one of: {', '.join(NOTIFY_MODES)}.")
        return self

    def changes_from(self, old: "AntiSpamSettings") -> List[Tuple[str, object, object]]:
        """(name, old value, new value) for every setting that differs from old."""
        return [(field.name, getattr(old, field.name), getattr(self, field.name))
                for field in fields(self) if getattr(old, field.name) != getattr(self, field.name)]

    def rule_sentence(self) -> str:
        sentence = (f"Timeout **{humanize(self.timeout_seconds)}** if a user plays **{self.max_plays}** sounds "
                    f"within **{humanize(self.window_seconds)}**")
        if self.reset_gap_seconds:
            sentence += f" without a **{humanize(self.reset_gap_seconds)}** break"
        return sentence


DEFAULT_SETTINGS = AntiSpamSettings()


@dataclass(frozen=True)
class TimeoutInfo:
    """One row of sound_timeouts."""
    id: Optional[int]
    guild_id: int
    user_id: int
    reason: str                     # 'auto' | 'manual'
    started_at: int                 # unix epoch seconds
    expires_at: int                 # unix epoch seconds
    issued_by: Optional[int] = None
    revoked_at: Optional[int] = None
    revoked_by: Optional[int] = None
    trigger_plays: Optional[int] = None
    trigger_window_s: Optional[int] = None
    note: Optional[str] = None

    @property
    def duration(self) -> int:
        return self.expires_at - self.started_at

    @classmethod
    def from_row(cls, row) -> "TimeoutInfo":
        names = {field.name for field in fields(cls)}
        return cls(**{key: row[key] for key in row.keys() if key in names})


class PlayWindow:
    """
    Recent play timestamps per (guild_id, user_id), kept in memory only.
    Losing them on restart just gives everyone a fresh window.
    """
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._plays: Dict[tuple, deque] = {}

    def record(self, key, settings: AntiSpamSettings) -> Optional[int]:
        """Records a play, returns the number of plays in the window if the rule tripped, else None."""
        now = self._clock()
        plays = self._plays.setdefault(key, deque())
        if plays and settings.reset_gap_seconds > 0 and now - plays[-1] >= settings.reset_gap_seconds:
            # the user paused, forgive the streak
            plays.clear()
        plays.append(now)
        while plays and now - plays[0] > settings.window_seconds:
            plays.popleft()
        if len(plays) >= settings.max_plays:
            count = len(plays)
            # the timeout is the penalty now, start over once it ends
            del self._plays[key]
            return count
        return None

    def forget(self, key):
        self._plays.pop(key, None)


class TimeoutStore:
    """
    SQLite persistence for antispam_settings and sound_timeouts in metadata.db.
    Methods are blocking, SoundGuard calls them through asyncio.to_thread.
    """
    def __init__(self, db_path, db_factory=None):
        self.db_path = db_path
        self._db_factory = db_factory or GetDB

    def _db(self):
        db = self._db_factory(self.db_path)
        db.set_row_factory(sqlite3.Row)
        return db

    def ensure_schema(self):
        schema = SCHEMA_PATH.read_text()
        with self._db() as db:
            db.conn.executescript(schema)
            db.commit()

    def load_settings(self, guild_id) -> AntiSpamSettings:
        with self._db() as db:
            row = db.cursor.execute("SELECT * FROM antispam_settings WHERE guild_id = ?", (guild_id,)).fetchone()
        return AntiSpamSettings.from_row(row) if row else DEFAULT_SETTINGS

    def load_all_settings(self) -> Dict[int, AntiSpamSettings]:
        with self._db() as db:
            rows = db.cursor.execute("SELECT * FROM antispam_settings").fetchall()
        return {row["guild_id"]: AntiSpamSettings.from_row(row) for row in rows}

    def save_settings(self, guild_id, settings: AntiSpamSettings, updated_by, now):
        row = settings.to_row()
        params = (guild_id, row["enabled"], row["max_plays"], row["window_seconds"], row["reset_gap_seconds"],
                  row["timeout_seconds"], row["escalation_enabled"], row["escalation_multiplier"],
                  row["escalation_lookback_seconds"], row["max_timeout_seconds"], row["exempt_role_ids"],
                  row["exempt_administrators"], row["count_random"], row["count_quicksounds"],
                  row["count_ignored_attempts"], row["notify_mode"], row["log_to_log_channel"],
                  row["apply_discord_timeout"], now, updated_by)
        with self._db() as db:
            db.cursor.execute(
                """
                INSERT INTO antispam_settings (
                    guild_id, enabled, max_plays, window_seconds, reset_gap_seconds,
                    timeout_seconds, escalation_enabled, escalation_multiplier,
                    escalation_lookback_seconds, max_timeout_seconds, exempt_role_ids,
                    exempt_administrators, count_random, count_quicksounds,
                    count_ignored_attempts, notify_mode, log_to_log_channel,
                    apply_discord_timeout, updated_at, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (guild_id) DO UPDATE SET
                    enabled = excluded.enabled,
                    max_plays = excluded.max_plays,
                    window_seconds = excluded.window_seconds,
                    reset_gap_seconds = excluded.reset_gap_seconds,
                    timeout_seconds = excluded.timeout_seconds,
                    escalation_enabled = excluded.escalation_enabled,
                    escalation_multiplier = excluded.escalation_multiplier,
                    escalation_lookback_seconds = excluded.escalation_lookback_seconds,
                    max_timeout_seconds = excluded.max_timeout_seconds,
                    exempt_role_ids = excluded.exempt_role_ids,
                    exempt_administrators = excluded.exempt_administrators,
                    count_random = excluded.count_random,
                    count_quicksounds = excluded.count_quicksounds,
                    count_ignored_attempts = excluded.count_ignored_attempts,
                    notify_mode = excluded.notify_mode,
                    log_to_log_channel = excluded.log_to_log_channel,
                    apply_discord_timeout = excluded.apply_discord_timeout,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                params,
            )
            db.commit()

    def insert_timeout(self, info: TimeoutInfo) -> int:
        with self._db() as db:
            db.cursor.execute(
                "INSERT INTO sound_timeouts (guild_id, user_id, reason, issued_by, started_at, expires_at, "
                "trigger_plays, trigger_window_s, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (info.guild_id, info.user_id, info.reason, info.issued_by, info.started_at, info.expires_at,
                 info.trigger_plays, info.trigger_window_s, info.note),
            )
            db.commit()
            return db.cursor.lastrowid

    def active_timeouts(self, guild_id, now) -> List[TimeoutInfo]:
        with self._db() as db:
            rows = db.cursor.execute(
                "SELECT * FROM sound_timeouts WHERE guild_id = ? AND expires_at > ? AND revoked_at IS NULL "
                "ORDER BY expires_at",
                (guild_id, now),
            ).fetchall()
        return [TimeoutInfo.from_row(row) for row in rows]

    def all_active(self, now) -> List[TimeoutInfo]:
        with self._db() as db:
            rows = db.cursor.execute(
                "SELECT * FROM sound_timeouts WHERE expires_at > ? AND revoked_at IS NULL ORDER BY expires_at",
                (now,),
            ).fetchall()
        return [TimeoutInfo.from_row(row) for row in rows]

    def count_recent(self, guild_id, user_id, since) -> int:
        """Timeouts that started at or after `since` and weren't pardoned, used for escalation."""
        with self._db() as db:
            row = db.cursor.execute(
                "SELECT COUNT(*) AS n FROM sound_timeouts WHERE guild_id = ? AND user_id = ? AND started_at >= ? "
                "AND revoked_at IS NULL",
                (guild_id, user_id, since),
            ).fetchone()
        return row["n"]

    def history(self, guild_id, user_id, limit=10) -> List[TimeoutInfo]:
        with self._db() as db:
            rows = db.cursor.execute(
                "SELECT * FROM sound_timeouts WHERE guild_id = ? AND user_id = ? ORDER BY started_at DESC, id DESC "
                "LIMIT ?",
                (guild_id, user_id, limit),
            ).fetchall()
        return [TimeoutInfo.from_row(row) for row in rows]

    def revoke(self, timeout_id, by, now):
        with self._db() as db:
            db.cursor.execute(
                "UPDATE sound_timeouts SET revoked_at = ?, revoked_by = ? WHERE id = ? AND revoked_at IS NULL",
                (now, by, timeout_id),
            )
            db.commit()

    def revoke_active(self, guild_id, user_id, by, now) -> int:
        """Revokes every unexpired timeout of a user, returns how many were revoked."""
        with self._db() as db:
            db.cursor.execute(
                "UPDATE sound_timeouts SET revoked_at = ?, revoked_by = ? "
                "WHERE guild_id = ? AND user_id = ? AND expires_at > ? AND revoked_at IS NULL",
                (now, by, guild_id, user_id, now),
            )
            db.commit()
            return db.cursor.rowcount


class SoundGuard:
    """
    Facade used by the cogs. Blocking checks only read in-memory state (loaded by load() at
    AntiSpam cog load), database writes go through asyncio.to_thread.
    Until load() has run the guard is inert: nothing is blocked or counted.
    """
    BLOCKED_NOTICE_INTERVAL = 30

    def __init__(self, store: TimeoutStore, clock=time.monotonic, wall_clock=time.time):
        self.store = store
        self._clock = clock
        self._wall_clock = wall_clock
        self.window = PlayWindow(clock)
        self._settings: Dict[int, AntiSpamSettings] = {}
        self._active: Dict[tuple, TimeoutInfo] = {}
        self._last_notice: Dict[tuple, float] = {}
        self.loaded = False

    def now(self) -> int:
        return int(self._wall_clock())

    async def load(self):
        await asyncio.to_thread(self.store.ensure_schema)
        self._settings = await asyncio.to_thread(self.store.load_all_settings)
        self._active = {}
        for info in await asyncio.to_thread(self.store.all_active, self.now()):
            key = (info.guild_id, info.user_id)
            if key not in self._active or info.expires_at > self._active[key].expires_at:
                self._active[key] = info
        self.loaded = True

    # -- settings -----------------------------------------------------------

    def settings_for(self, guild_id) -> AntiSpamSettings:
        return self._settings.get(guild_id, DEFAULT_SETTINGS)

    async def update_settings(self, guild_id, settings: AntiSpamSettings, updated_by) -> AntiSpamSettings:
        settings.validate()
        await asyncio.to_thread(self.store.save_settings, guild_id, settings, updated_by, self.now())
        self._settings[guild_id] = settings
        return settings

    # -- checks -------------------------------------------------------------

    @staticmethod
    def is_exempt(member, settings: AntiSpamSettings) -> bool:
        permissions = getattr(member, "guild_permissions", None)
        if settings.exempt_administrators and permissions is not None and permissions.administrator is True:
            return True
        role_ids = {role.id for role in getattr(member, "roles", [])}
        return bool(role_ids.intersection(settings.exempt_role_ids))

    @staticmethod
    def should_count(play_type, settings: AntiSpamSettings) -> bool:
        if play_type == "direct":
            return True
        if play_type == "random":
            return settings.count_random
        if play_type == "quicksound":
            return settings.count_quicksounds
        # entrance sounds and anything else are never user spam
        return False

    def active_timeout(self, guild_id, user_id) -> Optional[TimeoutInfo]:
        key = (guild_id, user_id)
        info = self._active.get(key)
        if info is None:
            return None
        if info.expires_at <= self.now():
            del self._active[key]
            return None
        return info

    def active_count(self, guild_id) -> int:
        return sum(1 for (g, u) in list(self._active) if g == guild_id and self.active_timeout(g, u))

    def is_blocked(self, member) -> Optional[TimeoutInfo]:
        """The member's active timeout if they may not play sounds right now, else None."""
        if not self.loaded:
            return None
        settings = self.settings_for(member.guild.id)
        if not settings.enabled or self.is_exempt(member, settings):
            return None
        return self.active_timeout(member.guild.id, member.id)

    def should_notify_blocked(self, guild_id, user_id) -> bool:
        """True at most once every BLOCKED_NOTICE_INTERVAL seconds per user."""
        key = (guild_id, user_id)
        now = self._clock()
        last = self._last_notice.get(key)
        if last is not None and now - last < self.BLOCKED_NOTICE_INTERVAL:
            return False
        self._last_notice[key] = now
        return True

    # -- recording and issuing ----------------------------------------------

    async def on_play(self, member, play_type, ignored=False) -> Optional[TimeoutInfo]:
        """
        Records a play that is about to start (or, with ignored=True, a command the bot ignored
        because it was busy). Returns the new TimeoutInfo if this play tripped the rule.
        """
        if not self.loaded:
            return None
        guild_id, user_id = member.guild.id, member.id
        settings = self.settings_for(guild_id)
        if not settings.enabled or self.is_exempt(member, settings):
            return None
        if not self.should_count(play_type, settings):
            return None
        if ignored and not settings.count_ignored_attempts:
            return None
        if self.active_timeout(guild_id, user_id) is not None:
            return None
        plays = self.window.record((guild_id, user_id), settings)
        if plays is None:
            return None
        seconds = await self.timeout_for(guild_id, user_id, settings)
        return await self.issue(guild_id, user_id, seconds, "auto",
                                trigger_plays=plays, trigger_window_s=settings.window_seconds)

    async def timeout_for(self, guild_id, user_id, settings: AntiSpamSettings) -> int:
        """Base timeout, doubled (by the multiplier) for every prior offence in the lookback, capped."""
        if not settings.escalation_enabled:
            return settings.timeout_seconds
        since = self.now() - settings.escalation_lookback_seconds
        prior = await asyncio.to_thread(self.store.count_recent, guild_id, user_id, since)
        cap = max(settings.max_timeout_seconds, settings.timeout_seconds)
        seconds = float(settings.timeout_seconds)
        for _ in range(prior):
            seconds *= settings.escalation_multiplier
            if seconds >= cap:
                break
        return int(min(seconds, cap))

    async def issue(self, guild_id, user_id, seconds, reason, issued_by=None, note=None,
                    trigger_plays=None, trigger_window_s=None) -> TimeoutInfo:
        """Times a user out of sounds, replacing any timeout they already have."""
        key = (guild_id, user_id)
        now = self.now()
        if self.active_timeout(guild_id, user_id) is not None:
            await asyncio.to_thread(self.store.revoke_active, guild_id, user_id, issued_by, now)
        info = TimeoutInfo(id=None, guild_id=guild_id, user_id=user_id, reason=reason, started_at=now,
                           expires_at=now + int(seconds), issued_by=issued_by, trigger_plays=trigger_plays,
                           trigger_window_s=trigger_window_s, note=note)
        timeout_id = await asyncio.to_thread(self.store.insert_timeout, info)
        info = replace(info, id=timeout_id)
        self._active[key] = info
        self.window.forget(key)
        self._last_notice.pop(key, None)
        return info

    async def pardon(self, guild_id, user_id, by) -> bool:
        """Lifts a user's active timeout, returns False if they didn't have one."""
        key = (guild_id, user_id)
        had_active = self.active_timeout(guild_id, user_id) is not None
        revoked = await asyncio.to_thread(self.store.revoke_active, guild_id, user_id, by, self.now())
        self._active.pop(key, None)
        self.window.forget(key)
        return had_active or revoked > 0

    async def list_active(self, guild_id) -> List[TimeoutInfo]:
        return await asyncio.to_thread(self.store.active_timeouts, guild_id, self.now())

    async def history(self, guild_id, user_id, limit=10) -> List[TimeoutInfo]:
        return await asyncio.to_thread(self.store.history, guild_id, user_id, limit)


# config.metadata_db_path is the full path to metadata.db
guard = SoundGuard(TimeoutStore(config.metadata_db_path))


# ---------------------------------------------------------------------------
# Hooks for the sound playing prefix commands
# ---------------------------------------------------------------------------

class SoundTimeoutActive(commands.CheckFailure):
    """Raised by sound_guard_check when the author is timed out, handled by the AntiSpam cog."""
    def __init__(self, info: TimeoutInfo, play_type: str):
        self.info = info
        self.play_type = play_type
        super().__init__(f"User {info.user_id} is timed out from playing sounds until {info.expires_at}")


def sound_guard_check(play_type):
    """Command check that blocks timed out users from a sound playing command."""
    async def predicate(ctx):
        if ctx.guild is None:
            return True
        info = guard.is_blocked(ctx.author)
        if info is not None:
            raise SoundTimeoutActive(info, play_type)
        return True
    return commands.check(predicate)


async def record_play(ctx, play_type, ignored=False) -> Optional[TimeoutInfo]:
    """
    Call right before a sound starts playing (or with ignored=True where a busy bot drops the command).
    If the play trips the rule, the AntiSpam cog is told through the "sound_timeout" event,
    so the play itself is never held up or broken by notifications or database errors.
    """
    try:
        info = await guard.on_play(ctx.author, play_type, ignored=ignored)
    except Exception as e:
        print(f"antispam: failed to record play: {e}")
        return None
    if info is not None:
        ctx.bot.dispatch("sound_timeout", ctx, info)
    return info
