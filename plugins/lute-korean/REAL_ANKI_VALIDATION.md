# Real Anki validation — Sprint 3 hardening

Validation date: 2026-09-30. This is an operational and linguistic audit of the
real collection, not an acquisition assessment. No scoring, automatic status
promotion, card editing or new pedagogical functionality was implemented.

## Verdict

**NO — not yet an unqualified, trustworthy source of lexical Knowledge Evidence
for the next sprint.**

The read-only connector, persistence, review provenance, full-history recovery,
idempotency and JSON summaries passed against the real collection. The current
linguistic projection and collection content have two material blockers:

1. **17 notes / 17 occurrences** of forms of `좋아하다` are projected as
   `좋다 + 하다`. Those sources have **98 associated review events**. Raw morphology
   is retained correctly, but these lexical associations are not reliable enough
   to feed an unqualified learner-state calculation. A deliberate morphological
   projection decision and regression coverage are needed; no result was silently
   rewritten to make the audit look correct.
2. **Two notes** contain Portuguese explanation/speaker labels inside `Coreano`,
   creating **16 unintended non-Korean lexical items**. Their content must be
   explicitly corrected or excluded by an agreed import scope before considering
   the entire collection clean. This audit neither edits nor excludes them.

The Windows/WSL route is a separate operational prerequisite: direct WSL
localhost failed and validation used a temporary read-only bridge. For regular
operation, use the existing CLI on Windows alongside Anki, or establish a stable
local forwarding route. The temporary bridge is not a deployed integration.

Historical uncertainty, absence of reverse cards in this collection, and absence
of naturally new reviews during the audit are stated below. They are not hidden
as passing tests and do not independently constitute a connector bug.

## Environment

| Component | Observed value |
| --- | --- |
| Analysis/runtime OS | Linux / WSL2, kernel 6.6.87.2-microsoft-standard-WSL2 |
| Anki host OS | Microsoft Windows 11 Pro 10.0.26200 |
| Python | 3.14.4 |
| Lute | 3.10.3 |
| Plugin | lute-korean 0.3.0 |
| Kiwi | kiwipiepy 0.23.2 / kiwipiepy-model 0.23.0 |
| Anki | 26.9 |
| AnkiConnect | API version 6; add-on release/build not reported by this API |
| Active profile | Usuário 1 |
| Real endpoint | Windows http://127.0.0.1:8765 |
| Validation endpoint | WSL http://127.0.0.1:18765 → Windows loopback |
| Staging database | /tmp/lute-real-anki-validation/staging.db |

`doctor` was executed first, followed by `preview`, before any product-code
change. Initially both failed at WSL `127.0.0.1:8765`: after bypassing the sandbox
network restriction, the actual error was connection refused. Opening Anki on
Windows did not make WSL localhost reachable. A Windows-local read-only version
request succeeded. A temporary loopback bridge then allowed the real CLI to run.

The bridge only accepts an explicit allowlist of read-only actions. It forwards
requests to Windows localhost using PowerShell; it does not modify Anki or send
collection data to cloud services. Temporary diagnostic-script corrections were
not changes to the product adapter. Its process-start overhead is included in all
reported live timings.

Initial discovery intentionally used `mappings: {}`. Doctor reached the real
collection but returned `ok=false` because all 875 notes were unmapped. Preview
reported the same fields. After an explicit mapping was written, doctor returned
`ok=true`; preview reported zero unmapped notes and zero problems.

## Collection

| Metric | Observed |
| --- | --- |
| Notes discovered / analyzable with the explicit mapping | 875 |
| Cards | 875 |
| Active note types | 1 |
| Defined note types | 19 |
| Populated decks | 10 |
| Cards per note | 875 notes have exactly one card |
| Suspended cards | 4 |
| Review events | 6055 |
| Notes with sound markup | 875 |
| Notes with HTML in any field | 197 |
| Notes with HTML in Coreano | 196 |
| Cleaned Korean fields containing a newline | 1 |
| Mapped Korean fields without Hangul | 0 |
| Notes with Hangul in multiple fields | 72 |
| Unique cleaned source texts | 850 |

