# Real Anki validation after ingestion hardening

Date: 2026-09-30. Scope: Sprint 3.6 only. Baseline: [REAL_ANKI_VALIDATION.md](REAL_ANKI_VALIDATION.md).

## Final verdict

**YES** — the real Anki integration is now suitable as a lexical Evidence source for the future Learner State Engine, under the documented content eligibility and historical-provenance policies.

Both observed linguistic blockers are resolved in a clean staging rebuild. This verdict does not certify every possible Kiwi analysis, historical note text, or previously contaminated import. Reviews remain indirect sentence-level events; no status, scoring, learner-state engine or pedagogical feature was implemented.

## Environment

- OS: WSL2 Linux 6.6.87.2-microsoft-standard-WSL2; Windows 11 Pro 10.0.26200.
- Python: 3.14.4; Lute: 3.10.3; plugin: 0.3.0.
- Kiwi: kiwipiepy 0.23.2; model 0.23.0.
- Windows Anki 26.9; AnkiConnect API 6; real profile `Usuário 1`.
- Real Anki transport: temporary WSL loopback bridge → Windows PowerShell → Windows loopback AnkiConnect. Only allowlisted read actions; no LAN/public listener, cloud, changed firewall or Anki writes.
- Principal database: `docker/my_data/lute.db`, opened read-only for backup. Existing project migrations applied only to the fresh staging copy.

## Collection and mapping

- Exactly the same 875 note IDs and cleaned content hashes as baseline; 875 cards and 6,055 review events.
- One active note type: `Coreano`; explicit Korean field `Coreano`, translation `Tradução`, metadata `Notas` and `Áudio`. No automatic mapping persistence.
- Ten populated decks; 19 defined note types, 18 empty. Query remains explicitly all notes in the selected profile.
- One card per note; no real reverse-card example. Existing synthetic two-card/review coverage passed; real reverse-card validation is not claimed.
- All 875 notes have audio markers; baseline compatibility coverage includes 196 HTML Korean fields and one multiline dialogue. Cleanup, audio handling and rendering were not changed.
- Existing note duplicates were preserved. No notes, cards, tags or deck content were deduplicated or edited.

## 좋아하다

### Root cause and morphology

The raw Kiwi projection can emit `좋/VA + 어/EC + 하/VX` for one conjugated orthographic unit. The previous unit-level head projection interpreted these independently as `좋다` and `하다`. These are valid raw morphological components, but wrong pedagogical identities for lexicalized 좋아하다 in these contexts. Context sometimes makes Kiwi emit the already correct `좋아하/VV` instead.

Example, `뭐 좋아해요?`: `좋/VA [2,3)`, `어/EC [3,4)`, `하/VX [4,5)`, `어요/EF [4,6)`. The ending overlaps the predicate span. No assumption of non-overlapping endings was added.

### Solution and false-positive protection

- New generic `KoreanLexicalNormalizer`, called after raw analysis and before acquisition ingestion for all source types.
- Initial stable rule ID: `ko.lexical.johahada.v1`; explicit registry, deterministic matches, versioned processing signature.
- Exact adjacent forms/POS, contiguous component offsets, same original unit, bounded source spans and original `좋아` composition are required. This is not a substring search or unrestricted `좋 + 하` merge.
- Raw parser, morphology, raw heads, original surface/context and offsets stay intact. Occurrence metadata records canonical heads, rule ID/confidence/spans, eligibility and Kiwi/policy versions.
- Native `좋아하/VV` retains its correct lemma without applying the rule.
- Positive conjugations: 좋아해요, 좋아했어요, 좋아하면, 좋아해서, 좋아하고, 좋아하는, 좋아할 거예요, 좋아할 것 같아요; all reuse 좋아하다.
- Negative tests protect 좋아요, 날씨가 좋아요, 좋아서 다시 왔어요, 좋은 것 같아요, spaced 좋아 하세요, 운동해요, 공부해요 and 뭐 해요. POS/source/adjacency guards have independent tests.

