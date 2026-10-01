# Sprint 6 validation — Korean daily study workspace

## Verdict

**YES** — the Korean acquisition tracker is usable as a daily study workflow
without routine CLI commands after one-time installation and explicit Anki
configuration. This validates local study orchestration, not measured Korean
comprehension. No Sprint 7 functionality was implemented.

## Environment and validation boundaries

- Linux/WSL2, kernel `6.6.87.2-microsoft-standard-WSL2`.
- Python 3.14.4; Lute 3.10.3; lute-korean 0.3.0; Kiwi 0.23.2;
  Flask 3.1.3; SQLAlchemy 2.1.1.
- Real approved Sprint 4.5 snapshot was copied into a **new full Lute sandbox**:
  `/tmp/lute-sprint-6/full/test_korean_daily_v2.db`.
- Snapshot: 352 lexical, 5 grammar, 3,117 occurrences and 6,055 Anki reviews.
  Reading suggestions remain 188 presented / 164 practicing; grammar 5 practicing.
  Listening and production remain insufficiently observed.
- Real Windows TPRS EP1–EP7 files were read from the supplied OneDrive folder.
  Only original Korean subtitles entered analysis; translations remained metadata.
- The main database and approved staging were not modified. Their SHA-256 values
  remained respectively `ca44b1654eed5c22955317428d5f2f33d9566c89472f40f74d281e2916de98e7`
  and `c590f7050a3bf985943ab1917ed5a3a077a1befe488e1d6ab21f22c1e26830f0`.
- Sprint 6 made no real Anki network calls or writes. UI sync orchestration used
  a fake external adapter with the real existing sync service. Prior live Anki
  validation remains the evidence for that unchanged adapter/service boundary.
  Daily Windows/WSL connectivity must use an explicitly verified local route.

## Architecture

Lute previously exposed parser plugins, but no application-route extension point.
The only required core integration is the generic optional `lute.plugin.app`
entry-point loader, its invocation after parser initialization and a menu link
loop. Optional plugin initialization failures are logged without breaking Lute.
The loader supports both modern and legacy importlib entry-point APIs.

Everything Korean-specific lives in the plugin: Blueprint, server-rendered
templates, scoped CSS, minimal presentation JavaScript, session service, cache,
orchestration and exports. The workspace uses Lute's existing database/session,
base template and theme. It introduces no SPA or browser-testing dependency.

Existing Korean parsing, normalization, grammar detection, overlap, Anki sync,
HumanEvidence, learner-state and CI services are reused. There is no second
lexical pipeline or UI copy of a classification policy. One fresh batched learner
snapshot is reused across all candidates in a compare request.

### Policy integrity

Learner policy `ko.learner-state.v1` unchanged: **YES**.

Parameter fingerprint:
`94819404fd433591b54a9cc1e5b132065c7f35bbe19bc1f88077dcfcef0f24f3`.

CI policy `ko.ci-analysis.v1` unchanged: **YES**.

Parameter fingerprint:
`be113a87005f95b382b183f4addc9f5aae0e797127ee7e96f29053266240b45e`.

No status application, policy threshold adjustment or new pedagogical inference
was added. Export limits and page size are presentation settings, not policy.

## Database additions

Migration `20260930_04_korean_study.sql` adds:

| Table | Purpose |
|---|---|
| korean_study_contents | Stable fingerprint, cleaned segments stored once, name/kind/format/hash |
| korean_study_sessions | Distinct actual sessions, activity, status, actual timestamps and reference |
| korean_study_consumed_segments | Exact consumed indices/timestamps and reused Source links |
| korean_study_observations | Session links to existing HumanEvidence rows |

Core Terms and existing acquisition tables are not redefined. Contents are
deduplicated by original hash, kind, format and cleaned segment representation;
renaming the same content does not create a second content row. Start request keys
and session/segment/item evidence keys make retries idempotent. Separate real
re-study sessions reuse Sources/Occurrences but create distinct exposure events.

Services use savepoints and leave commit/rollback ownership to callers. The UI
commits once per successful explicit mutation; failures roll back. CLI mutations
require an existing migrated database and explicit `--writable`.

## Screens and routes

