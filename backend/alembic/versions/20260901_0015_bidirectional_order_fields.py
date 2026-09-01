"""add directional flow fields to order records

Revision ID: 20260901_0015
Revises: 20260830_0014
"""

from alembic import op
import sqlalchemy as sa


revision = "20260901_0015"
down_revision = "20260830_0014"
branch_labels = None
depends_on = None


def _add_flow_fields(table_name: str, prefix: str) -> None:
    with op.batch_alter_table(table_name) as batch:
        batch.add_column(
            sa.Column(
                "flow_direction",
                sa.String(16),
                nullable=False,
                server_default="downward",
            )
        )
        batch.add_column(
            sa.Column(
                "cargo_category",
                sa.String(20),
                nullable=False,
                server_default="agricultural",
            )
        )
        batch.add_column(sa.Column("origin_node_id", sa.String(32), nullable=True))
        batch.add_column(sa.Column("destination_node_id", sa.String(32), nullable=True))
        batch.create_check_constraint(
            f"{prefix}_flow_direction_check",
            "flow_direction in ('upward','downward')",
        )
        batch.create_check_constraint(
            f"{prefix}_cargo_category_check",
            "cargo_category in ('agricultural','industrial')",
        )


def upgrade() -> None:
    _add_flow_fields("orders", "orders")
    _add_flow_fields("order_requests", "order_requests")


def downgrade() -> None:
    with op.batch_alter_table("order_requests") as batch:
        batch.drop_constraint("order_requests_cargo_category_check", type_="check")
        batch.drop_constraint("order_requests_flow_direction_check", type_="check")
        batch.drop_column("destination_node_id")
        batch.drop_column("origin_node_id")
        batch.drop_column("cargo_category")
        batch.drop_column("flow_direction")
    with op.batch_alter_table("orders") as batch:
        batch.drop_constraint("orders_cargo_category_check", type_="check")
        batch.drop_constraint("orders_flow_direction_check", type_="check")
        batch.drop_column("destination_node_id")
        batch.drop_column("origin_node_id")
        batch.drop_column("cargo_category")
        batch.drop_column("flow_direction")
