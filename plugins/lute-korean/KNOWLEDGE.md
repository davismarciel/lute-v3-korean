# Sprint 2: persistent Korean acquisition

## Architecture and relationship to Sprint 1

`KoreanParser.analyze(text)` and reading tokens are unchanged. The new ingestion
service consumes their original text, lexical heads and ordered morphology.
Lute Terms and their numeric statuses remain exclusively part of reading.
Knowledge items have independent UUIDs, identities and manual pedagogical statuses.

The proposed model was presented before implementation. Tables are additive:

```text
KnowledgeItem (lexical | grammar | chunk)
  ├── dimensional statuses (reading | listening | production)
  ├── occurrence associations ── Occurrence ── Source revision
  └── Evidence ── optional Occurrence
```

- `korean_knowledge_items`: unique `(kind, identity)`; default status `unknown`.
  All items support `unknown`, `presented`, `practicing`, `consolidated`, `future`.
- `korean_knowledge_dimensions`: optional manual assessment per item/dimension.
  Unassessed dimensional statuses export as null, independent of overall status.
- `korean_knowledge_sources`: original input stored once per immutable source key,
  with content hash and optional link to the Lute page (`texts.TxID`).
- `korean_knowledge_occurrences`: original span, surface, context bounds and small
  useful morphology metadata. Offsets address the original source, end exclusive.
- `korean_knowledge_occurrence_items`: one span can belong to multiple items,
  including lexical, grammar and manually selected chunks.
- `korean_knowledge_evidence`: events, source attribution, dimension, UTC timestamp,
  small metadata and optional deduplication key. Occurrence evidence derives its
  surface/context instead of copying source text into every event.

`tables.py` maps migration-owned tables through SQLAlchemy Core; it does not
register models globally or use `create_all`. `KnowledgeService` owns persistence
and exposes dictionary DTOs. Consumers need no SQL. `KnowledgeIngestionService`
owns analysis-to-tracking translation. `GrammarPatternDetector` is the detector
extension contract. No web UI or automatic reading/import hook was added.

## Migration and installation

The only core addition is `lute/db/schema/migrations/20260930_01_korean_knowledge.sql`.
Start this fork normally to run the existing Lute migration/backup mechanism.
Existing tables are untouched. The migration is tracked in `_migrations` and must
not be edited after deployment; later schema changes require another migration.

Install/update the plugin in the same environment:

```sh
python -m pip install -e plugins/lute-korean
```

A stock upstream installation without this fork's migration can diagnose text,
but cannot persist knowledge. CLI persistence requires an existing migrated
Lute database; it never creates or migrates a database implicitly. Source
snapshots preserve acquisition evidence after page edits or deletion. If SQLite
foreign keys are enabled, page deletion nulls the optional page reference.
Uninstalling the plugin does not drop knowledge tables or erase evidence.
Lute's existing language/demo reset does not clear this separate knowledge layer.

## Services and transaction ownership

```python
from lute.db import db
from lute_korean_parser.knowledge.service import KnowledgeService
from lute_korean_parser.knowledge.ingestion import KnowledgeIngestionService

# Inside a Lute application context:
service = KnowledgeService(db.session)
ingestion = KnowledgeIngestionService(db.session)
ingestion.ingest("한국에 가면 많이 먹을 거예요.", "manual:sample:1")
go = service.get_lexical("가다")
service.set_status(go["id"], "consolidated")
condition = service.find_item("grammar", "-(으)면")
service.set_status(condition["id"], "practicing")
ingestion.ingest("시간이 있으면 친구랑 같이 갈 거예요.", "manual:sample:2")
db.session.commit()  # Explicit: services never commit the caller's transaction.
```

Ingestion uses a savepoint and explicitly starts the SQLite outer transaction
when necessary to prevent legacy sqlite3 savepoint release from committing early.
Failures roll back that ingestion, leaving prior work intact. Callers still own
commit/rollback and must handle failures of their other service operations.

Other public operations:

- `get_or_create_lexical(lemma)`, `get_or_create_grammar(pattern)`,
  `find_item(kind, identity)`, `get_item(id)`, `list_items(kind)`.
- `list_surface_forms(id)`, `list_occurrences(id)`, `list_evidence(id)`.
- `set_status(id, status, dimension=None)`; ingestion never changes statuses.
- `record_evidence(id, evidence_type, dimension=..., source_type=...,
  source_reference=..., occurrence_id=..., occurred_at=..., metadata=...,
  event_key=...)`. Timestamps must be timezone-aware.
- `get_or_create_chunk(text)`, `find_chunk(text)`, `list_chunks()`,
  `update_chunk(id, text=..., status=...)`, `delete_chunk(id)`.
- `ensure_source(...)` and `associate_occurrence(...)` attach manually selected
  spans to chunks; then record evidence with the returned occurrence ID.
- `ingest_lute_text(page_id)` explicitly ingests a Korean (Kiwi) page. Its source
  key includes the page ID and content hash. Reading and imports remain independent.
- `export()` returns a JSON-safe public snapshot, schema version 1, with stable
  IDs, types, statuses, surfaces and evidence summaries for all three dimensions.

