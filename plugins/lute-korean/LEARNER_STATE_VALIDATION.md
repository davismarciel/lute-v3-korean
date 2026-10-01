# Learner State Policy V1 validation

Date: 2026-09-30. Scope: Sprint 4; suggestions and human inspection only.

## Verdict

**YES** — Policy V1 is pedagogically reasonable enough to **orient future comprehensible-input selection**, with manual state authoritative and explicit confidence/provenance warnings.

This means conservative planning support, not scientific measurement of acquisition, proof of comprehension, a recommendation system, or a validated learner level. Human review of the calibration sample is still pending. There is no auto-apply or Sprint 5 implementation.

## Policy

Architecture and exact parameters/gates are documented in [LEARNER_STATE.md](LEARNER_STATE.md). The implemented policy was based on evidence semantics and synthetic cases before inspecting the real distribution; no threshold was tuned to reproduce manual labels or make collection counts look attractive.

- Policy version: `ko.learner-state.v1`.
- Parameter fingerprint: `94819404fd433591b54a9cc1e5b132065c7f35bbe19bc1f88077dcfcef0f24f3`.
- Reference time: `2026-09-30T19:07:10.816967+00:00`.
- On-demand batched snapshot; explicit export includes full parameter set, timestamps, evidence/input fingerprints. No suggestion table or new migration.
- Direct item-scoped recognition/use is stronger than contextual evidence; exposure alone is presented, never consolidated.
- Anki reviews: indirect note/card evidence, unspecified modality, repeated signal saturated and capped by logical source/context; not independent item successes.
- Conservative recency retains 60% floor with 365-day half-life for the attenuated portion.
- Historical first-observed associations use a 0.35 quality multiplier, and unspecified modality uses 0.4. All events remain counted/provenance-preserved.
- Consolidation requires recognition/use and diversity gates, not raw volume. Source/context caps, three direct or six contextual recognition contexts, strength ≥6 and no recent direct miss apply.
- Confidence reflects coverage/reliability; it can differ from pedagogical status. Future is only preserved from manual deferment.

No current review is reassigned to a reading recognition event. It only supplies bounded contextual support to an already observed reading lane. No audio-based listening inference, production inference or cross-skill transfer occurs.

## Synthetic cases

| Case | Fixture | Reading | Listening | Production |
| --- | --- | --- | --- | --- |
| A | Two exposures, no recognition | presented (low) | unknown (low) | unknown (low) |
| B | One note, 100 Good sentence reviews | presented (low) | unknown (low) | unknown (low) |
| C | Eight distinct contexts/sources/forms with direct recognition | consolidated (high) | unknown (low) | unknown (low) |
| D | Eight recognized contexts plus recent direct misses | practicing (high) | unknown (low) | unknown (low) |
| E | Strong reading, no listening events | consolidated (high) | unknown (low) | unknown (low) |
| F | Three direct confirmations in distinct contexts | consolidated (low) | unknown (low) | unknown (low) |
| G | Eight direct produced events, production only | unknown (low) | unknown (low) | consolidated (high) |

Additional public-service regressions verify:

- One note with 300 Good events never consolidates its words; two reverse cards with 200 combined events also do not consolidate by volume.
- Increasing independent recognition contexts from 1→5 has over ten times the strength impact of repeated reviews from 101→105. Both source and context ceilings remain bounded.
- Identical normalized sentences across 30 sources yield one context. Unknown context does not manufacture independent contexts.
- Different surface forms provide at most 0.3 bounded support and never create independent contexts by themselves.
- Same ratings in different chronological sequences preserve a larger contextual lapse signal when Again is latest; neither result means an individual word is unknown.
- First-observed historical review association is weaker than verified content, remains indirect and has no observed modality.
- Manual reading practicing can disagree with suggested consolidated; the official status and Evidence remain unchanged. Manual future remains visible with a computed diagnostic state.
- Policy version/parameter changes can recompute output without changing Evidence. Manual labels cannot change computed gates or calibration sample selection.
- Foreign items are excluded by the default lexical policy; canonical 좋아하다 links are used with zero new parser calls.
- Old exposure remains presented; future-dated events are excluded and naive clocks fail explicitly.
- Explicit production affects only production; generic Knowledge-only installations work without Anki tables.
- CLI read-only SQLite exports leave database bytes unchanged and reject overwriting the database.

## Real collection

Input is the **same clean staging database** validated in Sprint 3.6:

| Entity | Count |
| --- | ---: |
| Lexical Concepts | 354 |
| Grammar Patterns | 5 |
| Sources | 875 |
| Occurrences | 3,120 |
| Occurrence-item links / generic exposures | 3,307 / 3,307 |
| Canonical Anki reviews | 6,055 |

The engine made no connection to Anki and performed no sync, parsing or writes. It evaluated existing canonical associations; Anki content, the principal database, staging data and manual status were untouched.

### Suggested distribution

| Type / dimension | unknown | presented | practicing | consolidated | future |
| --- | ---: | ---: | ---: | ---: | ---: |
| lexical / reading | 0 | 189 | 165 | 0 | 0 |
| lexical / listening | 354 | 0 | 0 | 0 | 0 |
| lexical / production | 354 | 0 | 0 | 0 | 0 |
| grammar / reading | 0 | 0 | 5 | 0 | 0 |
| grammar / listening | 5 | 0 | 0 | 0 | 0 |
| grammar / production | 5 | 0 | 0 | 0 | 0 |

### Confidence distribution

| Type / dimension | low | medium | high |
| --- | ---: | ---: | ---: |
| lexical / reading | 170 | 184 | 0 |
| lexical / listening | 354 | 0 | 0 |
| lexical / production | 354 | 0 | 0 |
| grammar / reading | 0 | 5 | 0 |
| grammar / listening | 5 | 0 | 0 |
| grammar / production | 5 | 0 | 0 |

The absence of consolidated is intentional evidence semantics: the current collection supplies exposures and historically uncertain sentence-level reviews, not explicit lexical/grammar recognition/use. Frequent diversified encounters suggest practice; rare encounters suggest presentation. Listening/production remain unknown because coverage is absent. These categories do not assert that the learner lacks actual knowledge.

During development, a failing surface-diversity test revealed that the planned bonus was always clamped away. Fixing that behavior changed lexical reading from the preliminary 197 presented / 157 practicing to 189 presented / 165 practicing. No threshold or manual-label target changed. Later cap tests enforce positive-bearing source/context headroom rather than allowing a negative-only source to fund a bonus.

## Required samples

All required items below exist in staging. Every sample has official overall `unknown` and unassessed reading/listening/production manual dimensions. Listening and production suggestions are always `unknown (low)` with explicit no-evidence warnings. The following details report reading only; this shared dimensional result is not inferred from audio.

| Item | Reading suggestion | Occurrences | Sources | Contexts | Surfaces | Anki notes | Indirect reviews | Again |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 있다 | practicing (medium) | 143 | 143 | 133 | 14 | 143 | 955 | 88 |
| 먹다 | practicing (medium) | 129 | 125 | 118 | 14 | 125 | 732 | 64 |
| 좋아하다 | practicing (medium) | 109 | 96 | 95 | 7 | 96 | 589 | 17 |
| 하다 | practicing (medium) | 87 | 85 | 84 | 16 | 85 | 585 | 78 |
| 오늘 | practicing (medium) | 72 | 72 | 70 | 3 | 72 | 417 | 38 |
| 가다 | practicing (medium) | 71 | 63 | 66 | 12 | 63 | 297 | 27 |
| 공부하다 | practicing (medium) | 50 | 50 | 49 | 8 | 50 | 299 | 13 |
| 한국 | practicing (medium) | 37 | 36 | 36 | 6 | 36 | 233 | 16 |
| 한국어 | practicing (medium) | 36 | 36 | 36 | 4 | 36 | 214 | 22 |
| 친구 | practicing (medium) | 23 | 23 | 23 | 5 | 23 | 147 | 13 |
| 피곤하다 | practicing (medium) | 22 | 22 | 21 | 6 | 22 | 140 | 16 |
| 말하다 | practicing (medium) | 21 | 19 | 17 | 5 | 19 | 100 | 9 |
| 보다 | practicing (medium) | 19 | 19 | 18 | 7 | 19 | 104 | 12 |
| 많이 | practicing (medium) | 18 | 18 | 17 | 1 | 18 | 90 | 6 |
| 내일 | practicing (medium) | 17 | 17 | 17 | 3 | 17 | 92 | 2 |
| -(으)ㄹ 거예요 | practicing (medium) | 51 | 50 | 51 | 13 | 50 | 305 | 35 |
| -(으)면 | practicing (medium) | 63 | 62 | 56 | 18 | 62 | 364 | 55 |
| -고 싶다 | practicing (medium) | 55 | 54 | 53 | 24 | 54 | 295 | 26 |
| -는데 | practicing (medium) | 51 | 51 | 50 | 21 | 51 | 281 | 15 |
| -아/어서 | practicing (medium) | 56 | 56 | 56 | 17 | 56 | 278 | 28 |

