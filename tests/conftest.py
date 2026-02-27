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
    now: datetime | None = None,
) -> Event:
    now = now or datetime.now(tz=UTC)
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
        team_min_size=2 if event_type == EventType.team else None,
        team_max_size=5 if event_type == EventType.team else None,
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
            issued_by="ОВД",
            division_code="770-001",
            issue_date=date(2020, 1, 1),
            birth_date=date(2000, 1, 1),
            birth_place="Москва",
            registration_address="Москва, ул. Ленина, 1",
        ),
    )
