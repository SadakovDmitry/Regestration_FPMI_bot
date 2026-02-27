"""initial schema

Revision ID: 20260227_0001
Revises:
Create Date: 2026-02-27 18:30:00

"""

from alembic import op
import sqlalchemy as sa


revision = "20260227_0001"
down_revision = None
branch_labels = None
depends_on = None


event_type = sa.Enum("solo", "team", name="event_type", create_type=False)
event_status = sa.Enum("draft", "published", "archived", name="event_status", create_type=False)
registration_status = sa.Enum(
    "registered",
    "waitlist",
    "invited_from_waitlist",
    "confirmed",
    "declined",
    "auto_declined",
    "cancelled_by_user",
    name="registration_status",
    create_type=False,
)
person_role = sa.Enum(
    "solo",
    "captain",
    "team_not_mipt_member",
    name="person_role",
    create_type=False,
)
delivery_kind = sa.Enum(
    "new_event",
    "ping_4d",
    "confirmation_24h",
    "ping_2h",
    "waitlist_invite",
    name="delivery_kind",
    create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tg_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("is_reachable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("middle_name", sa.String(length=255), nullable=True),
        sa.Column("contact", sa.String(length=255), nullable=True),
        sa.Column("group_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tg_id", name="uq_users_tg_id"),
    )
    op.create_index("ix_users_tg_id", "users", ["tg_id"], unique=True)

    op.create_table(
        "admins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tg_id", sa.BigInteger(), nullable=False),
        sa.Column("added_by_tg_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tg_id", name="uq_admins_tg_id"),
    )
    op.create_index("ix_admins_tg_id", "admins", ["tg_id"], unique=True)

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type", event_type, nullable=False),
        sa.Column("status", event_status, nullable=False, server_default="draft"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("registration_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("registration_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("team_min_size", sa.Integer(), nullable=True),
        sa.Column("team_max_size", sa.Integer(), nullable=True),
        sa.Column("photo_file_id", sa.String(length=255), nullable=True),
        sa.Column("channel_post_message_id", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_events_type", "events", ["type"])
    op.create_index("ix_events_status", "events", ["status"])
    op.create_index("ix_events_start_at", "events", ["start_at"])

    op.create_table(
        "registrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", registration_status, nullable=False),
        sa.Column("team_name", sa.String(length=255), nullable=True),
        sa.Column("team_size", sa.Integer(), nullable=True),
        sa.Column("has_not_mipt_members", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("pd_consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pd_consent_version", sa.String(length=32), nullable=True),
        sa.Column("waitlist_invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("waitlist_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmation_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmation_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_registrations_event_id", "registrations", ["event_id"])
    op.create_index("ix_registrations_user_id", "registrations", ["user_id"])
    op.create_index("ix_registrations_status", "registrations", ["status"])

    op.create_table(
        "registration_people",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "registration_id",
            sa.Integer(),
            sa.ForeignKey("registrations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", person_role, nullable=False),
        sa.Column("last_name", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=False),
        sa.Column("middle_name", sa.String(length=255), nullable=True),
        sa.Column("contact", sa.String(length=255), nullable=True),
        sa.Column("group_name", sa.String(length=255), nullable=True),
        sa.Column("is_not_mipt", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("passport_series", sa.String(length=16), nullable=True),
        sa.Column("passport_number", sa.String(length=16), nullable=True),
        sa.Column("passport_issued_by", sa.Text(), nullable=True),
        sa.Column("passport_division_code", sa.String(length=16), nullable=True),
        sa.Column("passport_issue_date", sa.Date(), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("birth_place", sa.Text(), nullable=True),
        sa.Column("registration_address", sa.Text(), nullable=True),
    )
    op.create_index("ix_registration_people_registration_id", "registration_people", ["registration_id"])
    op.create_index("ix_registration_people_role", "registration_people", ["role"])

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=True),
        sa.Column("kind", delivery_kind, nullable=False),
        sa.Column("payload_ref", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "event_id", "kind", name="uq_notification_delivery"),
    )
    op.create_index("ix_notification_deliveries_user_id", "notification_deliveries", ["user_id"])
    op.create_index("ix_notification_deliveries_event_id", "notification_deliveries", ["event_id"])
    op.create_index("ix_notification_deliveries_kind", "notification_deliveries", ["kind"])


def downgrade() -> None:
    op.drop_index("ix_notification_deliveries_kind", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_event_id", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_user_id", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")

    op.drop_index("ix_registration_people_role", table_name="registration_people")
    op.drop_index("ix_registration_people_registration_id", table_name="registration_people")
    op.drop_table("registration_people")

    op.drop_index("ix_registrations_status", table_name="registrations")
    op.drop_index("ix_registrations_user_id", table_name="registrations")
    op.drop_index("ix_registrations_event_id", table_name="registrations")
    op.drop_table("registrations")

    op.drop_index("ix_events_start_at", table_name="events")
    op.drop_index("ix_events_status", table_name="events")
    op.drop_index("ix_events_type", table_name="events")
    op.drop_table("events")

    op.drop_index("ix_admins_tg_id", table_name="admins")
    op.drop_table("admins")

    op.drop_index("ix_users_tg_id", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    delivery_kind.drop(bind, checkfirst=True)
    person_role.drop(bind, checkfirst=True)
    registration_status.drop(bind, checkfirst=True)
    event_status.drop(bind, checkfirst=True)
    event_type.drop(bind, checkfirst=True)