### 있다

Suggested reading: **practicing / medium**. Manual reading: unassessed; overall: unknown.

Evidence: 143 occurrences, 143 physical / 143 logical sources, 133 contexts, 14 forms; 955 indirect reviews, all 955 historically uncertain.

Reasons:

- 143 dimension-specific events; 133 distinct contexts; 143 logical sources
- 0 directly recognized/used contexts; 0 total recognition/use contexts
- 14 observed surface forms; conservative temporal weighting retains older exposure
- 955 sentence-level Anki events provide capped contextual support
- Negative evidence retained; indirect failures do not imply this item is unknown

Warnings:

- Exposure is not proof of comprehension; consolidation is gated on recognition/use
- Anki reviews are indirect, note scoped and modality unspecified; not individual word successes
- Historical/inferred associations reduce evidence strength and confidence
- No observed listening evidence; no observed production evidence.

### 먹다

Suggested reading: **practicing / medium**. Manual reading: unassessed; overall: unknown.

Evidence: 129 occurrences, 125 physical / 125 logical sources, 118 contexts, 14 forms; 732 indirect reviews, all 732 historically uncertain.

Reasons:

- 129 dimension-specific events; 118 distinct contexts; 125 logical sources
- 0 directly recognized/used contexts; 0 total recognition/use contexts
- 14 observed surface forms; conservative temporal weighting retains older exposure
- 732 sentence-level Anki events provide capped contextual support
- Negative evidence retained; indirect failures do not imply this item is unknown

Warnings:

- Exposure is not proof of comprehension; consolidation is gated on recognition/use
- Anki reviews are indirect, note scoped and modality unspecified; not individual word successes
- Historical/inferred associations reduce evidence strength and confidence
- No observed listening evidence; no observed production evidence.

### 좋아하다

Suggested reading: **practicing / medium**. Manual reading: unassessed; overall: unknown.

Evidence: 109 occurrences, 96 physical / 96 logical sources, 95 contexts, 7 forms; 589 indirect reviews, all 589 historically uncertain.

Reasons:

- 109 dimension-specific events; 95 distinct contexts; 96 logical sources
- 0 directly recognized/used contexts; 0 total recognition/use contexts
- 7 observed surface forms; conservative temporal weighting retains older exposure
- 589 sentence-level Anki events provide capped contextual support
- Negative evidence retained; indirect failures do not imply this item is unknown

Warnings:

- Exposure is not proof of comprehension; consolidation is gated on recognition/use
- Anki reviews are indirect, note scoped and modality unspecified; not individual word successes
- Historical/inferred associations reduce evidence strength and confidence
- No observed listening evidence; no observed production evidence.

### 하다

Suggested reading: **practicing / medium**. Manual reading: unassessed; overall: unknown.

Evidence: 87 occurrences, 85 physical / 85 logical sources, 84 contexts, 16 forms; 585 indirect reviews, all 585 historically uncertain.

Reasons:

- 87 dimension-specific events; 84 distinct contexts; 85 logical sources
- 0 directly recognized/used contexts; 0 total recognition/use contexts
- 16 observed surface forms; conservative temporal weighting retains older exposure
- 585 sentence-level Anki events provide capped contextual support
- Negative evidence retained; indirect failures do not imply this item is unknown

Warnings:

- Exposure is not proof of comprehension; consolidation is gated on recognition/use
- Anki reviews are indirect, note scoped and modality unspecified; not individual word successes
- Historical/inferred associations reduce evidence strength and confidence
- No observed listening evidence; no observed production evidence.

### 오늘

Suggested reading: **practicing / medium**. Manual reading: unassessed; overall: unknown.

Evidence: 72 occurrences, 72 physical / 72 logical sources, 70 contexts, 3 forms; 417 indirect reviews, all 417 historically uncertain.

Reasons:

- 72 dimension-specific events; 70 distinct contexts; 72 logical sources
- 0 directly recognized/used contexts; 0 total recognition/use contexts
- 3 observed surface forms; conservative temporal weighting retains older exposure
- 417 sentence-level Anki events provide capped contextual support
- Negative evidence retained; indirect failures do not imply this item is unknown

Warnings:

