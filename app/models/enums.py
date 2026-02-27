from enum import Enum


class EventType(str, Enum):
    solo = "solo"
    team = "team"


class EventStatus(str, Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class RegistrationStatus(str, Enum):
    registered = "registered"
    waitlist = "waitlist"
    invited_from_waitlist = "invited_from_waitlist"
    confirmed = "confirmed"
    declined = "declined"
    auto_declined = "auto_declined"
    cancelled_by_user = "cancelled_by_user"


class PersonRole(str, Enum):
    solo = "solo"
    captain = "captain"
    team_not_mipt_member = "team_not_mipt_member"


class DeliveryKind(str, Enum):
    new_event = "new_event"
    registration_started = "registration_started"
    registration_ends_soon = "registration_ends_soon"
    ping_4d = "ping_4d"
    confirmation_24h = "confirmation_24h"
    ping_2h = "ping_2h"
    waitlist_invite = "waitlist_invite"
