"""Durable finite automation plans and scheduled video runs."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "automation_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("channel_id", sa.String(100), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "automation_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("plan_id", sa.String(36), sa.ForeignKey("automation_plans.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("publish_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id")),
        sa.Column("publish_id", sa.String(36), sa.ForeignKey("publish_attempts.id")),
        sa.Column("error", sa.Text()),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("retry_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("plan_id", "position", name="uq_automation_slot"),
    )
    for field in ("plan_id", "state", "publish_at"):
        op.create_index("ix_automation_runs_" + field, "automation_runs", [field])


def downgrade():
    op.drop_table("automation_runs")
    op.drop_table("automation_plans")
