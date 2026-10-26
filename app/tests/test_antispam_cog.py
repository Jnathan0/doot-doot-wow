"""
/antispam commands, permission handling and the notification listeners (cogs/AntiSpam.py),
with a real SoundGuard over a tmp metadata.db.
"""
import dataclasses
import datetime
import discord
import pytest
from unittest.mock import MagicMock, AsyncMock
from discord import app_commands
from discord.ext import commands

import cogs.AntiSpam as module
from modules.antispam import AntiSpamSettings, InvalidSetting, SoundTimeoutActive
from modules.permissions import NotGuildAdmin
from tests.conftest import db_rows, make_member, sent_text


def make_admin_interaction(guild_id=10, user_id=99, admin=True, owner=False):
    interaction = MagicMock()
    interaction.client.is_owner = AsyncMock(return_value=owner)
    interaction.guild_id = guild_id
    interaction.guild.id = guild_id
    interaction.user.id = user_id
    interaction.user.__str__ = MagicMock(return_value="admin")
    interaction.permissions.administrator = admin
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.channel.send = AsyncMock()
    return interaction


def reply(interaction):
    return sent_text(interaction.response.send_message) + sent_text(interaction.followup.send)


@pytest.fixture
def cog(antispam_guard, mocker):
    mocker.patch.object(module, "guard", antispam_guard)
    log = mocker.patch.object(module.Logger, "log", new_callable=AsyncMock)
    cog = module.AntiSpam(MagicMock())
    cog.log = log
    cog.guard = antispam_guard
    return cog


@pytest.fixture
def interaction():
    return make_admin_interaction()


def settings_row(tmp_path):
    return db_rows(tmp_path / "metadata.db", "SELECT * FROM antispam_settings")


async def run(cog, name, interaction, *args, **kwargs):
    await getattr(type(cog), name).callback(cog, interaction, *args, **kwargs)


# ---------------------------------------------------------------------------
# Registration and permissions
# ---------------------------------------------------------------------------

async def test_command_tree(antispam_guard, mocker):
    mocker.patch.object(module, "guard", antispam_guard)
    bot = commands.Bot(command_prefix="'", intents=discord.Intents.default())
    await module.setup(bot)

    group = bot.tree.get_command("antispam")
    assert isinstance(group, app_commands.Group)
    assert group.default_permissions.administrator is True
    assert group.guild_only is True
    assert {c.name for c in group.commands} == {
        "status", "enable", "disable", "rule", "duration", "escalation", "counting", "notify", "options",
        "reset-defaults", "exempt-role", "timeout", "pardon", "active", "history"}
    exempt = group.get_command("exempt-role")
    assert {c.name for c in exempt.commands} == {"add", "remove", "list"}

    unit = group.get_command("duration").get_parameter("unit")
    assert [choice.value for choice in unit.choices] == ["seconds", "minutes", "hours", "days", "weeks"]

    payload = group.to_dict(bot.tree)
    assert int(payload["default_member_permissions"]) == discord.Permissions(administrator=True).value


def all_commands(group):
    for command in group.commands:
        if isinstance(command, app_commands.Group):
            yield from all_commands(command)
        else:
            yield command


async def test_every_command_runs_the_admin_check(antispam_guard, mocker):
    mocker.patch.object(module, "guard", antispam_guard)
    bot = commands.Bot(command_prefix="'", intents=discord.Intents.default())
    await module.setup(bot)
    commands_ = list(all_commands(bot.tree.get_command("antispam")))
    assert len(commands_) == 17
    for command in commands_:
        with pytest.raises(NotGuildAdmin):
            await command._check_can_run(make_admin_interaction(admin=False))
        assert await command._check_can_run(make_admin_interaction(admin=True)) is True
        # the bot owner passes the admin tier
        assert await command._check_can_run(make_admin_interaction(admin=False, owner=True)) is True


