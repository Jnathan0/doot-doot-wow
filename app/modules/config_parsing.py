# Normalising config values that arrive as strings from environment variables
# (Docker) or as ints / lists from config.yaml. Kept free of other app imports so
# app_config and permissions can both use it.


def normalize_owb_id(value):
    """
    OWB_ID can be a role id or a role name. discord.py treats an int as a role id and a
    str as a role name, and env vars are always str, so digits are converted to int here.
    Returns an int (role id), a str (role name) or None (no OWB role configured).
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    value = str(value).strip()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    return value


def parse_id_list(value):
    """
    Parses a list of discord ids from a comma separated string ("1, 2"), a single int,
    or a yaml list. Entries that aren't ids are skipped with a warning.
    """
    if value is None or isinstance(value, bool):
        return []
    if isinstance(value, int):
        return [value]
    items = value if isinstance(value, (list, tuple, set)) else str(value).split(",")
    ids = []
    for item in items:
        item = str(item).strip()
        if not item:
            continue
        if item.isdigit():
            ids.append(int(item))
        else:
            print(f"Warning: ignoring \"{item}\", not a discord user id")
    return ids
