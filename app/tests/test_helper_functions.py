import pytest
import datetime
from unittest.mock import MagicMock, patch, call
from modules.helper_functions import (
    format_markdown,
    get_last_thursday,
    increment_playcount,
    checkExists,
    checkGroup,
    isLoud,
    checkExceedsDurationLimit,
)


# ---------------------------------------------------------------------------
# Pure / no-mock tests
# ---------------------------------------------------------------------------

def test_format_markdown():
    result = format_markdown("hello")
    assert result == "```\nhello\n```"


def test_get_last_thursday_is_thursday():
    result = get_last_thursday()
    # weekday() == 3 is Thursday
    assert result.weekday() == 3


def test_get_last_thursday_is_current_month():
    result = get_last_thursday()
    assert result.month == datetime.date.today().month


# ---------------------------------------------------------------------------
# increment_playcount — patch sqlite3.connect
# ---------------------------------------------------------------------------

def test_increment_playcount(mocker):
    mock_connect = mocker.patch("modules.helper_functions.sqlite3.connect")
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    sound_id = "test_sound"
    increment_playcount(sound_id)

    # execute was called once; its argument should mention UPDATE and the sound id
    mock_cursor.execute.assert_called_once()
    sql_arg = mock_cursor.execute.call_args[0][0]
    assert "UPDATE" in sql_arg
    assert sound_id in sql_arg

    mock_conn.commit.assert_called_once()


# ---------------------------------------------------------------------------
# checkExists — patch GetDB
# ---------------------------------------------------------------------------

def test_check_exists_true(mocker):
    mock_GetDB = mocker.patch("modules.helper_functions.GetDB")
    mock_db = MagicMock()
    mock_GetDB.return_value = mock_db
    mock_db.cursor.execute.return_value.fetchall.return_value = [(1,)]

    result = checkExists("mygroup", "mysound")

    assert result is True
    mock_db.close.assert_called_once()


def test_check_exists_false(mocker):
    mock_GetDB = mocker.patch("modules.helper_functions.GetDB")
    mock_db = MagicMock()
    mock_GetDB.return_value = mock_db
    mock_db.cursor.execute.return_value.fetchall.return_value = [(0,)]

    result = checkExists("mygroup", "mysound")

    assert result is False
    mock_db.close.assert_called_once()


# ---------------------------------------------------------------------------
# checkGroup — patch GetDB
# ---------------------------------------------------------------------------

def test_check_group_true(mocker):
    mock_GetDB = mocker.patch("modules.helper_functions.GetDB")
    mock_db = MagicMock()
    mock_GetDB.return_value = mock_db
    mock_db.cursor.execute.return_value.fetchall.return_value = [(1,)]

    result = checkGroup("mygroup")

    assert result is True
    mock_db.close.assert_called_once()


def test_check_group_false(mocker):
    mock_GetDB = mocker.patch("modules.helper_functions.GetDB")
    mock_db = MagicMock()
    mock_GetDB.return_value = mock_db
    mock_db.cursor.execute.return_value.fetchall.return_value = [(0,)]

    result = checkGroup("mygroup")

    assert result is False
    mock_db.close.assert_called_once()


# ---------------------------------------------------------------------------
# isLoud — patch ffmpeg
# ---------------------------------------------------------------------------

def test_is_loud_true(mocker):
    mocker.patch("modules.helper_functions.ffmpeg.input", return_value=MagicMock())
    mocker.patch("modules.helper_functions.ffmpeg.filter_", return_value=MagicMock())
    mocker.patch("modules.helper_functions.ffmpeg.output", return_value=MagicMock())
    mocker.patch(
        "modules.helper_functions.ffmpeg.run",
        return_value=(b"", b"mean_volume: -5.0 dB"),
    )

    result = isLoud("/sounds/loud.mp3")

    assert result is True


def test_is_loud_false(mocker):
    mocker.patch("modules.helper_functions.ffmpeg.input", return_value=MagicMock())
    mocker.patch("modules.helper_functions.ffmpeg.filter_", return_value=MagicMock())
    mocker.patch("modules.helper_functions.ffmpeg.output", return_value=MagicMock())
    mocker.patch(
        "modules.helper_functions.ffmpeg.run",
        return_value=(b"", b"mean_volume: -20.0 dB"),
    )

    result = isLoud("/sounds/quiet.mp3")

    assert result is False


def test_is_loud_ffmpeg_error(mocker):
    mocker.patch("modules.helper_functions.ffmpeg.input", return_value=MagicMock())
    mocker.patch("modules.helper_functions.ffmpeg.filter_", return_value=MagicMock())
    mocker.patch("modules.helper_functions.ffmpeg.output", return_value=MagicMock())
    mocker.patch(
        "modules.helper_functions.ffmpeg.run",
        return_value=(b"some error", b""),
    )

    with pytest.raises(Exception):
        isLoud("/sounds/bad.mp3")


# ---------------------------------------------------------------------------
# checkExceedsDurationLimit — patch ffmpeg + config
# ---------------------------------------------------------------------------

def test_exceeds_duration_limit_true(mocker):
    mocker.patch("modules.helper_functions.ffmpeg.input", return_value=MagicMock())
    mocker.patch("modules.helper_functions.ffmpeg.output", return_value=MagicMock())
    mocker.patch(
        "modules.helper_functions.ffmpeg.run",
        return_value=(b"", b"Duration: 00:04:00"),
    )
    # 240 seconds > 180 second limit configured in conftest mock_config
    mocker.patch("modules.helper_functions.config.media_duration_limit", 180)

    result = checkExceedsDurationLimit("/sounds/long.mp3")

    assert result is True


def test_exceeds_duration_limit_false(mocker):
    mocker.patch("modules.helper_functions.ffmpeg.input", return_value=MagicMock())
    mocker.patch("modules.helper_functions.ffmpeg.output", return_value=MagicMock())
    mocker.patch(
        "modules.helper_functions.ffmpeg.run",
        return_value=(b"", b"Duration: 00:02:00"),
    )
    # 120 seconds < 180 second limit
    mocker.patch("modules.helper_functions.config.media_duration_limit", 180)

    result = checkExceedsDurationLimit("/sounds/short.mp3")

    assert result is False
