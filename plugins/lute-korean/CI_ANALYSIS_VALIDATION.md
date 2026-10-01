# CI Analysis Policy V1 validation

## Verdict

**YES** — useful as cautious guidance for choosing supplied Korean input. This is
a heuristic reading/transcript analysis, not a scientific measurement of comprehension.
No Sprint 6 features were implemented.

## Policy

Version: `ko.ci-analysis.v1`. Thresholds were specified from evidence/category
semantics before viewing real episode results. They were not fitted to manual
judgments or forced into episode order.

Parameter fingerprint: `be113a87005f95b382b183f4addc9f5aae0e797127ee7e96f29053266240b45e`.

```json
{
  "version": "ko.ci-analysis.v1",
  "strong_familiar_weight": 0.0,
  "familiar_weight": 0.0,
  "seen_weight": 0.45,
  "deferred_weight": 1.2,
  "unassessed_weight": 1.0,
  "untracked_weight": 1.0,
  "proper_noun_factor": 0.25,
  "proper_noun_segment_cap": 0.75,
  "grammar_factor": 1.5,
  "low_confidence_support_penalty": 0.15,
  "support_uncertainty_segment_cap": 0.3,
  "light_threshold": 0.2,
  "stretch_threshold": 1.5,
  "segment_dense_threshold": 3.0,
  "segment_dense_ratio": 0.45,
  "segment_absolute_dense": 6.0,
  "fit_dense_segment_ratio": 0.35,
  "fit_dense_streak": 3,
  "fit_stretch_segment_ratio": 0.3,
  "fit_weak_unique_ratio": 0.4,
  "fit_low_support_ratio": 0.65,
  "fit_weak_grammar_ratio": 0.5,
  "fit_grammar_mean_load": 0.6,
  "medium_confidence_ratio": 0.5,
  "high_confidence_ratio": 0.75,
  "manual_confidence": "medium",
  "hardest_limit": 10,
  "novelty_limit": 20,
  "compact_item_limit": 20,
  "compact_cluster_limit": 10,
  "compact_text_limit": 160
}
```

Interpretation/combination/order are documented in [CI_ANALYSIS.md](CI_ANALYSIS.md).
Numeric load is heuristic evidence-based linguistic burden, not mastery probability.

## Synthetic cases

Sandbox-only manual assessments/fake Anki evidence; approved staging was untouched.

| Case | Scenario | Fit | Confidence | Segment loads 0/1/2/3 |
|---|---|---|---|---|
| A | Familiar sentence | comfortable | medium | 1/0/0/0 |
| B | Four distributed novelties | productive | medium | 0/4/0/0 |
| C | Same four novelties, same supported link count, clustered | stretch | medium | 3/0/0/1 |
| D | Many unknown proper names | productive | low | 0/1/0/0 |
| E | Familiar lexical items, unassessed tracked grammar | stretch | medium | 0/0/1/0 |
| F | 먹고 싶어요 lexical/grammar overlap | stretch | medium | 0/0/1/0 |
| G | Only fake Anki indirect familiarity (120 sentence reviews) | comfortable | medium | 1/0/0/0 |
| H | Podcast transcript, no listening evidence | comfortable | medium | 1/0/0/0 |

B and C have four untracked links and the same familiar lexical link count.
B is productive; C has one dense cue and becomes stretch. D stays productive
despite many names, retaining their roles/states instead of calling them known.
F suppresses only the 싶다 component covered by -고 싶다; outside-span 싶다 remains.
G is comfortable but only medium confidence; repeated indirect reviews do not
produce high certainty. H calculates transcript fit, with listening_fit set to
insufficient_evidence. Explicit manual reading/future precedence, unknown-vs-
untracked, finite policy parameters, foreign-only input, unchanged status,
distinct occurrence/unique coverage and zero-write/bounded-query contracts have
separate regression tests.

## Real learner snapshot

Approved clean Sprint 4.5 staging:
`/tmp/lute-sprint-4-5/verified/staging.db`.

SHA-256: `c590f7050a3bf985943ab1917ed5a3a077a1befe488e1d6ab21f22c1e26830f0`.

352 lexical + 5 grammar items; 3,117 occurrences; 6,055 preserved Anki reviews.
Reading suggestions: 188 presented, 164 practicing; five grammar practicing.
No artificial human Evidence was added, no statuses applied and no Anki call
was necessary. Listening and production remain unobserved.