### Decks with cards

| Deck | Cards |
| --- | --- |
| Korean | 122 |
| Korean::Core Korean | 377 |
| Korean::Days of the week | 7 |
| Korean::Months | 12 |
| Korean::Native Numbers | 32 |
| Korean::Sino Numbers | 32 |
| Korean::TPRS ep4 | 113 |
| Korean::TPRS ep5 | 104 |
| Korean::TPRS ep6 | 50 |
| Korean::TPRS ep7 | 26 |

`Default` is also defined, with no cards in this snapshot. Suspended cards are included in all counts.

### Note types and mappings

| Note type | Notes | Fields | Explicit roles |
| --- | --- | --- | --- |
| Coreano | 875 | Coreano / Tradução / Áudio / Notas | Coreano → Korean; Tradução → translation; Notas + Áudio → context/media metadata |

The 72 additional Hangul-containing candidates are `Notas`, not a second main
sentence field. They remain metadata; they were not concatenated into the Korean
source. `Tradução` and `Áudio` had no cleaned Hangul candidates. Field roles were
chosen explicitly after live discovery, not silently persisted by autodetection.

The following 18 other note types are defined but have **zero notes** in the
queried collection. No mapping or real content compatibility is claimed for them:

- Anki Generator — Básico
- Basic
- Básico
- Básico (cartão invertido opcional)
- Básico (digite a resposta)
- Básico (e cartão invertido)
- Cloze Hangul
- Generic Simple Model
- Generic Simple Model+
- Generic Simple Model+ copy
- Generic Simple Model++
- Korean Detailed Grammar (with reversed card)
- Korean Detailed Vocabulary (with reversed card)
- Korean Sentence
- Korean Vocab
- Language Reactor - Word
- Oclusão de Imagem
- Omissão de Palavras

The temporary mapping used was:

```yaml
anki:
  source_identity: windows-real-coreano-validation
  profile: Usuário 1
  endpoint: http://127.0.0.1:18765  # temporary validation bridge
  query: ''                      # entire active profile
  timeout: 150
  mappings:
    Coreano:
      korean_fields: [Coreano]
      translation_fields: [Tradução]
      metadata_fields: [Notas, Áudio]
```

The normal Windows-local endpoint is `http://127.0.0.1:8765`. The profile and source
identity must remain explicit and stable when reusing staging history. Renaming
source identity would create a different provenance namespace.

## Compatibility and legacy content

- **HTML:** 196 Korean fields contain presentation HTML. All 875 extracted sources
  ingested successfully. Presentation tags were removed; original field hashes,
  clean text, Unicode offsets and punctuation remain available.
- **Audio:** all 875 notes contain `[sound:...]`; media markers were removed from
  linguistic text and `has_audio=true` was preserved. Audio was not downloaded.
  No listening/production evidence was inferred.
- **Multiline:** one note contains a dialogue with Portuguese speaker labels.
  Its line break and Korean punctuation are preserved; the labels also become
  lexical heads, which is a content-quality issue described below.
- **Reverse cards:** zero real examples. All 875 cards use ordinal 0 / `Card 1`,
  with direct question fields `Coreano | Áudio` and answer fields
  `Notas | Tradução`. Real reverse-card behavior is **not validated here**;
  synthetic Sprint 3 coverage remains the available evidence for that case.
- **Legacy:** older, simple TPRS/location sentences, individual number words,
  HTML-wrapped fields, recent multi-clause conversational sentences and mixed
  Portuguese explanations coexist under the same current note type. There are
  no current alternate legacy note types or notes without audio to test.
