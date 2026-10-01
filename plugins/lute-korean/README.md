# lute-korean — Korean reading and acquisition

An independent Lute v3 plugin with Kiwi morphological analysis and reading tokens
based on orthographic units (eojeol). Requires Python 3.10+; 64-bit Python 3.12/3.13
is recommended on Linux/WSL or Windows. Kiwi and its models are Python dependencies;
no Java, MeCab, or external analyzer installation is required.

## Install and enable

From the root of this fork, in the Python environment that runs Lute:

```sh
python -m pip install -e .
python -m pip install -e plugins/lute-korean
lute-korean-install
lute
```

The second command installs kiwipiepy automatically. For development, install
pytest in the same environment. On Windows, activate the virtual environment
before running these commands. The CLI installs the bundled YAML into Lute's
language catalog; it requires write access to that Python environment. Restart
Lute, select **Korean** in **New language**, save, and import your text normally.
The parser appears as **Korean (Kiwi)**. If Korean already exists, change its parser
to this one and remove character substitutions to preserve original quotes and
punctuation.

For Docker, install the plugin and run the CLI while building the image, using
the same Python environment as Lute. Installing only on the host does not enable
the plugin in the container. Lute updates may require running
`lute-korean-install` again. The command is idempotent and refuses to overwrite
a different YAML definition.

## Analysis API

```python
from lute_korean_parser.parser import KoreanParser
analysis = KoreanParser().analyze("한국에 가면 많이 먹었어요.")
for unit in analysis.units:
    print(unit.surface, unit.lemma, unit.lexical_heads, unit.grammatical_tokens)
```

`analysis.text` is the original input; `units` retains surface forms, start/end
positions, and lexical heads. `morphemes` retains every token, including punctuation,
tags, normalized forms, lemmas, and the original Kiwi object in `raw`. Positions
are Python Unicode character indices with exclusive ends; spans can overlap in
contractions. The entire sentence is analyzed in context. A unit without analysis
has empty morphemes/heads and a `None` lemma. Runtime/model errors propagate rather
than appearing as successful analysis.

The display adapter does not need to execute the model: it keeps contiguous
letters, numbers, and combining marks as one term, with punctuation and whitespace
separate. Line breaks become the `¶` marker required by Lute. Conjugated forms are
not replaced with lemmas. The core can normalize whitespace during rendering;
exact preservation is guaranteed in plugin tokens, except for the paragraph
protocol.

## Tests

```sh
python -m pytest plugins/lute-korean/tests
```

See `DECISIONS.md` for Sprint 1 architecture and `KNOWLEDGE.md` for the acquisition layer.

## Limitations and next steps

Kiwi is probabilistic: ambiguity, unknown names, and transcription errors can
produce incorrect analyses. The parser itself does not select pedagogical
structures; the optional knowledge layer supplies five conservative detectors. Compound heads are simple
projections; consult the complete morpheme sequence as well. The reading adapter
does not persist analysis or group native Lute term statuses by lemma. The optional
Sprint 2 knowledge layer persists its own concepts and evidence.
Model initialization takes time and memory; the model is shared within the process.
Supported Kiwi versions are restricted to the 0.23 series to control API changes.
Windows requires a wheel compatible with its Python version and architecture;
the implementation accommodates Windows, but this sprint was executed on Linux.

The knowledge layer uses the analysis API to associate occurrences with lexical
concepts while retaining surface forms. Chunks are created explicitly; automatic
chunk recognition remains a future layer above ordered spans/morphemes. Anki ingestion is optional and read-only; see [ANKI.md](ANKI.md).
External AI and automatic status promotion have not been implemented. The optional
learner-state and CI policies provide explainable suggestions, and Korean Study
provides a local daily workspace over these existing services.

## Korean Study daily workspace

