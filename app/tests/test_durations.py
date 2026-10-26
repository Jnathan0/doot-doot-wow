import pytest

from modules.durations import to_seconds, humanize, UNIT_SECONDS


@pytest.mark.parametrize("amount,unit,expected", [
    (1, "seconds", 1),
    (1, "minutes", 60),
    (1, "hours", 3600),
    (1, "days", 86400),
    (1, "weeks", 604800),
    (3, "minutes", 180),
    (0, "seconds", 0),
    (10_000, "weeks", 10_000 * 604800),
])
def test_to_seconds(amount, unit, expected):
    assert to_seconds(amount, unit) == expected


def test_to_seconds_rejects_unknown_unit():
    with pytest.raises(ValueError):
        to_seconds(1, "fortnights")


def test_to_seconds_rejects_negative():
    with pytest.raises(ValueError):
        to_seconds(-1, "seconds")


@pytest.mark.parametrize("seconds,expected", [
    (0, "0s"),
    (-5, "0s"),
    (1, "1s"),
    (59, "59s"),
    (60, "1m"),
    (90, "1m 30s"),
    (600, "10m"),
    (3600, "1h"),
    (86400, "1d"),
    (604800, "1w"),
    (604800 + 2 * 86400 + 3 * 3600, "1w 2d 3h"),
    (52 * 604800, "52w"),
])
def test_humanize(seconds, expected):
    assert humanize(seconds) == expected


@pytest.mark.parametrize("unit", list(UNIT_SECONDS))
def test_one_of_each_unit_round_trips(unit):
    assert humanize(to_seconds(1, unit)) == "1" + unit[0]
