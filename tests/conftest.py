from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base, Event, EventStatus, EventType, User
from app.services.schemas import PassportInput, PersonInput


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session

    await engine.dispose()


async def create_user(session: AsyncSession, tg_id: int) -> User:
    user = User(tg_id=tg_id, username=f"user_{tg_id}", is_reachable=True)
    session.add(user)
    await session.flush()
    return user


async def create_event(
    session: AsyncSession,
    *,
    event_type: EventType = EventType.solo,
    capacity: int = 1,
    team_min_size: int | None = None,
    team_max_size: int | None = None,
    now: datetime | None = None,
) -> Event:
    now = now or datetime.now(tz=UTC)
    resolved_team_min = team_min_size if team_min_size is not None else (2 if event_type == EventType.team else None)
    resolved_team_max = team_max_size if team_max_size is not None else (5 if event_type == EventType.team else None)
    event = Event(
        type=event_type,
        status=EventStatus.published,
        title="Test Event",
        description="desc",
        location="Campus",
        registration_start_at=now - timedelta(days=1),
        registration_end_at=now + timedelta(days=1),
        start_at=now + timedelta(days=2),
        capacity=capacity,
        team_min_size=resolved_team_min,
        team_max_size=resolved_team_max,
    )
    session.add(event)
    await session.flush()
    return event


def mipt_person(contact: str = "@user") -> PersonInput:
    return PersonInput(
        last_name="Иванов",
        first_name="Иван",
        middle_name="Иванович",
        contact=contact,
        group_name="Б01-001",
        is_not_mipt=False,
        passport=None,
    )


def not_mipt_person(contact: str = "@user") -> PersonInput:
    return PersonInput(
        last_name="Петров",
        first_name="Петр",
        middle_name=None,
        contact=contact,
        group_name=None,
        is_not_mipt=True,
        passport=PassportInput(
            series="1234",
            number="567890",
            issue_date=date(2020, 1, 1),
        ),
    )