@pytest.mark.parametrize("path", [("status",), ("enable",), ("pardon",), ("exempt-role", "add")])
async def test_admin_check_by_path(antispam_guard, mocker, path):
    mocker.patch.object(module, "guard", antispam_guard)
    bot = commands.Bot(command_prefix="'", intents=discord.Intents.default())
    await module.setup(bot)
    command = bot.tree.get_command("antispam")
    for name in path:
        command = command.get_command(name)

    with pytest.raises(NotGuildAdmin):
        await command._check_can_run(make_admin_interaction(admin=False))
    assert await command._check_can_run(make_admin_interaction(admin=True)) is True


async def test_non_admin_gets_permission_message(cog):
    interaction = make_admin_interaction(admin=False)
    with pytest.raises(NotGuildAdmin) as excinfo:
        await type(cog).status_command.checks[0](interaction)
    await cog.cog_app_command_error(interaction, excinfo.value)
    assert "Administrator permission required" in reply(interaction)
    assert interaction.response.send_message.call_args.kwargs["ephemeral"] is True


async def test_invalid_setting_error_is_shown(cog, interaction):
    error = app_commands.CommandInvokeError(type(cog).rule_command, InvalidSetting("Max plays must be between 2 and 100."))
    await cog.cog_app_command_error(interaction, error)
    assert "Max plays must be between 2 and 100." in reply(interaction)


async def test_unexpected_error_is_reported_generically(cog, interaction):
    error = app_commands.CommandInvokeError(type(cog).status_command, RuntimeError("boom"))
    await cog.cog_app_command_error(interaction, error)
    assert "An error occoured" in reply(interaction)
    assert "boom" not in reply(interaction)


# ---------------------------------------------------------------------------
# Settings commands
# ---------------------------------------------------------------------------

async def test_status_on_fresh_deploy_is_disabled_and_writes_nothing(cog, interaction, tmp_path):
    await run(cog, "status_command", interaction)
    embed = interaction.response.send_message.call_args.kwargs["embed"]
    assert embed.description.startswith("**Disabled**")
    assert "**10** sounds within **3m** without a **30s** break" in embed.description
    fields = {field.name: field.value for field in embed.fields}
    assert fields["Active timeouts"] == "0"
    assert "Off" in fields["Discord timeout"]
    assert settings_row(tmp_path) == []


async def test_enable_and_disable(cog, interaction, tmp_path):
    await run(cog, "enable_command", interaction)
    assert cog.guard.settings_for(10).enabled is True
    assert "enabled" in reply(interaction)
    assert db_rows(tmp_path / "metadata.db", "SELECT enabled, updated_by FROM antispam_settings") == [(1, 99)]
    assert "set enabled False→True" in cog.log.call_args.args[0]

    interaction = make_admin_interaction()
    await run(cog, "disable_command", interaction)
    assert cog.guard.settings_for(10).enabled is False
    assert "not lifted" in reply(interaction)


async def test_rule(cog, interaction, tmp_path):
    await run(cog, "rule_command", interaction, 3, 1, "minutes", 10, "seconds")
    settings = cog.guard.settings_for(10)
    assert (settings.max_plays, settings.window_seconds, settings.reset_gap_seconds) == (3, 60, 10)
    assert "**3** sounds within **1m** without a **10s** break" in reply(interaction)
    log = cog.log.call_args.args[0]
    assert "set max_plays 10→3" in log and "set window_seconds 3m→1m" in log


async def test_rule_reset_gap_zero_turns_forgiveness_off(cog, interaction):
    await run(cog, "rule_command", interaction, 10, 3, "minutes", 0, "seconds")
    assert cog.guard.settings_for(10).reset_gap_seconds == 0
    assert "break" not in reply(interaction)


async def test_rule_keeps_reset_gap_when_omitted(cog, interaction):
    await run(cog, "rule_command", interaction, 12, 5, "minutes")
    assert cog.guard.settings_for(10).reset_gap_seconds == 30


