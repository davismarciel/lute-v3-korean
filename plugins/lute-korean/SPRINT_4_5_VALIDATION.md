# Sprint 4.5 validation

Date: 2026-09-30. Scope: lexical/grammar representation, factual human Evidence infrastructure and unchanged-policy recalculation.

## Final verdict

**YES** — the corrected representation and explicit construction overlap are reliable enough to begin CI difficulty work within the tracked-pattern scope. This is not a claim of perfect semantic parsing or a CI implementation. Remaining compositional/auxiliary granularity is exposed in the integrity audit and must not be assumed to be an independent-difficulty ontology.

## Lexical integrity

- 어제: one real context returned 어/IC + 저/NP + 의/JKG, with relative spans (0,1), (1,2), (1,2). The full original context was reproduced; the bug was morphological ambiguity, not incorrect offsets or boundary loss. The new full-unit rule maps it to 어제 and preserves the three raw morphemes.
- 재미있는데: raw 재미/NNG + 있/VV + 는데/EC projected 재미 and 있다. The lexicalized compound is now 재미있다. Existing native 재미있/VA analyses remain unchanged.
- The multiword-NNP audit also found 캡틴 아메리카 and 카니예 웨스트 projected twice into partial surfaces. ko.projection.multiword-nnp.v1 now projects each full exact NNP source span once; parser units are unchanged. The same verified category includes 맛있다; it occurs in this collection, but its real captured analyses already use the correct native head. No additional speculative compounds were added.
- Standalone 있다, particle-separated 재미가 있어요, pronouns, 좋아하다 guards and reader surface/offset behavior are regression-tested.

See [LEXICAL_INTEGRITY_AUDIT.md](LEXICAL_INTEGRITY_AUDIT.md) for exact real note IDs, raw/canonical heads and every 어제 occurrence. See [LEXICAL_INTEGRITY.md](LEXICAL_INTEGRITY.md) for policy and reconciliation.

## Audit

- All 354 original and 352 rebuilt lexical identities inspected. After: 0 critical automated findings; 0 span/canonical important findings.
- Human review classified auxiliary 물어봐도, compositional noun+하다, noun combinations and numeral projection separately. The two fully reproduced high-confidence contamination families and the subsequently reproduced multiword-NNP duplicate projection were corrected. No blanket merges or removal of legitimate compound constituents were performed.

## Knowledge relationships

- Additive roles/relations tables; no change to central Lute tables or existing Evidence.
- One high-confidence component_of relation: lexical 싶다 → grammar -고 싶다, rule ko.overlap.desire.v1.
- Other active constructions: -(으)면, -는데 and -아/어서 consist of endings; -(으)ㄹ 거예요 uses already-excluded NNB/copula. No speculative lexical relations added.
- 먹고 싶어요: raw 먹다 / 싶다 / -고 싶다; effective 먹다 / -고 싶다; suppression reason and covering spans are returned. A lexical-only region retains 싶다; unrelated Sources are unaffected.
- Effective resolution performs bounded source, joined-occurrence and relation queries; no query per linked item. Raw links/Evidence remain unchanged.

## Named entities

- ko.role.pos.v1 uses exact NNP head evidence; roles permit general/proper_noun/foreign_name/unknown and explicit manual override. No NER, priority inference or status change.
- Real 스타로드, 부산, 서울 and 한국 are proper_noun. They remain fully tracked and can be pedagogically valuable. Latin brands remain metadata under existing eligibility.

## Human Evidence

- HumanEvidenceService previews/validates entire JSON, then explicitly applies factual observed events through the existing Evidence model. No new Evidence types or source enums.
- Existing identity, explicit dimension/directness/scope, source reference, aware timestamp and recorder are required. Unsupported fields, ambiguous items, future time, invalid production modality and conflicting event keys fail.
- Stable payload-derived event key or explicit external key; repeated import reuses IDs. Savepoint protects atomicity; caller controls commit/rollback.
- Validate/preview CLI opens read-only SQLite. Apply requires an explicitly selected existing database. preview-human-calibration returns no fabricated candidates.
- Synthetic fixture: reading practicing/medium → consolidated after multiple direct contexts, manual reading practicing unchanged; listening/production unknown. Direct recent grammar misses remain practicing, and production affects production only.
- No real human Evidence or real status was written; examples and fixtures are synthetic. See [HUMAN_EVIDENCE.md](HUMAN_EVIDENCE.md).

## Policy

**LearnerStatePolicyV1 unchanged: YES.**