- Exposure is not proof of comprehension; consolidation is gated on recognition/use
- Anki reviews are indirect, note scoped and modality unspecified; not individual word successes
- Historical/inferred associations reduce evidence strength and confidence
- No observed listening evidence; no observed production evidence.

### 가다

Suggested reading: **practicing / medium**. Manual reading: unassessed; overall: unknown.

Evidence: 71 occurrences, 63 physical / 63 logical sources, 66 contexts, 12 forms; 297 indirect reviews, all 297 historically uncertain.

Reasons:

- 71 dimension-specific events; 66 distinct contexts; 63 logical sources
- 0 directly recognized/used contexts; 0 total recognition/use contexts
- 12 observed surface forms; conservative temporal weighting retains older exposure
- 297 sentence-level Anki events provide capped contextual support
- Negative evidence retained; indirect failures do not imply this item is unknown

Warnings:

- Exposure is not proof of comprehension; consolidation is gated on recognition/use
- Anki reviews are indirect, note scoped and modality unspecified; not individual word successes
- Historical/inferred associations reduce evidence strength and confidence
- No observed listening evidence; no observed production evidence.

### 공부하다

Suggested reading: **practicing / medium**. Manual reading: unassessed; overall: unknown.

Evidence: 50 occurrences, 50 physical / 50 logical sources, 49 contexts, 8 forms; 299 indirect reviews, all 299 historically uncertain.

Reasons:

- 50 dimension-specific events; 49 distinct contexts; 50 logical sources
- 0 directly recognized/used contexts; 0 total recognition/use contexts
- 8 observed surface forms; conservative temporal weighting retains older exposure
- 299 sentence-level Anki events provide capped contextual support
- Negative evidence retained; indirect failures do not imply this item is unknown

Warnings:

- Exposure is not proof of comprehension; consolidation is gated on recognition/use
- Anki reviews are indirect, note scoped and modality unspecified; not individual word successes
- Historical/inferred associations reduce evidence strength and confidence
- No observed listening evidence; no observed production evidence.

### 한국

Suggested reading: **practicing / medium**. Manual reading: unassessed; overall: unknown.

Evidence: 37 occurrences, 36 physical / 36 logical sources, 36 contexts, 6 forms; 233 indirect reviews, all 233 historically uncertain.

Reasons:

- 37 dimension-specific events; 36 distinct contexts; 36 logical sources
- 0 directly recognized/used contexts; 0 total recognition/use contexts
- 6 observed surface forms; conservative temporal weighting retains older exposure
- 233 sentence-level Anki events provide capped contextual support
- Negative evidence retained; indirect failures do not imply this item is unknown

Warnings:

- Exposure is not proof of comprehension; consolidation is gated on recognition/use
- Anki reviews are indirect, note scoped and modality unspecified; not individual word successes
- Historical/inferred associations reduce evidence strength and confidence
- No observed listening evidence; no observed production evidence.

### 한국어

Suggested reading: **practicing / medium**. Manual reading: unassessed; overall: unknown.

Evidence: 36 occurrences, 36 physical / 36 logical sources, 36 contexts, 4 forms; 214 indirect reviews, all 214 historically uncertain.

Reasons:

- 36 dimension-specific events; 36 distinct contexts; 36 logical sources
- 0 directly recognized/used contexts; 0 total recognition/use contexts
- 4 observed surface forms; conservative temporal weighting retains older exposure
- 214 sentence-level Anki events provide capped contextual support
- Negative evidence retained; indirect failures do not imply this item is unknown

Warnings:

- Exposure is not proof of comprehension; consolidation is gated on recognition/use
- Anki reviews are indirect, note scoped and modality unspecified; not individual word successes
- Historical/inferred associations reduce evidence strength and confidence
- No observed listening evidence; no observed production evidence.

### 친구

Suggested reading: **practicing / medium**. Manual reading: unassessed; overall: unknown.

Evidence: 23 occurrences, 23 physical / 23 logical sources, 23 contexts, 5 forms; 147 indirect reviews, all 147 historically uncertain.

Reasons:

- 23 dimension-specific events; 23 distinct contexts; 23 logical sources
- 0 directly recognized/used contexts; 0 total recognition/use contexts
- 5 observed surface forms; conservative temporal weighting retains older exposure
- 147 sentence-level Anki events provide capped contextual support
- Negative evidence retained; indirect failures do not imply this item is unknown

Warnings:

- Exposure is not proof of comprehension; consolidation is gated on recognition/use
- Anki reviews are indirect, note scoped and modality unspecified; not individual word successes
- Historical/inferred associations reduce evidence strength and confidence
- No observed listening evidence; no observed production evidence.

### 피곤하다

Suggested reading: **practicing / medium**. Manual reading: unassessed; overall: unknown.

Evidence: 22 occurrences, 22 physical / 22 logical sources, 21 contexts, 6 forms; 140 indirect reviews, all 140 historically uncertain.

Reasons:

- 22 dimension-specific events; 21 distinct contexts; 22 logical sources
- 0 directly recognized/used contexts; 0 total recognition/use contexts
- 6 observed surface forms; conservative temporal weighting retains older exposure
- 140 sentence-level Anki events provide capped contextual support
- Negative evidence retained; indirect failures do not imply this item is unknown

Warnings:

- Exposure is not proof of comprehension; consolidation is gated on recognition/use
- Anki reviews are indirect, note scoped and modality unspecified; not individual word successes
- Historical/inferred associations reduce evidence strength and confidence
- No observed listening evidence; no observed production evidence.

### 말하다

Suggested reading: **practicing / medium**. Manual reading: unassessed; overall: unknown.

Evidence: 21 occurrences, 19 physical / 19 logical sources, 17 contexts, 5 forms; 100 indirect reviews, all 100 historically uncertain.

Reasons:

- 21 dimension-specific events; 17 distinct contexts; 19 logical sources
- 0 directly recognized/used contexts; 0 total recognition/use contexts
- 5 observed surface forms; conservative temporal weighting retains older exposure
- 100 sentence-level Anki events provide capped contextual support
- Negative evidence retained; indirect failures do not imply this item is unknown

Warnings:

- Exposure is not proof of comprehension; consolidation is gated on recognition/use
- Anki reviews are indirect, note scoped and modality unspecified; not individual word successes
- Historical/inferred associations reduce evidence strength and confidence
- No observed listening evidence; no observed production evidence.

### 보다

Suggested reading: **practicing / medium**. Manual reading: unassessed; overall: unknown.

Evidence: 19 occurrences, 19 physical / 19 logical sources, 18 contexts, 7 forms; 104 indirect reviews, all 104 historically uncertain.

Reasons:

- 19 dimension-specific events; 18 distinct contexts; 19 logical sources
- 0 directly recognized/used contexts; 0 total recognition/use contexts
- 7 observed surface forms; conservative temporal weighting retains older exposure
- 104 sentence-level Anki events provide capped contextual support
- Negative evidence retained; indirect failures do not imply this item is unknown

Warnings:

- Exposure is not proof of comprehension; consolidation is gated on recognition/use
- Anki reviews are indirect, note scoped and modality unspecified; not individual word successes
- Historical/inferred associations reduce evidence strength and confidence
- No observed listening evidence; no observed production evidence.

### 많이

Suggested reading: **practicing / medium**. Manual reading: unassessed; overall: unknown.

Evidence: 18 occurrences, 18 physical / 18 logical sources, 17 contexts, 1 forms; 90 indirect reviews, all 90 historically uncertain.

Reasons:

- 18 dimension-specific events; 17 distinct contexts; 18 logical sources
- 0 directly recognized/used contexts; 0 total recognition/use contexts
- 1 observed surface forms; conservative temporal weighting retains older exposure
- 90 sentence-level Anki events provide capped contextual support
- Negative evidence retained; indirect failures do not imply this item is unknown

Warnings:

- Exposure is not proof of comprehension; consolidation is gated on recognition/use
- Anki reviews are indirect, note scoped and modality unspecified; not individual word successes
- Historical/inferred associations reduce evidence strength and confidence
- No observed listening evidence; no observed production evidence.

### 내일

Suggested reading: **practicing / medium**. Manual reading: unassessed; overall: unknown.

Evidence: 17 occurrences, 17 physical / 17 logical sources, 17 contexts, 3 forms; 92 indirect reviews, all 92 historically uncertain.

Reasons:

- 17 dimension-specific events; 17 distinct contexts; 17 logical sources
- 0 directly recognized/used contexts; 0 total recognition/use contexts
- 3 observed surface forms; conservative temporal weighting retains older exposure
- 92 sentence-level Anki events provide capped contextual support
- Negative evidence retained; indirect failures do not imply this item is unknown

Warnings:

- Exposure is not proof of comprehension; consolidation is gated on recognition/use
- Anki reviews are indirect, note scoped and modality unspecified; not individual word successes
- Historical/inferred associations reduce evidence strength and confidence
- No observed listening evidence; no observed production evidence.

