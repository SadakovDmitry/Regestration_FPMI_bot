from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event
from app.models.enums import EventStatus
from app.services.event_service import EventService
from app.services.exceptions import NotFoundError
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PublishResult:
    event: Event
    published_now: bool
    notifications_sent: int


class PublicationService:
    def __init__(self, session: AsyncSession, bot: Bot):
        self.session = session
        self.bot = bot

    async def publish_event(self, event_id: int, now: datetime | None = None) -> PublishResult:
        now = now or datetime.now(tz=UTC)
        result = await self.session.execute(
            select(Event).where(Event.id == event_id).with_for_update()
        )
        event = result.scalar_one_or_none()
        if not event:
            raise NotFoundError("Event not found")

        if event.status == EventStatus.published:
            return PublishResult(event=event, published_now=False, notifications_sent=0)

        event = await EventService(self.session).publish(event_id=event_id, now=now)

        # Channel posting is intentionally disabled:
        # all notifications are delivered only in direct messages.

        event.planned_publish_at = None
        sent = await NotificationService(self.session, self.bot).notify_new_event(event)
        return PublishResult(event=event, published_now=True, notifications_sent=sent)

    async def process_scheduled_publications(self, now: datetime | None = None) -> list[int]:
        now = now or datetime.now(tz=UTC)
        result = await self.session.execute(
            select(Event.id).where(
                Event.status == EventStatus.draft,
                Event.planned_publish_at.is_not(None),
                Event.planned_publish_at <= now,
            )
        )
        event_ids = [event_id for event_id in result.scalars().all()]

        published_ids: list[int] = []
        for event_id in event_ids:
            outcome = await self.publish_event(event_id=event_id, now=now)
            if outcome.published_now:
                published_ids.append(outcome.event.id)
        return published_ids

    async def process_registration_window_posts(self, now: datetime | None = None) -> list[tuple[int, str]]:
        now = now or datetime.now(tz=UTC)
        result = await self.session.execute(
            select(Event.id).where(
                Event.status == EventStatus.published,
                Event.registration_end_at >= now - timedelta(hours=1),
            )
        )
        event_ids = [event_id for event_id in result.scalars().all()]

        posted: list[tuple[int, str]] = []
        for event_id in event_ids:
            status = await self._process_single_event_window_post(event_id=event_id, now=now)
            posted.extend((event_id, item) for item in status)
        return posted

    async def _process_single_event_window_post(self, event_id: int, now: datetime) -> list[str]:
        result = await self.session.execute(
            select(Event).where(Event.id == event_id).with_for_update()
        )
        event = result.scalar_one_or_none()
        if not event:
            return []

        posted: list[str] = []
        notifier = NotificationService(self.session, self.bot)

        if (
            event.registration_open_notified_at is None
            and event.registration_start_at <= now <= event.registration_end_at
        ):
            event.registration_open_notified_at = now
            sent = await notifier.notify_registration_started(event)
            logger.info(
                "Registration started notifications event_id=%s users_sent=%s",
                event.id,
                sent,
            )
            posted.append("registration_open")

        if (
            event.registration_close_soon_notified_at is None
            and event.registration_end_at - timedelta(hours=1) <= now < event.registration_end_at
        ):
            event.registration_close_soon_notified_at = now
            sent = await notifier.notify_registration_ends_soon(event)
            logger.info(
                "Registration ending soon notifications event_id=%s users_sent=%s",
                event.id,
                sent,
            )
            posted.append("registration_close_soon")

        return posted
