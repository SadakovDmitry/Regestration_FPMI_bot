from __future__ import annotations

from datetime import UTC, datetime


def parse_dt(value: str) -> datetime:
    # Expected format: YYYY-MM-DD HH:MM (UTC)
    dt = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M")
    return dt.replace(tzinfo=UTC)
