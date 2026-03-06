"""add profile mipt/passport fields to users

Revision ID: 20260306_0005
Revises: 20260306_0004
Create Date: 2026-03-06 23:55:00

"""

from alembic import op
import sqlalchemy as sa


revision = "20260306_0005"
down_revision = "20260306_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_not_mipt", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("passport_series", sa.String(length=16), nullable=True))
    op.add_column("users", sa.Column("passport_number", sa.String(length=16), nullable=True))
    op.add_column("users", sa.Column("passport_issue_date", sa.Date(), nullable=True))
    op.alter_column("users", "is_not_mipt", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "passport_issue_date")
    op.drop_column("users", "passport_number")
    op.drop_column("users", "passport_series")
    op.drop_column("users", "is_not_mipt")