async def test_invalid_rule_is_rejected_and_not_saved(cog, interaction, tmp_path):
    with pytest.raises(InvalidSetting):
        # 20s window is shorter than the 30s reset gap
        await run(cog, "rule_command", interaction, 10, 20, "seconds")
    assert cog.guard.settings_for(10) == AntiSpamSettings()
    assert settings_row(tmp_path) == []


@pytest.mark.parametrize("unit,expected", [
    ("seconds", "1s"), ("minutes", "1m"), ("hours", "1h"), ("days", "1d"), ("weeks", "1w")])
async def test_duration_accepts_every_unit(cog, interaction, unit, expected):
    await run(cog, "duration_command", interaction, 1, unit)
    assert cog.guard.settings_for(10).timeout_seconds == {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}[expected[-1]]
    assert f"**{expected}**" in reply(interaction)


async def test_duration_raises_max_timeout_to_match(cog, interaction):
    await run(cog, "duration_command", interaction, 2, "weeks")
    settings = cog.guard.settings_for(10)
    assert settings.timeout_seconds == settings.max_timeout_seconds == 2 * 604800
    assert "Max timeout raised to **2w**" in reply(interaction)


async def test_duration_out_of_range(cog, interaction):
    with pytest.raises(InvalidSetting):
        await run(cog, "duration_command", interaction, 53, "weeks")


async def test_duration_limited_to_4_weeks_with_discord_timeout(cog, interaction):
    await run(cog, "options_command", interaction, discord_timeout=True)
    with pytest.raises(InvalidSetting):
        await run(cog, "duration_command", make_admin_interaction(), 5, "weeks")
    await run(cog, "duration_command", make_admin_interaction(), 4, "weeks")


async def test_escalation(cog, interaction):
    await run(cog, "escalation_command", interaction, True, 3.0, 2, "days", 12, "hours")
    settings = cog.guard.settings_for(10)
    assert (settings.escalation_enabled, settings.escalation_multiplier, settings.max_timeout_seconds,
            settings.escalation_lookback_seconds) == (True, 3.0, 2 * 86400, 12 * 3600)
    assert "×3 per offence within 12h, capped at 2d" in reply(interaction)

    interaction = make_admin_interaction()
    await run(cog, "escalation_command", interaction, False)
    assert cog.guard.settings_for(10).escalation_enabled is False
    assert "off" in reply(interaction)


async def test_escalation_max_below_base_is_rejected(cog, interaction):
    with pytest.raises(InvalidSetting):
        await run(cog, "escalation_command", interaction, True, None, 5, "minutes")


async def test_counting(cog, interaction, tmp_path):
    await run(cog, "counting_command", interaction, random=False, ignored_attempts=True)
    settings = cog.guard.settings_for(10)
    assert (settings.count_random, settings.count_quicksounds, settings.count_ignored_attempts) == (False, True, True)

    # no options just shows the current values
    cog.log.reset_mock()
    interaction = make_admin_interaction()
    await run(cog, "counting_command", interaction)
    assert "random **no**" in reply(interaction)
    cog.log.assert_not_called()


async def test_notify(cog, interaction):
    await run(cog, "notify_command", interaction, "dm")
    assert cog.guard.settings_for(10).notify_mode == "dm"


async def test_options_discord_timeout_warns(cog, interaction):
    interaction.guild.me.guild_permissions.moderate_members = False
    await run(cog, "options_command", interaction, exempt_admins=False, discord_timeout=True)
    settings = cog.guard.settings_for(10)
    assert (settings.exempt_administrators, settings.apply_discord_timeout) == (False, True)
    assert "server-wide" in reply(interaction)
    assert "does not have Moderate Members" in reply(interaction)


async def test_turning_off_log_channel_still_logs_that_change(cog, interaction):
    await run(cog, "options_command", interaction, log_channel=False)
    assert "set log_to_log_channel True→False" in cog.log.call_args.args[0]
    cog.log.reset_mock()
    await run(cog, "enable_command", make_admin_interaction())
    cog.log.assert_not_called()