Install this updated fork and plugin together, then restart Lute and select
**Korean Study** from its navigation. Daily Anki sync, learner inspection, input
analysis/comparison, explicit study sessions, factual observations and teacher
exports are available without routine CLI commands. Analysis creates no evidence;
only explicit consumption saves create exposure. Manual statuses remain separate
from suggestions. See [KOREAN_STUDY_WORKFLOW.md](KOREAN_STUDY_WORKFLOW.md) for setup,
Windows/WSL operation and conservative study semantics, and
[SPRINT_6_VALIDATION.md](SPRINT_6_VALIDATION.md) for validation results.

## Sprint 2 knowledge layer

The optional persistent acquisition layer is documented in [KNOWLEDGE.md](KNOWLEDGE.md).
It adds lexical concepts, selected grammar patterns, manually tracked chunks,
occurrences, evidence, manual statuses and JSON export. Install the updated plugin
and start this fork to apply its additive database migration. Reading tokens and
the Sprint 1 analysis API remain unchanged.

```sh
lute-korean-analyze-knowledge "한국에 가면 많이 먹을 거예요."
```

This command is read-only unless `--persist` is explicitly supplied.
Automatic status promotion, AI and difficulty calculations remain out of scope.


## Sprint 3 Anki integration

See [ANKI.md](ANKI.md) for explicit note-type mappings, preview, dry-run,
read-only AnkiConnect synchronization, revision/event identity and optional JSON
summaries. Start the updated fork to apply its additional migration; install
the updated plugin to enable `lute-korean-anki`. Reviews remain indirect evidence
and never promote acquisition statuses.

## Sprint 3.6 ingestion quality

Acquisition ingestion now applies a generic, provenance-preserving lexical
normalizer and Hangul lexical eligibility. `좋아하다` compounds share one concept;
foreign names remain metadata. Anki Korean-field diagnostics quarantine dominant
wrong-language content while retaining its source/reviews. Raw parser output and
reading appearance remain unchanged. See [KNOWLEDGE.md](KNOWLEDGE.md),
[ANKI.md](ANKI.md), and
[the real hardening audit](REAL_ANKI_VALIDATION_AFTER_HARDENING.md).

## Sprint 4 learner suggestions

Install the updated plugin to enable read-only inspection:

```sh
lute-korean-state inspect 먹다 --database /path/to/migrated-staging.db
lute-korean-state calibrate --database /path/to/migrated-staging.db --count 25
```

The engine provides independent categorical suggestions/confidence with reasons
and provenance warnings; manual status stays authoritative. No percentage of
mastery or automatic promotion is calculated. See [LEARNER_STATE.md](LEARNER_STATE.md)
and [LEARNER_STATE_VALIDATION.md](LEARNER_STATE_VALIDATION.md).

## Sprint 4.5 integrity and explicit observations

Read [LEXICAL_INTEGRITY.md](LEXICAL_INTEGRITY.md) for canonical projection, proper
names, component overlap and explicit rebuild boundaries. Use
`lute-korean-knowledge audit-integrity --database staging.db` or
`lute-korean-knowledge inspect-overlap '먹고 싶어요'` for diagnosis.
[HUMAN_EVIDENCE.md](HUMAN_EVIDENCE.md) describes the JSON/API and explicit
`lute-korean-evidence validate|preview|apply` commands. Preview never writes.
[SPRINT_4_5_VALIDATION.md](SPRINT_4_5_VALIDATION.md) reports the real-derived
staging rebuild; Policy V1 and official statuses remain unchanged.

## Sprint 5 candidate input analysis

`lute-korean-ci analyze|compare` estimates explainable reading/transcript linguistic
fit from local text, SRT, VTT and TPRS files. It opens Knowledge SQLite read-only;
candidate analysis never records exposure or changes learner state. Use `--compact`
for a bounded JSON report. See [CI_ANALYSIS.md](CI_ANALYSIS.md) and
[CI_ANALYSIS_VALIDATION.md](CI_ANALYSIS_VALIDATION.md), including the real EP1–EP7
comparison and synthetic validation.