### Exactly the 17 affected real notes

Live read-only fetch found **23 relevant forms across 17 notes**, including 17 decomposed units and six already canonical units. All 17 notes now have correct 좋아하다 associations. Their 98 raw reviews remain canonical events associated through those Sources. There are zero false 좋다/하다 associations originating from these normalized forms.

| Note ID | Surface | Raw Kiwi heads | Canonical heads | Applied rule |
| --- | --- | --- | --- | --- |
| 1784072371653 | 좋아하는데 | 좋아하다 | 좋아하다 | None: native VV identity |
| 1784072371653 | 좋아해요 | 좋다 + 하다 | 좋아하다 | ko.lexical.johahada.v1 |
| 1784072371655 | 좋아하는데 | 좋아하다 | 좋아하다 | None: native VV identity |
| 1784072371655 | 좋아해요 | 좋다 + 하다 | 좋아하다 | ko.lexical.johahada.v1 |
| 1784072371727 | 좋아해요 | 좋다 + 하다 | 좋아하다 | ko.lexical.johahada.v1 |
| 1784072371729 | 좋아해요 | 좋다 + 하다 | 좋아하다 | ko.lexical.johahada.v1 |
| 1784072371731 | 좋아해요 | 좋다 + 하다 | 좋아하다 | ko.lexical.johahada.v1 |
| 1784072371761 | 좋아해요 | 좋다 + 하다 | 좋아하다 | ko.lexical.johahada.v1 |
| 1784072371783 | 좋아하는데 | 좋아하다 | 좋아하다 | None: native VV identity |
| 1784072371783 | 좋아해요 | 좋다 + 하다 | 좋아하다 | ko.lexical.johahada.v1 |
| 1784072371785 | 좋아하는데 | 좋아하다 | 좋아하다 | None: native VV identity |
| 1784072371785 | 좋아해요 | 좋다 + 하다 | 좋아하다 | ko.lexical.johahada.v1 |
| 1784129923451 | 좋아해요 | 좋다 + 하다 | 좋아하다 | ko.lexical.johahada.v1 |
| 1784129923453 | 좋아하는데 | 좋아하다 | 좋아하다 | None: native VV identity |
| 1784129923453 | 좋아해요 | 좋다 + 하다 | 좋아하다 | ko.lexical.johahada.v1 |
| 1784129923457 | 좋아해요 | 좋다 + 하다 | 좋아하다 | ko.lexical.johahada.v1 |
| 1789261653519 | 좋아하는데 | 좋다 + 하다 | 좋아하다 | ko.lexical.johahada.v1 |
| 1789261653519 | 좋아해요 | 좋아하다 | 좋아하다 | None: native VV identity |
| 1789354088687 | 좋아해요 | 좋다 + 하다 | 좋아하다 | ko.lexical.johahada.v1 |
| 1789354089868 | 좋아해요 | 좋다 + 하다 | 좋아하다 | ko.lexical.johahada.v1 |
| 1789354091797 | 좋아해요 | 좋다 + 하다 | 좋아하다 | ko.lexical.johahada.v1 |
| 1789354097914 | 좋아해요 | 좋다 + 하다 | 좋아하다 | ko.lexical.johahada.v1 |
| 1789354106794 | 좋아해요 | 좋다 + 하다 | 좋아하다 | ko.lexical.johahada.v1 |

## Foreign content

### Root cause

The original Anki extraction only required some Hangul anywhere in the mapped field. Both problematic fields contained Hangul, so both passed. Generic ingestion also accepted Latin `SL` heads as Korean concepts. Together these created 16 unintended Portuguese identities (including Kiwi fragments `cotid` and `ianos.`). BTS was a legitimate foreign name, but also became a Korean concept under that earlier policy.

### Policy

