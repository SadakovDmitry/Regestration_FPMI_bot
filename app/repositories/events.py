from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event
from app.models.enums import EventStatus


class EventRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, event_id: int) -> Event | None:
        result = await self.session.execute(select(Event).where(Event.id == event_id))
        return result.scalar_one_or_none()

    async def list_published(self, now: datetime | None = None) -> list[Event]:
        stmt = select(Event).where(Event.status == EventStatus.published)
        if now:
            stmt = stmt.where(Event.start_at >= now)
        stmt = stmt.order_by(Event.start_at.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_due_windows(self, now: datetime) -> list[Event]:
        stmt = select(Event).where(
            and_(
                Event.status == EventStatus.published,
                Event.registration_start_at <= now,
                Event.start_at > now,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
