"""Immutable revisions, quality, learning and publishing records."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pipeline_revisions",
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column(
            "job_id",
            sa.String(length=36),
            sa.ForeignKey("jobs.id"),
            nullable=False,
            primary_key=False,
        ),
        sa.Column("parent_id", sa.String(length=36), nullable=True, primary_key=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False, primary_key=False),
        sa.Column("package", sa.JSON(), nullable=False, primary_key=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_index("ix_pipeline_revisions_job_id", "pipeline_revisions", ["job_id"])
    op.create_index("ix_pipeline_revisions_content_hash", "pipeline_revisions", ["content_hash"])
    op.create_table(
        "step_runs",
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column(
            "job_id",
            sa.String(length=36),
            sa.ForeignKey("jobs.id"),
            nullable=False,
            primary_key=False,
        ),
        sa.Column(
            "revision_id",
            sa.String(length=36),
            sa.ForeignKey("pipeline_revisions.id"),
            nullable=False,
            primary_key=False,
        ),
        sa.Column("step", sa.String(length=40), nullable=False, primary_key=False),
        sa.Column("state", sa.String(length=20), nullable=False, primary_key=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False, primary_key=False),
        sa.Column("output_hash", sa.String(length=64), nullable=True, primary_key=False),
        sa.Column("config", sa.JSON(), nullable=False, primary_key=False),
        sa.Column("output", sa.JSON(), nullable=False, primary_key=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True, primary_key=False),
    )
    op.create_index("ix_step_runs_revision_id", "step_runs", ["revision_id"])
    op.create_index("ix_step_runs_job_id", "step_runs", ["job_id"])
    op.create_table(
        "evaluations",
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("step_runs.id"),
            nullable=False,
            primary_key=False,
        ),
        sa.Column("evaluator", sa.String(length=100), nullable=False, primary_key=False),
        sa.Column("dimension", sa.String(length=80), nullable=False, primary_key=False),
        sa.Column("outcome", sa.String(length=20), nullable=False, primary_key=False),
        sa.Column("score", sa.Float(), nullable=True, primary_key=False),
        sa.Column("evidence", sa.JSON(), nullable=False, primary_key=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_index("ix_evaluations_run_id", "evaluations", ["run_id"])
    op.create_table(
        "review_feedback",
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column(
            "job_id",
            sa.String(length=36),
            sa.ForeignKey("jobs.id"),
            nullable=False,
            primary_key=False,
        ),
        sa.Column(
            "revision_id",
            sa.String(length=36),
            sa.ForeignKey("pipeline_revisions.id"),
            nullable=False,
            primary_key=False,
        ),
        sa.Column("scope", sa.String(length=20), nullable=False, primary_key=False),
        sa.Column("artifact_hash", sa.String(length=64), nullable=False, primary_key=False),
        sa.Column("decision", sa.String(length=20), nullable=False, primary_key=False),
        sa.Column("labels", sa.JSON(), nullable=False, primary_key=False),
        sa.Column("note", sa.Text(), nullable=False, primary_key=False),
        sa.Column("timecode", sa.Float(), nullable=True, primary_key=False),
        sa.Column("edit_diff", sa.Text(), nullable=True, primary_key=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_index("ix_review_feedback_job_id", "review_feedback", ["job_id"])
    op.create_table(
        "learning_configs",
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column("family", sa.String(length=30), nullable=False, primary_key=False),
        sa.Column("branch", sa.String(length=20), nullable=False, primary_key=False),
        sa.Column("state", sa.String(length=20), nullable=False, primary_key=False),
        sa.Column("config", sa.JSON(), nullable=False, primary_key=False),
        sa.Column("provenance", sa.JSON(), nullable=False, primary_key=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_index("ix_learning_configs_state", "learning_configs", ["state"])
    op.create_table(
        "experiments",
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column(
            "candidate_id",
            sa.String(length=36),
            sa.ForeignKey("learning_configs.id"),
            nullable=False,
            primary_key=False,
        ),
        sa.Column("baseline", sa.JSON(), nullable=False, primary_key=False),
        sa.Column("dataset", sa.JSON(), nullable=False, primary_key=False),
        sa.Column("report", sa.JSON(), nullable=False, primary_key=False),
        sa.Column("state", sa.String(length=20), nullable=False, primary_key=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_table(
        "publish_attempts",
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column(
            "job_id",
            sa.String(length=36),
            sa.ForeignKey("jobs.id"),
            nullable=False,
            primary_key=False,
        ),
        sa.Column("artifact_hash", sa.String(length=64), nullable=False, primary_key=False),
        sa.Column("state", sa.String(length=20), nullable=False, primary_key=False),
        sa.Column("platform_id", sa.String(length=100), nullable=True, primary_key=False),
        sa.Column("details", sa.JSON(), nullable=False, primary_key=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.UniqueConstraint("job_id", "artifact_hash", name="uq_publish_artifact"),
    )
    op.create_index("ix_publish_attempts_job_id", "publish_attempts", ["job_id"])
    op.create_table(
        "outcome_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column(
            "publish_id",
            sa.String(length=36),
            sa.ForeignKey("publish_attempts.id"),
            nullable=False,
            primary_key=False,
        ),
        sa.Column("metrics", sa.JSON(), nullable=False, primary_key=False),
        sa.Column("sampled_at", sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_index("ix_outcome_snapshots_publish_id", "outcome_snapshots", ["publish_id"])

    op.create_index(
        "uq_live_learning_config",
        "learning_configs",
        ["family", "branch"],
        unique=True,
        sqlite_where=sa.text("state IN ('active', 'canary')"),
        postgresql_where=sa.text("state IN ('active', 'canary')"),
    )


def downgrade():
    op.drop_table("outcome_snapshots")
    op.drop_table("publish_attempts")
    op.drop_table("experiments")
    op.drop_table("learning_configs")
    op.drop_table("review_feedback")
    op.drop_table("evaluations")
    op.drop_table("step_runs")
    op.drop_table("pipeline_revisions")
