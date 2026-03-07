from __future__ import annotations

import pytest

from app.services.event_service import EventService
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
