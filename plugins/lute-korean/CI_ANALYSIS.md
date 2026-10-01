# Candidate comprehensible input analysis

Sprint 5 adds deterministic **linguistic fit guidance**, not a measurement of
comprehension. Analyzing or opening a candidate does not mean studying it.
`ko.ci-analysis.v1` never creates Knowledge Items, Sources, Occurrences, Evidence,
or applies statuses. Anki is not contacted. All input is local.

## Architecture and domain

Adapters produce ephemeral `CandidateContent` and `CandidateSegment` objects:
identity/index, cleaned Korean text, original-content hash, time bounds and
metadata. Original subtitle/title/translation presentation stays provenance.
Offsets in candidate links refer to **clean segment text**, not file byte offsets.
No persisted IDs are needed for candidate occurrences or matches; tracked matches
retain the existing Knowledge Item ID, while untracked identities remain local.

Pipeline:

1. Format adapter → segments.
2. One existing `KoreanParser.analyze()` per segment; its singleton Kiwi model is
   reused. The existing normalizer, eligibility policy and grammar detectors run
   through `KnowledgeIngestionService.preview()` without a repository.
3. Shared pure `project_lexical_units()` preserves canonical heads, foreign
   metadata and multiword proper-name source spans. Persistent ingestion uses
   this same projection; no second identity algorithm was added.
4. One batched learner-state/role/relation snapshot → identity dictionary lookup.
5. Shared pure, span-scoped `resolve_effective_rows()` → raw/effective/suppressed
   links. The existing declared desire component can also be resolved if its
   items are not yet persisted. No relation is inserted.
6. CI policy → segment loads, distributions, clusters, explanations and export.

The analyzer, snapshot and report/export seams are separate from persistence.
There are no migrations or changes to parser rendering, detectors, lexical rules
or LearnerStatePolicyV1.

## Installation and commands

Install the updated plugin in the same Python environment as Lute:

```sh
python -m pip install -e plugins/lute-korean
lute-korean-ci analyze text.txt --database /path/to/approved-staging.db
lute-korean-ci analyze episode.srt --database /path/to/approved-staging.db
lute-korean-ci analyze transcript.txt --format tprs --kind tprs --database staging.db
lute-korean-ci analyze --text '한국에 가면 많이 먹을 거예요.' --database staging.db
lute-korean-ci analyze podcast.vtt --kind podcast --compact --database staging.db
lute-korean-ci compare episode1.txt episode2.txt episode3.txt --database staging.db
lute-korean-ci analyze text.txt --database staging.db --json --export report.json
```

`--compact` emits bounded JSON without full segment inventories, raw morphology,
or raw reviews; omitted detail/limits are explicit. `--export` writes only the
requested output file. It rejects database/input paths and database sidecars,
including aliases to the same file. `--as-of` accepts a timezone-aware ISO clock
for reproducible learner interpretation. Database connections use SQLite
`mode=ro`; commands do not run migrations or perform temporary writes/rollback.
An existing migrated database is required. `compare` analyzes only supplied
files, reusing one snapshot and Kiwi model. Its ordering is a diagnostic ordering,
not a search or external recommendation engine.

Windows files mounted in WSL can be read directly:

```sh
lute-korean-ci analyze '/mnt/c/Users/davis/OneDrive/Documentos/tprs/tprs_5.txt' \
  --format tprs --kind tprs --database /tmp/lute-sprint-4-5/verified/staging.db
```

Programmatic API: construct `CIContentAnalyzer(session)` once, then call
`analyze_text(text, name=..., format=..., kind=...)` or `analyze(candidate)`.
`CILearnerSnapshot` can be reused explicitly. Applications should supply a
read-only session and refresh the snapshot after learner data changes.

## Formats

- UTF-8 plain text: nonempty lines and punctuation-delimited sentences.
- Timestamp transcript: unmistakable leading `[00:01]` or `00:01` timestamps.
- SRT: cue IDs, start/end and original Korean subtitle text; cue numbers/settings
  never enter the linguistic text.
- VTT: WEBVTT/NOTE/STYLE/REGION blocks and cue settings are technical metadata.
- TPRS: exact `Time | Subtitle | Machine Translation` or tab-separated headers,
  optionally preceded by a title. The **Subtitle column alone** is analyzed.
  Translation remains metadata, even if it itself contains Korean. Real files
  with `2s`, `1m 13s` and `10:18` timestamps are supported.

HTML presentation, sound markup, inline VTT timing and explicit `speaker:` labels
are cleaned, retaining changed original text as metadata. Foreign names/text
remain unlinked foreign surface metadata under existing lexical eligibility.
Audio presence never establishes listening ability. Auto detection uses safe
headers/extension/structure; ambiguous or malformed formats fall back to plain
with a warning. Inspect such warnings and specify/correct the format before
trusting its linguistic result: the fallback preserves text rather than guessing
which ambiguous column is Korean. Files are never rewritten.

## Learner state precedence and categories

