from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.models import Event

NOT_MIPT_REG_NOTE = (
    "ℹ️ Для участников не с Физтеха регистрация доступна "
    "не позже чем за 3 дня до начала мероприятия."
)


def format_dt_tz(dt: datetime) -> str:
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    return dt.astimezone(tz).strftime("%d.%m.%Y %H:%M")


def render_event_card(event: Event) -> str:
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    start_at_local = event.start_at.astimezone(tz)
    description_block = f"📝 Описание: {event.description}\n" if event.description else ""

    return (
        f"🎯 {event.title}\n\n"
        f"{description_block}"
        f"🗓 Когда: {start_at_local:%d.%m.%Y %H:%M}\n"
        f"📍 Место: {event.location}\n"
        "👥 Количество мест ограничено.\n\n"
        f"{NOT_MIPT_REG_NOTE}"
    )
