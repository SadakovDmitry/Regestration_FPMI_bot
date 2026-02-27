from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(slots=True)
class PassportInput:
    series: str
    number: str
    issued_by: str
    division_code: str
    issue_date: date
    birth_date: date
    birth_place: str
    registration_address: str


@dataclass(slots=True)
class PersonInput:
    last_name: str
    first_name: str
    middle_name: str | None
    contact: str | None
    group_name: str | None
    is_not_mipt: bool
    passport: PassportInput | None = None


@dataclass(slots=True)
class RegistrationInput:
    captain_or_solo: PersonInput
    team_name: str | None = None
    team_size: int | None = None
    not_mipt_members: list[PersonInput] = field(default_factory=list)
    pd_consent: bool = False
    pd_consent_version: str | None = None


@dataclass(slots=True)
class EventCreateInput:
    type: str
    title: str
    description: str | None
    registration_start_at: datetime
    registration_end_at: datetime
    start_at: datetime
    location: str
    capacity: int
    team_min_size: int | None = None
    team_max_size: int | None = None
    photo_file_id: str | None = None
    planned_publish_at: datetime | None = None