1. An explicitly recorded manual **reading** assessment wins.
2. Otherwise manual overall `future` is deliberately deferred.
3. Otherwise use the suggested reading state/confidence.
4. Absent Knowledge Item → `untracked`.

Default overall `unknown` is not a human reading assessment. Nonfuture overall
statuses do not imply an observed skill dimension. An explicit reading assessment
also wins over an overall future flag. Manual assessments without a separate
confidence field receive medium classification confidence under this CI policy;
this is not an invented evidence event.

| Bucket | Interpretation |
|---|---|
| strong_familiar | consolidated |
| familiar | practicing/contextual support |
| seen | presented; observed exposure, understanding not established |
| deferred | manual future; intentionally postponed |
| unassessed | tracked item, but its effective reading state is unknown |
| untracked | identity absent from the Knowledge Model; not proof of ignorance |

Confidence remains separate. `supported = strong_familiar + familiar`;
`previously_seen = supported + seen`. Reports show effective lexical **link
occurrences** and **unique identities** separately. These descriptive percentages
are neither percentage learned nor probability of comprehension. A compound may
still produce multiple links; its segment load is not their naive sum.

## Policy V1

Exact parameters/fingerprint are exported and recorded in
[CI_ANALYSIS_VALIDATION.md](CI_ANALYSIS_VALIDATION.md). These are heuristic load
units, not statistically validated probabilities:

- Lexical weights: strong_familiar/familiar 0; seen .45; unassessed/untracked 1;
  deferred 1.2.
- Multiple lexical heads sharing the same source span contribute their **maximum**
  novelty weight, rather than multiple independent difficulties. Unmodeled
  auxiliary/compositional cases remain visible with warnings.
- Proper nouns/foreign names contribute .25 of ordinary lexical weight, with a
  .75 per-segment cap. Their full items/states/coverage remain visible separately.
  Names such as 서울/한국 are not judged unimportant or automatically familiar.
- Detected grammar contributes 1.5 times its bucket weight. Reading support with
  low confidence adds .15 uncertainty per link, capped at .3 per segment.
- Weighted density divides total load by ordinary lexical spans + .25 name spans
  + 1.5 grammar occurrences. Load 3 is ≥6, or ≥3 with density ≥.45; load 2 is
  otherwise ≥1.5; load 1 is otherwise >.2; load 0 is the remainder.
- Content `dense`: ≥35% of eligible segments dense, or ≥3 consecutive dense cues.
- Otherwise `stretch`: any dense segment; or ≥30% at load 2–3; or ≥40% weak
  unique general lexical identities together with <65% supported general lexical
  occurrences; or ≥50% weak detected grammar with mean load ≥.6.
- Otherwise `productive`: at least one segment with actual novelty load >.2.
  Otherwise `comfortable`. No eligible items → unavailable fit (`null`).

Weak means untracked/unassessed/deferred. Fit uses eligible segments for its
ratios; exported segment distributions also show empty/foreign cues. Cue
segmentation therefore matters, especially for dense streaks. A single hard cue
makes the overall label conservatively stretch; inspect its timestamp rather
than treating the whole material as equally difficult.

Fit confidence weights proper-name contribution and checks item confidence:
≥75% high permits high only without historical/indirect or format/representation
warnings; otherwise ≥50% medium/high gives medium, else low. Historical/indirect
Anki associations cap high at medium. Confidence is reliability of this fit
classification, not how skilled the learner is. No manual labels were used to
fit the thresholds to real episodes.

## Reports and scope

Reports include lexical occurrence/unique distribution, supported/seen coverage,
separate general/name novelty, tracked grammar counts, segment loads, consecutive
dense/difficult ranges, longest difficult cluster and total novelty load. Top ten
hardest segments keep timestamps and reasons. Frequency/context-ranked novelties,
practicing recycling and presented-item opportunities keep surfaces and samples.
No novelty automatically becomes an Anki task. Compact exports bound inventories,
text snippets and clusters; full JSON remains available explicitly.

`먹고 싶어요` retains raw 먹다/싶다/-고 싶다 and suppression provenance; effective
load uses 먹다/-고 싶다. Unrelated 싶다 in another span remains visible.

Only five tracked pedagogical grammar detectors exist. Unmodeled endings remain
morphology diagnostics, **not automatically unknown grammar**. Even full coverage
of detected patterns does not mean full Korean grammar coverage. Existing chunks
are not mined and candidate chunk matching is currently omitted.

Podcast mode reports `transcript_fit`, never audio difficulty; `listening_fit` is
`insufficient_evidence`. V1 does not estimate listening suitability even if a
future learner snapshot contains listening evidence. Text familiarity cannot
account for speed, accent, pronunciation or recognition without the transcript.

Limits: lemma polysemy (배), imperfect Kiwi segmentation/proper-name classification,
auxiliaries (물어봐도), noun+하다/numeral/compound representation, sentence/cue
boundaries, incomplete grammar, indirect learner evidence and conservative labels.
The report guides human choice; it does not certify understanding.