- Note IDs, treated as Anki's millisecond creation markers, span
  **2026-06-28 15:41:30.935 UTC → 2026-09-30 02:50:09.704 UTC**.
  **794 notes** have a modification marker more than 60 seconds after that ID.
  This is an edit indicator, not proof that Korean text changed: tags, audio or
  other fields may have changed. No historical original fields can be recovered
  from this snapshot alone.

### Duplicate and related content

There are **25 exact cleaned-text groups**, each containing two different notes:
**50 notes**, or 25 additional notes beyond 850 unique texts. They are real Anki
note-level duplicates, not reverse cards. All have the same current note type.
No duplicate text spanning different active note types was found because only
one type has notes.

Examples: `아시아는 지구에 있어요.`, `지구는 태양계에 있어요.`, `이건 뭐예요?`.
There was no automatic deduplication: each note retains its own Source and review
provenance, even when linguistic content is identical.

A diagnostic `SequenceMatcher` comparison of distinct texts at similarity
**≥0.90**, excluding texts shorter than ten characters, found **28 candidate
pairs**. This is a text-similarity count, not a semantic duplicate detector:

- `하늘에 구름이 있어요.` / `하늘에 구름이 없어요.` — opposite assertions.
- `서울은 한국에 있어요.` / `서울도 한국에 있어요.` — different particles.
- `유럽은 어디에 있어요?` / `유럽은 어디 있어요?` — related phrasing.

These demonstrate legitimate linguistic repetition. No candidates were merged,
deleted, or interpreted as independent acquisition tests.

## Linguistic analysis

### Persistent staging statistics

| Entity | Count |
| --- | --- |
| Lexical Concepts | 371 |
| Grammar Patterns | 5 |
| Chunks | 0 |
| Sources | 875 |
| Observed note revisions | 875 |
| Occurrences | 3124 |
| Occurrence ↔ item associations | 3346 |
| Generic Evidence rows (content exposures) | 3346 |
| Canonical Anki review events | 6055 |

Generic Evidence rows and canonical Anki events are separate counts. Reviews
are not copied into one separate row per word. One occurrence can relate to more
than one head, and grammar spans can overlap lexical spans. The 3,346 associations
contain 2,970 further associations beyond the 376 distinct items; this describes
reuse within the collection, not mastery. The copied principal database initially
had no Knowledge tables/items, so there was no pre-existing acquisition item to
reuse from that database.

All **376 items remain overall `unknown`**. There are **zero explicit dimensional
status rows**; unset skill statuses were not invented. Generic ingestion exposes
content in the existing reading dimension; Anki review modality remains
unspecified. Native Terms and their statuses were not changed.

### Surface diversity per lexical concept

| Distinct surfaces per lemma | Number of lemmas |
| --- | --- |
| 1 | 212 |
| 2 | 64 |
| 3 | 39 |
| 4 | 19 |
| 5 | 14 |
| 6 | 9 |
| 7 | 3 |
| 8 | 4 |
| 9 | 1 |
| 10 | 1 |
| 12 | 1 |
| 14 | 2 |
| 18 | 2 |

### Top 50 lemmas by linked occurrences

