# Learner State Engine — Policy V1

## Scope and architecture

The engine produces **suggestions**, never official assessments or mastery
percentages. Manual state remains authoritative. It reads canonical Knowledge
Items and their existing associations; it neither runs Kiwi nor interprets raw
lexical heads. No parser, detector, Anki adapter, UI or database schema change is
needed. No process applies suggested state or schedules recalculation.

```text
Knowledge Evidence + Source/Occurrence provenance + canonical Anki events
    → batched repository snapshot
    → EvidenceInterpreter / EvidenceQuality
    → LearnerStatePolicyV1 / LearnerStateEngine
    → categories, confidence, reasons, warnings
    → human inspection
```

Modules live in `lute_korean_parser.learner_state`: `repository`,
`interpretation`, `policy`, `engine`, `calibration`, and `cli`.

Calculation is **on-demand**. JSON snapshots include policy version, the full
parameter set and its SHA-256 fingerprint, timezone-aware `as_of`, evidence
fingerprint, and input fingerprint. The evidence fingerprint excludes manual
labels; the input fingerprint includes them. Saving an export is explicit and
never changes the database. A new policy recalculates existing evidence without
rewriting history. There are no new tables or migrations.

## Status and confidence

| Suggested status | Meaning |
| --- | --- |
| unknown | No useful observed evidence in this dimension. Missing coverage is not proof of inability. |
| presented | Real exposure/encounter exists; comprehension has not been established. |
| practicing | Partial recognition/use or repeated contextual support; uncertainty or misses remain. |
| consolidated | Strong recognition/use, with multiple observed contexts and bounded evidence strength. |
| future | Never calculated. It appears only to preserve an explicit manual deferment. |

Confidence describes reliability of the classification, not learner ability.
Three strong direct confirmations can yield consolidated/low; six or more
recognized contexts with recent direct misses can yield practicing/high.
Unobserved listening/production remains unknown/low. There is no “percent learned”.

`manual_state` has stored overall status plus separately assessed dimensions,
with null for unassessed dimensions. `suggested_state` supplies the three
independent dimensions. `suggested_overall` describes the strongest non-deferred observed
dimension without implying transfer to other skills. A deferred dimension cannot
reappear as visible overall consolidation when no other observed lane advances. Unspecified-only evidence
can suggest overall presented but cannot assert a dimension.

Manual `future` preserves visible future and `origin=manual_deferment`;
`computed_status` retains the underlying evidence calculation for diagnosis.
Overall manual future defers all visible dimensions. Nothing writes future into
other official dimensional rows. Other manual/suggested disagreements remain
visible. Comparison categories are equal, manual greater, manual lower, no
manual, or manual deferment. Overall unknown is stored by default in the current
schema; it cannot be reliably distinguished from an explicit unknown assessment.
Calibration reports disclose this instead of treating defaults as human labels.

## Evidence interpretation

Directness, scope, polarity, temporal relevance, association confidence and
modality confidence are separate quality axes. Source/context diversity is
calculated across interpreted events, not assigned from review volume.

- `exposure` is always weak/indirect, even if metadata claims directness.
- `recognized` or `produced` is direct only with
  `metadata={"directness":"direct", "scope":"item"}` (or `knowledge_item`).
  Otherwise it remains contextual/indirect.
- `manual_confirmation` defaults to item-scoped direct confirmation. It is an
  evidence event, separate from merely setting a manual status.
- `missed` can be direct with the same explicit item-scope contract. An indirect
  miss does not establish that the individual item failed.
- A generic event affects only its recorded dimension. Metadata
  `modality=unspecified` withholds dimensional interpretation.
- Audio presence never creates listening evidence. Production never implies
  reading or listening. The engine trusts explicit observed evidence dimensions;
  integrations are responsible for recording them honestly.

Anki reviews remain indirect, note/card-content scoped, with unspecified modality.
They contribute **bounded contextual support to an already evidenced reading
lane**. They never become reading-recognition events, direct word successes, or
listening/production evidence. They can help suggest practice, but cannot satisfy
recognition gates for consolidation. The export separately counts these
unspecified events and warns about the conditional contextual contribution.

