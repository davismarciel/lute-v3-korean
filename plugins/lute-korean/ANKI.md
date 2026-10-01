# Anki integration — Sprint 3

This fork reads Anki through a separate adapter. It never creates, modifies,
deletes, tags or schedules Anki notes/cards, and never invokes AnkiWeb sync.
Reviews are indirect evidence about a note/card, not individual tests of every
word in that note. All acquisition statuses remain manual.

## Install and configure

Install [AnkiConnect](https://git.sr.ht/~foosoft/anki-connect) in Anki Desktop
using its documented add-on installation procedure (add-on code `2055492159`),
restart Anki and keep the intended profile open. Install this updated fork and
plugin in the same Python environment:

```sh
python -m pip install -e .
python -m pip install -e plugins/lute-korean
lute
```

Starting the fork applies the additive acquisition migrations. Back up your Lute
SQLite database before upgrading. The separate plugin wheel does not install the
fork's migrations. Stop Lute while initially validating synchronization, and use
the existing, migrated SQLite database path for `--database`.

Create your own `anki.yml`; the following names are examples, not defaults:

```yaml
anki:
  source_identity: my-korean-collection
  profile: User 1                 # optional; require this active Anki profile
  endpoint: http://127.0.0.1:8765
  query: 'tag:language-korean'    # any valid Anki search, empty means all notes
  decks: []                      # optional exact deck names
  note_types: []                 # optional exact note type names
  batch_size: 200                # 1..500 IDs per batch
  timeout: 20
  mappings:
    Core Korean:
      korean_fields: [KO]
      translation_fields: [PT]
      metadata_fields: [NOTAS]
    Basic:
      korean_fields: [Front]
      translation_fields: [Back]
    Custom Korean:
      korean_fields: [Sentence]
      translation_fields: [Translation]
      metadata_fields: [Audio]
```

Choose a stable, unique `source_identity` for each collection/profile. Do not
reuse it for a different collection, even if Anki profile names match. Changing
identity creates a different integration. The actual profile is recorded and
checked again before persistence. Use explicit mappings per note type: no field
is permanently guessed. Lists must be YAML lists. Multiple Korean fields are
joined by newlines and analyzed once per note content revision.

Query, deck and note-type filters are combined with AND; multiple decks/types
within a filter use OR. Deck filtering uses exact names after discovery: list
subdecks explicitly if desired. Suspended cards remain included when the query
includes them. Cloze notes and reverse cards share their note's content analysis.

## Discover, inspect, then synchronize

```sh
lute-korean-anki doctor --config anki.yml
lute-korean-anki preview --config anki.yml
lute-korean-anki sync --config anki.yml --database /path/to/lute.db --dry-run
lute-korean-anki sync --config anki.yml --database /path/to/lute.db
lute-korean-anki status --config anki.yml --database /path/to/lute.db
```

`doctor` checks connection/API/profile, the configured query and explicit
mappings. `preview` shows note types, fields, counts, candidate fields with Hangul
sample counts, unmapped notes and validation problems. Its sample output exposes
only field lengths/types, not collection text or IDs. Neither command opens a
Knowledge database. A cardless note is visible in preview but excluded from sync.

Dry-run copies only acquisition tables to an in-memory SQLite database and runs
the same ingestion there. It reports notes created/changed/skipped, reviews and
knowledge items created, without writing any row to the original database.
It may execute Kiwi for changed/new content; memory use scales with acquisition
history. It does not create export files or update saved sync status.

`status` reads the last committed report without contacting Anki. Reports include
UTC last success, inspected/created/changed/skipped notes, metadata updates,
missing/out-of-scope sources, imported/skipped reviews, duration, error count and
up to 20 individual error messages. An aborted sync returns an error and keeps
the last committed report; it does not persist a misleading partial checkpoint.
A committed sync with recoverable note errors lists those explicitly.

## Content and evidence

HTML presentation is removed, `<br>` becomes a newline, `[sound:...]` is removed,
and cloze display markup is unwrapped. Hangul, meaningful punctuation and mixed
Latin text/numbers remain. Audio files are not downloaded. `has_audio`, tags,
selected translations/metadata, original field hashes and card/template field
relationships are retained locally. Entire raw HTML fields are not retained.

The unit of linguistic analysis is the note/revision, never the card. One note
with two reverse cards produces one set of linguistic occurrences, with separate
card metadata and review events. Existing lexical/grammar items are reused.
Initial ingestion creates ordinary `source_type=anki`, `evidence_type=exposure`
evidence through the existing Knowledge ingestion service. That content exposure
uses the existing reading dimension; it does not claim review recognition.

Canonical reviews live in a source-level event table, not duplicated as separate
per-word Evidence rows. `KnowledgeService.list_anki_reviews(item_id)` exposes
`evidence_type=anki_review`, `dimension=None`, `directness=indirect`, and
`scope=note_content`. Raw ratings (1 Again, 2 Hard, 3 Good, 4 Easy; others retained),
intervals, previous intervals, type, duration, factor, USN, timestamp, IDs and
card direction metadata remain available. No review implies listening or
production; merely containing audio does not establish listening comprehension.

`KnowledgeService.anki_summary(item_id)` counts distinct namespaced notes, cards
and canonical review events, bins ratings and reports the last review. This is
an informational association with contexts, not a count of independently tested
word mastery. Generic `evidence_count` continues to describe generic Evidence;
Anki reviews are summarized separately.

## Identity, revisions and incremental behavior

- Note identity: `(source_identity, real note ID)`.
- Card identity: `(source_identity, real card ID)`.
- Content source: note ID + cleaned text SHA-256 + Korean-field mapping hash.
- Event key: `anki:<escaped identity>:card:<card ID>:review:<review ID>`.
- Each observed content change adds a revision and retains prior sources,
  occurrences, exposure evidence and reviews. A return to previous content
  reuses that source but records a new observed revision window.
- Unchanged clean content/mapping skips Kiwi, even when tags, scheduling,
  translation, deck or suspension metadata changes. Notes/cards are still fetched
  in batches to detect edits reliably; this is not an incremental notes HTTP API.
- New cards fetch complete history in batches. Known cards fetch reviews through
  deck-level exclusive ID cursors, filtered per card. Successful transactions
  advance cursors; failures roll them back. Incoming duplicates are skipped;
  conflicting review semantics abort instead of silently overwriting history.
  Changes to Anki sync bookkeeping (`usn`) do not create or rewrite an event.

AnkiConnect does **not** provide historical note content at review time. On first
sync, old reviews are associated with the first observed snapshot and explicitly
marked `first_observed_snapshot`. With multiple observed revisions, note `mod`
when available supplies an approximate boundary; absent it, observation time is
used. Other uncertain historical associations are marked
`historical_snapshot_uncertain`. Already imported event associations never move
when a note is edited. This preserves actual observed history without claiming
that the current sentence was present during every historical review.

After importing old/backdated reviews into Anki, run:

```sh
lute-korean-anki sync --config anki.yml --database /path/to/lute.db --full-reviews
```

This fetches all selected card histories and reuses event keys. Normal cursors
assume new review IDs increase; backdated imports cannot be discovered by that
assumption. Historical events deleted in Anki remain here; edits to an imported
review abort when detected. Automated historical review replacement/deletion is
not implemented.

Notes/cards no longer matching the configured scope are checked by ID:
existing ones become `out_of_scope`, absent ones become `missing`. Suspension is
recorded separately. No knowledge item, evidence, revision or review is deleted.
Re-entering scope fetches complete card history again. Anki may change during
requests; synchronize while idle. Profile changes are guarded, but AnkiConnect
has no atomic multi-request collection snapshot.

## Services, transactions and export

`AnkiSourceAdapter` defines health, note discovery and note/card/review retrieval.
`AnkiConnectSourceAdapter` handles HTTP; immutable `AnkiNoteSnapshot`,
`AnkiCardSnapshot`, `AnkiReviewEvent` form the protocol-independent boundary.
`AnkiSyncService(session, adapter, config).sync()` coordinates extraction,
existing `KnowledgeIngestionService`, revisions, reviews and reconciliation.
`AnkiRepository` owns SQL and summaries. Consumers use these APIs, not raw SQL.

The caller owns `Session.commit()` / `rollback()`. Network collection and mapping
validation happen before writes. A whole-sync savepoint gives atomic persistence;
per-note savepoints allow isolated extraction/analyzer errors to be reported and
retried without losing valid notes. Connection, profile, database, inconsistent
review and mapping errors abort. Reviews for unsuccessful notes are skipped and
their cursors are not advanced. The CLI commits a completed report once, with no
batch commits or hidden checkpoints. Services do not commit callers' sessions.

Default Knowledge JSON is unchanged. Opt in to summaries:

```python
knowledge.anki_summary(item_id)
knowledge.list_anki_reviews(item_id)
knowledge.export(include_anki=True)
knowledge.export(include_anki=True, review_details=True)  # explicit raw detail
```

```sh
lute-korean-anki sync --config anki.yml --database /path/to/lute.db --export state.json
```

Add `--review-details` only when raw events are needed. Export files contain local
study content; choose where to share them. An export file error after database
commit does not undo the completed sync; rerunning is idempotent.

## Privacy and troubleshooting

Only loopback HTTP endpoints are accepted (`localhost`, `127.0.0.1`, `::1`);
redirects and environment HTTP proxies are disabled. No cloud API is called and
no credentials are needed. For WSL, run in an environment with Windows localhost
forwarding/mirrored networking, or run this Python CLI on Windows alongside Anki.
For Docker, its loopback belongs to the container: run the integration outside
that container with local Anki access and the same database mounted locally.
This sprint does not open AnkiConnect to LAN/cloud endpoints.

- Connection refused: start/restart Anki, enable AnkiConnect, check port/profile.
- API error: update AnkiConnect; API v6+ and the documented review actions are
  required. There is no silent degraded review import.
- Invalid query: validate it in Anki's browser first.
- Unmapped/missing fields: inspect preview and configure exact note-type/field
  names. Sync never persists a guessed mapping.
- No Korean: correct mappings/content; that note is reported and retried later.
- Missing table: start the updated fork and confirm both migrations were applied.
- SQLite locked: stop concurrent writers and retry; failed persistence rolls back.
- Profile mismatch: open the intended profile or choose a distinct source identity.

## Limits and extension points

No live personal collection or Windows runtime is required by automated tests;
see [ANKI_VALIDATION.md](ANKI_VALIDATION.md) for results and a manual smoke command.
There is no UI change, automatic chunk matching/mining, audio import, reverse
sync, package parser or scoring. Reviews support provenance even with unknown
modality and uncertain historical content. Initial acquisition SQL is intentionally
SQLite-specific, matching Lute's current backend.

A future package adapter can emit the same intermediate snapshots/events.
A scoring engine can consume canonical source events, directness, rating,
revision certainty and distinct contexts while consulting generic Evidence and
manual skill statuses. CI difficulty can consume explicit learner state and
context statistics. Podcast/TPRS ingestion can reuse the generic source/evidence
services. Optional JSON summaries are already suitable for learner-state export;
no ChatGPT integration or scoring formula is added here.

## Content validation and quarantine (Sprint 3.6)

Each explicitly mapped Korean field is validated independently after cleanup.
Preview/status reports include `content_language_warning`, reasons, per-field
script metrics, warning counts and `notes_anomalous`. No Hangul is an anomaly.
Dominant Latin prose is conservatively classified when Latin letters are at least
70% of letters, there are at least eight Latin-only words, and at least six are
lowercase. This is a transparent script/content heuristic, not a language detector
or translator. Ordinary mixed Korean plus Netflix/BTS/YouTube is a warning and
remains ingestible. Ambiguous short code-switching can require manual inspection.

A mapped content anomaly creates an identifiable Source/note revision and retains
metadata and raw review events. It bypasses Kiwi and creates no Occurrences,
Knowledge Items, lexical exposures or grammar associations. Reviews have
`linguistic_association=withheld_content_anomaly`; operational note state stays
`active` because the note still exists in the selected scope. The distinct
`content_validation.status=anomalous` describes its linguistic eligibility.
`doctor` reports unresolved anomalies as problems; an explicitly requested sync
can safely quarantine them and continue. Invalid field names still abort mapping
validation. Notes with genuine individual analysis errors retain the previous
isolated error behavior.

Portuguese speaker labels in an otherwise Korean dialogue only trigger a warning:
Korean concepts/grammar remain trackable; the Latin spans remain unlinked metadata.
Foreign content never becomes a Korean concept simply because Kiwi emits `SL`.
The Anki adapter does not implement linguistic 좋아하다 normalization; all source
adapters share the generic acquisition layer documented in KNOWLEDGE.md.

Policy changes create a new observed source revision even when content is unchanged.
Previously imported raw reviews keep their historical source links and are never
reassigned silently. Use clean staging/rebuild for old unqualified imports; the
hardening does not retroactively certify older contaminated associations.

## Windows Anki with WSL

Keep AnkiConnect bound to Windows loopback `127.0.0.1:8765`. Do not change it to
`0.0.0.0`, expose it publicly, or broaden origin/firewall rules just to make WSL
connect. The default endpoint is process-local: ordinary WSL NAT networking may
not reach a Windows loopback listener through WSL's own `127.0.0.1`.

For this checkout's Korean Study Desktop shortcut, a local bridge now provides
the daily route: `scripts/start_lute_wsl.sh` starts
`scripts/wsl_ankiconnect_bridge.py` on WSL `127.0.0.1:18765`, then Lute. The
bridge uses Windows PowerShell to call Windows AnkiConnect at
`127.0.0.1:8765` and accepts only the adapter's read actions. It stops with
Lute. Keep the Korean Study endpoint set to `http://127.0.0.1:18765` for this
route. This is separate from the native Lute browser Anki export, which uses
browser CORS and may write cards.

Other local daily options:

1. Run the existing plugin CLI natively in Windows against Windows AnkiConnect,
   using Python/wheels and an explicitly migrated Windows staging database.
   Keep `endpoint: http://127.0.0.1:8765`; use your real profile and mappings.
   Example: `.venv\Scripts\lute-korean-anki.exe preview --config anki.yml`.
   Do not operate on the same live SQLite database concurrently from Windows and WSL.
2. On supported Windows 11 systems, explicitly opt into WSL mirrored networking
   in the Windows user `.wslconfig` (`[wsl2]` / `networkingMode=mirrored`). Microsoft
   documents Windows↔WSL loopback connectivity in this mode. Applying the change
   requires a WSL restart; no OS/network configuration was changed by this sprint.
   After restarting, verify `doctor` at loopback before syncing. See
   [Microsoft WSL networking](https://learn.microsoft.com/windows/wsl/networking)
   and [WSL configuration](https://learn.microsoft.com/windows/wsl/wsl-config).

The earlier real audit used a temporary loopback-only bridge that was stopped
afterward. The current Desktop launcher supplies a separate, durable local
read-only bridge for ordinary Korean Study use. It makes no Anki collection or
AnkiConnect configuration changes. Native Windows CLI and mirrored mode remain
alternatives; neither is required for the local bridge. No cloud integration is
involved.
