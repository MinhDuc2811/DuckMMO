"""Executable checks for the prepared schema, not production IELTS persistence."""

import sqlite3

import pytest

from test_suite.support.paths import PROJECT_ROOT


@pytest.fixture
def knowledge(tmp_path):
    with sqlite3.connect(tmp_path / "knowledge.sqlite") as connection:
        folder = PROJECT_ROOT / "docs" / "ielts-shorts"
        connection.executescript((folder / "schema.sql").read_text())
        connection.executescript((folder / "seed.sql").read_text())
        yield connection


def test_topic_senses_samples_and_single_focus_are_linked(knowledge):
    assert knowledge.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert not knowledge.execute("PRAGMA foreign_key_check").fetchall()
    meanings = knowledge.execute(
        "SELECT id FROM lexical_senses WHERE entry_id='entry-address' ORDER BY sense_number"
    ).fetchall()
    assert meanings == [("sense-address-location",), ("sense-address-handle",)]
    topics = knowledge.execute(
        "SELECT topic_id FROM sense_topics WHERE sense_id='sense-flexible' ORDER BY topic_id"
    ).fetchall()
    assert topics == [("online-learning",), ("remote-work",)]
    assert knowledge.execute(
        "SELECT sense_id FROM sample_annotations WHERE id='annotation-vocab'"
    ).fetchone() == ("sense-self-paced",)
    assert knowledge.execute("SELECT count(*) FROM short_briefs").fetchone() == (6,)


@pytest.mark.parametrize(
    "invalid_change",
    [
        "UPDATE short_briefs SET focus_pattern_id='pattern-although' WHERE id='short-vocab'",
        "UPDATE short_briefs SET focus_sense_id=NULL WHERE id='short-vocab'",
        "UPDATE short_briefs SET focus_sense_id='missing' WHERE id='short-vocab'",
        "UPDATE sample_annotations SET pattern_id='pattern-although' WHERE id='annotation-vocab'",
        "UPDATE exercises SET pattern_id='pattern-although' WHERE id='exercise-access'",
        "UPDATE exercises SET answer_key_json='not-json' WHERE id='exercise-access'",
        "INSERT INTO lexical_entries VALUES ('duplicate','flexible','flexible','word','en')",
        "INSERT INTO sense_topics VALUES ('sense-self-paced','online-learning')",
        "UPDATE prompts SET module='both' WHERE id='prompt-writing'",
        "UPDATE topics SET parent_id=id WHERE id='education'",
        "UPDATE script_scenes SET pause_after_seconds=-1 WHERE id='scene-1'",
        "UPDATE script_scenes SET position=1 WHERE id='scene-2'",
        "DELETE FROM lexical_senses WHERE id='sense-self-paced'",
    ],
    ids=[
        "two-focuses",
        "no-focus",
        "dangling-focus",
        "ambiguous-annotation",
        "two-targets",
        "invalid-json",
        "duplicate-entry",
        "duplicate-topic",
        "wrong-module",
        "self-parent",
        "negative-pause",
        "duplicate-scene",
        "delete-used-sense",
    ],
)
def test_invalid_knowledge_is_rejected(knowledge, invalid_change):
    with pytest.raises(sqlite3.IntegrityError):
        knowledge.execute(invalid_change)


def test_seed_cannot_be_mistaken_for_approved_content(knowledge):
    for table in (
        "lexical_senses",
        "vocabulary_examples",
        "patterns",
        "pattern_examples",
        "prompts",
        "sample_versions",
        "exercises",
        "short_briefs",
        "script_revisions",
    ):
        assert knowledge.execute(
            f"SELECT count(*) FROM {table} WHERE review_status <> 'draft'"
        ).fetchone() == (0,)
    assert knowledge.execute(
        "SELECT rights_status FROM source_items WHERE id='origin-demo'"
    ).fetchone() == ("original_pending_review",)
    assert knowledge.execute(
        "SELECT snapshot_sha256 FROM script_revisions WHERE id='script-vocab-v1'"
    ).fetchone() == (None,)
