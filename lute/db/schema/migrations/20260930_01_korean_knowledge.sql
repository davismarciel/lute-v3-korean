-- Additive acquisition layer. No existing Lute tables or statuses are changed.
BEGIN TRANSACTION;
CREATE TABLE korean_knowledge_items (
    id TEXT PRIMARY KEY NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('lexical','grammar','chunk')),
    identity TEXT NOT NULL CHECK(length(identity)>0),
    status TEXT NOT NULL DEFAULT 'unknown'
        CHECK(status IN ('unknown','presented','practicing','consolidated','future')),
    UNIQUE(kind, identity)
);
CREATE TABLE korean_knowledge_dimensions (
    item_id TEXT NOT NULL REFERENCES korean_knowledge_items(id) ON DELETE CASCADE,
    dimension TEXT NOT NULL CHECK(dimension IN ('reading','listening','production')),
    status TEXT NOT NULL CHECK(status IN ('unknown','presented','practicing','consolidated','future')),
    PRIMARY KEY(item_id, dimension)
);
CREATE TABLE korean_knowledge_sources (
    id TEXT PRIMARY KEY NOT NULL,
    source_type TEXT NOT NULL CHECK(source_type IN ('lute_text','tprs','anki','conversation','podcast','manual')),
    reference TEXT NOT NULL CHECK(length(reference)>0),
    content_hash TEXT NOT NULL,
    content TEXT NOT NULL,
    lute_text_id INTEGER REFERENCES texts(TxID) ON DELETE SET NULL,
    UNIQUE(source_type, reference)
);
CREATE TABLE korean_knowledge_occurrences (
    id TEXT PRIMARY KEY NOT NULL,
    source_id TEXT NOT NULL REFERENCES korean_knowledge_sources(id) ON DELETE CASCADE,
    start INTEGER NOT NULL CHECK(start>=0),
    end INTEGER NOT NULL CHECK(end>start),
    surface TEXT NOT NULL,
    context_start INTEGER NOT NULL CHECK(context_start>=0 AND context_start<=start),
    context_end INTEGER NOT NULL CHECK(context_end>=end),
    metadata TEXT NOT NULL DEFAULT '{}',
    UNIQUE(source_id, start, end)
);
CREATE TABLE korean_knowledge_occurrence_items (
    occurrence_id TEXT NOT NULL REFERENCES korean_knowledge_occurrences(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES korean_knowledge_items(id) ON DELETE CASCADE,
    PRIMARY KEY(occurrence_id, item_id)
);
CREATE TABLE korean_knowledge_evidence (
    id TEXT PRIMARY KEY NOT NULL,
    item_id TEXT NOT NULL REFERENCES korean_knowledge_items(id) ON DELETE CASCADE,
    occurrence_id TEXT REFERENCES korean_knowledge_occurrences(id) ON DELETE SET NULL,
    evidence_type TEXT NOT NULL CHECK(evidence_type IN ('exposure','recognized','produced','missed','manual_confirmation')),
    source_type TEXT NOT NULL CHECK(source_type IN ('lute_text','tprs','anki','conversation','podcast','manual')),
    source_reference TEXT NOT NULL,
    dimension TEXT NOT NULL CHECK(dimension IN ('reading','listening','production')),
    surface TEXT,
    context TEXT,
    occurred_at TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    event_key TEXT UNIQUE
);
CREATE INDEX korean_knowledge_evidence_item ON korean_knowledge_evidence(item_id);
CREATE INDEX korean_knowledge_occurrence_item ON korean_knowledge_occurrence_items(item_id);
COMMIT;
