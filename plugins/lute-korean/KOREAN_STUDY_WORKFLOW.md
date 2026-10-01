# Korean Study: daily workflow

Korean Study is a local workspace inside Lute. The normal reader and its Terms
remain unchanged. Manual assessments, suggested learner states and observed
evidence remain separate. There is no automatic status promotion.

## One-time installation and migration

Use Python 3.10+ and install this updated fork and plugin in **the environment
running Lute**, then restart Lute:

```sh
python -m pip install -e .
python -m pip install -e plugins/lute-korean
lute-korean-install
lute
```

Back up the Lute database before updating. Normal startup applies the additive
`20260930_04_korean_study.sql` migration using Lute's migration runner. It creates
four plugin tables: contents, sessions, consumed segments and session observation
links. It does not alter Term tables or historical evidence. A missing or
unmigrated database produces a friendly error on Korean pages; those pages never
create or migrate a database implicitly.

Choose **Korean Study** in Lute's navigation. If it is missing, verify that both
the updated fork and `lute-korean` are installed in the running environment.
The parser entry point alone does not enable application pages: this fork also
loads the optional `lute.plugin.app` entry point. Docker requires installing the
plugin and running `lute-korean-install` **inside the image build**, after copying
the plugin into the image. A host installation does not update an existing image.

## Start from the Windows Desktop

