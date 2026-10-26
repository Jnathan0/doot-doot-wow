"""
Detection rule (PlayWindow) and SoundGuard behaviour, with a fake clock and a real
metadata.db in tmp for the persisted timeouts.
"""
import dataclasses
import pytest

from modules.antispam import AntiSpamSettings, PlayWindow, SoundGuard, InvalidSetting, TimeoutInfo
from tests.conftest import FakeClock, make_member

ON = AntiSpamSettings(enabled=True)


def plays_until_trip(window, clock, settings, spacings, key=(10, 1)):
    """Records a play after each spacing, returns the 1-based index of the play that tripped (or None)."""
    for index, spacing in enumerate(spacings, start=1):
        clock.advance(spacing)
        if window.record(key, settings) is not None:
            return index
    return None


# ---------------------------------------------------------------------------
# PlayWindow
# ---------------------------------------------------------------------------

def test_nine_plays_do_not_trip_the_tenth_does():
    clock = FakeClock()
    window = PlayWindow(clock)
    assert plays_until_trip(window, clock, ON, [5] * 9) is None
    clock.advance(5)
    assert window.record((10, 1), ON) == 10


def test_gap_resets_the_streak():
    clock = FakeClock()
    window = PlayWindow(clock)
    spacings = [1] * 5 + [31] + [1] * 4
    assert plays_until_trip(window, clock, ON, spacings) is None


def test_without_reset_gap_the_same_sequence_trips():
    clock = FakeClock()
    window = PlayWindow(clock)
    spacings = [1] * 5 + [31] + [1] * 4
    assert plays_until_trip(window, clock, dataclasses.replace(ON, reset_gap_seconds=0), spacings) == 10


def test_pause_shorter_than_reset_gap_does_not_forgive():
    clock = FakeClock()
    window = PlayWindow(clock)
    spacings = [1] * 5 + [29] + [1] * 4
    assert plays_until_trip(window, clock, ON, spacings) == 10


def test_plays_spaced_just_wider_than_the_window_allows_never_trip():
    # 10 plays span 9 gaps, so spacing > window / (max_plays - 1) keeps at most 9 in the window
    clock = FakeClock()
    window = PlayWindow(clock)
    spacing = ON.window_seconds // (ON.max_plays - 1) + 1     # 21s, below the 30s reset gap
    assert plays_until_trip(window, clock, ON, [spacing] * 200) is None


def test_window_edge_is_inclusive():
    # 10 plays exactly 20s apart span exactly 180s, which is still "within" the window
    clock = FakeClock()
    window = PlayWindow(clock)
    assert plays_until_trip(window, clock, ON, [20] * 10) == 10


def test_trip_clears_the_window():
    clock = FakeClock()
    window = PlayWindow(clock)
    assert plays_until_trip(window, clock, ON, [1] * 10) == 10
    assert plays_until_trip(window, clock, ON, [1] * 9) is None


def test_windows_are_per_user():
    clock = FakeClock()
    window = PlayWindow(clock)
    for _ in range(9):
        clock.advance(1)
        assert window.record((10, 1), ON) is None
        assert window.record((10, 2), ON) is None
        assert window.record((11, 1), ON) is None


# ---------------------------------------------------------------------------
# SoundGuard
# ---------------------------------------------------------------------------

async def enable(guard, **changes):
    return await guard.update_settings(10, dataclasses.replace(ON, **changes), updated_by=99)


async def spam(guard, member, clock, count, play_type="direct", spacing=1, ignored=False):
    """Plays `count` sounds, returns the TimeoutInfo of the first trip (or None)."""
    tripped = None
    for _ in range(count):
        clock.advance(spacing)
        info = await guard.on_play(member, play_type, ignored=ignored)
        tripped = tripped or info
    return tripped


async def test_trip_issues_and_persists_a_timeout(antispam_guard, antispam_store, clock):
    await enable(antispam_guard)
    member = make_member()
    info = await spam(antispam_guard, member, clock, 10)

    assert info is not None
    assert (info.reason, info.duration, info.trigger_plays, info.trigger_window_s) == ("auto", 600, 10, 180)
    assert info.issued_by is None
    assert antispam_guard.is_blocked(member) == info
    assert antispam_store.active_timeouts(10, antispam_guard.now()) == [info]


async def test_escalation_doubles_within_lookback_and_resets_after(antispam_guard, clock):
    await enable(antispam_guard)
    member = make_member()
    durations = []
    for _ in range(3):
        info = await spam(antispam_guard, member, clock, 10)
        durations.append(info.duration)
        clock.advance(info.duration)        # sit out the timeout
    assert durations == [600, 1200, 2400]

    clock.advance(86400)                    # beyond the lookback
    info = await spam(antispam_guard, member, clock, 10)
    assert info.duration == 600