async def test_exempt_roles(cog, interaction):
    role = MagicMock(id=555, mention="<@&555>")
    await run(cog, "exempt_role_add_command", interaction, role)
    await run(cog, "exempt_role_add_command", make_admin_interaction(), role)
    assert cog.guard.settings_for(10).exempt_role_ids == (555,)

    listing = make_admin_interaction()
    await run(cog, "exempt_role_list_command", listing)
    assert "<@&555>" in reply(listing)

    removing = make_admin_interaction()
    await run(cog, "exempt_role_remove_command", removing, role)
    assert cog.guard.settings_for(10).exempt_role_ids == ()
    assert "no longer exempt" in reply(removing)


class FakeConfirmation:
    def __init__(self, confirmed):
        self.confirmed = confirmed
        self.interaction = MagicMock()
        self.interaction.response.edit_message = AsyncMock()

    async def wait(self):
        pass


async def test_reset_defaults_keeps_enabled(cog, interaction, mocker):
    await cog.guard.update_settings(10, AntiSpamSettings(enabled=True, max_plays=3, notify_mode="dm",
                                                         exempt_role_ids=(1,)), updated_by=99)
    view = FakeConfirmation(True)
    mocker.patch.object(module, "SoundConfirmationDiag", return_value=view)
    await run(cog, "reset_defaults_command", interaction)
    assert cog.guard.settings_for(10) == AntiSpamSettings(enabled=True)
    assert "reset to defaults" in sent_text(view.interaction.response.edit_message)


@pytest.mark.parametrize("confirmed", [False, None])
async def test_reset_defaults_cancel_or_timeout_changes_nothing(cog, interaction, mocker, confirmed):
    custom = AntiSpamSettings(enabled=True, max_plays=3)
    await cog.guard.update_settings(10, custom, updated_by=99)
    mocker.patch.object(module, "SoundConfirmationDiag", return_value=FakeConfirmation(confirmed))
    await run(cog, "reset_defaults_command", interaction)
    assert cog.guard.settings_for(10) == custom


# ---------------------------------------------------------------------------
# Timeout commands
# ---------------------------------------------------------------------------

async def test_manual_timeout_pardon_active_history(cog, interaction):
    await run(cog, "enable_command", make_admin_interaction())
    member = make_member(user_id=5)

    await run(cog, "timeout_command", interaction, member, 10, "minutes", "too loud")
    info = cog.guard.is_blocked(member)
    assert (info.reason, info.duration, info.issued_by, info.note) == ("manual", 600, 99, "too loud")
    notice = sent_text(interaction.channel.send)
    assert "<@5>" in notice and "**10m**" in notice and f"<t:{info.expires_at}:R>" in notice
    assert "isn't enforced" not in reply(interaction)

    active = make_admin_interaction()
    await run(cog, "active_command", active)
    assert "<@5>" in reply(active) and "too loud" in reply(active)

    pardon = make_admin_interaction()
    await run(cog, "pardon_command", pardon, member)
    assert "can play sounds again" in reply(pardon)
    assert cog.guard.is_blocked(member) is None
    assert "pardoned" in cog.log.call_args.args[0]

    again = make_admin_interaction()
    await run(cog, "pardon_command", again, member)
    assert "isn't timed out" in reply(again)

    history = make_admin_interaction()
    await run(cog, "history_command", history, member)
    assert "manual: too loud" in reply(history) and "lifted" in reply(history)


async def test_manual_timeout_while_disabled_warns(cog, interaction):
    await run(cog, "timeout_command", interaction, make_member(user_id=5), 1, "hours")
    assert "isn't enforced" in reply(interaction)


