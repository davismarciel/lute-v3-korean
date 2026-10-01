-- Explicit sessions only: candidate analysis never inserts here.
BEGIN TRANSACTION;
CREATE TABLE korean_study_contents (
 id TEXT PRIMARY KEY NOT NULL,
 content_hash TEXT NOT NULL,
 name TEXT NOT NULL,
 kind TEXT NOT NULL,
 format TEXT NOT NULL,
 segments TEXT NOT NULL,
 segment_count INTEGER NOT NULL CHECK(segment_count>0),
 created_at TEXT NOT NULL
);
CREATE TABLE korean_study_sessions (
 id TEXT PRIMARY KEY NOT NULL,
 content_id TEXT NOT NULL REFERENCES korean_study_contents(id),
 request_key TEXT NOT NULL UNIQUE,
 activity TEXT NOT NULL CHECK(activity IN ('reading','listening_with_transcript','listening','mixed')),
 transcript_read INTEGER NOT NULL CHECK(transcript_read IN (0,1)),
 status TEXT NOT NULL CHECK(status IN ('started','partial','completed')),
 started_at TEXT NOT NULL,
 completed_at TEXT,
 external_reference TEXT,
 metadata TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE korean_study_consumed_segments (
 session_id TEXT NOT NULL REFERENCES korean_study_sessions(id),
 segment_index INTEGER NOT NULL,
 source_id TEXT NOT NULL REFERENCES korean_knowledge_sources(id),
 consumed_at TEXT NOT NULL,
 PRIMARY KEY(session_id,segment_index)
);
CREATE TABLE korean_study_observations (
 session_id TEXT NOT NULL REFERENCES korean_study_sessions(id),
 evidence_id TEXT NOT NULL REFERENCES korean_knowledge_evidence(id) ON DELETE CASCADE,
 PRIMARY KEY(session_id,evidence_id)
);
CREATE INDEX korean_study_sessions_content ON korean_study_sessions(content_id);
COMMIT;