async def test_escalation_is_capped(antispam_guard, clock):
    await enable(antispam_guard, max_timeout_seconds=1500)
    member = make_member()
    durations = []
    for _ in range(4):
        info = await spam(antispam_guard, member, clock, 10)
        durations.append(info.duration)
        clock.advance(info.duration)
    assert durations == [600, 1200, 1500, 1500]


async def test_escalation_with_many_prior_offences_does_not_overflow(antispam_guard, antispam_store):
    settings = await enable(antispam_guard, escalation_multiplier=10.0)
    now = antispam_guard.now()
    for i in range(500):
        antispam_store.insert_timeout(TimeoutInfo(None, 10, 1, "auto", started_at=now - i, expires_at=now - i + 1))
    assert await antispam_guard.timeout_for(10, 1, settings) == 604800


async def test_escalation_off_always_uses_base(antispam_guard, clock):
    await enable(antispam_guard, escalation_enabled=False)
    member = make_member()
    for _ in range(3):
        info = await spam(antispam_guard, member, clock, 10)
        assert info.duration == 600
        clock.advance(info.duration)


async def test_pardoned_timeouts_do_not_escalate(antispam_guard, clock):
    await enable(antispam_guard)
    member = make_member()
    await spam(antispam_guard, member, clock, 10)
    assert await antispam_guard.pardon(10, 1, by=99) is True
    info = await spam(antispam_guard, member, clock, 10)
    assert info.duration == 600


async def test_exempt_role_bypasses(antispam_guard, antispam_store, clock):
    await enable(antispam_guard, exempt_role_ids=(555,))
    member = make_member(role_ids=(555,))
    assert await spam(antispam_guard, member, clock, 50) is None
    await antispam_guard.issue(10, 1, 600, "manual", issued_by=99)
    assert antispam_guard.is_blocked(member) is None


async def test_exempt_admin_bypasses_unless_turned_off(antispam_guard, clock):
    admin = make_member(admin=True)
    await enable(antispam_guard)
    assert await spam(antispam_guard, admin, clock, 50) is None

    await enable(antispam_guard, exempt_administrators=False)
    assert await spam(antispam_guard, admin, clock, 10) is not None
    assert antispam_guard.is_blocked(admin) is not None


async def test_disabled_never_blocks_and_never_records(antispam_guard, antispam_store, clock):
    member = make_member()
    assert antispam_guard.settings_for(10).enabled is False
    assert await spam(antispam_guard, member, clock, 50) is None
    assert antispam_guard.window._plays == {}
    assert antispam_store.history(10, 1) == []

    # a timeout issued while enabled is paused (not enforced) while disabled, and applies again on re-enable
    await enable(antispam_guard)
    await antispam_guard.issue(10, 1, 600, "manual", issued_by=99)
    await enable(antispam_guard, enabled=False)
    assert antispam_guard.is_blocked(member) is None
    await enable(antispam_guard)
    assert antispam_guard.is_blocked(member) is not None


async def test_count_random_off_ignores_random_plays(antispam_guard, clock):
    await enable(antispam_guard, count_random=False)
    member = make_member()
    assert await spam(antispam_guard, member, clock, 50, play_type="random") is None
    assert await spam(antispam_guard, member, clock, 10, play_type="direct") is not None


async def test_count_quicksounds_off_ignores_quicksounds(antispam_guard, clock):
    await enable(antispam_guard, count_quicksounds=False)
    assert await spam(antispam_guard, make_member(), clock, 50, play_type="quicksound") is None


async def test_random_and_quicksounds_count_by_default(antispam_guard, clock):
    await enable(antispam_guard)
    member = make_member()
    await spam(antispam_guard, member, clock, 4, play_type="random")
    await spam(antispam_guard, member, clock, 3, play_type="quicksound")
    assert await spam(antispam_guard, member, clock, 3, play_type="direct") is not None


async def test_entrance_is_never_counted(antispam_guard, clock):
    await enable(antispam_guard)
    assert await spam(antispam_guard, make_member(), clock, 100, play_type="entrance") is None


async def test_ignored_attempts_only_count_when_enabled(antispam_guard, clock):
    member = make_member()
    await enable(antispam_guard)
    assert await spam(antispam_guard, member, clock, 50, ignored=True) is None
    await enable(antispam_guard, count_ignored_attempts=True)
    assert await spam(antispam_guard, member, clock, 10, ignored=True) is not None


async def test_expiry_and_pardon(antispam_guard, clock):
    await enable(antispam_guard)
    member = make_member()
    info = await spam(antispam_guard, member, clock, 10)

    clock.now = info.expires_at - 1
    assert antispam_guard.is_blocked(member) is not None
    clock.now = info.expires_at
    assert antispam_guard.is_blocked(member) is None

    info = await antispam_guard.issue(10, 1, 600, "manual", issued_by=99)
    assert antispam_guard.is_blocked(member) == info
    assert await antispam_guard.pardon(10, 1, by=99) is True
    assert antispam_guard.is_blocked(member) is None
    assert await antispam_guard.pardon(10, 1, by=99) is False


