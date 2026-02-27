from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models import Event, Registration, RegistrationPerson, User
from app.models.enums import EventStatus, EventType, PersonRole, RegistrationStatus
from app.repositories.registrations import RegistrationRepository
from app.services.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.services.schemas import PersonInput, RegistrationInput

WAITLIST_RESPONSE_TIMEOUT = timedelta(hours=12)
CONFIRMATION_RESPONSE_TIMEOUT = timedelta(hours=12)


class RegistrationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = RegistrationRepository(session)
        self.settings = get_settings()

    async def create_registration(
        self,
        user_id: int,
        event_id: int,
        data: RegistrationInput,
        now: datetime | None = None,
    ) -> Registration:
        now = now or datetime.now(tz=UTC)
        event = await self._get_event_locked(event_id)
        if not event:
            raise NotFoundError("Event not found")

        self._validate_event_window(event, now)
        await self._validate_user_uniqueness(user_id, event_id)
        self._validate_payload(event, data)

        occupied = await self.repo.occupied_slots(event_id)
        status = RegistrationStatus.registered if occupied < event.capacity else RegistrationStatus.waitlist

        any_not_mipt = data.captain_or_solo.is_not_mipt or any(p.is_not_mipt for p in data.not_mipt_members)
        registration = Registration(
            event_id=event_id,
            user_id=user_id,
            status=status,
            team_name=data.team_name,
            team_size=data.team_size,
            has_not_mipt_members=any_not_mipt,
            pd_consent_at=now if data.pd_consent and any_not_mipt else None,
            pd_consent_version=data.pd_consent_version if data.pd_consent and any_not_mipt else None,
        )

        registration.people.append(
            self._make_person(
                role=PersonRole.solo if event.type == EventType.solo else PersonRole.captain,
                person=data.captain_or_solo,
            )
        )

        for member in data.not_mipt_members:
            registration.people.append(
                self._make_person(role=PersonRole.team_not_mipt_member, person=member)
            )

        self.session.add(registration)
        await self.session.flush()

        await self._persist_profile(user_id, data.captain_or_solo)
        return registration

    async def cancel_registration(
        self,
        user_id: int,
        registration_id: int,
        now: datetime | None = None,
    ) -> Registration:
        now = now or datetime.now(tz=UTC)
        registration = await self._get_registration_locked(registration_id)
        if not registration:
            raise NotFoundError("Registration not found")
        if registration.user_id != user_id:
            raise PermissionDeniedError("This registration belongs to another user")

        if registration.status == RegistrationStatus.cancelled_by_user:
            return registration

        registration.status = RegistrationStatus.cancelled_by_user
        registration.cancelled_at = now

        event = await self._get_event_locked(registration.event_id)
        if event and event.start_at > now:
            await self.promote_waitlist(registration.event_id, now)

        return registration

    async def promote_waitlist(
        self,
        event_id: int,
        now: datetime | None = None,
    ) -> list[Registration]:
        now = now or datetime.now(tz=UTC)
        event = await self._get_event_locked(event_id)
        if not event:
            raise NotFoundError("Event not found")

        invited: list[Registration] = []
        occupied = await self.repo.occupied_slots(event_id)

        while occupied < event.capacity:
            candidate = await self.repo.first_waitlist(event_id)
            if not candidate:
                break
            candidate.status = RegistrationStatus.invited_from_waitlist
            candidate.waitlist_invited_at = now
            candidate.waitlist_expires_at = now + WAITLIST_RESPONSE_TIMEOUT
            invited.append(candidate)
            occupied += 1

        return invited

    async def respond_waitlist_invite(
        self,
        registration_id: int,
        accepted: bool,
        now: datetime | None = None,
    ) -> Registration:
        now = now or datetime.now(tz=UTC)
        registration = await self._get_registration_locked(registration_id)
        if not registration:
            raise NotFoundError("Registration not found")
        if registration.status != RegistrationStatus.invited_from_waitlist:
            raise ValidationError("Registration is not waiting for waitlist response")

        registration.waitlist_expires_at = None
        if accepted:
            registration.status = RegistrationStatus.registered
            return registration

        registration.status = RegistrationStatus.declined
        event = await self._get_event_locked(registration.event_id)
        if event and event.start_at > now:
            await self.promote_waitlist(registration.event_id, now)
        return registration

    async def expire_waitlist_invites(self, now: datetime | None = None) -> list[int]:
        now = now or datetime.now(tz=UTC)
        due = await self.repo.due_waitlist_timeouts(now)
        if not due:
            return []

        affected_events: set[int] = set()
        for registration in due:
            registration.status = RegistrationStatus.auto_declined
            registration.waitlist_expires_at = None
            affected_events.add(registration.event_id)

        for event_id in affected_events:
            event = await self._get_event_locked(event_id)
            if event and event.start_at > now:
                await self.promote_waitlist(event_id, now)

        return [r.id for r in due]

    async def request_confirmation_for_event(
        self,
        event_id: int,
        now: datetime | None = None,
    ) -> list[Registration]:
        now = now or datetime.now(tz=UTC)
        registrations = await self.repo.needs_confirmation_for_event(event_id)
        for registration in registrations:
            registration.confirmation_requested_at = now
            registration.confirmation_expires_at = now + CONFIRMATION_RESPONSE_TIMEOUT
        return registrations

    async def respond_confirmation(
        self,
        registration_id: int,
        going: bool,
        now: datetime | None = None,
    ) -> Registration:
        now = now or datetime.now(tz=UTC)
        registration = await self._get_registration_locked(registration_id)
        if not registration:
            raise NotFoundError("Registration not found")
        if not registration.confirmation_requested_at:
            raise ValidationError("Confirmation has not been requested")
        if registration.status not in (
            RegistrationStatus.registered,
            RegistrationStatus.invited_from_waitlist,
            RegistrationStatus.confirmed,
        ):
            raise ValidationError("Registration is not eligible for confirmation")

        registration.confirmation_expires_at = None

        if going:
            registration.status = RegistrationStatus.confirmed
            return registration

        registration.status = RegistrationStatus.declined
        event = await self._get_event_locked(registration.event_id)
        if event and event.start_at > now:
            await self.promote_waitlist(registration.event_id, now)
        return registration

    async def expire_confirmations(self, now: datetime | None = None) -> list[int]:
        now = now or datetime.now(tz=UTC)
        due = await self.repo.due_confirmation_timeouts(now)
        if not due:
            return []

        affected_events: set[int] = set()
        for registration in due:
            registration.status = RegistrationStatus.auto_declined
            registration.confirmation_expires_at = None
            affected_events.add(registration.event_id)

        for event_id in affected_events:
            event = await self._get_event_locked(event_id)
            if event and event.start_at > now:
                await self.promote_waitlist(event_id, now)

        return [r.id for r in due]

    async def _get_event_locked(self, event_id: int) -> Event | None:
        result = await self.session.execute(
            select(Event).where(Event.id == event_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def _get_registration_locked(self, registration_id: int) -> Registration | None:
        result = await self.session.execute(
            select(Registration)
            .options(selectinload(Registration.people))
            .where(Registration.id == registration_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def _validate_user_uniqueness(self, user_id: int, event_id: int) -> None:
        existing = await self.repo.active_registration_for_user_event(user_id=user_id, event_id=event_id)
        if existing:
            raise ValidationError("You already have an active registration for this event")

    def _validate_event_window(self, event: Event, now: datetime) -> None:
        if event.status != EventStatus.published:
            raise ValidationError("Event is not published")
        if now < event.registration_start_at or now > event.registration_end_at:
            raise ValidationError("Registration window is closed")

    def _validate_payload(self, event: Event, data: RegistrationInput) -> None:
        if event.type == EventType.solo:
            if data.team_name or data.team_size:
                raise ValidationError("Solo registration cannot include team fields")
            if data.not_mipt_members:
                raise ValidationError("Solo registration cannot include team members")

        if event.type == EventType.team:
            if not data.team_name:
                raise ValidationError("Team name is required")
            if data.team_size is None:
                raise ValidationError("Team size is required")
            if event.team_min_size and data.team_size < event.team_min_size:
                raise ValidationError("Team size is below minimum")
            if event.team_max_size and data.team_size > event.team_max_size:
                raise ValidationError("Team size exceeds maximum")

        needs_consent = data.captain_or_solo.is_not_mipt or any(
            member.is_not_mipt for member in data.not_mipt_members
        )
        if needs_consent and not data.pd_consent:
            raise ValidationError("PD consent is required for passport processing")

        for person in [data.captain_or_solo, *data.not_mipt_members]:
            if person.is_not_mipt and person.passport is None:
                raise ValidationError("Passport data is required for not_mipt person")

    @staticmethod
    def _make_person(role: PersonRole, person: PersonInput) -> RegistrationPerson:
        passport = person.passport
        return RegistrationPerson(
            role=role,
            last_name=person.last_name,
            first_name=person.first_name,
            middle_name=person.middle_name,
            contact=person.contact,
            group_name=person.group_name,
            is_not_mipt=person.is_not_mipt,
            passport_series=passport.series if passport else None,
            passport_number=passport.number if passport else None,
            passport_issued_by=passport.issued_by if passport else None,
            passport_division_code=passport.division_code if passport else None,
            passport_issue_date=passport.issue_date if passport else None,
            birth_date=passport.birth_date if passport else None,
            birth_place=passport.birth_place if passport else None,
            registration_address=passport.registration_address if passport else None,
        )

    async def _persist_profile(self, user_id: int, person: PersonInput) -> None:
        result = await self.session.execute(select(User).where(User.id == user_id).with_for_update())
        user = result.scalar_one_or_none()
        if not user:
            return
        user.last_name = person.last_name
        user.first_name = person.first_name
        user.middle_name = person.middle_name
        user.contact = person.contact
        user.group_name = person.group_name

    async def list_waitlist(self, event_id: int) -> list[Registration]:
        regs = await self.repo.list_by_event(event_id)
        return [r for r in regs if r.status == RegistrationStatus.waitlist]

    async def event_status_counters(self, event_id: int) -> dict[str, int]:
        regs = await self.repo.list_by_event(event_id)
        counters: dict[str, int] = defaultdict(int)
        for reg in regs:
            counters[reg.status.value] += 1
        return dict(counters)
