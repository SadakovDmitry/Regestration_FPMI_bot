"""add delivery kinds for registration timing notifications

Revision ID: 20260227_0003
Revises: 20260227_0002
Create Date: 2026-02-27 20:55:00

"""

from alembic import op


revision = "20260227_0003"
down_revision = "20260227_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE delivery_kind ADD VALUE IF NOT EXISTS 'registration_started'")
    op.execute("ALTER TYPE delivery_kind ADD VALUE IF NOT EXISTS 'registration_ends_soon'")


def downgrade() -> None:
    # PostgreSQL does not support dropping enum values safely in-place.
    pass
