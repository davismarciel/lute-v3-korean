# Sprint 3 validation

Environment: Linux, Python 3.14.4, Lute 3.10.3, lute-korean 0.3.0,
kiwipiepy 0.23.2 / models 0.23.0. All fixtures and databases are synthetic and
local; no personal Anki collection, Docker data or production database was read
or changed. Windows execution and a live Anki Desktop connection were not tested.

## Automated tests

```sh
python -m pytest plugins/lute-korean/tests tests/unit/parse tests/unit/language tests/unit/read tests/unit/book tests/unit/db/setup tests/orm/test_Term.py tests/orm/test_Language.py tests/orm/test_Text.py --ignore=tests/unit/parse/test_JapaneseParser.py -k 'not test_changing_text_to_same_thing_does_not_throw' -q -s
```

Final combined result: **293 passed, 1 deselected**. The plugin contains the
unchanged 52 Sprint 1 cases, 54 Sprint 2 cases, and 36 Sprint 3 cases. The relevant
existing Lute coverage is 132 unit tests and 19 ORM tests. The deselected Japanese
ORM case and excluded Japanese parser file require unavailable MeCab; they were
not modified. Temporary ignored test configuration was removed after the run.

New coverage includes:

- Explicit mappings for three note types, field discovery, privacy-safe preview,
  invalid query/transport/profile behavior, and no guessed persistent mappings.
- Plain/HTML/multiline/cloze/sound fields, Hangul and audio metadata.
- Stable note/card identity, reverse cards, real Kiwi analysis once per note
  revision, existing lexical reuse and unchanged manual acquisition statuses.
- Edited/reverted content, immutable historical event associations, metadata-only
  edits, deleted cards/notes, query exclusion, suspension and mapping revisions.
- Ratings Again/Hard/Good/Easy, canonical events, namespaced event keys,
  repeated/full/incremental imports, conflicting events, and mutable Anki USN.
- Atomic database failure and event failure rollback, caller rollback, recoverable
  individual note errors and mapping validation before persistence.
- Dry-run with SQL statement monitoring: no original-database writes.
- Local CLI doctor/preview/sync/status/export with fake transport/source and no
  Anki Desktop; existing JSON unchanged unless summaries/details are requested.
- Multiple occurrences of the same head do not multiply event summary counts.
- Additive migration through actual Lute startup twice; foreign-key checks pass.
- HTTP batches and a single template lookup per note type within one operation;
  new card histories and deck-based incremental review calls are tested.

Pylint passed for the Anki modules and amended KnowledgeService. Wheel and source
archive built offline; the wheel contains all nine Anki modules and its console
entry point. The console command was installed in the isolated environment and
its help verified. There are no new OS-level or cloud dependencies.

## Scale

The synthetic fixture contains **1,000 notes, 2,000 reverse cards and 40,000 review
events**, using real Kiwi rather than a fake morphology result:

- First ingestion: **17.757 seconds**; 1,000 analysis calls, 40,000 canonical events.
- Unchanged incremental run: **1.541 seconds**; zero additional analysis calls,
  zero additional review rows, all 1,000 notes skipped linguistically.

The Korean parser shares one Kiwi model in the process. HTTP batching is validated
separately through a fake transport; these timings measure local extraction,
analysis and SQLite ingestion, not live Anki network performance. Fixture notes
repeat one representative sentence; real lexical diversity will change costs.
No threshold derived from these measurements changes acquisition status.

## Actual fixture output

Note `123`, cards `456` and `789`, text:

```text
한국에 가면 많이 먹을 거예요.
```

```text
LEXICAL                  SURFACE
한국                     한국에
가다                     가면
많이                     많이
먹다                     먹을

GRAMMAR
-(으)면
-(으)ㄹ 거예요

Created: 4 lexical + 2 grammar items, all unknown
Content: one versioned Source, one occurrence per linguistic unit
Exposure: one generic exposure per associated item/occurrence
Reviews: 4 canonical events, not 4 events copied per item
Cards: 2, content analyzed once
Ratings: Again 1 / Hard 1 / Good 1 / Easy 1
Review dimension: unspecified; directness: indirect; scope: note_content
Last review: 2023-11-14T22:13:30.003000+00:00
```

A separate required fixture starts with `먹다 = practicing` and imports
`오늘 친구랑 같이 밥을 먹었어요.`. It reuses the lexical ID, preserves surface
`먹었어요`, records exposure/reviews and leaves status `practicing`.

Changing note `123` to `오늘은 피곤해서 일찍 잘 거예요.` produced:

```text
LEXICAL: 오늘, 피곤하다, 일찍, 자다
GRAMMAR: -아/어서, -(으)ㄹ 거예요
notes_changed: 1
reviews_imported: 0
```

Earlier sources and their four reviews remained intact. The tests additionally
cover the required edit adding `친구랑 같이` to the original Korean sentence,
with old/new reviews retaining their appropriate observed-source associations.

## Optional real connection smoke test

After configuring your own note-type mappings and starting local Anki:

```sh
python plugins/lute-korean/scripts/anki_smoke.py --config anki.yml
lute-korean-anki preview --config anki.yml
lute-korean-anki sync --config anki.yml --database /path/to/lute.db --dry-run
```

The script and preview do not open a database or print collection sentence text.
Dry-run uses an in-memory copy and never writes to the original database. A real
sync remains explicit; see ANKI.md for backups, identity and transaction policy.

## Scope review

The only Sprint 3 core change is its own additive migration; no Term, reader,
parser, grammar detector, central table, UI or automatic import hook was changed.
The KnowledgeService additions are opt-in summaries/review access. Existing
Sprint 2 work already present in the workspace and unrelated Docker data were
preserved. No package parsing, scoring, automatic statuses or Anki writes were
implemented. See ANKI.md for uncertain historical content, cursor/backdated import
and reconciliation limitations.
