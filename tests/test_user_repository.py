from __future__ import annotations

import pytest

from app.repositories.users import UserRepository


@pytest.mark.asyncio
async def test_ensure_user_autofills_contact_from_username(session):
    repo = UserRepository(session)
    user = await repo.ensure_user(tg_id=111, username="alice")
    assert user.contact == "@alice"


@pytest.mark.asyncio
async def test_ensure_user_updates_auto_contact_when_username_changed(session):
    repo = UserRepository(session)
    await repo.ensure_user(tg_id=222, username="oldnick")
    user = await repo.ensure_user(tg_id=222, username="newnick")
    assert user.contact == "@newnick"


@pytest.mark.asyncio
async def test_ensure_user_keeps_manual_contact_when_username_changed(session):
    repo = UserRepository(session)
    user = await repo.ensure_user(tg_id=333, username="oldnick")
    user.contact = "+79990001122"

    user = await repo.ensure_user(tg_id=333, username="newnick")
    assert user.contact == "+79990001122"