Learner policy unchanged: `ko.learner-state.v1`, fingerprint
`94819404fd433591b54a9cc1e5b132065c7f35bbe19bc1f88077dcfcef0f24f3`. Learner policy file SHA-256
`7849d57654f21f617a403e1838c15b41e2ab1b22583a308b77b89d135569d8a6`.

As-of: `2026-09-30T21:40:56.761638+00:00`. Input/evidence/role-relation fingerprints
are retained in [CI_TPRS_COMPARISON.json](CI_TPRS_COMPARISON.json).

## Real TPRS comparison

Read-only originals at Windows `C:\Users\davis\OneDrive\Documentos\tprs`,
accessed through `/mnt/c/Users/davis/OneDrive/Documentos/tprs`. All seven files
have a title followed by Time/Subtitle/Machine Translation tabular data. The
adapter selects only Subtitle; translations/title are metadata. Regression
tests use even a Korean translation/title to prove they cannot contaminate
lexical matching. All real files parsed as TPRS without format warnings.

| Episode | Segments | Fit | Confidence | Supported occurrences | Previously seen | Untracked occurrences | Loads 0/1/2/3 | Seconds |
|---|---:|---|---|---:|---:|---:|---|---:|
| EP1 | 147 | stretch | medium | 57.6% | 64.9% | 35.1% | 34/99/10/4 | 2.178 |
| EP2 | 177 | stretch | medium | 53.4% | 60.7% | 39.3% | 30/106/36/5 | 0.058 |
| EP3 | 151 | stretch | low | 40.8% | 49.1% | 50.9% | 21/57/66/7 | 0.054 |
| EP4 | 177 | stretch | medium | 70.4% | 87.3% | 12.7% | 85/82/8/2 | 0.059 |
| EP5 | 121 | productive | medium | 76.4% | 91.9% | 8.1% | 64/46/11/0 | 0.061 |
| EP6 | 120 | stretch | medium | 69.9% | 87.6% | 12.4% | 51/56/10/3 | 0.046 |
| EP7 | 115 | stretch | medium | 69.3% | 84.7% | 15.3% | 43/58/11/3 | 0.050 |

Fit distribution: productive 1; stretch 6; comfortable 0; dense 0. Confidence:
medium 6; low 1. No monotonic episode progression was assumed. CLI comparison
ordered EP5, EP4, EP6, EP7, EP1, EP2, EP3. Ordering within one category uses dense
segment fraction, then untracked occurrence fraction; this is deterministic
comparison of supplied content, not external recommendations.

EP1/EP2 have substantial untracked unique vocabulary despite repeated familiar
phrases. EP3 has frequent family vocabulary absent from the snapshot. EP4 has
high familiar support, but isolated dense cues still make its overall label
stretch under this conservative V1. EP5 offers repeated canonical 좋아하다 and
few concentrated novelties. Previously studied content may still appear stretch
because its actual recognition was never explicitly recorded. No thresholds
were changed to hide this difference.

### EP1

Lexical occurrence distribution: familiar: 274, seen: 35, untracked: 167.
Unique-item distribution: familiar: 25, seen: 4, untracked: 29.

Detected grammar: none of the five supported patterns.

Top novelty/reinforcement opportunities: 아니요 ×13 (seen, 11 contexts), 여러분 ×7 (untracked, 6 contexts), 모두 ×6 (untracked, 6 contexts), 자 ×5 (untracked, 3 contexts), 마법사 ×4 (untracked, 3 contexts).

Recycling: 사람 ×109, 이 ×72, 네 ×12, 한국 ×11, 고양이 ×10.

Hardest samples:

- 9:45: `여러분 우리 이번 시간에 '톰이에요' '톰이 아니에요'` — load 3; 3 untracked/unassessed/deferred general lexical links; 0 previously presented links; 0 weak detected tracked-grammar links; Proper names remain visible with reduced, capped segment influence.
- 5:22: `여러분 알면은 댓글에 알려 주세요.` — load 3; 3 untracked/unassessed/deferred general lexical links; 0 previously presented links; 0 weak detected tracked-grammar links.

Dense cues: 2.7%; longest difficult cluster: 3 cues.

### EP2

Lexical occurrence distribution: familiar: 310, seen: 42, untracked: 228.
Unique-item distribution: familiar: 47, seen: 20, untracked: 54.

Detected grammar: -는데 ×1 (familiar), -아/어서 ×1 (familiar).

Top novelty/reinforcement opportunities: 수염 ×38 (untracked, 31 contexts), 머리카락 ×18 (untracked, 16 contexts), 머리 ×18 (untracked, 15 contexts), 우산 ×9 (seen, 6 contexts), 아니요 ×7 (seen, 5 contexts).

