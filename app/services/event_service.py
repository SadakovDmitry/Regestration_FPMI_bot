from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event
from app.models.enums import EventStatus, EventType
from app.services.exceptions import NotFoundError, ValidationError
from app.services.schemas import EventCreateInput


class EventService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_draft(self, payload: EventCreateInput) -> Event:
        self._validate_payload(payload)
        event = Event(
            type=EventType(payload.type),
            status=EventStatus.draft,
            title=payload.title,
            description=payload.description,
            registration_start_at=payload.registration_start_at,
            registration_end_at=payload.registration_end_at,
            start_at=payload.start_at,
            location=payload.location,
            capacity=payload.capacity,
            team_min_size=payload.team_min_size,
            team_max_size=payload.team_max_size,
            photo_file_id=payload.photo_file_id,
            planned_publish_at=payload.planned_publish_at,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def get(self, event_id: int) -> Event | None:
        result = await self.session.execute(select(Event).where(Event.id == event_id))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Event]:
        result = await self.session.execute(select(Event).order_by(Event.created_at.desc()))
        return list(result.scalars().all())

    async def publish(self, event_id: int, now: datetime | None = None) -> Event:
        now = now or datetime.now(tz=UTC)
        result = await self.session.execute(
            select(Event).where(Event.id == event_id).with_for_update()
        )
        event = result.scalar_one_or_none()
        if not event:
            raise NotFoundError("Event not found")
        if event.status == EventStatus.published:
            return event

        self._validate_existing(event)
        event.status = EventStatus.published
        event.published_at = now
        return event

    async def archive(self, event_id: int) -> Event:
        event = await self.get(event_id)
        if not event:
            raise NotFoundError("Event not found")
        event.status = EventStatus.archived
        return event

    async def schedule_publish(self, event_id: int, publish_at: datetime) -> Event:
        result = await self.session.execute(
            select(Event).where(Event.id == event_id).with_for_update()
        )
        event = result.scalar_one_or_none()
        if not event:
            raise NotFoundError("Event not found")
        if event.status != EventStatus.draft:
            raise ValidationError("Only draft events can be scheduled")
        event.planned_publish_at = publish_at
        return event

    def _validate_payload(self, payload: EventCreateInput) -> None:
        if payload.registration_start_at >= payload.registration_end_at:
            raise ValidationError("Registration start must be before end")
        if payload.registration_end_at > payload.start_at:
            raise ValidationError("Registration must end before event start")
        if payload.capacity <= 0:
            raise ValidationError("Capacity must be positive")

        event_type = EventType(payload.type)
        if event_type == EventType.team:
            if payload.team_min_size is None or payload.team_max_size is None:
                raise ValidationError("Team min/max size is required for team events")
            if payload.team_min_size <= 0 or payload.team_max_size <= 0:
                raise ValidationError("Team min/max must be positive")
            if payload.team_min_size > payload.team_max_size:
                raise ValidationError("Team min size cannot exceed max")
        else:
            if payload.team_min_size is not None or payload.team_max_size is not None:
                raise ValidationError("Solo event cannot have team min/max")

    def _validate_existing(self, event: Event) -> None:
        payload = EventCreateInput(
            type=event.type.value,
            title=event.title,
            description=event.description,
            registration_start_at=event.registration_start_at,
            registration_end_at=event.registration_end_at,
            start_at=event.start_at,
            location=event.location,
            capacity=event.capacity,
            team_min_size=event.team_min_size,
            team_max_size=event.team_max_size,
            photo_file_id=event.photo_file_id,
            planned_publish_at=event.planned_publish_at,
        )
        self._validate_payload(payload)
