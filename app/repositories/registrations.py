from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Registration
from app.models.enums import RegistrationStatus


OCCUPYING_STATUSES = (
    RegistrationStatus.registered,
    RegistrationStatus.confirmed,
    RegistrationStatus.invited_from_waitlist,
)


class RegistrationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, registration_id: int) -> Registration | None:
        result = await self.session.execute(
            select(Registration)
            .options(selectinload(Registration.people))
            .where(Registration.id == registration_id)
        )
        return result.scalar_one_or_none()

    async def list_by_event(self, event_id: int) -> list[Registration]:
        result = await self.session.execute(
            select(Registration)
            .options(selectinload(Registration.people))
            .where(Registration.event_id == event_id)
            .order_by(Registration.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_by_user(self, user_id: int) -> list[Registration]:
        result = await self.session.execute(
            select(Registration)
            .options(selectinload(Registration.event), selectinload(Registration.people))
            .where(Registration.user_id == user_id)
            .order_by(Registration.created_at.desc())
        )
        return list(result.scalars().all())

    async def active_registration_for_user_event(
        self,
        user_id: int,
        event_id: int,
    ) -> Registration | None:
        result = await self.session.execute(
            select(Registration).where(
                Registration.user_id == user_id,
                Registration.event_id == event_id,
                Registration.status.in_(
                    (
                        RegistrationStatus.registered,
                        RegistrationStatus.waitlist,
                        RegistrationStatus.invited_from_waitlist,
                        RegistrationStatus.confirmed,
                    )
                ),
            )
        )
        return result.scalar_one_or_none()

    async def occupied_slots(self, event_id: int) -> int:
        result = await self.session.execute(
            select(func.count(Registration.id)).where(
                Registration.event_id == event_id,
                Registration.status.in_(OCCUPYING_STATUSES),
            )
        )
        return int(result.scalar_one() or 0)

    async def first_waitlist(self, event_id: int) -> Registration | None:
        result = await self.session.execute(
            select(Registration)
            .where(
                Registration.event_id == event_id,
                Registration.status == RegistrationStatus.waitlist,
            )
            .order_by(Registration.created_at.asc(), Registration.id.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def due_waitlist_timeouts(self, now: datetime) -> list[Registration]:
        result = await self.session.execute(
            select(Registration).where(
                Registration.status == RegistrationStatus.invited_from_waitlist,
                Registration.waitlist_expires_at.is_not(None),
                Registration.waitlist_expires_at <= now,
            )
        )
        return list(result.scalars().all())

    async def due_confirmation_timeouts(self, now: datetime) -> list[Registration]:
        result = await self.session.execute(
            select(Registration).where(
                Registration.status.in_(
                    (
                        RegistrationStatus.registered,
                        RegistrationStatus.invited_from_waitlist,
                    )
                ),
                Registration.confirmation_requested_at.is_not(None),
                Registration.confirmation_expires_at.is_not(None),
                Registration.confirmation_expires_at <= now,
            )
        )
        return list(result.scalars().all())

    async def needs_confirmation_for_event(
        self,
        event_id: int,
    ) -> list[Registration]:
        result = await self.session.execute(
            select(Registration).where(
                Registration.event_id == event_id,
                Registration.status.in_(
                    (
                        RegistrationStatus.registered,
                        RegistrationStatus.invited_from_waitlist,
                        RegistrationStatus.confirmed,
                    )
                ),
                Registration.confirmation_requested_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def list_not_mipt_for_event(self, event_id: int) -> list[Registration]:
        result = await self.session.execute(
            select(Registration)
            .options(selectinload(Registration.people))
            .where(
                Registration.event_id == event_id,
                Registration.status.in_(
                    (
                        RegistrationStatus.registered,
                        RegistrationStatus.invited_from_waitlist,
                        RegistrationStatus.confirmed,
                    )
                ),
                or_(Registration.has_not_mipt_members.is_(True), Registration.pd_consent_at.is_not(None)),
            )
        )
        return list(result.scalars().all())

    async def list_confirmed_for_event(self, event_id: int) -> list[Registration]:
        result = await self.session.execute(
            select(Registration)
            .options(selectinload(Registration.people))
            .where(
                Registration.event_id == event_id,
                Registration.status == RegistrationStatus.confirmed,
            )
        )
        return list(result.scalars().all())

    async def list_active_for_event(self, event_id: int) -> list[Registration]:
        result = await self.session.execute(
            select(Registration)
            .options(selectinload(Registration.people))
            .where(
                Registration.event_id == event_id,
                Registration.status.in_(
                    (
                        RegistrationStatus.registered,
                        RegistrationStatus.invited_from_waitlist,
                        RegistrationStatus.confirmed,
                        RegistrationStatus.waitlist,
                    )
                ),
            )
            .order_by(Registration.created_at.asc())
        )
        return list(result.scalars().all())

    async def count_registrations_by_status(self, event_id: int, status: RegistrationStatus) -> int:
        result = await self.session.execute(
            select(func.count(Registration.id)).where(
                Registration.event_id == event_id,
                Registration.status == status,
            )
        )
        return int(result.scalar_one() or 0)

    async def seats_freed_trigger_status(self, status: RegistrationStatus) -> bool:
        return status in (
            RegistrationStatus.declined,
            RegistrationStatus.auto_declined,
            RegistrationStatus.cancelled_by_user,
        )
