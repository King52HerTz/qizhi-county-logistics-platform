"""normalize master data operating hours

Revision ID: 20260726_0009
Revises: 20260726_0008
"""

from alembic import op


revision = "20260726_0009"
down_revision = "20260726_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE vehicles SET shift_start = shift_start + 420, shift_end = shift_end + 420 "
        "WHERE shift_start < 420 AND shift_end <= 600"
    )
    op.execute(
        "UPDATE orders SET window_start = window_start + 480, window_end = window_end + 480 "
        "WHERE window_end <= 600"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE orders SET window_start = window_start - 480, window_end = window_end - 480 "
        "WHERE window_start >= 480 AND window_end <= 1080"
    )
    op.execute(
        "UPDATE vehicles SET shift_start = shift_start - 420, shift_end = shift_end - 420 "
        "WHERE shift_start >= 420 AND shift_end <= 1020"
    )
