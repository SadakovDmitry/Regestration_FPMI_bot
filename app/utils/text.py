from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.models import Event


def format_dt_tz(dt: datetime) -> str:
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    return dt.astimezone(tz).strftime("%d.%m.%Y %H:%M")


def render_event_card(event: Event) -> str:
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    start_at_local = event.start_at.astimezone(tz)
    reg_start_local = event.registration_start_at.astimezone(tz)
    reg_end_local = event.registration_end_at.astimezone(tz)

    limits = f"Лимит: {event.capacity}"
    if event.type.value == "team":
        limits += f" команд (размер {event.team_min_size}-{event.team_max_size})"

    return (
        f"🎯 {event.title}\n\n"
        f"🗓 Когда: {start_at_local:%d.%m.%Y %H:%M} ({settings.timezone})\n"
        f"📍 Место: {event.location}\n"
        f"📝 Регистрация: {reg_start_local:%d.%m %H:%M}"
        f" — {reg_end_local:%d.%m %H:%M} ({settings.timezone})\n"
        f"👥 {limits}"
    )