async def test_manual_timeout_limits(cog, interaction):
    with pytest.raises(InvalidSetting):
        await run(cog, "timeout_command", interaction, make_member(user_id=5), 53, "weeks")
    bot_member = make_member(user_id=6)
    bot_member.bot = True
    with pytest.raises(InvalidSetting):
        await run(cog, "timeout_command", interaction, bot_member, 1, "hours")


async def test_active_paginates(cog, interaction, mocker):
    menu = mocker.patch.object(module, "ButtonMenu")
    for user_id in range(12):
        await cog.guard.issue(10, user_id, 600 + user_id, "auto", trigger_plays=10, trigger_window_s=180)
    await run(cog, "active_command", interaction)
    pages = menu.call_args.args[0]
    assert len(pages) == 2
    assert pages[0].count("•") == 10 and pages[1].count("•") == 2


async def test_active_and_history_empty(cog, interaction):
    await run(cog, "active_command", interaction)
    assert "No active sound timeouts" in reply(interaction)
    history = make_admin_interaction()
    await run(cog, "history_command", history, make_member(user_id=5))
    assert "no sound timeouts" in reply(history)


# ---------------------------------------------------------------------------
# Listeners
# ---------------------------------------------------------------------------

def make_ctx(member):
    ctx = MagicMock()
    ctx.author = member
    ctx.channel.send = AsyncMock()
    ctx.message.delete = AsyncMock()
    return ctx


async def auto_timeout(guard):
    return await guard.issue(10, 1, 600, "auto", trigger_plays=10, trigger_window_s=180)


async def test_trip_notice_in_channel(cog):
    member = make_member()
    ctx = make_ctx(member)
    info = await auto_timeout(cog.guard)
    await cog.on_sound_timeout(ctx, info)

    call = ctx.channel.send.call_args
    assert "<@1>" in call.args[0] and "**10m**" in call.args[0] and "10 plays in 3m" in call.args[0]
    assert f"<t:{info.expires_at}:R>" in call.args[0]
    assert call.kwargs["delete_after"] == 15
    assert call.kwargs["allowed_mentions"].users == [member]
    member.send.assert_not_called()
    member.timeout.assert_not_called()
    assert "timed out from sounds for 10m" in cog.log.call_args.args[0]


@pytest.mark.parametrize("mode,in_channel,in_dm", [("dm", False, True), ("both", True, True), ("none", False, False)])
async def test_trip_notice_modes(cog, mode, in_channel, in_dm):
    await cog.guard.update_settings(10, AntiSpamSettings(enabled=True, notify_mode=mode), updated_by=99)
    member = make_member()
    ctx = make_ctx(member)
    await cog.on_sound_timeout(ctx, await auto_timeout(cog.guard))
    assert ctx.channel.send.called is in_channel
    assert member.send.called is in_dm


async def test_trip_with_discord_timeout(cog):
    await cog.guard.update_settings(10, AntiSpamSettings(enabled=True, apply_discord_timeout=True), updated_by=99)
    member = make_member()
    await cog.on_sound_timeout(make_ctx(member), await auto_timeout(cog.guard))
    member.timeout.assert_awaited_once_with(datetime.timedelta(seconds=600), reason="Sound spam")


async def test_failed_notice_does_not_raise(cog):
    member = make_member()
    ctx = make_ctx(member)
    ctx.channel.send.side_effect = discord.Forbidden(MagicMock(status=403, reason="Forbidden"), "no")
    await cog.on_sound_timeout(ctx, await auto_timeout(cog.guard))


async def test_blocked_command_deletes_message_and_notices_once(cog):
    member = make_member()
    info = await auto_timeout(cog.guard)
    error = SoundTimeoutActive(info, "direct")

    first, second = make_ctx(member), make_ctx(member)
    await cog.on_command_error(first, error)
    await cog.on_command_error(second, error)

    first.message.delete.assert_awaited_once()
    second.message.delete.assert_awaited_once()
    assert "still timed out" in sent_text(first.channel.send)
    second.channel.send.assert_not_called()