async def test_no_plays_counted_while_timed_out(antispam_guard, clock):
    await enable(antispam_guard)
    member = make_member()
    info = await spam(antispam_guard, member, clock, 10)
    assert await spam(antispam_guard, member, clock, 30) is None
    assert antispam_guard.is_blocked(member) == info


async def test_manual_timeout_replaces_an_active_one(antispam_guard, antispam_store, clock):
    await enable(antispam_guard)
    first = await antispam_guard.issue(10, 1, 604800, "manual", issued_by=99)
    second = await antispam_guard.issue(10, 1, 60, "manual", issued_by=99)
    assert antispam_guard.is_blocked(make_member()) == second
    assert antispam_store.active_timeouts(10, antispam_guard.now()) == [second]
    revoked = [t for t in antispam_store.history(10, 1) if t.id == first.id][0]
    assert revoked.revoked_by == 99


async def test_timeouts_survive_a_restart(antispam_guard, antispam_store, clock):
    await enable(antispam_guard)
    member = make_member()
    info = await spam(antispam_guard, member, clock, 10)

    restarted = SoundGuard(antispam_store, clock=clock, wall_clock=clock)
    await restarted.load()
    assert restarted.settings_for(10) == antispam_guard.settings_for(10)
    assert restarted.is_blocked(member) == info


async def test_unloaded_guard_is_inert(antispam_store, clock):
    guard = SoundGuard(antispam_store, clock=clock, wall_clock=clock)
    guard._settings[10] = ON
    member = make_member()
    assert await spam(guard, member, clock, 50) is None
    assert guard.is_blocked(member) is None


def test_blocked_notice_is_rate_limited(antispam_store):
    clock = FakeClock()
    guard = SoundGuard(antispam_store, clock=clock, wall_clock=clock)
    assert guard.should_notify_blocked(10, 1) is True
    clock.advance(29)
    assert guard.should_notify_blocked(10, 1) is False
    assert guard.should_notify_blocked(10, 2) is True
    clock.advance(1)
    assert guard.should_notify_blocked(10, 1) is True


# ---------------------------------------------------------------------------
# Settings validation
# ---------------------------------------------------------------------------

def test_defaults_are_off_and_valid():
    settings = AntiSpamSettings().validate()
    assert settings.enabled is False
    assert (settings.max_plays, settings.window_seconds, settings.reset_gap_seconds, settings.timeout_seconds) == (10, 180, 30, 600)
    assert settings.rule_sentence() == "Timeout **10m** if a user plays **10** sounds within **3m** without a **30s** break"


@pytest.mark.parametrize("changes", [
    {"max_plays": 1}, {"max_plays": 101},
    {"window_seconds": 9}, {"window_seconds": 86401},
    {"reset_gap_seconds": -1}, {"reset_gap_seconds": 181},
    {"timeout_seconds": 0}, {"timeout_seconds": 52 * 604800 + 1, "max_timeout_seconds": 52 * 604800 + 1},
    {"escalation_multiplier": 0.5}, {"escalation_multiplier": 10.5},
    {"escalation_lookback_seconds": 59},
    {"max_timeout_seconds": 599},
    {"notify_mode": "pigeon"},
    {"apply_discord_timeout": True, "timeout_seconds": 5 * 604800, "max_timeout_seconds": 5 * 604800},
    {"apply_discord_timeout": True, "max_timeout_seconds": 5 * 604800},
])
def test_out_of_range_settings_are_rejected(changes):
    with pytest.raises(InvalidSetting):
        dataclasses.replace(AntiSpamSettings(), **changes).validate()


@pytest.mark.parametrize("changes", [
    {"max_plays": 2}, {"max_plays": 100},
    {"window_seconds": 10, "reset_gap_seconds": 10}, {"window_seconds": 86400},
    {"reset_gap_seconds": 0}, {"reset_gap_seconds": 180},
    {"timeout_seconds": 1}, {"timeout_seconds": 52 * 604800, "max_timeout_seconds": 52 * 604800},
    {"apply_discord_timeout": True, "timeout_seconds": 4 * 604800, "max_timeout_seconds": 4 * 604800},
])
def test_in_range_settings_are_accepted(changes):
    dataclasses.replace(AntiSpamSettings(), **changes).validate()


def test_rule_sentence_without_reset_gap():
    settings = AntiSpamSettings(reset_gap_seconds=0)
    assert settings.rule_sentence() == "Timeout **10m** if a user plays **10** sounds within **3m**"
