"""Add encrypted AI provider configuration."""

from alembic import op
import sqlalchemy as sa


revision = "20260724_0002"
down_revision = "20260723_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_provider_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(48), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("temperature", sa.Numeric(3, 2), nullable=False),
        sa.Column("last_test_status", sa.String(20), nullable=False),
        sa.Column("last_test_message", sa.Text(), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "last_test_status in ('untested','success','failed')",
            name="ai_config_test_status_check",
        ),
        sa.CheckConstraint(
            "temperature >= 0 and temperature <= 2",
            name="ai_config_temperature_check",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ai_config_creator_id_idx", "ai_provider_configs", ["created_by"])
    op.create_index(
        "ai_config_enabled_idx",
        "ai_provider_configs",
        ["updated_at"],
        postgresql_where=sa.text("enabled is true"),
    )


def downgrade() -> None:
    op.drop_table("ai_provider_configs")
