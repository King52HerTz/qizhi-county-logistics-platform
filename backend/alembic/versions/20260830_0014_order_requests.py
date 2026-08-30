"""customer order requests and public user role

Revision ID: 20260830_0014
Revises: 20260729_0013
"""

from alembic import op
import sqlalchemy as sa


revision = "20260830_0014"
down_revision = "20260729_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("users_role_check", type_="check")
        batch.create_check_constraint(
            "users_role_check",
            "role in ('admin','dispatcher','driver','viewer','user')",
        )

    op.create_table(
        "order_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("request_code", sa.String(32), nullable=False),
        sa.Column("requester_id", sa.Integer(), nullable=False),
        sa.Column("node_id", sa.String(32), nullable=False),
        sa.Column("cargo_name", sa.Text(), nullable=False),
        sa.Column("customer_name", sa.Text(), nullable=False),
        sa.Column("customer_phone", sa.String(32), nullable=True),
        sa.Column("delivery_address", sa.Text(), nullable=True),
        sa.Column("weight_kg", sa.Integer(), nullable=False),
        sa.Column("window_start", sa.Integer(), nullable=False),
        sa.Column("window_end", sa.Integer(), nullable=False),
        sa.Column("service_minutes", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("cold_chain", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("priority", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending_review"),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("operational_order_id", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("weight_kg > 0", name="order_requests_weight_positive"),
        sa.CheckConstraint("window_end > window_start", name="order_requests_window_check"),
        sa.CheckConstraint("service_minutes >= 0", name="order_requests_service_nonnegative"),
        sa.CheckConstraint(
            "priority in ('normal','urgent')",
            name="order_requests_priority_check",
        ),
        sa.CheckConstraint(
            "status in ('pending_review','needs_info','rejected','converted','cancelled')",
            name="order_requests_status_check",
        ),
        sa.ForeignKeyConstraint(
            ["requester_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["node_id"], ["logistics_nodes.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["operational_order_id"], ["orders.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_code"),
    )
    op.create_index(
        "order_requests_requester_created_idx",
        "order_requests",
        ["requester_id", "created_at"],
    )
    op.create_index(
        "order_requests_status_created_idx",
        "order_requests",
        ["status", "created_at"],
    )
    op.create_index("order_requests_node_id_idx", "order_requests", ["node_id"])
    op.create_index(
        "order_requests_operational_order_idx",
        "order_requests",
        ["operational_order_id"],
    )


def downgrade() -> None:
    op.drop_index("order_requests_operational_order_idx", table_name="order_requests")
    op.drop_index("order_requests_node_id_idx", table_name="order_requests")
    op.drop_index("order_requests_status_created_idx", table_name="order_requests")
    op.drop_index("order_requests_requester_created_idx", table_name="order_requests")
    op.drop_table("order_requests")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("users_role_check", type_="check")
        batch.create_check_constraint(
            "users_role_check",
            "role in ('admin','dispatcher','driver','viewer')",
        )
