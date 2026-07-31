"""map provider configuration and product wording

Revision ID: 20260728_0012
Revises: 20260728_0011
"""

from alembic import op
import sqlalchemy as sa


revision = "20260728_0012"
down_revision = "20260728_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "map_provider_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("encrypted_web_key", sa.Text(), nullable=False),
        sa.Column("encrypted_security_code", sa.Text(), nullable=False),
        sa.Column("map_style", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_test_status", sa.String(length=20), nullable=False),
        sa.Column("last_test_message", sa.Text(), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("provider in ('amap')", name="map_config_provider_check"),
        sa.CheckConstraint(
            "map_style in ('normal','whitesmoke','fresh','light')",
            name="map_config_style_check",
        ),
        sa.CheckConstraint(
            "last_test_status in ('untested','success','failed')",
            name="map_config_test_status_check",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("map_config_creator_id_idx", "map_provider_configs", ["created_by"])
    op.create_index("map_config_updated_by_idx", "map_provider_configs", ["updated_by"])
    op.create_index(
        "map_config_single_enabled_idx",
        "map_provider_configs",
        ["enabled"],
        unique=True,
        postgresql_where=sa.text("enabled IS TRUE"),
        sqlite_where=sa.text("enabled IS 1"),
    )
    op.execute(
        sa.text(
            "UPDATE scenario_versions SET name = "
            "REPLACE(REPLACE(name, '演示场景', '基础场景'), '竞赛', '运营') "
            "WHERE name LIKE '%演示%' OR name LIKE '%竞赛%'"
        )
    )


def downgrade() -> None:
    op.drop_index("map_config_single_enabled_idx", table_name="map_provider_configs")
    op.drop_index("map_config_updated_by_idx", table_name="map_provider_configs")
    op.drop_index("map_config_creator_id_idx", table_name="map_provider_configs")
    op.drop_table("map_provider_configs")