Recycling: 있다 ×78, 없다 ×43, 이 ×23, 누구 ×16, 태웅 ×14.

Hardest samples:

- 8:31: `'제이슨과 태웅이' = '제이슨이랑 태웅이' 똑같아요.` — load 3; 5 untracked/unassessed/deferred general lexical links; 0 previously presented links; 0 weak detected tracked-grammar links.
- 8:40: `'제이슨[과] 태웅이'는 글을 쓸 때` — load 3; 4 untracked/unassessed/deferred general lexical links; 0 previously presented links; 0 weak detected tracked-grammar links; Proper names remain visible with reduced, capped segment influence.

Dense cues: 2.8%; longest difficult cluster: 7 cues.

### EP3

Lexical occurrence distribution: familiar: 211, seen: 43, untracked: 263.
Unique-item distribution: familiar: 34, seen: 10, untracked: 70.

Detected grammar: -아/어서 ×5 (familiar), -는데 ×1 (familiar).

Top novelty/reinforcement opportunities: 언니 ×23 (untracked, 17 contexts), 매기 ×20 (untracked, 13 contexts), 오빠 ×19 (untracked, 14 contexts), 형 ×18 (seen, 13 contexts), 여자 ×12 (untracked, 11 contexts).

Recycling: 있다 ×31, 이 ×25, 태웅 ×22, 누나 ×16, 저 ×13.

Hardest samples:

- 5:09: `'여자 동생' 줄여서 '여동생', 여동생이에요.` — load 3; 5 untracked/unassessed/deferred general lexical links; 0 previously presented links; 0 weak detected tracked-grammar links.
- 4:22: `'남자 동생' 줄여서 '남동생'이라고 해요.` — load 3; 4 untracked/unassessed/deferred general lexical links; 0 previously presented links; 0 weak detected tracked-grammar links.

Dense cues: 4.6%; longest difficult cluster: 8 cues.

### EP4

Lexical occurrence distribution: familiar: 409, seen: 98, untracked: 74.
Unique-item distribution: familiar: 49, seen: 17, untracked: 32.

Detected grammar: -(으)면 ×6 (familiar), -고 싶다 ×1 (familiar), -아/어서 ×1 (familiar).

Top novelty/reinforcement opportunities: 하늘 ×13 (seen, 10 contexts), 오페라 ×9 (seen, 7 contexts), 하우스 ×9 (seen, 7 contexts), 아니요 ×8 (seen, 7 contexts), 여러분 ×6 (untracked, 6 contexts).

Recycling: 있다 ×126, 어디 ×27, 부산 ×24, 한국 ×21, 태웅 ×17.

Hardest samples:

- 1:39: `좀비들이 막, 왁! 나와요.` — load 3; 4 untracked/unassessed/deferred general lexical links; 0 previously presented links; 0 weak detected tracked-grammar links.
- 10:23: `BTS는 어느 나라 사람(들)이에요?` — load 3; 3 untracked/unassessed/deferred general lexical links; 0 previously presented links; 0 weak detected tracked-grammar links.

Dense cues: 1.1%; longest difficult cluster: 2 cues.

### EP5

Lexical occurrence distribution: familiar: 331, seen: 67, untracked: 35.
Unique-item distribution: familiar: 58, seen: 21, untracked: 19.

Detected grammar: -는데 ×2 (familiar), -(으)면 ×1 (familiar), -아/어서 ×1 (familiar).

Top novelty/reinforcement opportunities: 북극곰 ×7 (seen, 4 contexts), 그러면 ×6 (untracked, 6 contexts), 버거 ×6 (seen, 3 contexts), 치즈 ×6 (seen, 3 contexts), 팔다 ×6 (seen, 3 contexts).

Recycling: 좋아하다 ×89, 고양이 ×15, 안 ×14, 상자 ×14, 저 ×13.

Hardest samples:

- 0s: `자 여러분 안녕하세요.` — load 2; 2 untracked/unassessed/deferred general lexical links; 1 previously presented links; 0 weak detected tracked-grammar links.
- 11s: `여러분 우리 episode 2, 두 번째 시간에 '있어요' '없어요' 했어요.` — load 2; 2 untracked/unassessed/deferred general lexical links; 1 previously presented links; 0 weak detected tracked-grammar links.

Dense cues: 0.0%; longest difficult cluster: 2 cues.

### EP6