On this Windows/WSL installation, the **Lute Korean Study** shortcut is on the
Windows Desktop (redirected to OneDrive's Desktop folder). Double-click it to
start Lute in the `Ubuntu` WSL distribution. Keep the terminal window open while
studying, then open <http://localhost:5001/korean/> in the Windows browser. Stop
Lute with `Ctrl+C` in that terminal. If port 5001 is already occupied, close the
previous Lute process before starting another one.

The shortcut targets `C:\Windows\System32\wsl.exe` with these arguments:

```text
--distribution Ubuntu --cd /home/davi/lute-v3-korean --exec /home/davi/lute-v3-korean/plugins/lute-korean/scripts/start_lute_wsl.sh
```

The launcher starts a local, read-only Anki bridge on WSL `127.0.0.1:18765`,
then starts Lute. It stops its bridge when Lute exits. It uses the persistent
Python environment in the checkout and the database configured in
`/home/davi/lute-korean-data/config.yml`; it does not use `/tmp`. Anki must be
open in Windows for synchronization, but Lute can open without it. Starting
Lute never starts Anki sync automatically. If you move the checkout, rename the
WSL distribution or move the data directory, update the shortcut's Target or the
launcher's data-directory setting accordingly.

## Recommended daily flow

1. Open **Anki**, preview your explicit mapping if needed, then **Sync Anki**.
2. Inspect **Learner & knowledge**. Suggestions are diagnostic; manual assessments
   remain authoritative.
3. Open **Analyze input** and paste Korean or upload TXT, SRT, VTT or TPRS files.
   Select several files to compare them. TPRS analysis uses the Korean subtitle,
   not its machine translation.
4. Inspect fit **and segment distribution**, novelty, reinforcement, recycling and
   hardest passages. Analysis does not claim the material was studied.
5. Deliberately choose **Start study**, selecting the actual activity.
6. After consuming content, select the inclusive segment range actually studied
   and save partial progress or complete the session.
7. Optionally select a specific tracked item and record a factual recognized,
   missed, produced or manual-confirmation observation.
8. Inspect the refreshed suggestions or analyze the next candidate. Exports can
   provide compact context to a teacher or ChatGPT without any external API call.

No routine CLI work is needed after installation/configuration.

## Learner and knowledge pages

Search lexical items, grammar or chunks, filter status or lack of manual
assessment, and open an item to inspect its surfaces, role, source/context counts,
manual and suggested states, reasons, warnings, recent evidence and relationships.
Reviews are summarized rather than dumped individually. Editing reading,
listening or production requires a deliberate **Save**.

**Record observation** uses the existing HumanEvidenceService. Enter the item,
observed dimension, event, factual context/reference, timestamp and note. Produced
events require the production dimension. Reading recognition does not establish
listening or production. A stable event key prevents retries from duplicating the
same observation. Repeated real observations are separate events.

## Anki setup and operation

Anki must be open with AnkiConnect installed. The Anki page shows saved sync
status without contacting Anki on GET. **Check connection**, **Preview** and
**Dry run** are explicit actions; they do not write Knowledge evidence. Preview
never silently saves suggested mappings. Edit and deliberately save the reviewed
YAML configuration on the page. For example:

```yaml
anki:
  source_identity: my-korean-profile
  profile: My profile
  endpoint: http://127.0.0.1:8765
  query: 'deck:"My Korean deck"'
  mappings:
    My Korean note type:
      korean_fields: [Sentence]
      translation_fields: [Translation]
      metadata_fields: [Notes, Audio]
```

Use your actual names. See [ANKI.md](ANKI.md) for all supported settings. The file
is saved locally as `korean-anki.yml` in Lute's data directory; an application
configuration `KOREAN_ANKI_CONFIG` can specify an existing explicit path. Saving
configuration changes this file, not Anki. Invalid settings do not replace it.

**Sync Anki** is the normal incremental action. Historical **Full reviews** is
advanced and explicit. Results show inspected/created/changed/skipped notes,
imported/skipped reviews, errors and duration. Anki remains strictly read-only.
Sentence reviews remain indirect and unspecified in modality; no rating changes
manual statuses. Connection failures produce a readable diagnostic.

### Windows Anki and WSL Lute

This installation uses a local read-only transport because ordinary WSL loopback
does not reach AnkiConnect on Windows loopback. The Desktop shortcut launches
`scripts/start_lute_wsl.sh`, which owns `scripts/wsl_ankiconnect_bridge.py` for
that Lute session. The Korean Study Anki configuration retains its stable source
identity, mappings and endpoint `http://127.0.0.1:18765`. The bridge forwards only
the adapter's allowlisted read actions to Windows `127.0.0.1:8765`; it refuses
Anki write actions. Both listeners remain on their respective local loopback
interfaces. No firewall, Anki bind address or Windows network mode is changed.

Keep Anki and AnkiConnect open, then use **Doctor**, **Preview** or **Sync Anki**
in Korean Study. A previously running Lute session launched without the bridge
must be stopped before opening the updated Desktop shortcut. The native Lute
Settings → AnkiConnect browser test is a separate path and uses browser CORS;
Korean Study sync is server-side and does not depend on that CORS setting. See
[ANKI.md](ANKI.md) for Windows-native and mirrored-network alternatives.

## Candidate analysis and presentation

Fit categories describe **reading/transcript linguistic load**, not measured
comprehension. Coverage describes familiar occurrences and unique items, not
mastery. Podcast transcripts always distinguish transcript fit from listening
ability; transcript analysis does not infer listening comprehension.

Original Korean remains intact. Segments show timestamps, load, effective lexical
and grammar items, suppressed overlap and reasons. Filters apply to the complete
report; segment pages contain at most 200 cues. Technical morphology/raw-item
detail opens separately on demand. Metrics and exports still cover the entire
content. Names remain visible with their roles and existing policy semantics.

Recent candidates are temporary, browser-owned, bounded to 32 entries and expire
after two hours or an application restart. They are not persistent Sources or
Evidence. Returning to a candidate recalculates it with a fresh learner snapshot;
the home page's last-analysis label is a dated summary. Saved sessions can reopen
their content as a fresh candidate or start a new study session.

## Study semantics and persistence

Starting a session persists its stable content fingerprint, cleaned segments
once per content, activity, actual start time and optional external reference.
It creates **no lexical evidence** by itself. Session states are started, partial
and completed. The selected consumed range can be a subset of an episode; later
cues are never claimed as consumed.

Reading and listening-with-transcript sessions record **reading exposure only**
for consumed text. Mixed sessions require an explicit declaration that the
transcript was read. Pure listening or mixed activity without reading records
session/source provenance without lexical or grammatical skill evidence.
Exposure means the content was encountered; it does not mean recognized,
understood, produced or consolidated.

Consumed segments reuse canonical ingestion and stable segment Sources and
Occurrences. A whole episode has a StudyContent identity; Knowledge Sources here
represent its individual cues, not independent media episodes. Repeating a save
for the same session/range creates no duplicate exposure. Re-studying creates a
new session and another factual exposure event while reusing content/Sources.
Completed sessions cannot silently acquire additional ranges. Start a new session
for later consumption or re-study. History shows exact consumed cue positions,
observation links and timestamps; elapsed time is wall time, not measured active
study duration.

EP1–EP7 are **not backfilled** merely because files exist. For a verified historical
session, the optional CLI accepts explicit actual start/consumption timestamps.
Do not invent historical completion or recognition.

## Exports

**Export learner context** produces compact/default/detailed JSON or Markdown:
snapshot/policy identities, summaries, important items, manual vs suggested
states, grammar, recent direct factual observations and recent studied content.
It excludes raw Anki reviews and private internal reasoning.

**Export for study** includes CI summary, novelty, recycling, grammar, hardest
passages and snapshot identity. Source Korean is included only when requested.
Compact/default exports bound lists; detailed exports or explicitly including all
Korean segments can be large. Exporting does not consume content or create evidence.
All files are generated locally; uploading one to a teacher is your separate action.

## Advanced CLI

```sh
lute-korean-study start episode.txt --database /absolute/lute.db --writable --kind tprs --format tprs
lute-korean-study partial SESSION_ID --database /absolute/lute.db --writable --start 0 --end 20
lute-korean-study complete SESSION_ID --database /absolute/lute.db --writable --start 21 --end 50
lute-korean-study list --database /absolute/lute.db
lute-korean-study show SESSION_ID --database /absolute/lute.db
```

CLI ranges are zero-based and inclusive; UI labels are one-based. Mutating
commands require an existing migrated database and explicit `--writable`.
Existing Anki, knowledge, evidence, learner-state and CI CLIs remain supported.

## Safety and limitations

Only explicit POST saves/sync/session actions write domain data. All Korean POSTs
validate standard Flask-WTF CSRF tokens, including when Lute globally disables
CSRF. GET, analyze, compare and exports make zero Knowledge writes. Services leave
commit/rollback ownership with the caller. Failures roll back the action.

There is no audio player, speech recognition, automatic listening evaluation,
automatic observation extraction, historical-study inference, external discovery
or status application. Kiwi ambiguity, lemma polysemy, five-pattern grammar
coverage and indirect historical Anki evidence remain existing limitations.
Candidate storage assumes Lute's normal single-process local server; a custom
multi-process deployment needs request affinity or reanalysis. Sync is synchronous
and may occupy a request for a large collection; it never runs on page load.
