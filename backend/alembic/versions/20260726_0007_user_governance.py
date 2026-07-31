"""user governance metadata

Revision ID: 20260726_0007
Revises: 20260726_0006
"""

from alembic import op
import sqlalchemy as sa


revision = "20260726_0007"
down_revision = "20260726_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
        )
        batch.create_index("users_role_active_idx", ["role", "is_active"])


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_index("users_role_active_idx")
        batch.drop_column("updated_at")
        batch.drop_column("password_changed_at")