### -(으)ㄹ 거예요

Suggested reading: **practicing / medium**. Manual reading: unassessed; overall: unknown.

Evidence: 51 occurrences, 50 physical / 50 logical sources, 51 contexts, 13 forms; 305 indirect reviews, all 305 historically uncertain.

Reasons:

- 51 dimension-specific events; 51 distinct contexts; 50 logical sources
- 0 directly recognized/used contexts; 0 total recognition/use contexts
- 13 observed surface forms; conservative temporal weighting retains older exposure
- 305 sentence-level Anki events provide capped contextual support
- Negative evidence retained; indirect failures do not imply this item is unknown

Warnings:

- Exposure is not proof of comprehension; consolidation is gated on recognition/use
- Anki reviews are indirect, note scoped and modality unspecified; not individual word successes
- Historical/inferred associations reduce evidence strength and confidence
- No observed listening evidence; no observed production evidence.

### -(으)면

Suggested reading: **practicing / medium**. Manual reading: unassessed; overall: unknown.

Evidence: 63 occurrences, 62 physical / 62 logical sources, 56 contexts, 18 forms; 364 indirect reviews, all 364 historically uncertain.

Reasons:

- 63 dimension-specific events; 56 distinct contexts; 62 logical sources
- 0 directly recognized/used contexts; 0 total recognition/use contexts
- 18 observed surface forms; conservative temporal weighting retains older exposure
- 364 sentence-level Anki events provide capped contextual support
- Negative evidence retained; indirect failures do not imply this item is unknown

Warnings:

- Exposure is not proof of comprehension; consolidation is gated on recognition/use
- Anki reviews are indirect, note scoped and modality unspecified; not individual word successes
- Historical/inferred associations reduce evidence strength and confidence
- No observed listening evidence; no observed production evidence.

### -고 싶다

Suggested reading: **practicing / medium**. Manual reading: unassessed; overall: unknown.

Evidence: 55 occurrences, 54 physical / 54 logical sources, 53 contexts, 24 forms; 295 indirect reviews, all 295 historically uncertain.

Reasons:

- 55 dimension-specific events; 53 distinct contexts; 54 logical sources
- 0 directly recognized/used contexts; 0 total recognition/use contexts
- 24 observed surface forms; conservative temporal weighting retains older exposure
- 295 sentence-level Anki events provide capped contextual support
- Negative evidence retained; indirect failures do not imply this item is unknown

Warnings:

- Exposure is not proof of comprehension; consolidation is gated on recognition/use
- Anki reviews are indirect, note scoped and modality unspecified; not individual word successes
- Historical/inferred associations reduce evidence strength and confidence
- No observed listening evidence; no observed production evidence.

### -는데

Suggested reading: **practicing / medium**. Manual reading: unassessed; overall: unknown.

Evidence: 51 occurrences, 51 physical / 51 logical sources, 50 contexts, 21 forms; 281 indirect reviews, all 281 historically uncertain.

Reasons:

- 51 dimension-specific events; 50 distinct contexts; 51 logical sources
- 0 directly recognized/used contexts; 0 total recognition/use contexts
- 21 observed surface forms; conservative temporal weighting retains older exposure
- 281 sentence-level Anki events provide capped contextual support
- Negative evidence retained; indirect failures do not imply this item is unknown

Warnings:

- Exposure is not proof of comprehension; consolidation is gated on recognition/use
- Anki reviews are indirect, note scoped and modality unspecified; not individual word successes
- Historical/inferred associations reduce evidence strength and confidence
- No observed listening evidence; no observed production evidence.

### -아/어서

Suggested reading: **practicing / medium**. Manual reading: unassessed; overall: unknown.

Evidence: 56 occurrences, 56 physical / 56 logical sources, 56 contexts, 17 forms; 278 indirect reviews, all 278 historically uncertain.

Reasons:

- 56 dimension-specific events; 56 distinct contexts; 56 logical sources
- 0 directly recognized/used contexts; 0 total recognition/use contexts
- 17 observed surface forms; conservative temporal weighting retains older exposure
- 278 sentence-level Anki events provide capped contextual support
- Negative evidence retained; indirect failures do not imply this item is unknown

Warnings:

- Exposure is not proof of comprehension; consolidation is gated on recognition/use
- Anki reviews are indirect, note scoped and modality unspecified; not individual word successes
- Historical/inferred associations reduce evidence strength and confidence
- No observed listening evidence; no observed production evidence.