- Anki validates every configured Korean field after presentation cleanup, preserving diagnostics and real note/source identity.
- No Hangul → anomaly. Dominant Latin prose → anomaly when Latin letters ≥70%, Latin-only words ≥8 and lowercase Latin words ≥6. Foreign script alone → warning, not whole-sentence rejection.
- This is an explicit conservative content heuristic, not identification/translation of a language. Short ambiguous mixed text needs manual inspection.
- Generic Korean lexical eligibility admits heads with Hangul letters; foreign/code-switching/numeric spans remain source/occurrence metadata without Korean item/evidence links.
- Anomalous notes bypass Kiwi and linguistic ingestion. Their Source/note/revision and raw reviews are retained. There are no Occurrences, lexical/grammar Items or linguistic exposures from their invalid content.
- Note operational state `active` still means it exists/in-scope; `content_validation.status=anomalous` separately describes content. Reviews carry `linguistic_association=withheld_content_anomaly` when applicable.

### The two real notes

| Note ID | Observed content class | Result | Occurrences | Raw reviews |
| --- | --- | --- | --- | --- |
| 1788834838513 | Portuguese speaker labels with predominantly Korean dialogue | Warning; Korean tracked, labels unlinked | 6 | 5 |
| 1790736609704 | Portuguese prose containing three Korean examples | Anomalous; linguistic ingestion skipped | 0 | 0 |

Note `1788834838513` retains `한국 어때요?` and `생각보다 재미있어요.` with original multiline context. `Alguém` and `Eu` remain foreign metadata, not Concepts. Its five reviews continue to relate indirectly to valid Korean content.

Note `1790736609704` has nine Hangul letters and 79 Latin letters (89.77% Latin), 13 lowercase Latin-only words. It is quarantined with source identity/diagnostics preserved. It currently has zero real reviews; fake-adapter tests separately prove that anomalous-note review events are retained without any linguistic association.

All 16 unintended Portuguese concepts are absent after rebuilding. The three BTS-containing notes remain valid mixed sources; BTS no longer becomes a Korean Lexical Concept. Pure Portuguese/English, mixed Netflix and BTS를 좋아해요 tests all passed. No Anki field was altered.

## Before vs After

| Metric | Before | After |
| --- | ---: | ---: |
| Notes / cards | 875 / 875 | 875 / 875 |
| Lexical Concepts | 371 | 354 |
| Grammar Patterns | 5 | 5 |
| Sources / observed revisions | 875 / 875 | 875 / 875 |
| Occurrences | 3,124 | 3,120 |
| Occurrence–item links | 3,346 | 3,307 |
| Generic exposure Evidence rows | 3,346 | 3,307 |
| Canonical review events | 6,055 | 6,055 |
| Unintended Portuguese concepts | 16 | 0 |
| Foreign-name Concepts (BTS) | 1 | 0 (metadata retained) |
| Problematic 좋아하다 notes | 17 | 0 |
| Content warnings, including anomalies | Not enforced | 5 |
| Anomalous notes / skipped linguistic analyses | 0 | 1 / 1 |
| Initial Kiwi calls | 875 | 874 |
| Unchanged Kiwi calls | 0 | 0 |
| Overall status | 376 unknown | 359 unknown |
| Explicit dimensional status rows | 0 | 0 |

The lexical count decrease is exactly the removal of 16 unintended Portuguese identities and one Latin-name identity. 좋아하다 already existed and was reused; independent 좋다/하다 legitimately remain elsewhere. Four fewer Occurrences reflect withholding the prose note while preserving unlinked foreign spans. Exposure rows and Anki raw events are different entities; reviews are not multiplied by the number of concepts.

## Real sync and performance

All runs use real Windows Anki and the fresh staging copy, not a replacement collection. Times below are measured wall time including the local transport; small variations are not optimization evidence.

| Run | Time | Baseline time | Kiwi calls | Notes new / changed / skipped | Reviews imported / skipped |
| --- | ---: | ---: | ---: | --- | --- |
| first-dry-run | 31.019 s | — | 874 | 875 / 0 / 0 | 6055 / 0 |
| first | 30.343 s | 29.59 s | 874 | 875 / 0 / 0 | 6055 / 0 |
| second | 20.557 s | 20.70 s | 0 | 0 / 0 / 875 | 0 / 0 |
| full-dry-run | 17.643 s | — | 0 | 0 / 0 / 875 | 0 / 6055 |
| full | 17.865 s | 16.90 s | 0 | 0 / 0 / 875 | 0 / 6055 |

