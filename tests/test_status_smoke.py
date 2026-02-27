from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.models.enums import EventType, RegistrationStatus
from app.services.registration_service import RegistrationService
from app.services.schemas import RegistrationInput
from tests.conftest import create_event, create_user, not_mipt_person


@pytest.mark.asyncio
async def test_team_flow_smoke(session):
    now = datetime.now(tz=UTC)
    event = await create_event(session, event_type=EventType.team, capacity=1, now=now)
    user = await create_user(session, tg_id=700)

    service = RegistrationService(session)
    reg = await service.create_registration(
        user.id,
        event.id,
        RegistrationInput(
            captain_or_solo=not_mipt_person("@captain"),
            team_name="Alpha",
            team_size=3,
            not_mipt_members=[],
            pd_consent=True,
            pd_consent_version="v1",
        ),
        now=now,
    )

    assert reg.status == RegistrationStatus.registered
    assert reg.has_not_mipt_members is True

    await service.request_confirmation_for_event(event.id, now=now)
    await service.respond_confirmation(reg.id, going=True, now=now)
    assert reg.status == RegistrationStatus.confirmed
