from __future__ import annotations

from datetime import datetime, date

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import DeliveryKind, EventStatus, EventType, PersonRole, RegistrationStatus


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_reachable: Mapped[bool] = mapped_column(Boolean, default=True)

    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    middle_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    group_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    registrations: Mapped[list[Registration]] = relationship(back_populates="user")


class Admin(TimestampMixin, Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    added_by_tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class Event(TimestampMixin, Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[EventType] = mapped_column(Enum(EventType, name="event_type"), index=True)
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, name="event_status"), default=EventStatus.draft, index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str] = mapped_column(String(255))

    registration_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    registration_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    capacity: Mapped[int] = mapped_column(Integer)
    team_min_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    team_max_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    photo_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    planned_publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    channel_post_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    registration_open_post_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    registration_open_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    registration_close_soon_post_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    registration_close_soon_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    registrations: Mapped[list[Registration]] = relationship(back_populates="event")


class Registration(TimestampMixin, Base):
    __tablename__ = "registrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    status: Mapped[RegistrationStatus] = mapped_column(
        Enum(RegistrationStatus, name="registration_status"), index=True
    )

    team_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    team_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_not_mipt_members: Mapped[bool] = mapped_column(Boolean, default=False)

    pd_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pd_consent_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    waitlist_invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    waitlist_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    confirmation_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmation_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    event: Mapped[Event] = relationship(back_populates="registrations")
    user: Mapped[User] = relationship(back_populates="registrations")
    people: Mapped[list[RegistrationPerson]] = relationship(back_populates="registration", cascade="all, delete-orphan")


class RegistrationPerson(Base):
    __tablename__ = "registration_people"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    registration_id: Mapped[int] = mapped_column(
        ForeignKey("registrations.id", ondelete="CASCADE"), index=True
    )

    role: Mapped[PersonRole] = mapped_column(Enum(PersonRole, name="person_role"), index=True)
    last_name: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(255))
    middle_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    group_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_not_mipt: Mapped[bool] = mapped_column(Boolean, default=False)

    passport_series: Mapped[str | None] = mapped_column(String(16), nullable=True)
    passport_number: Mapped[str | None] = mapped_column(String(16), nullable=True)
    passport_issued_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    passport_division_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    passport_issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    birth_place: Mapped[str | None] = mapped_column(Text, nullable=True)
    registration_address: Mapped[str | None] = mapped_column(Text, nullable=True)

    registration: Mapped[Registration] = relationship(back_populates="people")


class NotificationDelivery(TimestampMixin, Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("user_id", "event_id", "kind", name="uq_notification_delivery"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=True, index=True
    )
    kind: Mapped[DeliveryKind] = mapped_column(Enum(DeliveryKind, name="delivery_kind"), index=True)
    payload_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