### Example: manually track a chunk

```python
chunk = service.get_or_create_chunk("시간이 있으면")
source = service.ensure_source("manual", "chunk:sample:1", "시간이 있으면 공부할 거예요.")
occurrence = service.associate_occurrence(chunk["id"], source["id"], 0, 7)
service.record_evidence(chunk["id"], "manual_confirmation", occurrence_id=occurrence["id"])
service.set_status(chunk["id"], "consolidated")
```

## Identity and reprocessing policy

Lexical identity uses the existing head/lemma, normalized to NFC for the key only;
original source text is never normalized. Derived heads like `공부하다` and
`피곤하다` come directly from Sprint 1's POS-based composition. `가요` is analyzed
in context: Kiwi can also recognize it as the noun meaning popular song; no
artificial conversion overrides that analysis.

The default `LexicalPolicy` excludes bound nouns, copulas and numeric tokens from
pedagogical lexical items. Thus `거` and `이다` are grammatical scaffolding in the
future construction; their morphology is still available in the original analysis.
Configure the policy explicitly to include those heads if desired. Auxiliary
`보다` and `싶다` remain lexical concepts; `-고 싶다` can coexist as a grammar item.
Particular particles and past endings remain occurrence metadata, not automatically
created pedagogical items.

Source identity is `(source_type, reference)`. Reingesting identical content under
that reference reuses source, spans, item links and exposure evidence for the same
dimension. A different dimension adds its own exposure. Changed content under the
same reference is rejected; choose a new revision reference. Separate references
represent separate input sources even if their text is identical. Lute page keys
include their content hash, automatically preserving separate revisions.

Manual events without `event_key` are distinct observations. Integrations should
supply stable event keys for retries; mismatched event payloads are rejected.
Reprocessing is not a new reading event: record an explicit new event if the
student genuinely encounters the same span again. Detector policy additions can
add links/evidence on reprocessing; existing records are not silently rewritten or
deleted. A future analysis-version migration should deliberately reconcile them.

## Conservative grammar detectors

All five detectors use Kiwi forms, POS and ordered adjacency, not text regexes:

| Pattern | Required evidence |
| --- | --- |
| `-(으)면` | predicate followed in its unit by 면/으면 EC |
| `-아/어서` | predicate followed in its unit by 아서/어서 EC, including contracted 가서 |
| `-는데` | predicate followed in its unit by 는데/은데/ᆫ데 EC |
| `-고 싶다` | adjacent 고 EC and 싶 VX after a predicate; no intervening sentence break |
| `-(으)ㄹ 거예요` | predicate + ㄹ/을 ETM + 거 NNB + copula VCP + 예요 EF |

Spaces/tabs are allowed between related units; newlines and punctuation do not
join multiword constructions. Pass a custom detector tuple (or `()`) to control
pedagogical selection. Grammar occurrences cover complete affected display units,
not clickable morphemes. The source reading appearance is unchanged.

## CLI and JSON

```sh
# Read-only diagnosis; no database required or written.
lute-korean-analyze-knowledge "한국에 가면 많이 먹을 거예요."

# Explicit ingestion; repeat with the same reference to avoid duplicate evidence.
lute-korean-analyze-knowledge --file transcript.txt --persist \
  --database /path/to/lute.db --source-reference manual:transcript:v1 \
  --dimension reading --export knowledge.json
```

Before reinstalling the updated plugin, the equivalent module command is:
`python -m lute_korean_parser.knowledge.cli "한국에 가면 많이 먹을 거예요."`.
The database/export flags require `--persist`. Transcript files retain original
UTF-8 text and CRLF offsets. `knowledge.json` excludes source text, raw Kiwi objects,
SQL internals and review histories. It contains both overall manual status and
optional dimensional manual statuses plus event counts. Counts are summaries,
not acquisition scores.

## Limitations and future extension points

- Lemma-only identity does not distinguish homographs or senses. Kiwi ambiguity
  and malformed input can still misidentify heads; there is no human correction UI.
- The five detectors recognize narrow morphological shapes, not every equivalent
  construction or every pragmatic meaning. No automatic detector for other patterns,
  particles as study items, or chunks is implemented.
- This is one Korean acquisition profile per Lute database. No multi-user profile,
  UI, implicit ingest, or migration/backfill of existing Terms is included.
- Source snapshots intentionally retain original contexts; they are not a text
  editing system. No automatic reconciliation/removal of older analysis evidence.
- Metadata is limited to 8 KiB per record. Context is sentence/line scoped using
  Kiwi sentence punctuation and original line breaks, without full discourse analysis.
- Sprint 3 adds a read-only Anki adapter using this ingestion API, stable
  note/card/review identifiers, and canonical indirect review evidence. See
  [ANKI.md](ANKI.md) for source revisions, uncertain historical associations,
  transactions and optional summaries. Ratings do not become individual
  recognized/missed/produced claims or proficiency statuses.
- `reading`, `listening`, and `production` accept attributed events now, but real
  listening/production capture is deferred. Anki reviews retain unspecified
  modality separately instead of inventing listening or production evidence.