- Version before/after: ko.learner-state.v1.
- Parameter fingerprint before/after: `94819404fd433591b54a9cc1e5b132065c7f35bbe19bc1f88077dcfcef0f24f3`.
- Policy source SHA-256 before/after: `7849d57654f21f617a403e1838c15b41e2ab1b22583a308b77b89d135569d8a6`.
- No threshold, weight, confidence gate, manual-status behavior or engine code changed.

## Real-derived staging and synchronization

This run used the safely captured real 875-note/875-card/6,055-review snapshot from the preceding live audit. It did not reconnect to Windows Anki or assert new live operational coverage. Rebuilt Sources have an identical content multiset to the clean Sprint 3.6 staging, and every historical review event key matches. No fake synthetic collection replaced the real content.

| Metric | Before | After |
| --- | ---: | ---: |
| Lexical items | 354 | 352 |
| Grammar items | 5 | 5 |
| Sources | 875 | 875 |
| Occurrences | 3,120 | 3,117 |
| Occurrence-item links | 3,307 | 3,302 |
| Generic exposure rows | 3,307 | 3,302 |
| Canonical review events | 6,055 | 6,055 |
| Anomalous notes | 1 | 1 |

- Removed only spurious identities 어 and 재미: each existed solely as a component of the misanalyses. No items were deleted from the old database; the counts describe a new clean rebuild.
- All historical reviews retain indirect/note-scoped/unspecified modality and first-observed association uncertainty.
- Initial sync: 875 inspected, 874 Kiwi calls, one quarantined; 6,055 reviews imported. Second full-history sync: 875 skipped, zero Kiwi, zero new items, zero new reviews, 6,055 existing review events skipped.
- Canonical item ID/status fingerprint identical across both runs; new clean-build UUIDs are not claimed to equal the old staging UUIDs.
- Foreign-key check returned no violations. Principal and original staging hashes remained unchanged; original staging SHA-256: cd928c0b2dad6a9f94b73267cc58a1095b54b033e0144e69a65ffaa7eb53db6f.

## Learner-state recalculation

| Type / reading status | Before | After |
| --- | ---: | ---: |
| lexical / unknown | 0 | 0 |
| lexical / presented | 189 | 188 |
| lexical / practicing | 165 | 164 |
| lexical / consolidated | 0 | 0 |
| lexical / future | 0 | 0 |
| grammar / unknown | 0 | 0 |
| grammar / presented | 0 | 0 |
| grammar / practicing | 5 | 5 |
| grammar / consolidated | 0 | 0 |
| grammar / future | 0 | 0 |

Listening and production remain unknown/low for all real items. All stored overall statuses remain unknown and dimensional manual rows remain absent. No target distribution was used.

| Item | Occurrences before → after | Sources before → after | Contexts before → after | Suggestion before → after |
| --- | --- | --- | --- | --- |
| 저 | 49 → 48 | 48 → 47 | 48 → 47 | practicing/medium → practicing/medium |
| 어제 | 8 → 9 | 8 → 9 | 6 → 7 | practicing/medium → practicing/medium |
| 있다 | 143 → 142 | 143 → 142 | 133 → 132 | practicing/medium → practicing/medium |
| 재미있다 | 6 → 7 | 6 → 7 | 6 → 7 | practicing/medium → practicing/medium |
| 싶다 | 55 → 55 | 54 → 54 | 53 → 53 | practicing/medium → practicing/medium |
| -고 싶다 | 55 → 55 | 54 → 54 | 53 → 53 | practicing/medium → practicing/medium |
| 스타로드 | 7 → 7 | 6 → 6 | 6 → 6 | practicing/medium → practicing/medium |

### Surfaces before → after