### Exact default contribution policy

The complete machine-readable policy is exported with every calculation.
Defaults below are heuristic strength units, not probabilities or scientific
measurements:

| Parameter | Default |
| --- | ---: |
| exposure | 0.35 |
| direct recognized | 2.5 |
| direct produced / manual_confirmation | 3.0 / 3.0 |
| direct missed | 2.5 negative |
| indirect non-exposure multiplier | 0.4 |
| first_observed_snapshot / historical_snapshot_uncertain association | 0.35 |
| observed_revision_modification_boundary association | 0.65 |
| verified_content / explicit_item / explicit generic item evidence | 1.0 |
| unknown association basis | 0.35 |
| unspecified modality multiplier | 0.4 |
| review Good / Easy positive signal | 0.6 / 0.8 |
| review Again negative signal | 1.0 |
| review Hard signal | 0.15 positive and 0.15 negative |
| review positive / negative cap per logical source+context | 0.9 / 0.55 |
| context positive / negative ceiling | 3.0 / 2.5 |
| logical source positive / negative ceiling | 6.0 / 5.0 |
| surface diversity bonus / total cap | 0.1 per additional form / 0.3 |
| practice strength threshold | 1.5 |
| consolidation strength threshold | 6.0 |

Generic contributions are multiplied by association and temporal relevance;
indirect recognized/produced/confirmation/missed events also use the indirect
factor. Reviews additionally use the unspecified-modality factor. All historical
reviews are kept and counted, even though their associated lexical interpretation
is discounted. Missing/uncertified historical note text is never silently upgraded.
Quarantined source reviews have no item links and are not interpreted lexically.

Recency is deliberately slow:

```text
0.6 + 0.4 × 2^(-age_days / 365)
```

This retains at least 60% of old contribution. Future-dated events are excluded;
naive timestamps fail explicitly. Ingestion exposure time is observation time,
not proof of comprehension on that date. Old exposure remains presented, and no
manual consolidated status is downgraded.

Repeated review signal uses `n / (n + 5)`, where n is the sum of quality-weighted
positive/negative signals within a logical source+context. The most recent Again
boosts that group's negative signal by 1.5. Subsequent consecutive Good/Easy
signals attenuate prior negative signal by 0.75 per event, capped at three
recovery events. Ordering uses actual timestamp plus event key; it is preserved
as contextual sequence, never interpreted as individual-word failure/recovery.

Source/context aggregate ceilings are both applied. Identical normalized sentences
in different Sources share a context ceiling. Anki revisions/reverse cards share
one logical note identity; Lute page revisions share one page identity. Source
versions/events remain distinct in provenance/statistics. Surface bonus is only
available with multiple contexts and recognition or review support, and stays
inside the aggregate budgets. Multiple forms in one sentence never manufacture
multiple contexts.

### Categorical gates

- No dimension-specific observed event → unknown.
- Observed event without stronger gates → presented. Exposure-only evidence
  never goes beyond presented, however numerous.
- Practice requires strength ≥1.5 plus recognition/use or contextual reviews;
  any recent direct miss also indicates practice rather than consolidation.
- Consolidation requires **all**:
  - positive strength ≥6;
  - at least three observed contexts;
  - three directly recognized/used contexts **or** six explicitly recorded
    contextual recognition/use contexts;
  - at least two logical sources, unless three direct contexts independently
    satisfy the diversity exception;
  - negative strength ≤20% of positive strength;
  - no direct miss in the preceding 45 days.
- Anki reviews never count towards the recognition-context gate.

Default confidence is low. Explicit recognition plus ≥3 contexts and ≥6 events
can provide medium confidence; ≥6 recognized contexts with adequate association
quality can provide high confidence. Review-supported practice/presentation with
≥3 observed contexts is at most medium. Historical associations cap high
confidence unless ≥6 reliable direct contexts independently support it. When all
observed evidence has temporal relevance below 0.8, high confidence is reduced
to medium. These reliability rules are distinct from status gates.

