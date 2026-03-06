"""reduce passport fields to minimal required set

Revision ID: 20260306_0004
Revises: 20260227_0003
Create Date: 2026-03-06 18:40:00

"""

from alembic import op


revision = "20260306_0004"
down_revision = "20260227_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("registration_people", "passport_issued_by")
    op.drop_column("registration_people", "passport_division_code")
    op.drop_column("registration_people", "birth_date")
    op.drop_column("registration_people", "birth_place")
    op.drop_column("registration_people", "registration_address")


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade is not supported for this migration because removed passport data cannot be restored."
    )