| Screen/action | Route | Behavior |
|---|---|---|
| Korean Home | GET /korean/ | Batched summaries, saved Anki status and dated recent candidates |
| Knowledge | GET /korean/knowledge | Search/filter lexical, grammar, chunks and no manual assessment |
| Item | GET /korean/items/ID | Manual vs suggested dimensions, surfaces, reasons, evidence and relations |
| Save manual assessment | POST /korean/items/ID/assessment | Deliberate dimensional status save |
| Human observation | POST /korean/observations | Validated, factual, item-specific event |
| Anki | GET/POST /korean/anki | Offline status; explicit doctor, preview, dry run, incremental/full sync and settings |
| Analyze/compare | GET/POST /korean/analyze | Paste/upload supplied candidates; zero Knowledge writes |
| Candidate | GET /korean/candidates/TOKEN | Fresh snapshot and report; start action and export |
| Start session | POST /korean/sessions/start | Session/content only; no inferred acquisition |
| History | GET /korean/history | Real sessions, actual ranges, timestamps and wall elapsed time |
| Session | GET /korean/sessions/ID | Current report, consumed cues and observations |
| Partial/complete | POST /korean/sessions/ID/consume | Explicit range; conservative exposure semantics |
| Reopen as candidate | GET /korean/sessions/ID/candidate | Analyze saved content again without consuming it |
| Segment diagnostics | GET candidate/session /segments/INDEX | Raw/effective/morphology detail on demand |
| Exports | GET /korean/export and /export/learner, /export/content/TOKEN, /export/session/ID | Local JSON/Markdown attachments |

Global segment filters apply before pagination. At most 200 cues are rendered on
a page, while metrics and exports cover the full content. Names and suppressed
overlap remain visible. A selected item can prefill a factual observation form;
the user still deliberately saves it. There is no “understood everything” action.

## Workflow and study semantics

Validated route flow:

1. View overview/Anki status with no domain writes.
2. Analyze `한국에 가면 많이 먹을 거예요.` and see lexical/conditional/future
   grammar, fit and segment load without creating items or evidence.
3. Explicitly start a session; no recognition/exposure is created by starting.
4. Save actual partial consumption or complete a selected range. Only selected
   segments are persisted; later transcript cues remain unconsumed.
5. Reading/text-following generates **exposure only**, not recognized/produced.
6. Record a specific reading recognition once using HumanEvidenceService; manual
   state stays unchanged and fresh suggestions naturally reflect the new data.
7. Analyze again using a fresh snapshot, or start a distinct re-study session.

Pure listening and mixed sessions without a declared transcript read record only
session/Source provenance, not token-level reading/listening recognition. Reading
events do not affect listening/production. Repeating the same completion does not
duplicate exposure; attempting to add new ranges to a completed session is rejected.
No historical EP1–EP7 sessions were invented or backfilled.

Sources are stable per cleaned content segment, with an episode-level StudyContent
parent. Source counts therefore mean cue Sources, not independent episode counts.

## Explicit writes

| Explicit action | Writes |
|---|---|
| Save Anki settings | Reviewed local YAML file only |
| Anki sync / advanced full reviews | Existing Anki/Knowledge sync persistence; Anki itself remains read-only |
| Save manual assessment | Existing dimensional manual state |
| Save human observation | Existing factual HumanEvidence, optional session association |
| Start study | Study content/session rows only |
| Save partial / complete consumption | Selected Sources/Occurrences, session records, exposure only when text read |

GET/views, analyze, compare, connection checks, preview, exports and candidate
reopening make no Knowledge writes. Anki dry run uses the existing isolated
temporary database behavior, never production writes. All Korean POSTs validate
standard Flask-WTF CSRF tokens even though normal Lute disables global CSRF.
Missing/unmigrated databases fail gracefully rather than being created on GET.

## Exports

Learner context: timestamp, policy identities, lexical summaries, prioritized
presented/practicing items, grammar, recent factual direct events, studied sources
and limitations. Manual, suggested and observed evidence remain distinct.

Content context: CI summary, novelty, reinforcement/recycling, tracked grammar,
hardest segments and learner snapshot identity; all original Korean is optional.
Compact/default exports bound lists; detailed exports are explicit. JSON and
readable Markdown are generated locally without sending anything to ChatGPT.
No raw Anki review dump, private internal reasoning or automatic “known” collapse.

## Tests

Combined Sprints 1–6 and relevant Lute parser/language/reader/book/database/ORM
suite: **469 passed, 1 deselected in 79.45 s**.

Sprint 6 adds **30 tests** across `test_study.py`, `test_study_web.py` and
`test_app_plugins.py`. Covered lifecycle/fingerprints, partial consumption,
restudy, completed-session immutability, exposure-only behavior, listening/mixed
semantics, rollback, idempotency, manual preservation, HumanEvidence validation
and skill separation, fresh learner snapshots, bounded exports, CLI writable
guard, batched overview, route forms, Anki orchestration, CSRF despite global
disablement, connection/encoding/file/format errors, browser-owned candidate
privacy, unmigrated/missing DB, read-only views/exports, global filters/pagination
and lazy technical diagnostics.

