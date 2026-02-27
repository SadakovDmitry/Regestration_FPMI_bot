from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from celery.utils.log import get_task_logger
from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.jobs.celery_app import celery_app
from app.models import Event
from app.models.enums import EventStatus
from app.services.notification_service import NotificationService
from app.services.publication_service import PublicationService
from app.services.registration_service import RegistrationService
from app.config import get_settings

logger = get_task_logger(__name__)


@celery_app.task(name="app.jobs.tasks.process_periodic_workflow")
def process_periodic_workflow() -> None:
    asyncio.run(_process_periodic_workflow())


async def _process_periodic_workflow() -> None:
    settings = get_settings()
    bot = Bot(token=settings.bot_token)

    now = datetime.now(tz=UTC)
    async with AsyncSessionLocal() as session:
        reg_service = RegistrationService(session)
        publication_service = PublicationService(session, bot)

        await reg_service.expire_waitlist_invites(now)
        await reg_service.expire_confirmations(now)
        published_ids = await publication_service.process_scheduled_publications(now)
        posted_windows = await publication_service.process_registration_window_posts(now)

        result = await session.execute(
            select(Event).where(
                Event.status == EventStatus.published,
                Event.start_at > now - timedelta(days=1),
            )
        )
        events = list(result.scalars().all())

        notifier = NotificationService(session, bot)

        for event in events:
            if event.start_at - timedelta(hours=24) <= now <= event.start_at - timedelta(hours=12):
                await reg_service.request_confirmation_for_event(event.id, now)
                await notifier.notify_confirmations(event.id)

            if event.start_at - timedelta(days=4) <= now <= event.start_at:
                await notifier.notify_ping_4d(event.id)

            if event.start_at - timedelta(hours=2) <= now <= event.start_at:
                await notifier.notify_ping_2h(event.id)

            await notifier.notify_waitlist_invites(event.id)

        await session.commit()

    await bot.session.close()
    logger.info(
        "Periodic workflow processed published=%s window_posts=%s",
        len(published_ids),
        len(posted_windows),
    )