Lexical occurrence distribution: familiar: 292, seen: 74, untracked: 52.
Unique-item distribution: familiar: 47, seen: 19, untracked: 24.

Detected grammar: -고 싶다 ×1 (familiar).

Top novelty/reinforcement opportunities: 그러면 ×9 (untracked, 9 contexts), 여러분 ×8 (untracked, 8 contexts), 언제 ×7 (seen, 5 contexts), 떡볶이 ×6 (seen, 6 contexts), 고기 ×6 (seen, 5 contexts).

Recycling: 먹다 ×88, 초밥 ×23, 안 ×15, 이 ×14, 음식 ×14.

Hardest samples:

- 12s: `여러분 우리, 지난 시간에` — load 3; 3 untracked/unassessed/deferred general lexical links; 0 previously presented links; 0 weak detected tracked-grammar links.
- 6:40: `오징어튀김, 새우튀김.. 튀김이에요.` — load 3; 5 untracked/unassessed/deferred general lexical links; 0 previously presented links; 0 weak detected tracked-grammar links.

Dense cues: 2.5%; longest difficult cluster: 4 cues.

### EP7

Lexical occurrence distribution: familiar: 271, seen: 60, untracked: 60.
Unique-item distribution: familiar: 51, seen: 19, untracked: 31.

Detected grammar: -아/어서 ×6 (familiar), -(으)면 ×1 (familiar), -고 싶다 ×1 (familiar).

Top novelty/reinforcement opportunities: 샌드위치 ×8 (untracked, 7 contexts), 떡볶이 ×8 (seen, 6 contexts), 친척 ×6 (seen, 6 contexts), -아/어서 ×6 (familiar, 5 contexts), 돈가스 ×6 (seen, 5 contexts).

Recycling: 가다 ×47, 집 ×22, 이 ×17, 있다 ×17, 먹다 ×16.

Hardest samples:

- 5:18: `우리 지난 시간에 '샌드위치/돈가스/떡볶이를 먹었어요' 얘기했어요.` — load 3; 3 untracked/unassessed/deferred general lexical links; 3 previously presented links; 0 weak detected tracked-grammar links.
- 5:08: `양고기 집의 이름은 '줘마양다리구이 본점'이에요. 최고` — load 3; 3 untracked/unassessed/deferred general lexical links; 1 previously presented links; 0 weak detected tracked-grammar links.

Dense cues: 2.6%; longest difficult cluster: 2 cues.

## Overlap, proper nouns and suspicious representation

Raw/effective/suppression records retain span and reasons. Existing desire
component relations suppress 싶다 only inside the detected -고 싶다 span, including
when a candidate item is not yet stored. 먹다 remains effective. Other auxiliary
spans retain warnings and their raw links; same-span components contribute the
maximum load instead of independent summed novelty.

Multiword names such as 캡틴 아메리카 keep one projected name span. 서울/부산 remain
visible and important; their influence is separated/reduced, not erased. Real
TPRS roles follow stored overrides or Kiwi NNP signals; they are not comprehensive
NER. 매기 in EP3 is analyzed as general in some contexts, illustrating imperfect
proper-name classification. This remains an explicit limitation, not a new
dictionary rule fitted to the episode. Foreign Netflix/BTS or English headings
do not become Korean lexical matches under existing eligibility.

Other suspicious/missing modeling: 자 as a discourse expression; incomplete
family-name/compound segmentation; quoted grammatical teaching explanations;
unmodeled auxiliaries and grammar outside the five detectors. Cue boundaries
can divide constructions across subtitles. Such diagnostics do not automatically
create new pedagogical grammar or claim exact independent difficulty.

## Performance

Python 3.14.4, Kiwi/kiwipiepy 0.23.2, Linux/WSL; plugin 0.3.0, Lute 3.4.2+;
same environment as previous validation. All figures are local measurements.

Snapshot: 1.140 s. First episode: 2.178 s including
cold singleton Kiwi initialization. Subsequent episodes: 0.046–0.061 s each.
One analysis call per cue: 147/177/151/177/121/120/115; total 1,008.
No extra analysis for grammar, matching, overlap or exports.

Throughput benchmark uses five representative sentences (present, conditional,
future, causal, desire/contrast), repeated without application-level analysis
caching. It is not a worst-case benchmark of 20k distinct unknown words.
Model initialization is measured separately; JSON serialization is outside the
timed analysis and compact byte count uses UTF-8 non-pretty JSON.

| Words (whitespace units) | Segments / Kiwi calls | Analysis seconds | Compact bytes |
|---:|---:|---:|---:|
| 5,000 | 1,000 | 0.432 | 21,866 |
| 20,000 | 4,000 | 1.958 | 21,881 |

