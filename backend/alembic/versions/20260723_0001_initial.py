"""Initial logistics persistence schema."""

from alembic import op
import sqlalchemy as sa


revision = "20260723_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(24), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role in ('admin','dispatcher','viewer')", name="users_role_check"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "logistics_nodes",
        sa.Column("id", sa.String(32), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("longitude", sa.Numeric(10, 6), nullable=False),
        sa.Column("latitude", sa.Numeric(10, 6), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind in ('depot','town','village','processor')", name="nodes_kind_check"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("nodes_kind_idx", "logistics_nodes", ["kind"])
    op.create_table(
        "vehicles",
        sa.Column("id", sa.String(32), nullable=False),
        sa.Column("plate", sa.Text(), nullable=False),
        sa.Column("capacity_kg", sa.Integer(), nullable=False),
        sa.Column("cold_chain", sa.Boolean(), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("cost_per_km", sa.Numeric(8, 2), nullable=False),
        sa.Column("shift_start", sa.Integer(), nullable=False),
        sa.Column("shift_end", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("capacity_kg > 0", name="vehicles_capacity_positive"),
        sa.CheckConstraint("shift_end > shift_start", name="vehicles_shift_check"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plate"),
    )
    op.create_index("vehicles_available_cold_idx", "vehicles", ["available", "cold_chain"])
    op.create_table(
        "orders",
        sa.Column("id", sa.String(32), nullable=False),
        sa.Column("node_id", sa.String(32), nullable=False),
        sa.Column("weight_kg", sa.Integer(), nullable=False),
        sa.Column("window_start", sa.Integer(), nullable=False),
        sa.Column("window_end", sa.Integer(), nullable=False),
        sa.Column("service_minutes", sa.Integer(), nullable=False),
        sa.Column("cold_chain", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.String(16), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("priority in ('normal','urgent')", name="orders_priority_check"),
        sa.CheckConstraint("status in ('pending','planned','completed','cancelled')", name="orders_status_check"),
        sa.CheckConstraint("weight_kg > 0", name="orders_weight_positive"),
        sa.CheckConstraint("window_end > window_start", name="orders_window_check"),
        sa.ForeignKeyConstraint(["node_id"], ["logistics_nodes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("orders_node_id_idx", "orders", ["node_id"])
    op.create_index("orders_status_created_idx", "orders", ["status", "created_at"])
    op.create_index(
        "orders_pending_time_idx",
        "orders",
        ["window_start"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_table(
        "optimization_runs",
        sa.Column("id", sa.String(32), nullable=False),
        sa.Column("scenario_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("solver", sa.String(40), nullable=False),
        sa.Column("solve_time_ms", sa.Integer(), nullable=False),
        sa.Column("distance_km", sa.Numeric(10, 1), nullable=False),
        sa.Column("estimated_cost_cny", sa.Numeric(12, 2), nullable=False),
        sa.Column("vehicles_used", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=True),
        sa.Column("event_vehicle_id", sa.String(32), nullable=True),
        sa.Column("output", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status in ('optimal','feasible','infeasible')", name="runs_status_check"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("runs_creator_id_idx", "optimization_runs", ["created_by"])
    op.create_index("runs_scenario_created_idx", "optimization_runs", ["scenario_id", "created_at"])
    op.create_index("runs_status_created_idx", "optimization_runs", ["status", "created_at"])
    op.create_index("runs_created_id_idx", "optimization_runs", ["created_at", "id"])
    op.create_table(
        "dispatch_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("vehicle_id", sa.String(32), nullable=True),
        sa.Column("occurred_at_minute", sa.Integer(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("optimization_run_id", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["optimization_run_id"], ["optimization_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("events_run_id_idx", "dispatch_events", ["optimization_run_id"])
    op.create_index("events_type_created_idx", "dispatch_events", ["event_type", "created_at"])


def downgrade() -> None:
    op.drop_table("dispatch_events")
    op.drop_table("optimization_runs")
    op.drop_table("orders")
    op.drop_table("vehicles")
    op.drop_table("logistics_nodes")
    op.drop_table("users")
