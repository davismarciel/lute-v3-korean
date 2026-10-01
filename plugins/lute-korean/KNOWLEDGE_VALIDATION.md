# Sprint 2 validation

Environment: Linux, Python 3.14.4, Lute 3.10.3, lute-korean 0.2.0,
kiwipiepy 0.23.2 and kiwipiepy-model 0.23.0. All databases and the Python
environment used for validation are temporary; Docker user data was untouched.

## Tests and commands

```sh
python -m pytest plugins/lute-korean/tests -q
python -m pytest plugins/lute-korean/tests tests/unit/parse tests/unit/language tests/unit/read tests/unit/book tests/unit/db/setup tests/orm/test_Term.py tests/orm/test_Language.py tests/orm/test_Text.py --ignore=tests/unit/parse/test_JapaneseParser.py -k 'not test_changing_text_to_same_thing_does_not_throw' -q
python -m pylint plugins/lute-korean/lute_korean_parser/knowledge --score=n
uv build plugins/lute-korean --out-dir /tmp/lute-korean-dist
```

The combined run before adding the dialogue fixture passed 256 tests with one
Japanese ORM case deselected. Existing coverage comprised 132 unit tests and
19 ORM tests. The plugin retains 52 unchanged Sprint 1 tests and adds 54 Sprint 2
cases, including the subsequent dialogue test.

The initial ORM run passed 19 tests and failed one Japanese case because MeCab
was unavailable (`Unsupported parser type 'japanese'`). That case was deselected
in the passing combined run. Japanese parser tests require the same missing
system dependency and were explicitly excluded. No Japanese tests were edited.

New coverage includes:

- Required lexical identity across conjugations, particles and adjectives.
- All six required sentences and positive/negative cases for each detector,
  including punctuation and newline boundaries.
- Persistence/reload, manual statuses and per-skill dimensions, chunks CRUD,
  occurrence relationships, small metadata, supported future source types.
- Idempotency, source revision conflicts, event-key conflicts, timestamp validation,
  failed-ingestion rollback and caller-controlled commit/rollback.
- Production migrator on an existing database: migration runs once, retains core
  rows and enforces knowledge constraints. App startup tests cover fresh migration.
- Opt-in Korean page adapter, page revisions/deletion, unchanged Term statuses,
  reading/term-form routes and rejection of other-language pages.
- JSON structure/stability, read-only diagnosis, explicit persistence/export and
  preservation of transcript-file CRLF offsets.

Pylint passed. The updated package was installed into the isolated environment;
its actual console command produced the outputs below. Wheel/source distribution
built; the wheel includes knowledge modules, Korean YAML and both CLI entry points.
The fork's SQL migration is distributed with Lute, not the independent plugin wheel.

## Transcript measurements

These are single-run observations, not a production performance guarantee:

- 200-line synthetic repetition of the six required sentences: 3,764 characters,
  999 distinct occurrences, approximately 6.22 seconds for first ingestion including
  lazy model initialization. One analysis call per ingestion. Reprocessing reused
  all item/occurrence/evidence IDs and made one additional analysis call.
- 64-line original practical dialogue fixture (`tests/fixtures/korean_dialogue.txt`):
  1,826 characters, 471 occurrences, approximately 3.60 seconds in a separate
  process including lazy initialization. This is sample test input, not a recording.

Neither importing nor reading automatically invokes knowledge ingestion.

## Actual diagnostic output

Input: `한국에 가면 많이 먹을 거예요.`

```text
LEXICAL
한국
가다
많이
먹다

GRAMMAR
-(으)면
-(으)ㄹ 거예요
```

Input: `오늘은 피곤해서 일찍 잘 거예요.`

```text
LEXICAL
오늘
피곤하다
일찍
자다

GRAMMAR
-아/어서
-(으)ㄹ 거예요
```

Persistence creates these items with overall status `unknown`. The tested final
scenario sets 가다 to consolidated and -(으)면 to practicing, ingests
`시간이 있으면 친구랑 같이 갈 거예요.`, and verifies stable IDs, retained statuses
and additional occurrences/evidence. Source text remains unchanged.

No Windows execution, browser automation, production database migration or Sprint 3
integration was performed. The temporary ignored config required by upstream tests
was removed after validation. See KNOWLEDGE.md for migration and behavioral limits.