- First dry-run: 875 inspected notes, 874 analyzed, one quarantined, 354 lexical/5 grammar creations predicted; zero errors.
- Both dry-runs: zero observed write statements to staging and identical before/after staging hashes. Principal hashes also remained identical.
- First staging sync fetched all historical reviews explicitly; all 6,055 events were imported once.
- Second unchanged sync: 875 skipped, zero Kiwi, zero new items/events. Full-history sync: all 6,055 fetched again and skipped as existing.
- Fingerprints of every acquisition/provenance table except operational integration reporting are identical across first, second and full sync: item IDs/status, dimensions, Sources, Occurrences, links, Evidence, notes, revisions, cards/cursors and review IDs/event keys.
- Foreign-key check returned no violations. Operational sync timestamps/reports change intentionally, so persisted-run whole-file hashes differ.
- Initial/full-history runs use 21 allowlisted HTTP actions: batched note/card/review fetching. Unchanged incremental run uses 26 (10 cardReviews groups). HTTP time is about 16–19 s, mostly transport/API overhead; no new per-note network calls were introduced.
- No naturally new real review was available: the unchanged incremental query imported zero events. No artificial Anki edit/review was forced. Fake-adapter tests cover new-review-only increments.
- Synthetic scale: 1,000 notes, 2,000 cards, 40,000 reviews; initial 20.630 s, incremental 1.626 s with zero additional Kiwi calls. This is a local fake-transport observation, not a live performance guarantee.

## Review provenance and status

- Ratings unchanged: Again 717, Hard 214, Good 5,025, Easy 99.
- All 6,055 events retain `association_basis=first_observed_snapshot`, indirect directness, sentence/note scope, and unspecified review modality.
- Baseline timing classification (5,165 before the current modification marker, 890 at/after) still applies because all note content/IDs and review events match. It is not proof of exact historical text. Zero events are certified to have recoverable exact historical Korean content.
- No overall or skill status was promoted. Synthetic services prove existing 먹다/practicing and 좋아하다/practicing IDs/statuses survive ingestion/reviews.
- Quarantine separates operational event preservation from linguistic eligibility. A review is not individual-word mastery evidence; no scoring formula was added.

## Regression tests

| Suite | Result |
| --- | --- |
| Sprint 1 parser/installation/read integration | 52 passed |
| Sprint 2 knowledge + Lute integration | 54 passed |
| Sprint 3 fake adapter/protocol/sync | 36 passed |
| New Sprint 3.6 lexical/content hardening | 49 passed |
| Relevant existing Lute parser/language/read/book/db/Term/Language/Text | 151 passed |
| Combined selected suite | 342 passed; one Japanese-specific case deselected |
| Japanese parser + Japanese Term case, separately | Six environmental failures: missing mecab-config/libmecab.so |

Command for the combined run:

```sh
python -m pytest plugins/lute-korean/tests tests/unit/parse tests/unit/language tests/unit/read tests/unit/book tests/unit/db/setup tests/orm/test_Term.py tests/orm/test_Language.py tests/orm/test_Text.py --ignore=tests/unit/parse/test_JapaneseParser.py -k 'not test_changing_text_to_same_thing_does_not_throw' -q
```

The final combined run completed in 64.82 s. The plugin contributes 191 of its passing tests. The plugin wheel was built offline through the configured Flit backend, and its new normalizer/content modules were verified. CLI help and `BTS를 좋아해요.` diagnosis also passed. Standard `python -m build` was unavailable in the venv; `uv build --offline` successfully used the cached declared backend instead. Pylint found only three pre-existing optional Anki import-placement notices (9.96/10); no new lint finding remained.

A temporary ignored test-only config points to a test-prefixed database under `/tmp`; it is removed afterwards. No principal database or reader configuration is migrated for tests.

