"""node spatial governance and coordinate revisions

Revision ID: 20260729_0013
Revises: 20260728_0012
"""

from alembic import op
import sqlalchemy as sa


revision = "20260729_0013"
down_revision = "20260728_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("logistics_nodes") as batch:
        batch.add_column(sa.Column("wgs84_longitude", sa.Numeric(10, 6), nullable=True))
        batch.add_column(sa.Column("wgs84_latitude", sa.Numeric(10, 6), nullable=True))
        batch.add_column(
            sa.Column(
                "coordinate_system",
                sa.String(16),
                server_default="gcj02",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column(
                "coordinate_source",
                sa.String(24),
                server_default="seed",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column(
                "coordinate_status",
                sa.String(20),
                server_default="unverified",
                nullable=False,
            )
        )
        batch.add_column(sa.Column("coordinate_accuracy_m", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("calibrated_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("calibrated_by", sa.Integer(), nullable=True))
        batch.create_check_constraint(
            "nodes_coordinate_system_check", "coordinate_system in ('gcj02')"
        )
        batch.create_check_constraint(
            "nodes_coordinate_source_check",
            "coordinate_source in ('seed','imported','geocoded','manual')",
        )
        batch.create_check_constraint(
            "nodes_coordinate_status_check",
            "coordinate_status in ('unverified','verified','needs_review')",
        )
        batch.create_check_constraint(
            "nodes_coordinate_accuracy_check",
            "coordinate_accuracy_m is null or coordinate_accuracy_m >= 0",
        )
        batch.create_foreign_key(
            "nodes_calibrated_by_fkey",
            "users",
            ["calibrated_by"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(
            "nodes_coordinate_status_idx", ["coordinate_status", "updated_at"]
        )
        batch.create_index("nodes_calibrated_by_idx", ["calibrated_by"])

    op.create_table(
        "node_coordinate_revisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("node_id", sa.String(32), nullable=False),
        sa.Column("before_longitude", sa.Numeric(10, 6), nullable=True),
        sa.Column("before_latitude", sa.Numeric(10, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(10, 6), nullable=False),
        sa.Column("latitude", sa.Numeric(10, 6), nullable=False),
        sa.Column("wgs84_longitude", sa.Numeric(10, 6), nullable=False),
        sa.Column("wgs84_latitude", sa.Numeric(10, 6), nullable=False),
        sa.Column("coordinate_source", sa.String(24), nullable=False),
        sa.Column("coordinate_status", sa.String(20), nullable=False),
        sa.Column("coordinate_accuracy_m", sa.Integer(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_username", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "coordinate_source in ('seed','imported','geocoded','manual')",
            name="node_coordinate_revisions_source_check",
        ),
        sa.CheckConstraint(
            "coordinate_status in ('unverified','verified','needs_review')",
            name="node_coordinate_revisions_status_check",
        ),
        sa.CheckConstraint(
            "coordinate_accuracy_m is null or coordinate_accuracy_m >= 0",
            name="node_coordinate_revisions_accuracy_check",
        ),
        sa.ForeignKeyConstraint(
            ["node_id"], ["logistics_nodes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "node_coordinate_revisions_node_created_idx",
        "node_coordinate_revisions",
        ["node_id", "created_at"],
    )
    op.create_index(
        "node_coordinate_revisions_actor_idx",
        "node_coordinate_revisions",
        ["actor_id"],
    )

    # Existing records remain visible in AMap as GCJ-02 but require explicit review.
    # WGS-84 values are populated by the application on the first calibration.


def downgrade() -> None:
    op.drop_index(
        "node_coordinate_revisions_actor_idx",
        table_name="node_coordinate_revisions",
    )
    op.drop_index(
        "node_coordinate_revisions_node_created_idx",
        table_name="node_coordinate_revisions",
    )
    op.drop_table("node_coordinate_revisions")
    with op.batch_alter_table("logistics_nodes") as batch:
        batch.drop_index("nodes_calibrated_by_idx")
        batch.drop_index("nodes_coordinate_status_idx")
        batch.drop_constraint("nodes_calibrated_by_fkey", type_="foreignkey")
        batch.drop_constraint("nodes_coordinate_accuracy_check", type_="check")
        batch.drop_constraint("nodes_coordinate_status_check", type_="check")
        batch.drop_constraint("nodes_coordinate_source_check", type_="check")
        batch.drop_constraint("nodes_coordinate_system_check", type_="check")
        batch.drop_column("calibrated_by")
        batch.drop_column("calibrated_at")
        batch.drop_column("coordinate_accuracy_m")
        batch.drop_column("coordinate_status")
        batch.drop_column("coordinate_source")
        batch.drop_column("coordinate_system")
        batch.drop_column("wgs84_latitude")
        batch.drop_column("wgs84_longitude")
