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
    reg_start_local = event.registration_start_at.astimezone(tz)
    reg_end_local = event.registration_end_at.astimezone(tz)

    limits = f"Лимит: {event.capacity}"
    if event.type.value == "team":
        limits += f" чел. (размер команды {event.team_min_size}-{event.team_max_size})"

    return (
        f"🎯 {event.title}\n\n"
        f"🗓 Когда: {start_at_local:%d.%m.%Y %H:%M}\n"
        f"📍 Место: {event.location}\n"
        f"📝 Регистрация: {reg_start_local:%d.%m %H:%M}"
        f" — {reg_end_local:%d.%m %H:%M}\n"
        f"👥 {limits}\n\n"
        f"{NOT_MIPT_REG_NOTE}"
    )
