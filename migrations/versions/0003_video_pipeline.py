"""Video production and final review artifacts."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jobs", sa.Column("render_config", sa.JSON(), nullable=True))
    op.add_column("jobs", sa.Column("video", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("jobs", "video")
    op.drop_column("jobs", "render_config")
