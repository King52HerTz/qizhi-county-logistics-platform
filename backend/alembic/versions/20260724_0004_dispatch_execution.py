"""add dispatch approval and driver execution workflow

Revision ID: 20260724_0004
Revises: 20260724_0003
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260724_0004"
down_revision: str | None = "20260724_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("users_role_check", type_="check")
        batch.create_check_constraint(
            "users_role_check",
            "role in ('admin','dispatcher','driver','viewer')",
        )

    op.create_table(
        "dispatch_plans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("submitted_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('pending_approval','approved','rejected','dispatched','accepted','executing','completed')",
            name="dispatch_plans_status_check",
        ),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["optimization_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index("dispatch_plans_run_id_idx", "dispatch_plans", ["run_id"])
    op.create_index("dispatch_plans_submitted_by_idx", "dispatch_plans", ["submitted_by"])
    op.create_index("dispatch_plans_reviewed_by_idx", "dispatch_plans", ["reviewed_by"])
    op.create_index("dispatch_plans_status_updated_idx", "dispatch_plans", ["status", "updated_at"])
    op.create_index(
        "dispatch_plans_active_idx",
        "dispatch_plans",
        ["updated_at"],
        postgresql_where=sa.text("status in ('approved','dispatched','accepted','executing')"),
        sqlite_where=sa.text("status in ('approved','dispatched','accepted','executing')"),
    )

    op.create_table(
        "driver_assignments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("route_index", sa.Integer(), nullable=False),
        sa.Column("vehicle_id", sa.String(length=32), nullable=False),
        sa.Column("plate", sa.Text(), nullable=False),
        sa.Column("assigned_driver_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("route_payload", sa.JSON(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completion_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("route_index >= 0", name="driver_assignments_route_index_check"),
        sa.CheckConstraint(
            "status in ('pending','accepted','executing','completed')",
            name="driver_assignments_status_check",
        ),
        sa.ForeignKeyConstraint(["assigned_driver_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["plan_id"], ["dispatch_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "route_index", name="driver_assignments_plan_route_key"),
    )
    op.create_index("driver_assignments_plan_id_idx", "driver_assignments", ["plan_id"])
    op.create_index("driver_assignments_driver_id_idx", "driver_assignments", ["assigned_driver_id"])
    op.create_index(
        "driver_assignments_driver_status_idx",
        "driver_assignments",
        ["assigned_driver_id", "status"],
    )

    op.create_table(
        "dispatch_transitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=True),
        sa.Column("from_status", sa.String(length=24), nullable=True),
        sa.Column("to_status", sa.String(length=24), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assignment_id"], ["driver_assignments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["dispatch_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "dispatch_transitions_plan_created_idx",
        "dispatch_transitions",
        ["plan_id", "created_at"],
    )
    op.create_index(
        "dispatch_transitions_assignment_id_idx",
        "dispatch_transitions",
        ["assignment_id"],
    )
    op.create_index("dispatch_transitions_actor_id_idx", "dispatch_transitions", ["actor_id"])


def downgrade() -> None:
    op.drop_table("dispatch_transitions")
    op.drop_table("driver_assignments")
    op.drop_table("dispatch_plans")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("users_role_check", type_="check")
        batch.create_check_constraint(
            "users_role_check",
            "role in ('admin','dispatcher','viewer')",
        )