Japanese/MeCab check, reported separately: **6 environmental failures in 2.69 s**
from unavailable `mecab-config`/`libmecab.so`. This includes the single otherwise
deselected Term regression that requests Japanese parsing. Korean tests and other
existing parsers passed. No Japanese code was modified.

Pylint error/fatal checks for the app hook and study package passed (10.00/10).
`git diff --check` passed. Offline wheel build succeeded, with all 15 study
templates, CSS/JS, app/parser entry points and the study CLI included.

## Browser and textual UI validation

Actual full Lute startup and GET `/` plus overview, knowledge, Anki, analyze,
history and export pages returned 200 in the sandbox. Existing local Chromium
was driven through Playwright with Flask's test client, without a network server
or new browser automation stack. Home/menu and real EP5 analysis rendered;
EP5 showed productive / medium, 121 cues and zero dense cues under the global
dense filter. Selecting all returned all 121 cues.

Screenshots:

- [Korean Home](docs/sprint6/home.png)
- [Real EP5 report](docs/sprint6/ep5.png)

Route tests provide textual end-to-end validation for completion, observation,
manual assessment, history and export. Anki UI operations used a fake adapter;
no live Windows connectivity is claimed for this sprint.

## Real EP1–EP7 comparison

Fresh analysis against the unmodified approved learner snapshot reproduced the
Sprint 5 qualitative results; no episode-specific values are hard-coded.

| Episode | Cues | Fit | Confidence | Supported occurrences | Previously seen | Loads 0 / 1 / 2 / 3 |
|---|---:|---|---|---:|---:|---|
| EP1 | 147 | stretch | medium | 57.6% | 64.9% | 34 / 99 / 10 / 4 |
| EP2 | 177 | stretch | medium | 53.4% | 60.7% | 30 / 106 / 36 / 5 |
| EP3 | 151 | stretch | low | 40.8% | 49.1% | 21 / 57 / 66 / 7 |
| EP4 | 177 | stretch | medium | 70.4% | 87.3% | 85 / 82 / 8 / 2 |
| EP5 | 121 | productive | medium | 76.4% | 91.9% | 64 / 46 / 11 / 0 |
| EP6 | 120 | stretch | medium | 69.9% | 87.6% | 51 / 56 / 10 / 3 |
| EP7 | 115 | stretch | medium | 69.3% | 84.7% | 43 / 58 / 11 / 3 |

EP4's high previously-seen coverage and isolated dense cues are shown together,
so its overall stretch label is not presented without context. This remains
transcript/reading fit, not evidence of listening comprehension.

## Performance

Local synthetic repeated Korean sentences, warm Kiwi, approved learner snapshot:

| Measurement | Result |
|---|---:|
| 5,000 words / 1,000 segments, domain analysis with preloaded snapshot | 0.388 s |
| 20,000 words / 4,000 segments, domain analysis with preloaded snapshot | 1.660 s |
| Full UI request, 5,000 words including fresh snapshot and rendering | 1.256 s |
| Full UI request, 20,000 words including fresh snapshot and rendering | 2.663 s |
| Full dashboard request | 1.045 s / 27 SELECTs including Lute template/settings and Anki status |
| Plugin-only overview query bound | At most 12 SELECTs in the service regression |

The domain timings remain close to Sprint 5's 0.43 / 1.96 s baselines. The
dashboard query count is batched and does not grow per Knowledge Item. No sync
runs on page load. Cold model initialization adds startup latency: first real
EP1 analysis took 2.159 s; subsequent EP2–EP7 analysis took 0.042–0.078 s each.

A presentation issue was found before final validation: eagerly embedding every
raw-item diagnostic generated roughly 51 MB HTML for 16,665 synthetic words.
Pagination and on-demand segment diagnostics reduced 20,000-word initial HTML
to **189,863 bytes**. The full analysis/export remains available; policies and
Korean text were not changed to achieve this reduction.

## Files changed for Sprint 6

Earlier Sprints' uncommitted files and private Docker data were preserved. This
list identifies this sprint's scope, rather than treating all working-tree files
as newly created in Sprint 6.

Core/additive integration:

- `lute/plugins.py`
- `lute/app_factory.py`
- `lute/templates/base.html`
- `lute/db/schema/migrations/20260930_04_korean_study.sql`