The hardening tests cover conjugation reuse/status, unchanged raw analysis/surface, false-positive POS/span/source guards, explicit registry behavior, 17 collection regressions, generic multi-source reuse, Portuguese/English/mixed brands, per-field validation, anomaly quarantine/reviews, dry-run and genuine isolated analysis failure. Existing tests cover transactions, mappings, revisions, deletion/reconciliation, reverse cards, export and incremental events.

A newly reproduced FK-enabled dry-run bug was fixed minimally: the in-memory acquisition copy now contains an isolated `texts(TxID)` parent stub with only referenced IDs. No reader content is copied and no schema in the real database is altered. The new anomalous-note dry-run tests reproduce and prevent that failure.

## Remaining suspicious analyses and limitations

- There are zero unhandled adjacent `VA + EC + 하/VX` sequences in the rebuilt collection. Standalone 싫어해요 demonstrates a similar potential split, but no real case of that family was found here. No speculative second rule was added.
- Existing context-dependent 아무/아무것 granularity and spaced 이해/하다 remain raw Kiwi behavior. The layer is not a semantic alias model or a noncontiguous compound parser.
- Only the existing five high-confidence grammar detectors are active. Future grammar constructions remain morphology/context, not fabricated matches.
- Source validation uses script proportions, not a full language classifier. It can miss short mixed prose or flag unusually long lower-case Latin code-switching; explicit warnings/metadata support manual review.
- Korean-written loanwords/names can be eligible; arbitrary Hangul and transcription errors are still subject to Kiwi ambiguity. Latin names are retained without a Korean concept under the default policy.
- Real reverse-card/alternate legacy-type coverage is absent in this collection; synthetic coverage is retained.
- Older imported revisions/links are immutable. Processing-signature changes create new revisions rather than silently rewriting history. Clean staging was rebuilt here; previously contaminated databases need an explicit rebuild/reconciliation before unqualified use. Generic ingestion callers must provide new revision references when changing policy.
- No collection correction, automatic status, cloud, scoring or new pedagogical feature was implemented.

## Operational route

Current WSL NAT loopback does not reach Windows AnkiConnect directly. The validation used a temporary loopback-only read-action allowlist bridge; Windows AnkiConnect remained at `127.0.0.1:8765`. No network security was weakened. The audit bridge was stopped after completion.