- 저: ["어제", "저", "저는", "저도", "저보다", "전", "제", "제가"] → ["저", "저는", "저도", "저보다", "전", "제", "제가"]
- 어제: ["어제", "어제는"] → ["어제", "어제는"]
- 있다: ["있는", "있는데", "있다가", "있다고", "있다고요", "있어서", "있어요", "있었는데", "있었어요", "있으면", "있잖아", "있잖아요", "있지", "재미있는데"] → ["있는", "있는데", "있다가", "있다고", "있다고요", "있어서", "있어요", "있었는데", "있었어요", "있으면", "있잖아", "있잖아요", "있지"]
- 재미있다: ["재미있다고", "재미있어요", "재미있을"] → ["재미있는데", "재미있다고", "재미있어요", "재미있을"]
- 싶다: ["싶네요", "싶다고", "싶어는데", "싶어요", "싶었는데", "싶은데"] → ["싶네요", "싶다고", "싶어는데", "싶어요", "싶었는데", "싶은데"]
- -고 싶다: ["가고 싶어요", "게임하고 싶다고", "게임하고 싶어요", "게임하고 싶은데", "공부하고 싶어요", "공부하고 싶은데", "듣고 싶었는데", "듣고 싶은데", "마시고 싶어요", "마시고 싶은데", "만나고 싶은데", "말하고 싶어요", "말하고 싶은데", "먹고 싶네요", "먹고 싶어요", "먹고 싶었는데", "먹고 싶은데", "보고 싶어요", "쉬고 싶어요", "쓰고 싶어요", "읽고 싶어는데", "잘하고 싶어요", "하고 싶어요", "하고 싶은데"] → ["가고 싶어요", "게임하고 싶다고", "게임하고 싶어요", "게임하고 싶은데", "공부하고 싶어요", "공부하고 싶은데", "듣고 싶었는데", "듣고 싶은데", "마시고 싶어요", "마시고 싶은데", "만나고 싶은데", "말하고 싶어요", "말하고 싶은데", "먹고 싶네요", "먹고 싶어요", "먹고 싶었는데", "먹고 싶은데", "보고 싶어요", "쉬고 싶어요", "쓰고 싶어요", "읽고 싶어는데", "잘하고 싶어요", "하고 싶어요", "하고 싶은데"]
- 스타로드: ["스타로드는", "스타로드를", "스타로드인데"] → ["스타로드는", "스타로드를", "스타로드인데"]

## Performance

- Real-capture initial rebuild/sync: 16.280 s; unchanged full-history sync: 1.334 s, zero Kiwi.
- These timings exclude live Anki HTTP/WSL bridge overhead and cannot be directly equated to the earlier 29.59/20.70/16.90 s live observations. No suspicious local regression was observed.
- Batched recalculation: 0.997 s before, 0.932 s after. Query counts: before {'BEGIN': 1, 'SELECT': 8, 'PRAGMA': 1}; after {'BEGIN': 1, 'SELECT': 8, 'PRAGMA': 1}.
- Human imports are small transactional operations; batched existing-item resolution avoids per-event identity lookup. Relationship lookup does not issue per-item queries. Measured resolution for regions with 1 and 13 raw links used the same three SELECTs plus one table-inspection PRAGMA each.

## Tests

- Final selected Sprints 1–4.5 plus relevant existing Lute tests: **413 passed, one Japanese-specific case deselected**, 81.38 s.
- New Sprint 4.5 tests: **36 passed**, including canonical negatives, preserved raw provenance/spans, overlap scope, relation idempotency/self guards, roles/manual overrides, human validation/preview/idempotency/conflict rollback/caller rollback, skill separation, unchanged manual status and exact Policy fingerprint/source hash.
- Earlier selected run with the first 26 new cases: 403 passed. Final run includes all 36; no earlier success is substituted for the final suite.
- Separate Japanese/MeCab checks: **six environmental failures**, missing mecab-config/libmecab.so. No Japanese parser code changed.
- Wheel builds offline; editable install registers the new CLI entry points. CLI preview/read-only diagnosis and isolated explicit apply are exercised without touching the principal database.

## Changes made

- `lute/db/schema/migrations/20260930_03_korean_representation.sql`
- `plugins/lute-korean/lute_korean_parser/knowledge/normalization.py`
- `plugins/lute-korean/lute_korean_parser/knowledge/representation.py`
- `plugins/lute-korean/lute_korean_parser/knowledge/human.py`
- `plugins/lute-korean/lute_korean_parser/knowledge/hardening_cli.py`
- `plugins/lute-korean/lute_korean_parser/knowledge/ingestion.py`
- `plugins/lute-korean/lute_korean_parser/knowledge/tables.py`
- `plugins/lute-korean/lute_korean_parser/anki/sync.py`
- `plugins/lute-korean/tests/test_anki.py`
- `plugins/lute-korean/tests/test_representation_hardening.py`
- `plugins/lute-korean/pyproject.toml`
- `plugins/lute-korean/README.md`
- `plugins/lute-korean/KNOWLEDGE.md`
- `plugins/lute-korean/CONTEXT.md`
- `plugins/lute-korean/LEXICAL_INTEGRITY.md`
- `plugins/lute-korean/LEXICAL_INTEGRITY_AUDIT.md`
- `plugins/lute-korean/HUMAN_EVIDENCE.md`
- `plugins/lute-korean/SPRINT_4_5_VALIDATION.md`

Prior uncommitted Sprints and private docker data were preserved. No raw parser, reader, grammar detector, learner engine/policy, principal database or Anki content was modified. No CI difficulty, novelty percentage, scoring adjustment, recommendations, automatic promotion or Sprint 5 was implemented.
