"""Time-parsing utilities."""

import datetime


def parse_timedelta(s: str) -> datetime.timedelta:
    """Parse a timedelta string to datetime.timedelta.

    Accepts 'H:MM:SS', 'H:MM:SS.f', 'D days, H:MM:SS', or 'D day, H:MM:SS'.

    Args:
        s: Timedelta string to parse.

    Returns:
        Parsed timedelta.

    Raises:
        ValueError: If the string cannot be parsed.
    """
    s = s.strip()
    days = 0
    if "day" in s:
        day_part, _, time_part = s.partition(",")
        days = int(day_part.split()[0])
        s = time_part.strip()
    parts = s.split(":")
    if len(parts) != 3:
        raise ValueError(f"Cannot parse timedelta string: {s!r}")
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])
    return datetime.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
