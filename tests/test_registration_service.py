from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.enums import EventType, RegistrationStatus
from app.services.registration_service import RegistrationService
from app.services.schemas import RegistrationInput
from tests.conftest import create_event, create_user, mipt_person


@pytest.mark.asyncio
async def test_capacity_and_waitlist_creation(session):
    now = datetime.now(tz=UTC)
    event = await create_event(session, event_type=EventType.solo, capacity=1, now=now)
    user1 = await create_user(session, tg_id=1)
    user2 = await create_user(session, tg_id=2)

    service = RegistrationService(session)
    reg1 = await service.create_registration(
        user1.id,
        event.id,
        RegistrationInput(captain_or_solo=mipt_person("@u1")),
        now=now,
    )
    reg2 = await service.create_registration(
        user2.id,
        event.id,
        RegistrationInput(captain_or_solo=mipt_person("@u2")),
        now=now,
    )

    assert reg1.status == RegistrationStatus.registered
    assert reg2.status == RegistrationStatus.waitlist


@pytest.mark.asyncio
async def test_waitlist_timeout_and_next_invite(session):
    now = datetime.now(tz=UTC)
    event = await create_event(session, event_type=EventType.solo, capacity=1, now=now)
    user1 = await create_user(session, tg_id=11)
    user2 = await create_user(session, tg_id=22)
    user3 = await create_user(session, tg_id=33)

    service = RegistrationService(session)
    reg1 = await service.create_registration(
        user1.id,
        event.id,
        RegistrationInput(captain_or_solo=mipt_person("@u11")),
        now=now,
    )
    reg2 = await service.create_registration(
        user2.id,
        event.id,
        RegistrationInput(captain_or_solo=mipt_person("@u22")),
        now=now,
    )
    reg3 = await service.create_registration(
        user3.id,
        event.id,
        RegistrationInput(captain_or_solo=mipt_person("@u33")),
        now=now,
    )

    await service.cancel_registration(user1.id, reg1.id, now=now)
    assert reg2.status == RegistrationStatus.invited_from_waitlist
    assert reg2.waitlist_expires_at == now + timedelta(hours=12)

    await service.expire_waitlist_invites(now + timedelta(hours=13))
    assert reg2.status == RegistrationStatus.auto_declined
    assert reg3.status == RegistrationStatus.invited_from_waitlist


@pytest.mark.asyncio
async def test_confirmation_timeout_and_waitlist_release(session):
    now = datetime.now(tz=UTC)
    event = await create_event(session, event_type=EventType.solo, capacity=1, now=now)
    user1 = await create_user(session, tg_id=101)
    user2 = await create_user(session, tg_id=202)

    service = RegistrationService(session)
    reg1 = await service.create_registration(
        user1.id,
        event.id,
        RegistrationInput(captain_or_solo=mipt_person("@u101")),
        now=now,
    )
    reg2 = await service.create_registration(
        user2.id,
        event.id,
        RegistrationInput(captain_or_solo=mipt_person("@u202")),
        now=now,
    )

    requested = await service.request_confirmation_for_event(event.id, now=now)
    assert len(requested) == 1
    assert reg1.confirmation_expires_at == now + timedelta(hours=12)

    await service.expire_confirmations(now + timedelta(hours=13))
    assert reg1.status == RegistrationStatus.auto_declined
    assert reg2.status == RegistrationStatus.invited_from_waitlist


@pytest.mark.asyncio
async def test_cancel_releases_slot(session):
    now = datetime.now(tz=UTC)
    event = await create_event(session, event_type=EventType.solo, capacity=1, now=now)
    user1 = await create_user(session, tg_id=501)
    user2 = await create_user(session, tg_id=502)

    service = RegistrationService(session)
    reg1 = await service.create_registration(
        user1.id,
        event.id,
        RegistrationInput(captain_or_solo=mipt_person("@u501")),
        now=now,
    )
    reg2 = await service.create_registration(
        user2.id,
        event.id,
        RegistrationInput(captain_or_solo=mipt_person("@u502")),
        now=now,
    )

    await service.cancel_registration(user1.id, reg1.id, now=now)

    assert reg1.status == RegistrationStatus.cancelled_by_user
    assert reg2.status == RegistrationStatus.invited_from_waitlist
