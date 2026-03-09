from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.services.event_service import EventService
from app.services.exceptions import ValidationError
from tests.conftest import create_event


@pytest.mark.asyncio
async def test_delete_event_removes_it(session):
    event = await create_event(session)
    await session.commit()

    service = EventService(session)
    await service.delete(event.id)
    await session.commit()

    deleted = await service.get(event.id)
    assert deleted is None


@pytest.mark.asyncio
async def test_update_event_fields_for_published_event(session):
    now = datetime.now(tz=UTC)
    event = await create_event(session, now=now)
    await session.commit()

    service = EventService(session)
    updated = await service.update_fields(
        event.id,
        {
            "title": "Новое название",
            "description": "Новое описание",
            "start_at": now + timedelta(days=5),
        },
    )
    await session.commit()

    assert updated.title == "Новое название"
    assert updated.description == "Новое описание"
    assert updated.start_at == now + timedelta(days=5)


@pytest.mark.asyncio
async def test_update_event_fields_validates_dates(session):
    now = datetime.now(tz=UTC)
    event = await create_event(session, now=now)
    await session.commit()

    service = EventService(session)
    with pytest.raises(ValidationError):
        await service.update_fields(
            event.id,
            {
                "registration_end_at": now + timedelta(days=10),
            },
        )
