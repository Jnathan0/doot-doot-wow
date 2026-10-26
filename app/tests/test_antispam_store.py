"""TimeoutStore against a real metadata.db in tmp."""
import dataclasses

from modules.antispam import AntiSpamSettings, TimeoutInfo, TimeoutStore, SoundGuard, DEFAULT_SETTINGS
from tests.conftest import RealGetDB, db_rows, FakeClock

NOW = 1_700_000_000


def timeout(user_id=1, guild_id=10, started_at=NOW, seconds=600, **kwargs):
    return TimeoutInfo(id=None, guild_id=guild_id, user_id=user_id, reason=kwargs.pop("reason", "auto"),
                       started_at=started_at, expires_at=started_at + seconds, **kwargs)


def test_schema_is_idempotent(antispam_store, tmp_path):
    antispam_store.ensure_schema()
    antispam_store.ensure_schema()
    tables = db_rows(tmp_path / "metadata.db", "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
    assert tables == [("antispam_settings",), ("sound_timeouts",)]


def test_schema_applies_to_an_existing_metadata_db(tmp_path):
    # the real metadata.db already has the metadata.sql tables, the antispam tables are added next to them
    import sqlite3
    from tests.conftest import APP_DIR
    db_file = tmp_path / "metadata.db"
    conn = sqlite3.connect(db_file)
    conn.executescript((APP_DIR / "db" / "metadata.sql").read_text())
    conn.close()
    before = {name for (name,) in db_rows(db_file, "SELECT name FROM sqlite_master WHERE type = 'table'")}

    TimeoutStore(str(db_file), db_factory=RealGetDB).ensure_schema()

    after = {name for (name,) in db_rows(db_file, "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert after == before | {"antispam_settings", "sound_timeouts"}


def test_sound_timeouts_columns_match_the_reports_contract(antispam_store, tmp_path):
    columns = [row[1] for row in db_rows(tmp_path / "metadata.db", "PRAGMA table_info(sound_timeouts)")]
    assert columns == ["id", "guild_id", "user_id", "reason", "issued_by", "started_at", "expires_at",
                       "revoked_at", "revoked_by", "trigger_plays", "trigger_window_s", "note"]


def test_no_row_means_defaults(antispam_store):
    assert antispam_store.load_settings(10) == DEFAULT_SETTINGS
    assert antispam_store.load_all_settings() == {}


async def test_loading_the_guard_does_not_write_settings(antispam_store, tmp_path):
    guard = SoundGuard(antispam_store, clock=FakeClock(), wall_clock=FakeClock())
    await guard.load()
    assert guard.settings_for(10).enabled is False
    assert db_rows(tmp_path / "metadata.db", "SELECT COUNT(*) FROM antispam_settings") == [(0,)]


def test_settings_round_trip(antispam_store):
    settings = AntiSpamSettings(enabled=True, max_plays=12, window_seconds=120, reset_gap_seconds=0,
                                timeout_seconds=60, escalation_enabled=False, escalation_multiplier=1.5,
                                escalation_lookback_seconds=3600, max_timeout_seconds=7200,
                                exempt_role_ids=(111111111111111111, 222222222222222222),
                                exempt_administrators=False, count_random=False, count_quicksounds=False,
                                count_ignored_attempts=True, notify_mode="both", log_to_log_channel=False,
                                apply_discord_timeout=True)
    antispam_store.save_settings(10, settings, updated_by=99, now=NOW)
    assert antispam_store.load_settings(10) == settings
    assert antispam_store.load_settings(11) == DEFAULT_SETTINGS


def test_save_settings_upserts_one_row(antispam_store, tmp_path):
    antispam_store.save_settings(10, AntiSpamSettings(enabled=True), updated_by=1, now=NOW)
    antispam_store.save_settings(10, AntiSpamSettings(enabled=False, max_plays=5), updated_by=2, now=NOW + 5)
    rows = db_rows(tmp_path / "metadata.db",
                   "SELECT guild_id, enabled, max_plays, updated_at, updated_by FROM antispam_settings")
    assert rows == [(10, 0, 5, NOW + 5, 2)]


def test_snowflakes_are_stored_exactly(antispam_store, tmp_path):
    big = 987654321098765432
    antispam_store.insert_timeout(timeout(user_id=big, guild_id=big, issued_by=big))
    assert db_rows(tmp_path / "metadata.db", "SELECT guild_id, user_id, issued_by FROM sound_timeouts") == [(big, big, big)]


def test_insert_and_query_timeouts(antispam_store):
    first_id = antispam_store.insert_timeout(timeout(user_id=1, trigger_plays=10, trigger_window_s=180))
    second_id = antispam_store.insert_timeout(timeout(user_id=2, seconds=60, reason="manual", issued_by=99, note="loud"))
    antispam_store.insert_timeout(timeout(user_id=3, started_at=NOW - 1000))          # expired
    antispam_store.insert_timeout(timeout(user_id=4, guild_id=11))                    # other guild

    active = antispam_store.active_timeouts(10, NOW + 1)
    assert [(t.id, t.user_id) for t in active] == [(second_id, 2), (first_id, 1)]   # soonest to end first
    assert active[0].note == "loud" and active[0].issued_by == 99 and active[0].reason == "manual"
    assert active[1].trigger_plays == 10 and active[1].trigger_window_s == 180
    assert {t.user_id for t in antispam_store.all_active(NOW + 1)} == {1, 2, 4}


def test_count_recent_skips_old_and_pardoned(antispam_store):
    antispam_store.insert_timeout(timeout(started_at=NOW - 100_000))
    antispam_store.insert_timeout(timeout(started_at=NOW - 100))
    pardoned = antispam_store.insert_timeout(timeout(started_at=NOW - 50))
    antispam_store.revoke(pardoned, by=99, now=NOW)
    antispam_store.insert_timeout(timeout(user_id=2, started_at=NOW - 10))
    assert antispam_store.count_recent(10, 1, since=NOW - 86400) == 1


def test_revoke_active_only_touches_unexpired(antispam_store):
    antispam_store.insert_timeout(timeout(started_at=NOW - 1000))     # expired
    antispam_store.insert_timeout(timeout())
    assert antispam_store.revoke_active(10, 1, by=99, now=NOW + 1) == 1
    assert antispam_store.active_timeouts(10, NOW + 1) == []
    assert antispam_store.revoke_active(10, 1, by=99, now=NOW + 1) == 0


def test_history_newest_first_and_limited(antispam_store):
    for i in range(12):
        antispam_store.insert_timeout(timeout(started_at=NOW + i))
    history = antispam_store.history(10, 1, limit=10)
    assert [t.started_at for t in history] == [NOW + i for i in range(11, 1, -1)]


def test_store_sql_is_parameterized(antispam_store):
    # a hostile note is stored as data
    note = "x'); DROP TABLE sound_timeouts; --"
    antispam_store.insert_timeout(timeout(note=note))
    assert antispam_store.history(10, 1)[0].note == note
