-- Operational Anki snapshots and canonical sentence-level evidence.
-- Existing Knowledge Evidence is item/dimension scoped; reviews are not.
BEGIN TRANSACTION;
CREATE TABLE korean_anki_integrations (
    identity TEXT PRIMARY KEY NOT NULL,
    profile TEXT NOT NULL,
    last_success TEXT,
    report TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE korean_anki_notes (
    integration TEXT NOT NULL REFERENCES korean_anki_integrations(identity),
    note_id INTEGER NOT NULL,
    source_id TEXT REFERENCES korean_knowledge_sources(id),
    content_hash TEXT,
    mapping_hash TEXT,
    modified INTEGER,
    state TEXT NOT NULL CHECK(state IN ('active','missing','out_of_scope','error')),
    metadata TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY(integration, note_id)
);
CREATE TABLE korean_anki_revisions (
    integration TEXT NOT NULL,
    note_id INTEGER NOT NULL,
    source_id TEXT NOT NULL REFERENCES korean_knowledge_sources(id),
    observed_at TEXT NOT NULL,
    effective_from INTEGER,
    metadata TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY(integration, note_id, observed_at),
    FOREIGN KEY(integration,note_id) REFERENCES korean_anki_notes(integration,note_id)
);
CREATE TABLE korean_anki_cards (
    integration TEXT NOT NULL,
    card_id INTEGER NOT NULL,
    note_id INTEGER NOT NULL,
    deck TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('active','suspended','missing','out_of_scope')),
    review_cursor INTEGER NOT NULL DEFAULT 0,
    metadata TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY(integration,card_id),
    FOREIGN KEY(integration,note_id) REFERENCES korean_anki_notes(integration,note_id)
);
CREATE TABLE korean_anki_reviews (
    integration TEXT NOT NULL,
    card_id INTEGER NOT NULL,
    review_id INTEGER NOT NULL,
    note_id INTEGER NOT NULL,
    source_id TEXT NOT NULL REFERENCES korean_knowledge_sources(id),
    event_key TEXT NOT NULL UNIQUE,
    occurred_at TEXT NOT NULL,
    rating INTEGER NOT NULL,
    interval INTEGER NOT NULL,
    previous_interval INTEGER NOT NULL,
    review_type INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    factor INTEGER NOT NULL,
    usn INTEGER NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY(integration,card_id,review_id),
    FOREIGN KEY(integration,card_id) REFERENCES korean_anki_cards(integration,card_id)
);
CREATE INDEX korean_anki_reviews_source ON korean_anki_reviews(source_id);
CREATE INDEX korean_anki_reviews_note ON korean_anki_reviews(integration,note_id);
COMMIT;
