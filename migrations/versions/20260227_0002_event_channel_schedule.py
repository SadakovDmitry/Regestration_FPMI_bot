"""add event publish scheduling and registration channel marks

Revision ID: 20260227_0002
Revises: 20260227_0001
Create Date: 2026-02-27 20:30:00

"""

from alembic import op
import sqlalchemy as sa


revision = "20260227_0002"
down_revision = "20260227_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("events", sa.Column("planned_publish_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "events",
        sa.Column("registration_open_post_message_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "events",
        sa.Column("registration_open_notified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "events",
        sa.Column("registration_close_soon_post_message_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "events",
        sa.Column("registration_close_soon_notified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("events", "registration_close_soon_notified_at")
    op.drop_column("events", "registration_close_soon_post_message_id")
    op.drop_column("events", "registration_open_notified_at")
    op.drop_column("events", "registration_open_post_message_id")
    op.drop_column("events", "planned_publish_at")
