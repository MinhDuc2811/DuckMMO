-- Design prototype v1; SQLite only. NOT an Alembic migration.
-- Run against a new, disposable database with foreign keys enabled.
PRAGMA foreign_keys = ON;

CREATE TABLE sources (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('book','website','original')),
    publisher TEXT,
    edition TEXT,
    url TEXT,
    verification_status TEXT NOT NULL DEFAULT 'unverified'
        CHECK (verification_status IN ('unverified','verified'))
);
CREATE TABLE source_items (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    locator TEXT NOT NULL,
    rights_status TEXT NOT NULL DEFAULT 'unknown'
        CHECK (rights_status IN ('unknown','reference_only','permission_granted','original_pending_review')),
    rights_note TEXT NOT NULL,
    UNIQUE (source_id, locator)
);

CREATE TABLE topics (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name_en TEXT NOT NULL,
    name_vi TEXT NOT NULL,
    parent_id TEXT REFERENCES topics(id) ON DELETE RESTRICT,
    CHECK (parent_id IS NULL OR parent_id <> id)
);
-- Longer parent cycles must be rejected by the taxonomy application service.
CREATE TABLE labels (
    id TEXT PRIMARY KEY,
    dimension TEXT NOT NULL CHECK (dimension IN (
        'skill','question_type','function','criterion','register','cefr','pedagogical_task_type'
    )),
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    UNIQUE (dimension, code)
);

CREATE TABLE lexical_entries (
    id TEXT PRIMARY KEY,
    headword TEXT NOT NULL,
    normalized_key TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('word','phrase','phrasal_verb','idiom','collocation')),
    language TEXT NOT NULL DEFAULT 'en' CHECK (language = 'en'),
    UNIQUE (language, normalized_key, kind)
);
CREATE TABLE lexical_senses (
    id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL REFERENCES lexical_entries(id) ON DELETE RESTRICT,
    sense_number INTEGER NOT NULL CHECK (sense_number > 0),
    part_of_speech TEXT NOT NULL,
    definition_en TEXT NOT NULL CHECK (length(trim(definition_en)) > 0),
    meaning_vi TEXT NOT NULL,
    usage_note TEXT NOT NULL DEFAULT '',
    source_item_id TEXT NOT NULL REFERENCES source_items(id) ON DELETE RESTRICT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','in_review','approved','rejected')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    UNIQUE (entry_id, sense_number)
);
CREATE TABLE sense_topics (
    sense_id TEXT NOT NULL REFERENCES lexical_senses(id) ON DELETE RESTRICT,
    topic_id TEXT NOT NULL REFERENCES topics(id) ON DELETE RESTRICT,
    PRIMARY KEY (sense_id, topic_id)
);
CREATE TABLE sense_labels (
    sense_id TEXT NOT NULL REFERENCES lexical_senses(id) ON DELETE RESTRICT,
    label_id TEXT NOT NULL REFERENCES labels(id) ON DELETE RESTRICT,
    PRIMARY KEY (sense_id, label_id)
);
CREATE TABLE lexical_relations (
    from_sense_id TEXT NOT NULL REFERENCES lexical_senses(id) ON DELETE RESTRICT,
    to_sense_id TEXT NOT NULL REFERENCES lexical_senses(id) ON DELETE RESTRICT,
    relation_type TEXT NOT NULL CHECK (relation_type IN (
        'near_synonym','antonym','word_family','collocation_component','contrast'
    )),
    note TEXT NOT NULL,
    CHECK (from_sense_id <> to_sense_id),
    PRIMARY KEY (from_sense_id, to_sense_id, relation_type)
);
CREATE TABLE word_forms (
    id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL REFERENCES lexical_entries(id) ON DELETE RESTRICT,
    form TEXT NOT NULL,
    grammatical_role TEXT NOT NULL,
    UNIQUE (entry_id, form, grammatical_role)
);
CREATE TABLE asset_references (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('audio','image','video','subtitle')),
    storage_key TEXT NOT NULL UNIQUE,
    sha256 TEXT,
    source_item_id TEXT NOT NULL REFERENCES source_items(id) ON DELETE RESTRICT,
    metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json))
);
CREATE TABLE pronunciations (
    id TEXT PRIMARY KEY,
    sense_id TEXT NOT NULL REFERENCES lexical_senses(id) ON DELETE RESTRICT,
    locale TEXT NOT NULL,
    ipa TEXT,
    audio_asset_id TEXT REFERENCES asset_references(id) ON DELETE RESTRICT,
    source_item_id TEXT NOT NULL REFERENCES source_items(id) ON DELETE RESTRICT,
    CHECK (ipa IS NOT NULL OR audio_asset_id IS NOT NULL)
);
CREATE TABLE vocabulary_examples (
    id TEXT PRIMARY KEY,
    sense_id TEXT NOT NULL REFERENCES lexical_senses(id) ON DELETE RESTRICT,
    text_en TEXT NOT NULL,
    translation_vi TEXT NOT NULL,
    source_item_id TEXT NOT NULL REFERENCES source_items(id) ON DELETE RESTRICT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','in_review','approved','rejected'))
);