Plugin services/metadata:

- `plugins/lute-korean/pyproject.toml`
- `plugins/lute-korean/lute_korean_parser/knowledge/ingestion.py`
- `plugins/lute-korean/lute_korean_parser/study/__init__.py`
- `plugins/lute-korean/lute_korean_parser/study/tables.py`
- `plugins/lute-korean/lute_korean_parser/study/service.py`
- `plugins/lute-korean/lute_korean_parser/study/workspace.py`
- `plugins/lute-korean/lute_korean_parser/study/cache.py`
- `plugins/lute-korean/lute_korean_parser/study/cli.py`
- `plugins/lute-korean/lute_korean_parser/study/web.py`

Plugin UI under `plugins/lute-korean/lute_korean_parser/study/`:

- `templates/korean/base.html`
- `templates/korean/macros.html`
- `templates/korean/home.html`
- `templates/korean/knowledge.html`
- `templates/korean/item.html`
- `templates/korean/analyze.html`
- `templates/korean/report.html`
- `templates/korean/report_body.html`
- `templates/korean/compare.html`
- `templates/korean/study.html`
- `templates/korean/history.html`
- `templates/korean/anki.html`
- `templates/korean/export.html`
- `templates/korean/error.html`
- `templates/korean/segment.html`
- `static/study.css`
- `static/study.js`

Tests/documentation/artifacts under `plugins/lute-korean/`:

- `tests/test_study.py`
- `tests/test_study_web.py`
- `tests/test_app_plugins.py`
- `README.md`
- `CONTEXT.md`
- `KNOWLEDGE.md`
- `KOREAN_STUDY_WORKFLOW.md`
- `SPRINT_6_VALIDATION.md`
- `docs/sprint6/home.png`
- `docs/sprint6/ep5.png`

## Compatibility and remaining limitations

Normal Lute reading, Terms/popups, language creation and non-Japanese parsers
passed relevant regressions. The generic app hook does not modify their domain
contracts. No core reader redesign was introduced.

This workspace does not add audio playback or validate listening comprehension.
Sources represent cues; diversity retains the existing policy's definition and
does not claim independent episode-level recognition. Known lemma/polysemy/Kiwi
and five-pattern grammar limitations remain visible. Sync and analysis are
synchronous local operations. Candidates expire on restart/after two hours and
assume Lute's normal single-process deployment. Detailed exports can be large.
Windows-specific server execution was not performed; the implementation avoids
OS-specific dependencies, but the Windows/WSL network route still requires an
explicitly verified local configuration. No actual Anki collection or primary
Knowledge database was changed during this sprint.

## Daily Windows/WSL Anki transport follow-up

The first daily Sync Anki attempt exposed an operational gap: the copied Korean
Study configuration still used the earlier audit endpoint
`http://127.0.0.1:18765`, but that temporary bridge had been stopped. The Windows
AnkiConnect service answered API v6 at Windows `127.0.0.1:8765`; WSL loopback on
both 8765 and 18765 initially refused connections. This is independent of native
Lute's browser CORS setting.

The checkout now includes `scripts/wsl_ankiconnect_bridge.py`, a loopback-only
transport accepting exactly the Korean adapter's AnkiConnect read actions, and
`scripts/start_lute_wsl.sh`, which owns the bridge for the lifetime of Lute. The
Windows Desktop shortcut now invokes the launcher. The existing source identity,
profile, mapping and 18765 endpoint are retained. No Anki config, note, card,
tag, firewall rule or public bind address was changed.

Live operational checks:

- Windows AnkiConnect `version` returned `6` directly and through WSL 18765.
- `addNote` was rejected by the bridge before reaching AnkiConnect.
- Korean Study `doctor` discovered **875 notes and 875 cards** in the configured
  profile. Its `ok=false` is solely the previously documented content-language
  anomaly in the collection; the transport is healthy.
- Explicit dry-run sync inspected **875 notes**, skipped all 875 unchanged,
  created/changed **0**, imported **0** reviews and reported **0** errors in
  **23.778 s**. The service uses an isolated RAM acquisition copy for dry runs.
- `bash -n`, Python bytecode compilation and `git diff --check` passed for the
  operational files. The full Sprint 1–6 suites were not repeated because this
  follow-up only adds the optional local transport and launcher.

The bridge started for diagnosis is temporary. Stop the previously running Lute
process and reopen the updated Desktop shortcut so the launcher owns the bridge
and stops it with Lute. The first study-session validation predates this
operational follow-up; the metrics and compatibility verdict above are unchanged.