### Canonical 좋아하다 and foreign content

The 좋아하다 state uses the single canonical Knowledge Item and its persisted links from hardening; raw 좋아하다 decompositions are not read by the state engine. No 좋다/하다 alias is rebuilt from morphology. Independent 하다 retains only its own existing links. No Portuguese concepts, BTS or Netflix enter the default lexical calculation. Zero Kiwi calls are needed; a public seam regression verifies no parser invocation.

## Calibration sample

[LEARNER_STATE_CALIBRATION.json](LEARNER_STATE_CALIBRATION.json) contains 25 lexicals plus all five GrammarPatterns. It includes stable IDs, policy parameters/fingerprint, manual/suggested state, confidence, evidence summaries, reasons and warnings; no raw reviews or full source sentences.

Selection is deterministic and covers high/mid/low frequency, Again/no-Again and multiple/single-surface strata. Manual labels are not inputs to ranking. The sample is for the user to inspect, not a report of human acceptance.

| Item | Manual reading | Suggested reading | Confidence | Reason summary |
| --- | --- | --- | --- | --- |
| 있다 | unassessed | practicing | medium | 133 contexts; 14 forms; 955 indirect events |
| 화장실 | unassessed | presented | low | 1 contexts; 1 forms; 8 indirect events |
| 기차 | unassessed | practicing | medium | 5 contexts; 2 forms; 17 indirect events |
| 먹다 | unassessed | practicing | medium | 118 contexts; 14 forms; 732 indirect events |
| 타다 | unassessed | practicing | medium | 9 contexts; 3 forms; 40 indirect events |
| 좋아하다 | unassessed | practicing | medium | 95 contexts; 7 forms; 589 indirect events |
| 안 | unassessed | practicing | medium | 50 contexts; 1 forms; 303 indirect events |
| 하다 | unassessed | practicing | medium | 84 contexts; 16 forms; 585 indirect events |
| 화요일 | unassessed | presented | low | 1 contexts; 1 forms; 16 indirect events |
| 네 | unassessed | practicing | medium | 5 contexts; 1 forms; 28 indirect events |
| 오늘 | unassessed | practicing | medium | 70 contexts; 3 forms; 417 indirect events |
| 스타로드 | unassessed | practicing | medium | 6 contexts; 3 forms; 36 indirect events |
| 가다 | unassessed | practicing | medium | 66 contexts; 12 forms; 297 indirect events |
| 좀 | unassessed | practicing | medium | 44 contexts; 1 forms; 291 indirect events |
| 싶다 | unassessed | practicing | medium | 53 contexts; 6 forms; 295 indirect events |
| 형 | unassessed | presented | low | 1 contexts; 1 forms; 5 indirect events |
| 동물 | unassessed | practicing | medium | 3 contexts; 3 forms; 19 indirect events |
| 공부하다 | unassessed | practicing | medium | 49 contexts; 8 forms; 299 indirect events |
| 결혼식 | unassessed | practicing | medium | 6 contexts; 1 forms; 16 indirect events |
| 저 | unassessed | practicing | medium | 48 contexts; 8 forms; 321 indirect events |
| 같이 | unassessed | practicing | medium | 30 contexts; 1 forms; 199 indirect events |
| 뭐 | unassessed | practicing | medium | 38 contexts; 10 forms; 354 indirect events |
| 행복하다 | unassessed | presented | low | 1 contexts; 1 forms; 7 indirect events |
| 또 | unassessed | practicing | medium | 4 contexts; 1 forms; 17 indirect events |
| 사람 | unassessed | practicing | medium | 35 contexts; 8 forms; 251 indirect events |
| -(으)ㄹ 거예요 | unassessed | practicing | medium | 51 contexts; 13 forms; 305 indirect events |
| -(으)면 | unassessed | practicing | medium | 56 contexts; 18 forms; 364 indirect events |
| -고 싶다 | unassessed | practicing | medium | 53 contexts; 24 forms; 295 indirect events |
| -는데 | unassessed | practicing | medium | 50 contexts; 21 forms; 281 indirect events |
| -아/어서 | unassessed | practicing | medium | 56 contexts; 17 forms; 278 indirect events |

## Manual divergences