CREATE TABLE patterns (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('grammar','expression','discourse')),
    title TEXT NOT NULL,
    template TEXT NOT NULL,
    explanation_vi TEXT NOT NULL,
    usage_limits TEXT NOT NULL,
    source_item_id TEXT NOT NULL REFERENCES source_items(id) ON DELETE RESTRICT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','in_review','approved','rejected')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0)
);
CREATE TABLE pattern_topics (
    pattern_id TEXT NOT NULL REFERENCES patterns(id) ON DELETE RESTRICT,
    topic_id TEXT NOT NULL REFERENCES topics(id) ON DELETE RESTRICT,
    PRIMARY KEY (pattern_id, topic_id)
);
CREATE TABLE pattern_labels (
    pattern_id TEXT NOT NULL REFERENCES patterns(id) ON DELETE RESTRICT,
    label_id TEXT NOT NULL REFERENCES labels(id) ON DELETE RESTRICT,
    PRIMARY KEY (pattern_id, label_id)
);
CREATE TABLE pattern_examples (
    id TEXT PRIMARY KEY,
    pattern_id TEXT NOT NULL REFERENCES patterns(id) ON DELETE RESTRICT,
    correct_text TEXT NOT NULL,
    translation_vi TEXT NOT NULL,
    incorrect_text TEXT,
    explanation_vi TEXT NOT NULL,
    source_item_id TEXT NOT NULL REFERENCES source_items(id) ON DELETE RESTRICT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','in_review','approved','rejected'))
);

CREATE TABLE prompts (
    id TEXT PRIMARY KEY,
    module TEXT NOT NULL CHECK (module IN ('academic','general_training','both')),
    skill TEXT NOT NULL CHECK (skill IN ('listening','reading','writing','speaking')),
    task_part TEXT NOT NULL,
    text_en TEXT NOT NULL,
    source_item_id TEXT NOT NULL REFERENCES source_items(id) ON DELETE RESTRICT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','in_review','approved','rejected')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    CHECK (module <> 'both' OR skill IN ('listening','speaking'))
);
CREATE TABLE prompt_topics (
    prompt_id TEXT NOT NULL REFERENCES prompts(id) ON DELETE RESTRICT,
    topic_id TEXT NOT NULL REFERENCES topics(id) ON DELETE RESTRICT,
    PRIMARY KEY (prompt_id, topic_id)
);
CREATE TABLE samples (
    id TEXT PRIMARY KEY,
    prompt_id TEXT REFERENCES prompts(id) ON DELETE RESTRICT,
    kind TEXT NOT NULL CHECK (kind IN ('sentence','paragraph','essay','speaking_answer','dialogue','passage')),
    title TEXT NOT NULL,
    source_item_id TEXT NOT NULL REFERENCES source_items(id) ON DELETE RESTRICT
);
CREATE TABLE sample_versions (
    id TEXT PRIMARY KEY,
    sample_id TEXT NOT NULL REFERENCES samples(id) ON DELETE RESTRICT,
    version INTEGER NOT NULL CHECK (version > 0),
    parent_version_id TEXT REFERENCES sample_versions(id) ON DELETE RESTRICT,
    revision_note TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','in_review','approved','rejected')),
    UNIQUE (sample_id, version),
    UNIQUE (id, sample_id)
);
CREATE TABLE sample_segments (
    id TEXT PRIMARY KEY,
    sample_version_id TEXT NOT NULL REFERENCES sample_versions(id) ON DELETE RESTRICT,
    position INTEGER NOT NULL CHECK (position > 0),
    role TEXT NOT NULL,
    text_en TEXT NOT NULL,
    translation_vi TEXT NOT NULL,
    UNIQUE (sample_version_id, position)
);
CREATE TABLE sample_topics (
    sample_id TEXT NOT NULL REFERENCES samples(id) ON DELETE RESTRICT,
    topic_id TEXT NOT NULL REFERENCES topics(id) ON DELETE RESTRICT,
    PRIMARY KEY (sample_id, topic_id)
);
CREATE TABLE sample_annotations (
    id TEXT PRIMARY KEY,
    segment_id TEXT NOT NULL REFERENCES sample_segments(id) ON DELETE RESTRICT,
    quoted_text TEXT NOT NULL,
    occurrence INTEGER NOT NULL DEFAULT 1 CHECK (occurrence > 0),
    sense_id TEXT REFERENCES lexical_senses(id) ON DELETE RESTRICT,
    pattern_id TEXT REFERENCES patterns(id) ON DELETE RESTRICT,
    note_vi TEXT NOT NULL,
    CHECK ((sense_id IS NOT NULL) + (pattern_id IS NOT NULL) = 1)
);
CREATE TABLE sample_assessments (
    id TEXT PRIMARY KEY,
    sample_version_id TEXT NOT NULL REFERENCES sample_versions(id) ON DELETE RESTRICT,
    criterion_id TEXT NOT NULL REFERENCES labels(id) ON DELETE RESTRICT,
    assessor_kind TEXT NOT NULL CHECK (assessor_kind IN ('official_source','human_estimate','ai_estimate')),
    assessor_name TEXT NOT NULL,
    estimated_band REAL CHECK (estimated_band BETWEEN 0 AND 9),
    feedback TEXT NOT NULL,
    source_item_id TEXT REFERENCES source_items(id) ON DELETE RESTRICT
);