| Rank | Lemma | Occurrences | Distinct surfaces |
| --- | --- | --- | --- |
| 1 | 있다 | 143 | 14 |
| 2 | 먹다 | 129 | 14 |
| 3 | 하다 | 104 | 18 |
| 4 | 좋아하다 | 93 | 7 |
| 5 | 오늘 | 72 | 3 |
| 6 | 가다 | 71 | 12 |
| 7 | 싶다 | 55 | 6 |
| 8 | 안 | 53 | 1 |
| 9 | 공부하다 | 50 | 8 |
| 10 | 저 | 49 | 8 |
| 11 | 좀 | 45 | 1 |
| 12 | 뭐 | 41 | 10 |
| 13 | 사람 | 37 | 8 |
| 14 | 한국 | 37 | 6 |
| 15 | 되다 | 36 | 6 |
| 16 | 지금 | 36 | 2 |
| 17 | 한국어 | 36 | 4 |
| 18 | 집 | 35 | 3 |
| 19 | 좋다 | 34 | 8 |
| 20 | 같이 | 33 | 1 |
| 21 | 초밥 | 33 | 6 |
| 22 | 같다 | 32 | 2 |
| 23 | 마시다 | 32 | 6 |
| 24 | 이 | 31 | 4 |
| 25 | 맛있다 | 30 | 9 |
| 26 | 진짜 | 30 | 2 |
| 27 | 너무 | 29 | 1 |
| 28 | 어떻다 | 27 | 2 |
| 29 | 조금 | 27 | 5 |
| 30 | 커피 | 27 | 5 |
| 31 | 어디 | 26 | 5 |
| 32 | 없다 | 26 | 4 |
| 33 | 음식 | 26 | 6 |
| 34 | 고양이 | 24 | 6 |
| 35 | 이거 | 24 | 2 |
| 36 | 부산 | 23 | 3 |
| 37 | 친구 | 23 | 5 |
| 38 | 시간 | 22 | 3 |
| 39 | 일 | 22 | 5 |
| 40 | 피곤하다 | 22 | 6 |
| 41 | 말하다 | 21 | 5 |
| 42 | 물 | 20 | 4 |
| 43 | 자다 | 20 | 4 |
| 44 | 잘 | 20 | 2 |
| 45 | 보다 | 19 | 7 |
| 46 | 더 | 18 | 1 |
| 47 | 많이 | 18 | 1 |
| 48 | 서울 | 18 | 5 |
| 49 | 십 | 18 | 18 |
| 50 | 내일 | 17 | 3 |

Counts include duplicate-note contexts and the issues identified in this audit; they are not knowledge scores.

### Grammar patterns

| Pattern | Detected occurrences |
| --- | --- |
| -(으)면 | 63 |
| -아/어서 | 56 |
| -고 싶다 | 55 |
| -는데 | 51 |
| -(으)ㄹ 거예요 | 51 |

These are the five existing conservative detectors. Past tense remains
morphological metadata, not an automatically created pedagogical pattern.
Constructions such as `-(으)ㄹ 것 같다`, `-아/어야 되다` and `-(으)ㄹ 수 있다`
are not implemented detectors; their absence below is expected, not a false claim
that the collection has no such grammar.

### Thirty real samples

The following deterministic sample covers actual present/past/future forms,
particles, all five detected patterns, short/long/legacy/travel/conversational,
HTML, number and multiline sources. This was a read-only analysis outside the
sync timing windows; the original Kiwi output was not manually corrected.
`—` means none of the five pedagogical detectors fired, not no grammar.