For daily use, run the existing CLI natively in Windows with an explicitly configured/migrated Windows staging database, or opt into supported Windows 11 WSL mirrored networking and verify loopback after a deliberate restart. Microsoft documents mirrored Windows↔WSL loopback connectivity: [WSL networking](https://learn.microsoft.com/windows/wsl/networking), [configuration](https://learn.microsoft.com/windows/wsl/wsl-config). Neither alternative was newly exercised end-to-end in this audit; do not mistake a recommendation for a passing test.

See [ANKI.md](ANKI.md) for the workflow. Do not expose AnkiConnect on `0.0.0.0`, broaden origins/firewall rules, or access one live SQLite database concurrently from Windows and WSL. No new transport feature was needed for linguistic validation.

## Changes made

This sprint changed only the files below; prior Sprint 2/3 migrations and other uncommitted work were preserved. No core, rendering, raw parser or detector code was changed.

- `lute_korean_parser/knowledge/normalization.py`
- `lute_korean_parser/knowledge/ingestion.py`
- `lute_korean_parser/knowledge/service.py`
- `lute_korean_parser/anki/content.py`
- `lute_korean_parser/anki/extraction.py`
- `lute_korean_parser/anki/sync.py`
- `tests/test_lexical_hardening.py`
- `tests/test_anki_hardening.py`
- `tests/test_anki.py`
- `tests/test_knowledge_lute.py`
- `tests/fixtures/johahada_regressions.json`
- `CONTEXT.md`
- `KNOWLEDGE.md`
- `ANKI.md`
- `README.md`
- `REAL_ANKI_VALIDATION_AFTER_HARDENING.md`

Architecture: generic rule registry/eligibility plus compact provenance; source-specific Anki validation/quarantine; unlinked foreign-span service access; versioned acquisition references; FK-safe dry-run. No new dependency or migration was introduced.

Principal database SHA-256 before/after all real runs:

```text
ca44b1654eed5c22955317428d5f2f33d9566c89472f40f74d281e2916de98e7
```

Private staging, instrumented metrics and full local diagnostics reside under `/tmp/lute-real-anki-hardening/`; the original audit staging remains untouched. Only the 17 relevant Korean regression sentences and focused diagnostics are included in repository artifacts, not the full collection or review history.

## Diagnostic statistics

### Grammar patterns

| Pattern | Linked occurrences |
| --- | ---: |
| -(으)ㄹ 거예요 | 51 |
| -(으)면 | 63 |
| -고 싶다 | 55 |
| -는데 | 51 |
| -아/어서 | 56 |

### Top 50 lexical heads by occurrences

These counts diagnose projection/reuse, not mastery.

| Rank | Lemma | Linked occurrences |
| --- | --- | ---: |
| 1 | 있다 | 143 |
| 2 | 먹다 | 129 |
| 3 | 좋아하다 | 109 |
| 4 | 하다 | 87 |
| 5 | 오늘 | 72 |
| 6 | 가다 | 71 |
| 7 | 싶다 | 55 |
| 8 | 안 | 53 |
| 9 | 공부하다 | 50 |
| 10 | 저 | 49 |
| 11 | 좀 | 45 |
| 12 | 뭐 | 41 |
| 13 | 사람 | 37 |
| 14 | 한국 | 37 |
| 15 | 되다 | 36 |
| 16 | 지금 | 36 |
| 17 | 한국어 | 36 |
| 18 | 집 | 35 |
| 19 | 같이 | 33 |
| 20 | 초밥 | 33 |
| 21 | 같다 | 32 |
| 22 | 마시다 | 32 |
| 23 | 이 | 31 |
| 24 | 맛있다 | 30 |
| 25 | 진짜 | 30 |
| 26 | 너무 | 29 |
| 27 | 어떻다 | 27 |
| 28 | 조금 | 27 |
| 29 | 커피 | 27 |
| 30 | 어디 | 26 |
| 31 | 없다 | 26 |
| 32 | 음식 | 26 |
| 33 | 고양이 | 24 |
| 34 | 이거 | 24 |
| 35 | 부산 | 23 |
| 36 | 친구 | 23 |
| 37 | 시간 | 22 |
| 38 | 일 | 22 |
| 39 | 피곤하다 | 22 |
| 40 | 말하다 | 21 |
| 41 | 물 | 20 |
| 42 | 자다 | 20 |
| 43 | 잘 | 20 |
| 44 | 보다 | 19 |
| 45 | 더 | 18 |
| 46 | 많이 | 18 |
| 47 | 서울 | 18 |
| 48 | 십 | 18 |
| 49 | 내일 | 17 |
| 50 | 쉬다 | 17 |

## Problems classification

| Severity | Finding | Disposition |
| --- | --- | --- |
| important, resolved | 17 좋아하다 notes / 98 reviews associated with decomposed heads | Generic canonicalization; all 17 corrected in clean staging |
| important, resolved | 16 unintended Portuguese concepts from two notes | Generic eligibility plus note validation/quarantine; zero unintended concepts |
| important, resolved | FK-enabled dry-run could fail for quarantined Source creation | Isolated parent-ID stub; regression tests pass |
| expected limitation | Exact historical note text is unavailable for 6,055 reviews | Explicit first-observed/indirect provenance retained |
| operational limitation | Default WSL NAT cannot reach Windows loopback AnkiConnect | Safe audit bridge validated; native Windows/mirrored daily workflows documented |
| environmental | Japanese/MeCab unavailable | Six failures reported separately; Korean/Lute selected tests pass |

No remaining blocker was found for the hardened collection as a lexical Evidence source. The next sprint was not implemented.