CREATE TABLE exercises (
    id TEXT PRIMARY KEY,
    format TEXT NOT NULL CHECK (format IN ('mcq','gap_fill','error_correction','rewrite','true_false_not_given')),
    question_text TEXT NOT NULL,
    sense_id TEXT REFERENCES lexical_senses(id) ON DELETE RESTRICT,
    pattern_id TEXT REFERENCES patterns(id) ON DELETE RESTRICT,
    segment_id TEXT REFERENCES sample_segments(id) ON DELETE RESTRICT,
    source_item_id TEXT NOT NULL REFERENCES source_items(id) ON DELETE RESTRICT,
    response_spec_json TEXT NOT NULL CHECK (json_valid(response_spec_json)),
    answer_key_json TEXT NOT NULL CHECK (json_valid(answer_key_json)),
    explanation_vi TEXT NOT NULL,
    evidence TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','in_review','approved','rejected')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    CHECK ((sense_id IS NOT NULL) + (pattern_id IS NOT NULL) + (segment_id IS NOT NULL) = 1)
);
CREATE TABLE short_briefs (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    objective TEXT NOT NULL CHECK (length(trim(objective)) > 0),
    format TEXT NOT NULL CHECK (format IN ('vocabulary','pattern','sample_analysis','quiz','shadowing','error_correction')),
    focus_sense_id TEXT REFERENCES lexical_senses(id) ON DELETE RESTRICT,
    focus_pattern_id TEXT REFERENCES patterns(id) ON DELETE RESTRICT,
    focus_segment_id TEXT REFERENCES sample_segments(id) ON DELETE RESTRICT,
    focus_exercise_id TEXT REFERENCES exercises(id) ON DELETE RESTRICT,
    target_seconds INTEGER NOT NULL CHECK (target_seconds BETWEEN 15 AND 90),
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','in_review','approved','rejected')),
    CHECK ((focus_sense_id IS NOT NULL) + (focus_pattern_id IS NOT NULL)
         + (focus_segment_id IS NOT NULL) + (focus_exercise_id IS NOT NULL) = 1)
);
CREATE TABLE script_revisions (
    id TEXT PRIMARY KEY,
    brief_id TEXT NOT NULL REFERENCES short_briefs(id) ON DELETE RESTRICT,
    version INTEGER NOT NULL CHECK (version > 0),
    input_snapshot_json TEXT NOT NULL CHECK (json_valid(input_snapshot_json)),
    -- NULL means not fingerprinted, and is never eligible for export.
    snapshot_sha256 TEXT CHECK (snapshot_sha256 IS NULL OR length(snapshot_sha256) = 64),
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','in_review','approved','rejected')),
    UNIQUE (brief_id, version)
);
CREATE TABLE script_scenes (
    id TEXT PRIMARY KEY,
    revision_id TEXT NOT NULL REFERENCES script_revisions(id) ON DELETE RESTRICT,
    position INTEGER NOT NULL CHECK (position > 0),
    role TEXT NOT NULL CHECK (role IN ('hook','teach','example','practice','answer','recap')),
    spoken_text TEXT NOT NULL,
    spoken_locale TEXT NOT NULL CHECK (spoken_locale IN ('en-US','en-GB','vi-VN')),
    display_text TEXT NOT NULL,
    translation_vi TEXT NOT NULL DEFAULT '',
    pause_after_seconds REAL NOT NULL DEFAULT 0 CHECK (pause_after_seconds BETWEEN 0 AND 15),
    visual_brief TEXT NOT NULL DEFAULT '',
    UNIQUE (revision_id, position)
);

CREATE INDEX ix_topics_parent ON topics(parent_id);
CREATE INDEX ix_sense_topics_topic ON sense_topics(topic_id, sense_id);
CREATE INDEX ix_pattern_topics_topic ON pattern_topics(topic_id, pattern_id);
CREATE INDEX ix_sample_topics_topic ON sample_topics(topic_id, sample_id);
CREATE INDEX ix_prompt_topics_topic ON prompt_topics(topic_id, prompt_id);
CREATE INDEX ix_senses_review ON lexical_senses(review_status, id);
CREATE INDEX ix_patterns_review ON patterns(review_status, id);
CREATE INDEX ix_samples_prompt ON samples(prompt_id);
CREATE INDEX ix_annotations_sense ON sample_annotations(sense_id);
CREATE INDEX ix_annotations_pattern ON sample_annotations(pattern_id);
CREATE INDEX ix_briefs_sense ON short_briefs(focus_sense_id);
CREATE INDEX ix_briefs_pattern ON short_briefs(focus_pattern_id);
CREATE INDEX ix_briefs_segment ON short_briefs(focus_segment_id);
CREATE INDEX ix_briefs_exercise ON short_briefs(focus_exercise_id);