| Sample / category | Original cleaned source | Actual lexical concepts | Actual patterns |
| --- | --- | --- | --- |
| S01 / past eat | 어제 초밥을 먹었어요. | 어제, 초밥, 먹다 | — |
| S02 / past go | 토요일에 친구 결혼식에 갔어요. 그래서 아침에 기차를 탔어요. | 토요일, 친구, 결혼식, 가다, 그래서, 아침, 기차, 타다 | — |
| S03 / adjective connective | 오늘은 너무 피곤해서 좀 쉴 거예요. | 오늘, 너무, 피곤하다, 좀, 쉬다 | -아/어서, -(으)ㄹ 거예요 |
| S04 / place particle 에서 | 저는 한국에서 일해요. | 저, 한국, 일하다 | — |
| S05 / place particle 에 | 부산은 한국에 있어요. | 부산, 한국, 있다 | — |
| S06 / topic particle | 한국은 아시아에 있어요. | 한국, 아시아, 있다 | — |
| S07 / -(으)ㄹ 거예요 | 내일 일할 거예요. | 내일, 일하다 | -(으)ㄹ 거예요 |
| S08 / -(으)면 | 피곤하면 자요. | 피곤하다, 자다 | -(으)면 |
| S09 / -고 싶다 | 또 먹고 싶어요. | 또, 먹다, 싶다 | -고 싶다 |
| S10 / -는데 | 졸린데 공부해야 돼요. | 졸리다, 공부하다, 되다 | -는데 |
| S11 / -아/어서 | 피곤해서 집에 가요. | 피곤하다, 집, 가다 | -아/어서 |
| S12 / legacy present | 구름이 하늘에 있어요. | 구름, 하늘, 있다 | — |
| S13 / legacy present | 하늘에 구름이 있어요. | 하늘, 구름, 있다 | — |
| S14 / legacy present | 하늘에 구름이 없어요. | 하늘, 구름, 없다 | — |
| S15 / short sentence | 둘 | 둘 | — |
| S16 / short sentence | 셋 | 셋 | — |
| S17 / long Korean sentence | 처음에는 아무것도 이해할 수 없었어요. 그런데 지금은 천천히 말하면 이해할 수 있어요. | 처음, 아무, 이해하다, 없다, 그런데, 지금, 천천히, 말하다, 있다 | -(으)면 |
| S18 / long Korean sentence | 첫 번째 시간에는 아무것도 이해 못 했어요. 지금은 조금 이해할 수 있어요. | 첫, 시간, 아무, 이해, 못, 하다, 지금, 조금, 이해하다, 있다 | — |
| S19 / travel/context | 친구가 이 식당이 맛있다고 했어요. | 친구, 이, 식당, 맛있다, 하다 | — |
| S20 / travel/context | 이 식당 어때요? 같이 가요? | 이, 식당, 어떻다, 같이, 가다 | — |
| S21 / travel/context | 이 학생들이 버스를 타고 학교에 가요 | 이, 학생, 버스, 타다, 학교, 가다 | — |
| S22 / conversation | 이거 어때요? 저는 좋은 것 같아요. | 이거, 어떻다, 저, 좋다, 같다 | — |
| S23 / conversation | 이제는 천천히 말하면 좀 알아들을 수 있어요. | 이제, 천천히, 말하다, 좀, 알아듣다, 있다 | -(으)면 |
| S24 / conversation | 처음에는 아무것도 못 알아들었어요. | 처음, 아무것, 못, 알아듣다 | — |
| S25 / multiline | Alguém: 한국 어때요? ↵ Eu: 생각보다 재미있어요. | Alguém, 한국, 어떻다, Eu, 생각, 재미있다 | — |
| S26 / mixed Portuguese content | 좋아요, porque você provavelmente encontrou mais 좋아해요, mas 좋다 aparece o tempo todo em pensamentos cotidianos. | 좋다, porque, você, provavelmente, encontrou, mais, 좋아하다, mas, aparece, o, tempo, todo, em, pensamentos, cotid, ianos. | — |
| S27 / HTML legacy | 서울은 한국에 있어요. | 서울, 한국, 있다 | — |
| S28 / HTML legacy | 프랑스는 유럽에 있어요. | 프랑스, 유럽, 있다 | — |
| S29 / number vocabulary | 하나 | 하나 | — |
| S30 / recent | 같이 가면 좋을 것 같아요. | 같이, 가다, 좋다, 같다 | -(으)면 |

### Sample assessment and suspicious analyses

- S01 retains `먹었어요` and relates it to `먹다`; S02 retains `갔어요` and relates
  it to `가다`. Past endings are retained in morphology.
- S03/S08/S11 relate conjugated `피곤하다` forms to one lexical concept; the
  connective/future/conditional detectors fire on the appropriate morphology.
- S04/S05/S06 share `한국` despite `한국에서`, `한국에`, `한국은`.
- S07/S09/S10 preserve future, desire and `-는데` evidence without fragmenting
  display text. S23/S24 recognize `알아듣다` in real conversational sentences.