- JSON export is the seam for ChatGPT or comprehensible-input difficulty tools.
  Those consumers must choose a policy using statuses, dimensions and evidence;
  this sprint computes no difficulty, recommendation or mastery score.

## Sprint 3.6 lexical hardening

The acquisition pipeline is now:

```text
Source cleanup/validation → KoreanParser.analyze → KoreanLexicalNormalizer
                         → LexicalPolicy → KnowledgeIngestionService
```

`knowledge.normalization` defines an explicit `LexicalNormalizationRule` registry.
The initial rule `ko.lexical.johahada.v1` consumes only contiguous
`좋/VA + 어/EC + 하/VX` inside one original orthographic unit, guarded by its
source composition/spans. It produces `좋아하다` without creating pedagogical
`좋다`/`하다` from that decomposition. Native `좋아하/VV` needs no rule. Independent
`좋다`, spaced predicates, and `하다` remain unchanged. Other potential compounds
require concrete evidence and their own tested rule; no broad concatenation rule
is installed.

`preview()` exposes both `analysis` (untouched) and `normalized` units.
Occurrences retain compact raw morphemes, raw heads, canonical heads, applied
rule IDs/spans, deterministic confidence, policy and Kiwi versions, eligible
heads and non-Korean heads. Full Kiwi objects are never serialized.

The default lexical eligibility policy tracks heads whose letters are Hangul,
including Korean-written names/loanwords. Latin names, code-switching and numeric
spans remain source/occurrence metadata; they are not Korean Lexical Concepts.
A mixed sentence is not rejected. `ensure_occurrence()` and
`list_source_occurrences()` allow consumers to inspect unlinked foreign spans.
Existing item IDs and manual statuses are reused; ingestion never sets status.

The processing signature includes the active normalization registry and lexical
policy. Anki and the opt-in Lute page adapter include it in their source revision
identity. Callers using `ingest(text, source_reference)` directly must supply a
new explicit reference when changing analysis policy. Source revisions are
immutable: older links and reviews are not silently rewritten or deleted.
An old unqualified staging/import must be rebuilt or explicitly reconciled before
its historical associations are used without qualification. This sprint builds a
clean staging database; it does not repair or migrate the user's principal data.
No additional database migration is required for this hardening.

## Sprint 4 suggested learner state

`LearnerStateEngine` reads canonical item associations, exposures and raw Anki
review provenance in bounded batches. It calculates on-demand and never writes
manual status, evidence or suggestion tables. The opt-in extension
`KnowledgeService.export(include_learner_state=True)` preserves the old export
when disabled and adds manual/suggested states, confidence, explanations,
comparisons and policy/snapshot metadata when enabled. Existing `set_status()`
remains the explicit manual assessment operation.

See [LEARNER_STATE.md](LEARNER_STATE.md),
[validation](LEARNER_STATE_VALIDATION.md) and
[human calibration sample](LEARNER_STATE_CALIBRATION.json). No new migration,
automatic apply, listening inference or recommendation feature was added.

## Sprint 4.5 representation hardening

The additive representation migration adds lexical roles and directed component
relations. `KnowledgeRepresentationService` provides role override, relation
listing, span-scoped effective-item resolution and read-only integrity diagnosis.
`HumanEvidenceService` validates/previews factual observations and explicitly
applies them with stable event keys and caller-owned transactions. Neither writes
manual statuses. LearnerStatePolicyV1 is unchanged.

The normalizer corrects the attested 어제 ambiguity and verified existential
compounds, retaining raw morphology. Ingestion projects multiword NNP spans once
without changing reader tokens. See [LEXICAL_INTEGRITY.md](LEXICAL_INTEGRITY.md),
[HUMAN_EVIDENCE.md](HUMAN_EVIDENCE.md) and
[SPRINT_4_5_VALIDATION.md](SPRINT_4_5_VALIDATION.md). Existing historical links
need explicit reconciliation or a clean rebuild; no automatic rewrite is performed.

## Candidate analysis boundary

Sprint 5 consumes a batched read-only learner/role/relation snapshot. Pure lexical
projection and span-scoped overlap resolution are shared with ingestion; candidate
rows remain ephemeral. No migrations, temporary database writes or Sources are
needed. See [CI_ANALYSIS.md](CI_ANALYSIS.md). Study/exposure persistence requires a
separate explicit workflow; running the analyzer is never such a workflow.

## Daily study orchestration

The optional Korean Study workspace uses the existing KnowledgeService,
KnowledgeIngestionService and HumanEvidenceService. StudySessionService preserves
the distinction between ephemeral candidate analysis, actual consumed content and
explicit human observations. Session consumption calls ingestion with
`record_exposure=False`, then records session-keyed exposure itself; the default
ingestion behavior remains unchanged for existing consumers. This avoids duplicate
first-study exposure and supports distinct real re-study events over reused
Sources/Occurrences. Pure listening records no inferred item-level skill evidence.
See `KOREAN_STUDY_WORKFLOW.md` for UI and transaction semantics.
