# Helpers for duration inputs on app commands (amount + unit) and for
# printing durations back to users in a compact form ("1w 2d 3h").
from typing import Literal

DurationUnit = Literal["seconds", "minutes", "hours", "days", "weeks"]

UNIT_SECONDS = {
    "seconds": 1,
    "minutes": 60,
    "hours": 60 * 60,
    "days": 24 * 60 * 60,
    "weeks": 7 * 24 * 60 * 60,
}

_SHORT_UNITS = (("w", UNIT_SECONDS["weeks"]), ("d", UNIT_SECONDS["days"]), ("h", UNIT_SECONDS["hours"]),
                ("m", UNIT_SECONDS["minutes"]), ("s", 1))


def to_seconds(amount, unit):
    """Converts an amount of a unit (one of UNIT_SECONDS) to whole seconds."""
    if unit not in UNIT_SECONDS:
        raise ValueError(f"Unknown duration unit \"{unit}\"")
    if amount < 0:
        raise ValueError("Duration cannot be negative")
    return int(amount) * UNIT_SECONDS[unit]


def humanize(seconds):
    """Formats seconds as the non-zero units largest first, e.g. 788580 -> "1w 2d 3h 3m"."""
    seconds = int(seconds)
    if seconds <= 0:
        return "0s"
    parts = []
    for suffix, size in _SHORT_UNITS:
        count, seconds = divmod(seconds, size)
        if count:
            parts.append(f"{count}{suffix}")
    return " ".join(parts)