- S17/S24 analyze `아무것도` differently (`아무` versus `아무것`) depending on
  context. The noun/scaffolding projection follows Kiwi; it does not provide a
  semantic alias layer for equivalent phrases. This is an expected lexical
  granularity limitation, not an invented correction.
- S18 analyzes separated `이해 못 했어요` as `이해 + 못 + 하다`, while another
  clause contains `이해하다`. The current unit-level projection does not fuse
  noncontiguous lexical constructions. This is preserved and documented.
- S25 creates `Alguém` and `Eu` from speaker labels in the source field. S26
  creates Portuguese heads from prose in the Korean field; even `cotidianos.`
  is split by Kiwi into `cotid` / `ianos.`. These are not trustworthy Korean
  lexical concepts. The full offending output is shown, not repaired.
- Three other mixed-Latin notes contain `BTS`, which is a legitimate name. The
  audit does not strip Latin text globally. In total there are **five** mixed-Latin
  Korean fields: three BTS notes and two problematic Portuguese-containing notes.

Additional real-source inspection found **17 notes / 17 occurrences** where
forms of `좋아하다` become `좋다 + 하다` rather than the expected lexical verb.
For example:

```text
뭐 좋아해요?
Surface: 좋아해요
Kiwi: 좋/VA + 어/EC + 하/VX + 어요/EF
Current lexical projection: 좋다, 하다
Expected lexical relationship in this context: 좋아하다
```

The same issue appears in `맥주는 좋아하는데 소주는 안 좋아해요.` and in negative
preference sentences. Other occurrences do yield `좋아하다`, so the concept's
93 linked occurrences coexist with these 17 fragmented cases. Of the 34
occurrences linked to `좋다`, 17 are these `좋아하다` forms. The 17 source notes
have **98 associated canonical review events**; these remain note-level indirect
reviews, not 98 direct tests of either lemma. This is an important quality limit
of the current analyzer/projection combination, not HTTP corruption or loss of
raw morphology. No broad rule or hardcoded replacement was added during the audit.

### Identity and span sanity checks

- No duplicate `(kind, identity)` items and no duplicate external event keys.
- All **3,124** occurrence surfaces exactly equal their original source slices;
  context/start/end bounds are valid. No surface was replaced with its lemma.
- `먹다` has 14 surface forms, including `먹어요`, `먹었어요`, `먹으면`, `먹어서`,
  `먹고`; no independent lexical `먹어요` or `먹었어요` item was created.
- `가다` has 12 forms, including `가요`, `갔어요`, `가면`, `가서`.
- `피곤하다` has six forms, including `피곤해요`, `피곤해서`.
- `한국` has six forms: `한국`, `한국에`, `한국에서`, `한국에서는`, `한국은`, `한국이`.
- `가지다` / forms containing `가지` are absent from the real collection, so this
  exact pair cannot be validated against real evidence. No artificial note was
  created to fill that coverage gap.
- `좋다` and `좋아하다` are distinct entities; the context-dependent fragmentation
  described above is an incorrect association risk, not an identity-key collision.

## Review history

| Metric | Observed |
| --- | --- |
| Total events | 6055 |
| Again (1) | 717 |
| Hard (2) | 214 |
| Good (3) | 5025 |
| Easy (4) | 99 |
| Other ratings | 0 |
| Cards without reviews | 28 |
| Cards with at least 20 reviews | 15 |
| Maximum reviews on one card | 50 |
| Earliest review UTC | 2026-06-30 00:38:45.903 |
| Latest review UTC | 2026-09-30 03:24:09.055 |

For example, `먹다` has **125 distinct note/card contexts and 732 associated
reviews**: Again 64 / Hard 26 / Good 634 / Easy 8. Its 129 lexical occurrences do
not multiply reviews when a sentence contains the word more than once. `가다`
has 63 notes/cards and 297 associated events. Neither summary implies a direct
word test or any status change.

## Historical uncertainty

