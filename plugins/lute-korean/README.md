# lute-korean — Sprint 1

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

See `DECISIONS.md` for the architecture and extension points for the next sprint.

## Limitations and next steps

Kiwi is probabilistic: ambiguity, unknown names, and transcription errors can
produce incorrect analyses. There is no pedagogical structure detector; endings,
particles, and POS tags are retained for a future layer. Compound heads are simple
projections; consult the complete morpheme sequence as well. Metadata is not
persisted, and Lute's database does not group term statuses by lemma.
Model initialization takes time and memory; the model is shared within the process.
Supported Kiwi versions are restricted to the 0.23 series to control API changes.
Windows requires a wheel compatible with its Python version and architecture;
the implementation accommodates Windows, but this sprint was executed on Linux.

Sprint 2 can use the analysis API to associate occurrences with lexical concepts
while retaining surface forms, and ordered spans/morphemes to recognize chunks.
Persistence and reading adapters will require explicit design decisions.
Anki, AI, scoring, dashboards, and chunk tracking have not been implemented.
