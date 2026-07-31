"""data quality rules and staged imports

Revision ID: 20260726_0010
Revises: 20260726_0009
"""

from alembic import op
import sqlalchemy as sa


revision = "20260726_0010"
down_revision = "20260726_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_import_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_code", sa.String(length=32), nullable=False),
        sa.Column("import_type", sa.String(length=24), server_default="orders", nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="validated", nullable=False),
        sa.Column("total_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("valid_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("warning_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("payload", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("errors", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("committed_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("import_type in ('orders')", name="data_import_type_check"),
        sa.CheckConstraint(
            "status in ('validated','rejected','committed')",
            name="data_import_status_check",
        ),
        sa.CheckConstraint(
            "total_rows >= 0 and valid_rows >= 0 and error_rows >= 0 and warning_rows >= 0",
            name="data_import_counts_nonnegative",
        ),
        sa.ForeignKeyConstraint(["committed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_code"),
    )
    op.create_index("data_import_creator_id_idx", "data_import_batches", ["created_by"])
    op.create_index("data_import_committer_id_idx", "data_import_batches", ["committed_by"])
    op.create_index(
        "data_import_status_created_idx",
        "data_import_batches",
        ["status", "created_at"],
    )

    op.create_table(
        "data_quality_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rule_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(length=24), nullable=False),
        sa.Column("severity", sa.String(length=16), server_default="error", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("config", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "entity_type in ('order','vehicle','node','scenario')",
            name="data_quality_entity_check",
        ),
        sa.CheckConstraint(
            "severity in ('error','warning')",
            name="data_quality_severity_check",
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_code"),
    )
    op.create_index("data_quality_updated_by_idx", "data_quality_rules", ["updated_by"])
    op.create_index(
        "data_quality_enabled_entity_idx",
        "data_quality_rules",
        ["enabled", "entity_type"],
    )

    rules = sa.table(
        "data_quality_rules",
        sa.column("rule_code", sa.String()),
        sa.column("name", sa.Text()),
        sa.column("description", sa.Text()),
        sa.column("entity_type", sa.String()),
        sa.column("severity", sa.String()),
        sa.column("enabled", sa.Boolean()),
        sa.column("config", sa.JSON()),
    )
    op.bulk_insert(
        rules,
        [
            {
                "rule_code": "order_active_node",
                "name": "订单引用启用网点",
                "description": "待发布订单必须关联当前启用的服务网点",
                "entity_type": "order",
                "severity": "error",
                "enabled": True,
                "config": {},
            },
            {
                "rule_code": "order_time_window",
                "name": "服务时间窗有效",
                "description": "订单结束时间必须晚于开始时间且位于当天范围",
                "entity_type": "order",
                "severity": "error",
                "enabled": True,
                "config": {},
            },
            {
                "rule_code": "vehicle_capacity",
                "name": "可用运力覆盖",
                "description": "待调度订单总重量不应超过三轮可用运力",
                "entity_type": "scenario",
                "severity": "warning",
                "enabled": True,
                "config": {"rounds": 3},
            },
            {
                "rule_code": "cold_chain_vehicle",
                "name": "冷链订单有冷链车辆",
                "description": "存在冷链订单时至少需要一台可用冷链车辆",
                "entity_type": "scenario",
                "severity": "error",
                "enabled": True,
                "config": {},
            },
            {
                "rule_code": "single_depot",
                "name": "唯一共配中心",
                "description": "发布场景必须且只能包含一个启用的共配中心",
                "entity_type": "node",
                "severity": "error",
                "enabled": True,
                "config": {},
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("data_quality_enabled_entity_idx", table_name="data_quality_rules")
    op.drop_index("data_quality_updated_by_idx", table_name="data_quality_rules")
    op.drop_table("data_quality_rules")
    op.drop_index("data_import_status_created_idx", table_name="data_import_batches")
    op.drop_index("data_import_committer_id_idx", table_name="data_import_batches")
    op.drop_index("data_import_creator_id_idx", table_name="data_import_batches")
    op.drop_table("data_import_batches")