| Stored association category | Events |
| --- | --- |
| Confirmed exact historical content snapshot | 0 |
| Observed multi-revision modification-boundary association | 0 |
| First observed snapshot; historical content unverified | 6055 |

**100%** of imported review events use `association_basis=first_observed_snapshot`.
All 875 notes were first observed during this audit, with one source revision per
note. AnkiConnect returns the current note content and review history, not its
complete historical text-edit log.

As an auxiliary marker-only check, **5,165 reviews (85.30%) precede the current
note modification timestamp**, while **890 (14.70%) occur at or after it**.
The latter are compatible with the current marker, but are **not reclassified as
proven exact text matches**. A modification can affect audio/tags/other fields,
markers have limited precision, and unobserved historical edits cannot be
reconstructed. There are no missing `mod` markers in this collection.

No real note was edited during validation. Consequently, creation of a second
observed content revision from a real edit was not exercised here; existing
synthetic revision coverage is not presented as a real-collection test. Notes
with old/current marker differences are indicators, not recovered revisions.

## Synchronization and performance

Every command contacted the real Windows Anki instance through the temporary
read-only bridge. No fake adapter or test collection replaced it. Timings below
are wall-clock measurements of the actual console-command execution, including
Windows bridge overhead and cold process startup.

| Run | Notes | New / changed / skipped | Reviews imported | Reviews skipped | Kiwi calls | Total seconds | HTTP/bridge seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Initial dry-run | 875 | 875/0/0 | 6055 | 0 | 875 | 28.858 | 15.613 |
| First staging sync | 875 | 875/0/0 | 6055 | 0 | 875 | 29.59 | 15.658 |
| Second unchanged sync | 875 | 0/0/875 | 0 | 0 | 0 | 20.697 | 19.636 |
| Full-review dry-run | 875 | 0/0/875 | 0 | 6055 | 0 | 16.867 | 15.639 |
| Full-review staging sync | 875 | 0/0/875 | 0 | 6055 | 0 | 16.897 | 15.715 |
| Later incremental sync | 875 | 0/0/875 | 0 | 0 | 0 | 20.281 | 19.175 |

All runs had **zero ingestion errors**, zero unmapped notes after configuration,
and zero missing/out-of-scope notes/cards. Initial dry-run would create 371 lexical
and five grammar items; unchanged/full-history runs created none. Suspended cards
were included. No notes were silently filtered out for source-quality concerns.

Initial/full-history requests used five `notesInfo` batches, five `cardsInfo`
batches, one template request, and five `getReviewsOfCards` batches. Incremental
requests used the same note/card batches and **ten deck-level `cardReviews`
requests**. Health/version/profile calls surround each snapshot. There was no
per-note/card HTTP N+1 pattern and zero redundant model analysis on unchanged notes.
The existing cached model was initialized once per process when analysis was needed.

The unchanged sync's 20.697 seconds contains 19.636 seconds of HTTP/bridge time;
local handling was about 1.06 seconds. The slower incremental transport relative
to full-history is explained by ten deck requests versus five card-history batches
and PowerShell startup per request. This measurement is not native Windows/direct
HTTP performance. No speculative optimization was made.

### Dry-run integrity

- Original staging database hashes remained identical across both dry-runs.
- SQL statement monitoring detected **zero INSERT/UPDATE/DELETE/DDL statements**
  against the original staging connection during dry-run. The simulated ingestion
  wrote only to its in-memory copy.
- The principal database hash remained
  `ca44b1654eed5c22955317428d5f2f33d9566c89472f40f74d281e2916de98e7`
  throughout all runs.

The principal `docker/my_data/lute.db` initially had **no acquisition tables**.
It was opened only read-only for a SQLite backup; both existing migrations were
applied with Lute's migrator **only to the copy**. No migration or first sync was
performed on the principal database. Updating/backing up that runtime before any
future principal ingestion remains an explicit deployment step.

### Second-sync and full-history integrity

