"""master data center

Revision ID: 20260726_0008
Revises: 20260726_0007
"""

from alembic import op
import sqlalchemy as sa


revision = "20260726_0008"
down_revision = "20260726_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("logistics_nodes") as batch:
        batch.add_column(sa.Column("address", sa.Text(), nullable=True))
        batch.add_column(sa.Column("contact_name", sa.Text(), nullable=True))
        batch.add_column(sa.Column("contact_phone", sa.String(length=32), nullable=True))
        batch.add_column(
            sa.Column(
                "service_radius_km",
                sa.Numeric(precision=6, scale=2),
                nullable=False,
                server_default="15.00",
            )
        )
        batch.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
        )
        batch.create_check_constraint(
            "nodes_service_radius_positive",
            "service_radius_km > 0",
        )
        batch.drop_index("nodes_kind_idx")
        batch.create_index("nodes_active_kind_idx", ["is_active", "kind"])

    with op.batch_alter_table("vehicles") as batch:
        batch.add_column(
            sa.Column("vehicle_type", sa.String(length=24), nullable=False, server_default="van")
        )
        batch.add_column(sa.Column("driver_name", sa.Text(), nullable=True))
        batch.add_column(sa.Column("driver_phone", sa.String(length=32), nullable=True))
        batch.add_column(
            sa.Column("status", sa.String(length=20), nullable=False, server_default="available")
        )
        batch.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
        )
        batch.create_check_constraint(
            "vehicles_type_check",
            "vehicle_type in ('van','truck','refrigerated')",
        )
        batch.create_check_constraint(
            "vehicles_status_check",
            "status in ('available','assigned','maintenance','offline')",
        )
        batch.drop_index("vehicles_available_cold_idx")
        batch.create_index("vehicles_status_cold_idx", ["status", "cold_chain"])

    with op.batch_alter_table("orders") as batch:
        batch.add_column(
            sa.Column("cargo_name", sa.Text(), nullable=False, server_default="农产品")
        )
        batch.add_column(
            sa.Column("customer_name", sa.Text(), nullable=False, server_default="未登记客户")
        )
        batch.add_column(sa.Column("customer_phone", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("delivery_address", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
        )
        batch.create_index(
            "orders_priority_cold_updated_idx",
            ["priority", "cold_chain", "updated_at"],
        )

    op.execute("UPDATE vehicles SET vehicle_type = 'refrigerated' WHERE cold_chain = true")
    op.execute("UPDATE vehicles SET status = 'offline' WHERE available = false")
    op.execute("UPDATE orders SET cargo_name = '黄花菜', customer_name = '祁东县农产品客户'")


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.drop_index("orders_priority_cold_updated_idx")
        batch.drop_column("updated_at")
        batch.drop_column("delivery_address")
        batch.drop_column("customer_phone")
        batch.drop_column("customer_name")
        batch.drop_column("cargo_name")

    with op.batch_alter_table("vehicles") as batch:
        batch.drop_index("vehicles_status_cold_idx")
        batch.create_index("vehicles_available_cold_idx", ["available", "cold_chain"])
        batch.drop_constraint("vehicles_status_check", type_="check")
        batch.drop_constraint("vehicles_type_check", type_="check")
        batch.drop_column("updated_at")
        batch.drop_column("status")
        batch.drop_column("driver_phone")
        batch.drop_column("driver_name")
        batch.drop_column("vehicle_type")

    with op.batch_alter_table("logistics_nodes") as batch:
        batch.drop_index("nodes_active_kind_idx")
        batch.create_index("nodes_kind_idx", ["kind"])
        batch.drop_constraint("nodes_service_radius_positive", type_="check")
        batch.drop_column("updated_at")
        batch.drop_column("is_active")
        batch.drop_column("service_radius_km")
        batch.drop_column("contact_phone")
        batch.drop_column("contact_name")
        batch.drop_column("address")
