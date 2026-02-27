from __future__ import annotations

from app.models import Event


def render_event_card(event: Event) -> str:
    limits = f"Лимит: {event.capacity}"
    if event.type.value == "team":
        limits += f" команд (размер {event.team_min_size}-{event.team_max_size})"

    return (
        f"{event.title}\n\n"
        f"Когда: {event.start_at:%d.%m.%Y %H:%M}\n"
        f"Место: {event.location}\n"
        f"Регистрация: {event.registration_start_at:%d.%m %H:%M} - {event.registration_end_at:%d.%m %H:%M}\n"
        f"{limits}"
    )