async def test_other_command_errors_keep_default_logging(cog, mocker):
    log = mocker.patch.object(module, "_command_log")
    ctx = make_ctx(make_member())
    ctx.command.has_error_handler = MagicMock(return_value=False)
    ctx.cog.has_error_handler = MagicMock(return_value=False)
    await cog.on_command_error(ctx, commands.CommandNotFound("nope"))
    log.error.assert_called_once()


# ---------------------------------------------------------------------------
# Acceptance script (plan §12) through the real Player command and checks
# ---------------------------------------------------------------------------

@pytest.fixture
def player_setup(cog, mocker, mock_sound):
    import cogs.Player as player_module
    from modules import antispam
    mocker.patch.object(antispam, "guard", cog.guard)
    play = mocker.patch("cogs.Player.player.play", new_callable=AsyncMock)
    mocker.patch("cogs.Player.increment_playcount")
    mocker.patch.object(player_module.config.worker_queue, "enqueue")
    mocker.patch.object(player_module.sounds, "alias_dict", {"test_sound": mock_sound})
    player_cog = player_module.Player(MagicMock())
    for command in player_cog.__cog_commands__:
        command.cog = player_cog
    return player_cog, play


async def invoke_sound(cog, player_cog, member):
    """Runs checks then the command like discord.py does, routing errors and events to the AntiSpam cog."""
    ctx = make_ctx(member)
    ctx.guild = MagicMock()
    ctx.message.guild.voice_client = None
    ctx.message.content = "!test_sound"
    ctx.bot.can_run = AsyncMock(return_value=True)
    events = []
    ctx.bot.dispatch = lambda name, *args: events.append((name, args))
    command = player_cog.master_command
    try:
        await command.can_run(ctx)
    except SoundTimeoutActive as error:
        await cog.on_command_error(ctx, error)
        return ctx, False
    await command(ctx)
    for name, args in events:
        assert name == "sound_timeout"
        await cog.on_sound_timeout(*args)
    return ctx, True


async def test_acceptance_script(cog, player_setup, clock):
    player_cog, play = player_setup
    for name, args in [("enable_command", ()), ("rule_command", (3, 1, "minutes", 10, "seconds")),
                       ("duration_command", (30, "seconds"))]:
        await run(cog, name, make_admin_interaction(), *args)
    member = make_member()

    # three back-to-back plays trip a 30s timeout, the third still plays
    results = []
    for _ in range(3):
        clock.advance(1)
        ctx, played = await invoke_sound(cog, player_cog, member)
        results.append(played)
    assert results == [True, True, True]
    assert play.await_count == 3
    assert "you're timed out from playing sounds for **30s**" in sent_text(ctx.channel.send)

    # 4th is blocked with one notice, 5th is blocked silently
    clock.advance(1)
    ctx4, played4 = await invoke_sound(cog, player_cog, member)
    ctx5, played5 = await invoke_sound(cog, player_cog, member)
    assert (played4, played5) == (False, False)
    assert "still timed out" in sent_text(ctx4.channel.send)
    ctx5.channel.send.assert_not_called()
    ctx5.message.delete.assert_awaited_once()
    assert play.await_count == 3

    # after 30s plays work again
    clock.advance(30)
    _, played = await invoke_sound(cog, player_cog, member)
    assert played is True and play.await_count == 4


async def test_acceptance_pause_forgives(cog, player_setup, clock):
    player_cog, play = player_setup
    for name, args in [("enable_command", ()), ("rule_command", (3, 1, "minutes", 10, "seconds")),
                       ("duration_command", (30, "seconds"))]:
        await run(cog, name, make_admin_interaction(), *args)
    member = make_member()
    for pause in (1, 1, 12, 1):
        clock.advance(pause)
        _, played = await invoke_sound(cog, player_cog, member)
        assert played is True
    assert cog.guard.is_blocked(member) is None
