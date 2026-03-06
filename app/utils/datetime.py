from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo


def parse_dt(value: str, timezone_name: str = "UTC") -> datetime:
    # Expected format: YYYY-MM-DD HH:MM in the provided timezone, converted to UTC.
    dt = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M")
    local_dt = dt.replace(tzinfo=ZoneInfo(timezone_name))
    return local_dt.astimezone(UTC)
