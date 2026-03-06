"""make user mipt status nullable by default

Revision ID: 20260307_0006
Revises: 20260306_0005
Create Date: 2026-03-07 00:20:00

"""

from alembic import op
import sqlalchemy as sa


revision = "20260307_0006"
down_revision = "20260306_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "is_not_mipt", existing_type=sa.Boolean(), nullable=True)
    op.execute(
        """
        UPDATE users
        SET is_not_mipt = NULL
        WHERE is_not_mipt = FALSE
          AND group_name IS NULL
          AND passport_series IS NULL
          AND passport_number IS NULL
          AND passport_issue_date IS NULL
        """
    )


def downgrade() -> None:
    op.execute("UPDATE users SET is_not_mipt = FALSE WHERE is_not_mipt IS NULL")
    op.alter_column("users", "is_not_mipt", existing_type=sa.Boolean(), nullable=False)