After the second sync, full-review sync and later incremental sync, ordered-row
fingerprints remained identical for all ten content/state/history tables:
items, dimensions, sources, occurrences, occurrence-item links, generic evidence,
notes, revisions, cards and reviews. IDs, statuses, content and external keys were
preserved. Only the integration's successful-sync timestamp/report changed.
Foreign-key checks returned no violations.

The complete historical fetch returned the same **6,055 event IDs** in dry-run
and staging. All were skipped as already imported; none was duplicated. Ordinary
unchanged sync performs operational upserts/cursor updates, so its physical
staging-file hash changes through the last-success report even though content
and event fingerprints do not. This is intentional operational persistence.

The later incremental poll found **zero naturally new reviews**. Positive import
of a newly performed real review is therefore **not validated in this session**.
No review was performed, fabricated or edited to force the scenario. The negative
incremental case and full-event idempotency passed against the real collection.

### Export and diagnostics

The actual `KnowledgeService.export(include_anki=True)` output contained schema
version 1, 371 lexical items and five grammar items, with 376 optional Anki
summaries and no raw `anki_reviews` arrays by default. Anki review statistics were
read through the public service, not interpreted as pedagogical statuses.
Operational JSON reports, snapshots, mappings and the staging database are kept
locally under `/tmp/lute-real-anki-validation/` (directory mode 700). The detailed
snapshot is intentionally not checked into the repository. This temporary folder
contains private study content and may disappear on system cleanup.

## Problems found

| Severity | Problem | Impact / disposition |
| --- | --- | --- |
| critical | No destructive write, lost history, duplicate event, transaction or span-corruption failure observed | All principal integrity and staging idempotency checks passed. |
| important | 17 좋아하다 forms fragmented as 좋다 + 하다 | 98 note-level reviews are linked to these sources; lexical evidence is ambiguous. Requires a deliberate projection decision, not an adapter guess. |
| important | Portuguese text inside two Korean source fields | 16 unintended lexical items; no automatic cleanup or exclusion. |
| important / operational | WSL localhost cannot reach Windows AnkiConnect directly | Temporary bridge validated the real pipeline; regular operation still needs Windows CLI or stable local forwarding. |
| minor | 25 exact duplicate-note groups / 28 near-text candidate pairs | Retained as distinct provenance. No automatic deduplication; similar text can have different meaning. |
| expected limitation | 6,055 first-snapshot historical associations | Exact past Korean text not recoverable; uncertainty preserved, never upgraded to direct mastery evidence. |
| expected limitation | No reverse cards, alternate active legacy types or naturally new reviews | Real coverage unavailable; not reported as passing real tests. |
| expected limitation | Context-dependent 아무/아무것 and separated 이해/하다 | Current unit-level lexical projection is not a semantic alias/noncontiguous-expression model. |
| expected limitation | Only five conservative grammar detectors | Unsupported grammar remains morphology/context; no perfect grammar parser claimed. |

## Changes made

**No production-code correction was necessary for the observed Sprint 3 transport,
persistence, idempotency or review import behavior.** No parser, grammar detector,
Knowledge Model, schema, source note, card or tag was modified during this audit.
The unexpected Kiwi decisions and source contamination were recorded rather than
replaced with artificial outputs. Therefore no product fix/regression test was
introduced and the existing Sprint 1–3 pytest suite was not rerun as if code had
changed. Actual CLI operations, SQL monitoring, row fingerprints, hashes, service
export and linguistic inspections constitute this live validation.

Repository addition: `plugins/lute-korean/REAL_ANKI_VALIDATION.md` only. Discovery,
bridge, timing/inventory helpers, mapping and staging artifacts were temporary
local validation tooling, not new shipped functionality. The bridge is stopped
after completion. The Anki Desktop process is left running and untouched.

The next work should resolve the two quality blockers and establish the normal
local runtime route, then repeat this audit. It should not introduce Evidence
Scoring, automatic promotions or any other Sprint 4 feature.
