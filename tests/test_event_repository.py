from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.enums import EventType
from app.repositories.events import EventRepository
from tests.conftest import create_event


@pytest.mark.asyncio
async def test_list_published_hides_events_with_closed_registration(session):
    now = datetime.now(tz=UTC)

    open_event = await create_event(session, event_type=EventType.solo, capacity=10, now=now)
    closed_event = await create_event(session, event_type=EventType.solo, capacity=10, now=now + timedelta(days=2))
    closed_event.registration_start_at = now - timedelta(days=2)
    closed_event.registration_end_at = now - timedelta(hours=1)

    await session.commit()

    events = await EventRepository(session).list_published(now)
    event_ids = {event.id for event in events}

    assert open_event.id in event_ids
    assert closed_event.id not in event_ids