- There are **zero explicit dimensional manual assessments**, so all 1,077 item-dimension comparisons are `no manual`.
- Stored overall default unknown is lower than the suggested presented/practicing state for 359 items. This is a mathematical comparison of stored fields, **not** disagreement with 359 deliberate human judgments.
- The schema cannot distinguish default unknown from an intentionally set overall unknown. Therefore no real calibration accuracy, precision/recall or manual-agreement score is reported.
- Synthetic tests preserve true manual practicing/consolidated/future comparisons and prove that changing labels does not fit/rewrite policy calculations.

## Performance and integrity

- All 359 items: **0.903892 seconds**, 8 SELECTs, 10 total SQL statements including transaction/schema inspection, **0 writes**.
- Query count is bounded, independent of item count; a regression checks no per-item queries.
- One-item inspection resolves only identity/UUID before a filtered batch. Type/all recalculation is explicit. No complex cache or materialized state was introduced.
- Both staging and principal hashes remained identical before/after real evaluation and CLI calls. All calculations use a consistent read transaction; CLI uses SQLite mode=ro.

| File | SHA-256 before = after |
| --- | --- |
| staging.db | `cd928c0b2dad6a9f94b73267cc58a1095b54b033e0144e69a65ffaa7eb53db6f` |
| lute.db | `ca44b1654eed5c22955317428d5f2f33d9566c89472f40f74d281e2916de98e7` |

## Tests

- New Sprint 4 public-service/protocol/CLI tests: **35 passed**.
- Final combined relevant suite: **377 passed** in 67.67 s, one Japanese-specific ORM case deselected.
- Existing Sprint 1 (52), Sprint 2 (54), Sprint 3 (36), Sprint 3.6 (49) and relevant Lute tests (151) retained their previous behavior.
- Japanese parser/Term cases were also rerun independently: **six environmental failures** because `mecab-config`/`libmecab.so` are unavailable. No Korean failure was hidden by this exclusion.
- Pylint for the new package: **10.00/10**. CLI help, installed entry point, read-only inspection/compare/calibration and offline wheel packaging were checked.

Combined command:

```sh
python -m pytest plugins/lute-korean/tests tests/unit/parse tests/unit/language tests/unit/read tests/unit/book tests/unit/db/setup tests/orm/test_Term.py tests/orm/test_Language.py tests/orm/test_Text.py --ignore=tests/unit/parse/test_JapaneseParser.py -k 'not test_changing_text_to_same_thing_does_not_throw' -q
```

The temporary upstream test config points to an isolated test-prefixed database under `/tmp` and is removed afterwards. Normal Lute configuration and principal data are preserved.

## Problems and limits

| Finding | Consequence / disposition |
| --- | --- |
| No explicit recognition/use in real data | No consolidated suggestions; practice represents contextual familiarity. Expected conservative limitation. |
| 6,055 first-observed historical associations | Downweighted and warned, never treated as certified past lexical content. |
| No listening/production coverage | Unknown/low in those dimensions; audio/card direction does not create modality evidence. |
| Default overall unknown lacks assessment provenance | Real manual-agreement calibration cannot be claimed. |
| Deterministic context fingerprint | Exact normalized duplicates collapse; semantically similar sentences still differ. No embeddings. |
| On-demand calculation | The exported snapshot is auditable; the engine does not maintain longitudinal suggested-state history unless the caller saves snapshots. |
| as_of filters events, not historical database reconstruction | Sources/occurrence statistics describe the stored snapshot; old unobserved text cannot be recovered. |
| Heuristic policy and human calibration pending | Appropriate for cautious input orientation, not a scientific mastery claim or autonomous pedagogical decision. |

## Files changed in Sprint 4

Prior Sprints and unrelated uncommitted/Docker data were preserved. No core or migration was added.

- `lute_korean_parser/learner_state/__init__.py`
- `lute_korean_parser/learner_state/policy.py`
- `lute_korean_parser/learner_state/repository.py`
- `lute_korean_parser/learner_state/interpretation.py`
- `lute_korean_parser/learner_state/engine.py`
- `lute_korean_parser/learner_state/calibration.py`
- `lute_korean_parser/learner_state/cli.py`
- `lute_korean_parser/knowledge/service.py`
- `tests/test_learner_state.py`
- `pyproject.toml`
- `CONTEXT.md`
- `KNOWLEDGE.md`
- `README.md`
- `LEARNER_STATE.md`
- `LEARNER_STATE_VALIDATION.md`
- `LEARNER_STATE_CALIBRATION.json`

No automatic status application, recommendation engine, CI difficulty, podcast search, new ingestion, dashboard, LLM, embeddings, Anki modification or Sprint 5 was implemented.