Snapshot SQL: 10 SELECTs + 2 read-only PRAGMAs + a read transaction BEGIN.
Exactly the same counts after seven real analyses plus 5k/20k benchmarks;
there is no query per token/item/segment and no SQL in overlap resolution.

## Integrity

Staging, principal DB and seven Windows input files had identical SHA-256
before/after. No INSERT/UPDATE/DELETE/DDL was emitted; BEGIN was the only
non-SELECT/non-PRAGMA statement. The CLI also opened SQLite mode=ro and exported
to a separate file. Tests observe statement verbs and verify unchanged byte
hashes for analyze, compare and JSON export. No Source/item/exposure/review
creation, no manual status changes and no Anki calls occurred.

## Tests

New Sprint 5 suite: 26 tests, adapters and real-format title/unit timing, canonical
identities, scoped overlap, roles, manual precedence, unknown/untracked, coverage,
recycling, foreign content, concentration, confidence, policy validation,
noncontiguous cue identity, explicit write/query checks and CLI exports.

Relevant integrated suite: **439 passed, 1 deselected in 76.00 s**.
Includes all plugin Sprint 1/2/3/3.6/4/4.5/5 tests; Lute parse except Japanese,
language, reading, book, database setup and ORM Term/Language/Text.

Separate Japanese/MeCab environmental check: **6 failed** because mecab-config /
libmecab.so are unavailable, including the Japanese-dependent Term case. That
case was the one deselected from the relevant suite. These environmental failures
are recorded separately; they were not caused or hidden by this implementation.
Wheel built offline; CLI installed/run against real files; compileall and
pylint error/fatal checks completed.

## Files changed in this sprint

- `lute_korean_parser/ci/__init__.py`
- `lute_korean_parser/ci/models.py`
- `lute_korean_parser/ci/adapters.py`
- `lute_korean_parser/ci/snapshot.py`
- `lute_korean_parser/ci/policy.py`
- `lute_korean_parser/ci/analyzer.py`
- `lute_korean_parser/ci/export.py`
- `lute_korean_parser/ci/cli.py`
- `lute_korean_parser/knowledge/projection.py` (shared pure extraction)
- `lute_korean_parser/knowledge/ingestion.py` (consume shared projection)
- `lute_korean_parser/knowledge/representation.py` (shared pure span resolver)
- `tests/test_ci.py`
- `pyproject.toml` (CLI entry point)
- `README.md`
- `CONTEXT.md`
- `KNOWLEDGE.md`
- `CI_ANALYSIS.md`
- `CI_ANALYSIS_VALIDATION.md`
- `CI_TPRS_COMPARISON.json`

Prior uncommitted sprint work/private docker data were preserved. No core Lute,
parser/rendering, normalization rule, grammar detector, LearnerStatePolicyV1
or database migration was changed.

## Artifacts and reproduction

Versioned episode summaries: [CI_TPRS_COMPARISON.json](CI_TPRS_COMPARISON.json).
Full local reports with raw/effective/morphology and all segment diagnostics:
`/tmp/lute-ci-validation/tprs_1.json` through `tprs_7.json`; compact comparison
`/tmp/lute-ci-validation/tprs-comparison.json`; CLI full comparison
`/tmp/lute-ci-validation/cli-comparison.json`; timing/hashes in `metrics.json`;
mixed benchmark in `mixed-benchmark.json`; sandbox cases in `synthetic.json`.
Temporary validation artifacts/staging may not survive environment cleanup.

```sh
lute-korean-ci compare /mnt/c/Users/davis/OneDrive/Documentos/tprs/tprs_{1,2,3,4,5,6,7}.txt \
  --format tprs --kind tprs --database /tmp/lute-sprint-4-5/verified/staging.db \
  --compact --export /tmp/tprs-comparison.json
```

## Remaining limitations

Only five grammar detectors, lemma polysemy, imperfect proper-name recognition,
compound/auxiliary modeling and cue segmentation; no deterministic chunk matching
in this version. Coverage is not comprehension. Much familiarity is based on
indirect sentence-level Anki evidence, with historical association uncertainty.
Single dense cue makes overall fit conservatively stretch. Inspect reasons and
hardest timestamps. No listening fit, audio difficulty, semantic similarity or
automatic study/promotion/recommendation is inferred.

The verdict concerns practical input guidance only. It does not certify that
the learner understands a given episode, and does not implement Sprint 6.