Context identity is deterministic: NFKC, case folding, punctuation-to-space and
collapsed whitespace, then SHA-256. It is not semantic similarity. Missing context
text contributes no context diversity. Summary counts distinguish events,
occurrences, physical Sources, logical sources, contexts, source types, surfaces,
notes/cards and indirect review events. Counts are provenance, never successes.

## Services, CLI and export

```python
from lute_korean_parser.learner_state.engine import LearnerStateEngine
from lute_korean_parser.learner_state.policy import LearnerStatePolicyV1

engine = LearnerStateEngine(session)
engine.inspect("먹다")
engine.calculate(kind="grammar")
engine.calculate(item_id="<stable knowledge UUID>")
engine.calculate()  # Recalculate all, zero writes.
engine.compare()
engine.export()  # No raw reviews or internal strengths by default.
```

A caller owns its transaction. SQLite calculation explicitly begins a consistent
read transaction when needed. Read-only CLI opens `mode=ro`; repository queries
are batched and do not depend on the number of items. Generic Knowledge-only
installations work without Anki tables.

Install the updated plugin to register the new command:

```sh
python -m pip install -e plugins/lute-korean
lute-korean-state inspect 먹다 --database /path/to/migrated-staging.db
lute-korean-state inspect --database /path/to/migrated-staging.db -- "-(으)면"
lute-korean-state calculate --database /path/to/migrated-staging.db --kind grammar
lute-korean-state compare --database /path/to/migrated-staging.db
lute-korean-state calibrate --database /path/to/migrated-staging.db --count 25 --export calibration.json
```

The `--` in the grammar example protects a leading hyphen from CLI option parsing.
`--json` emits JSON for inspection; `--as-of` accepts a timezone-aware ISO timestamp;
`--policy policy.json` supplies dataclass parameter overrides; the version plus
fingerprint records the exact configuration. Use a new version label for a revised
policy. `--diagnostics` explicitly includes internal strength values. No command
writes manual states, Evidence or suggestions to the database. `--export` writes
only a separate JSON file and refuses to overwrite the database.

Calibration selects 25 lexical items by deterministic frequency/Again/surface
strata plus all grammar items. It never uses manual labels to select samples or
fit thresholds. Review [LEARNER_STATE_CALIBRATION.json](LEARNER_STATE_CALIBRATION.json)
and [LEARNER_STATE_VALIDATION.md](LEARNER_STATE_VALIDATION.md) before relying on
suggestions for planning.

The existing export remains unchanged unless explicitly requested:

```python
KnowledgeService(session).export(include_learner_state=True)
```

The opt-in extension adds manual/suggested states, overall suggestion, comparison,
learner evidence summary and policy/snapshot metadata. It omits raw review history
and internal strength by default. `include_anki`/`review_details` retain their
previous independent behavior.

Manual assessment already has an explicit service operation:

```python
KnowledgeService(session).set_status(item_id, "practicing", dimension="reading")
session.commit()  # Only when the caller intentionally authorizes this assessment.
```

This operation was not invoked against real data during Sprint 4 validation.
Merely changing a manual label cannot change computed evidence gates; it only
changes comparison and special future visibility.

## Limitations and next boundary

V1 is a conservative heuristic for orienting future input selection, not a
scientific measurement of actual acquisition or a recommendation algorithm.
The real collection currently has no explicit lexical recognition/use, listening,
production or dimensional manual assessments. Suggested practice is contextual
familiarity, not demonstrated comprehension. No real item is consolidated by
historical sentence reviews alone.

Source/context caps reduce repetition, not semantic aliasing. Near-identical
sentences still count separately; no embeddings or LLM are used. Old contaminated
imports require explicit reconciliation/rebuild before calculation. The engine
uses canonical item links and never reintroduces raw 좋아하다 components.

Human calibration is still pending. Policies can be replaced and recomputed with
unchanged Evidence; future input-selection consumers should inspect manual state,
confidence, warnings and weak dimensions together. No CI scoring, podcast search,
recommendations, TPRS ingestion, UI, automatic apply, Anki writes or Sprint 5 was
implemented.
