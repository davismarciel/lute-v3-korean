# Korean acquisition

Knowledge represents acquisition separately from Lute's reading terms.

## Language

**Surface form**: The original written form encountered in input, including its conjugation or particles.

**Lexical concept**: A lexical unit identified by an eligible canonical Korean head, shared across surface forms. Raw Kiwi heads remain separate provenance. It is not a Lute Term.

**Grammar pattern**: A pedagogically selected construction detected from morphological evidence. Not every particle or ending is a pattern to study.

**Chunk**: A phrase deliberately tracked as a whole, coexisting with its constituent lexical concepts and grammar patterns.

**Occurrence**: A bounded surface span in a versioned source, providing morphological context for zero or more knowledge items. Foreign/code-switching spans can remain unlinked metadata.

**Evidence**: An exposure, recognition, production, miss, or manual confirmation for an item in a skill dimension. Evidence does not determine status automatically.

**Anki review evidence**: One canonical card review event, related to items through its source revision and occurrences. It is indirect evidence about note content, with unspecified modality. It is not an independent test of every associated item.

**Observed note revision**: A content snapshot seen during explicit synchronization. Historical review-to-content associations retain their certainty metadata; observation does not recover unobserved Anki edit history.

**Pedagogical status**: A manual assessment: unknown, presented, practicing, consolidated, or future. Future means deliberately deferred, not merely unknown.

**Lexical normalization**: A versioned, deterministic rule registry between raw Korean analysis and acquisition ingestion. It never changes the original source, reading tokens, or Kiwi morphology.

**Content anomaly**: Unexpected content in an explicitly mapped Korean field. Source-specific validation can withhold linguistic associations while preserving the source identity, content, diagnostic and raw card reviews.

**Suggested learner state**: An on-demand, policy-versioned interpretation of evidence. It includes independent dimensions, confidence, reasons and warnings, and never replaces official manual state.

**Classification confidence**: Coverage/reliability of an evidence-based category, independent of learner ability or evidence strength.

**Logical source**: A stable study-content identity grouping Anki note revisions/reverse cards or Lute page revisions for contribution caps. Physical revisions remain separate provenance.

**Calibration sample**: A deterministic frequency/negative/surface-diversity sample for human inspection, selected without fitting or using manual labels.

**Lexical role**: POS-supported or manually overridden representation metadata,
separate from pedagogical priority and status. Proper nouns remain knowledge.

**Knowledge relationship**: An explicit relation between distinct items, initially
component_of. It does not merge their identities or erase their evidence.

**Effective items**: Occurrence-scoped links after transparent construction
coverage resolution. Raw links and suppression reasons remain inspectable; this
is not a difficulty score.

**Human Evidence**: An explicitly recorded factual observation with dimension,
scope, directness, actual timestamp, recorder and idempotent event identity.
It is distinct from a manual status and never automatically applies a status.

**Candidate content**: Ephemeral text/segments under consideration, with identities,
timestamps and canonical knowledge matches. Analyzing it is not observed study,
and creates neither Sources nor Evidence.

**Linguistic fit**: Versioned, explainable candidate reading/transcript load from
familiarity, novelty distribution, detected grammar and representation limits.
It is not demonstrated comprehension, mastery percentage or listening ability.

## Sprint 6 daily workspace

`study/` owns the Korean Study Blueprint, templates/assets, bounded ephemeral
candidate cache, StudySessionService, orchestration and compact teacher exports.
UI presentation calls existing learner/CI/Anki/HumanEvidence services; policies
remain unchanged. The generic optional `lute.plugin.app` hook is the only required
core extension, with its menu integration. Four additive study tables are owned
by migration `20260930_04_korean_study.sql`.

Candidate analysis is read-only. Start persists a session, not acquisition.
Explicit consumed segment saves record reading exposure only when the transcript
was actually read; listening without transcript reading records provenance only.
Human recognition/misses/production require separate factual events. Services
leave commit ownership to the caller. See `KOREAN_STUDY_WORKFLOW.md` and
`SPRINT_6_VALIDATION.md`. No automatic status application or Anki writes exist.
