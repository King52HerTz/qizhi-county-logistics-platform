"""create cold chain storage and temperature monitoring tables

Revision ID: 20260928_0016
Revises: 20260901_0015
"""

from alembic import op
import sqlalchemy as sa


revision = "20260928_0016"
down_revision = "20260901_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cold_stores",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("store_type", sa.String(24), nullable=False, server_default="county_hub"),
        sa.Column("node_id", sa.String(32), sa.ForeignKey("logistics_nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("temperature_zone", sa.String(16), nullable=False, server_default="chilled"),
        sa.Column("capacity_tons", sa.Integer(), nullable=False),
        sa.Column("shared", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("contact", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("capacity_tons > 0", name="cold_stores_capacity_positive"),
        sa.CheckConstraint(
            "store_type in ('county_hub','township','field_precool')",
            name="cold_stores_type_check",
        ),
        sa.CheckConstraint(
            "temperature_zone in ('chilled','frozen','ambient')",
            name="cold_stores_zone_check",
        ),
        sa.CheckConstraint(
            "status in ('active','maintenance','closed')",
            name="cold_stores_status_check",
        ),
    )
    op.create_index("cold_stores_node_id_idx", "cold_stores", ["node_id"])
    op.create_index("cold_stores_status_idx", "cold_stores", ["status", "shared"])

    op.create_table(
        "cold_store_bookings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cold_store_id", sa.String(32), sa.ForeignKey("cold_stores.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("order_id", sa.String(32), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("booking_date", sa.String(10), nullable=False),
        sa.Column("purpose", sa.String(24), nullable=False, server_default="precool"),
        sa.Column("tons", sa.Numeric(8, 2), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="reserved"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("tons > 0", name="cold_store_bookings_tons_positive"),
        sa.CheckConstraint(
            "purpose in ('precool','short_storage','transit')",
            name="cold_store_bookings_purpose_check",
        ),
        sa.CheckConstraint(
            "status in ('reserved','active','completed','cancelled')",
            name="cold_store_bookings_status_check",
        ),
    )
    op.create_index("cold_store_bookings_store_date_idx", "cold_store_bookings", ["cold_store_id", "booking_date"])
    op.create_index("cold_store_bookings_status_idx", "cold_store_bookings", ["status"])

    op.create_table(
        "temperature_sensors",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("sensor_type", sa.String(16), nullable=False, server_default="vehicle"),
        sa.Column("vehicle_id", sa.String(32), sa.ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("cold_store_id", sa.String(32), sa.ForeignKey("cold_stores.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_low_c", sa.Numeric(4, 1), nullable=False, server_default="0.0"),
        sa.Column("target_high_c", sa.Numeric(4, 1), nullable=False, server_default="4.0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "sensor_type in ('vehicle','storage')",
            name="temperature_sensors_type_check",
        ),
        sa.CheckConstraint("target_high_c > target_low_c", name="temperature_sensors_range_check"),
        sa.CheckConstraint(
            "status in ('active','inactive')",
            name="temperature_sensors_status_check",
        ),
    )
    op.create_index("temperature_sensors_vehicle_idx", "temperature_sensors", ["vehicle_id"])
    op.create_index("temperature_sensors_store_idx", "temperature_sensors", ["cold_store_id"])

    op.create_table(
        "temperature_readings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("sensor_id", sa.String(32), sa.ForeignKey("temperature_sensors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("temperature_c", sa.Numeric(5, 2), nullable=False),
        sa.Column("humidity_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("context", sa.String(24), nullable=False, server_default="in_transit"),
        sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("driver_assignments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "context in ('outbound','in_transit','inbound','storage')",
            name="temperature_readings_context_check",
        ),
    )
    op.create_index("temperature_readings_sensor_time_idx", "temperature_readings", ["sensor_id", "recorded_at"])

    op.create_table(
        "temperature_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("sensor_id", sa.String(32), sa.ForeignKey("temperature_sensors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reading_id", sa.Integer(), sa.ForeignKey("temperature_readings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("level", sa.String(16), nullable=False, server_default="warning"),
        sa.Column("alert_type", sa.String(24), nullable=False, server_default="threshold_breach"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("measured_c", sa.Numeric(5, 2), nullable=True),
        sa.Column("threshold_c", sa.Numeric(5, 2), nullable=True),
        sa.Column("deviation_c", sa.Numeric(5, 2), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("acknowledged_by", sa.String(64), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "level in ('info','warning','critical')",
            name="temperature_alerts_level_check",
        ),
        sa.CheckConstraint(
            "alert_type in ('threshold_breach','anomaly_trend')",
            name="temperature_alerts_type_check",
        ),
        sa.CheckConstraint(
            "status in ('open','acknowledged','resolved')",
            name="temperature_alerts_status_check",
        ),
    )
    op.create_index("temperature_alerts_status_created_idx", "temperature_alerts", ["status", "created_at"])
    op.create_index("temperature_alerts_sensor_created_idx", "temperature_alerts", ["sensor_id", "created_at"])


def downgrade() -> None:
    op.drop_table("temperature_alerts")
    op.drop_table("temperature_readings")
    op.drop_table("temperature_sensors")
    op.drop_table("cold_store_bookings")
    op.drop_table("cold_stores")
