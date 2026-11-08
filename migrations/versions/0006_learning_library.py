"""Typed IELTS units, topic links, provenance and review history."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "learning_topics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), unique=True, nullable=False),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("learning_topics.id")),
    )
    op.create_table(
        "learning_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("source", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64), unique=True, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_learning_items_kind", "learning_items", ["kind"])
    op.create_table(
        "learning_item_topics",
        sa.Column("item_id", sa.String(36), sa.ForeignKey("learning_items.id"), primary_key=True),
        sa.Column("topic_id", sa.String(36), sa.ForeignKey("learning_topics.id"), primary_key=True),
    )
    columns = {
        "vocabulary_senses": [
            ("lemma", sa.String(2000)),
            ("part_of_speech", sa.String(20)),
            ("sense", sa.Text()),
            ("ipa_uk", sa.String(200)),
            ("definition", sa.Text()),
            ("examples", sa.JSON()),
        ],
        "grammar_patterns": [
            ("form", sa.Text()),
            ("function", sa.Text()),
            ("explanation", sa.Text()),
            ("examples", sa.JSON()),
        ],
        "learning_samples": [
            ("skill", sa.String(20)),
            ("prompt", sa.Text()),
            ("response", sa.Text()),
            ("annotations", sa.JSON()),
        ],
        "learning_exercises": [
            ("question", sa.Text()),
            ("options", sa.JSON()),
            ("answer", sa.Text()),
            ("explanation", sa.Text()),
        ],
    }
    for name, fields in columns.items():
        op.create_table(
            name,
            sa.Column(
                "item_id", sa.String(36), sa.ForeignKey("learning_items.id"), primary_key=True
            ),
            *[sa.Column(key, kind, nullable=False) for key, kind in fields],
        )
    op.create_index("ix_vocabulary_senses_lemma", "vocabulary_senses", ["lemma"])
    op.create_table(
        "learning_reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("learning_items.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("reviewer", sa.String(2000), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_learning_reviews_item_id", "learning_reviews", ["item_id"])

    op.create_table(
        "learning_revisions",
        sa.Column("item_id", sa.String(36), sa.ForeignKey("learning_items.id"), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    for name in (
        "learning_revisions",
        "learning_reviews",
        "learning_exercises",
        "learning_samples",
        "grammar_patterns",
        "vocabulary_senses",
        "learning_item_topics",
        "learning_items",
        "learning_topics",
    ):
        op.drop_table(name)
