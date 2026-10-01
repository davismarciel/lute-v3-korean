# Explicit human Evidence

Evidence records an observed event. A manual status records a person's overall
assessment. Neither operation replaces the other; no Evidence import applies a
status. LearnerStatePolicyV1 can recalculate suggestions from new observations
without any policy changes or automatic promotion.

## API and factual contract

```python
from lute_korean_parser.knowledge.human import HumanEvidenceService
service = HumanEvidenceService(session)
service.preview(document)  # validation, resolved IDs/event keys, zero writes
service.apply(document)    # caller explicitly commits or rolls back
```

Accept one JSON event, a list, or `{ "events": [...] }`:

```json
{
  "item": "먹다",
  "kind": "lexical",
  "dimension": "reading",
  "event_type": "recognized",
  "directness": "direct",
  "source_reference": "human-calibration:2026-09-30:observation-1",
  "context": "한국에 가면 많이 먹을 거예요.",
  "occurred_at": "2026-09-30T12:00:00+00:00",
  "recorded_by": "human observer",
  "notes": "Recognized the item in this context."
}
```

This is a **format example**, not a claim that this observation happened.
Required: item, dimension, event_type, directness, source_reference, context,
actual timezone-aware observation timestamp and recorder. The item must already
exist; use kind if identity is ambiguous. Unknown fields fail instead of silently
ignoring a misspelled dimension or source. Optional fields: kind, scope,
source_type, notes, event_key.

Types reuse recognized, produced, missed and manual_confirmation. Dimensions
are reading, listening and production. Produced requires production. Direct
requires item scope; indirect defaults to context scope. Source defaults to
conversation; manual and tprs are also accepted. Metadata records directness,
scope, explicit-item association basis, recorder, factual notes and import
version. Keep notes factual; do not store private internal reasoning.

Timestamp must not be future-dated. Preview does not manufacture an observation
time, create items, import past chats, or infer recognition from exposure/audio.
Listening and production are never inferred from reading. No Anki operation is
used by this service.

## CLI

```sh
lute-korean-evidence validate human-evidence.json --database staging.db
lute-korean-evidence preview human-evidence.json --database staging.db
lute-korean-evidence apply human-evidence.json --database writable-sandbox.db
lute-korean-evidence preview-human-calibration
```

Validate/preview open SQLite in read-only mode. Apply requires an existing,
explicitly selected writable database and commits one validated import. Validation
of the entire file precedes writes; a savepoint rolls back an event-key conflict
without leaving partial imported events. Service callers still own commit/rollback.
No implicit database selection, write mode on preview, or auto-apply exists.

`preview-human-calibration` returns an empty candidate list and explains that no
structured verified observations were supplied. The project contains language
examples, not certified past human recognition events; it does not fabricate them.

## Idempotency and correction

Absent an explicit event_key, a stable SHA-256 key covers the resolved item ID,
normalized factual payload, UTC time, recorder and metadata. Reimporting the same
observation reuses its Evidence ID. Explicit keys can preserve an external
assessment identity; reusing a key for changed facts fails. Across a clean rebuild,
re-resolve identities and preserve externally meaningful event keys. Distinct
actual observations need distinct timestamp/source identity or explicit keys.
No automatic editing or deletion of historical Evidence is implemented.

Synthetic fixtures demonstrate reading practicing/medium becoming consolidated
through repeated direct recognition across contexts, with listening/production
still unknown and manual reading practicing unchanged. Direct recent misses keep
a grammar suggestion practicing. Production events affect production only.
No human Evidence was applied to the real collection or principal database.
