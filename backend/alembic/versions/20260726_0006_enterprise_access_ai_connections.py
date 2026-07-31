"""enterprise access controls and managed AI connections

Revision ID: 20260726_0006
Revises: 20260724_0005
"""

from alembic import op
import sqlalchemy as sa


revision = "20260726_0006"
down_revision = "20260724_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("display_name", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("last_login_ip", sa.String(length=64), nullable=True))

    with op.batch_alter_table("ai_provider_configs") as batch:
        batch.add_column(
            sa.Column("name", sa.Text(), nullable=False, server_default="AI 服务连接")
        )
        batch.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch.add_column(sa.Column("updated_by", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "ai_provider_configs_updated_by_fkey",
            "users",
            ["updated_by"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ai_config_updated_by_idx", ["updated_by"])

    op.execute(
        """
        UPDATE ai_provider_configs
        SET enabled = false
        WHERE enabled = true
          AND id NOT IN (
            SELECT id FROM ai_provider_configs
            WHERE enabled = true
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
          )
        """
    )
    op.create_index(
        "ai_config_single_enabled_idx",
        "ai_provider_configs",
        ["enabled"],
        unique=True,
        postgresql_where=sa.text("enabled = true"),
        sqlite_where=sa.text("enabled = 1"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False, server_default="success"),
        sa.Column("resource_type", sa.String(length=48), nullable=True),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_username", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "outcome in ('success','failed','blocked')",
            name="audit_logs_outcome_check",
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("audit_logs_actor_created_idx", "audit_logs", ["actor_id", "created_at"])
    op.create_index(
        "audit_logs_category_created_idx", "audit_logs", ["category", "created_at"]
    )
    op.create_index(
        "audit_logs_resource_idx",
        "audit_logs",
        ["resource_type", "resource_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_index("ai_config_single_enabled_idx", table_name="ai_provider_configs")
    with op.batch_alter_table("ai_provider_configs") as batch:
        batch.drop_index("ai_config_updated_by_idx")
        batch.drop_constraint("ai_provider_configs_updated_by_fkey", type_="foreignkey")
        batch.drop_column("updated_by")
        batch.drop_column("description")
        batch.drop_column("name")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("last_login_ip")
        batch.drop_column("last_login_at")
        batch.drop_column("locked_until")
        batch.drop_column("failed_login_count")
        batch.drop_column("display_name")
