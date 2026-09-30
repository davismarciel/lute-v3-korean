# Sprint 1: decisions before implementation

Lute is a Flask/SQLAlchemy application. Language.parser delegates to the registry,
which discovers AbstractParser classes through `lute.plugin.parse` entry points.
The template and Mandarin plugin demonstrate this contract; Japanese demonstrates
platform support checks. Book pagination and reading consume ParsedToken values;
term matching uses their surface strings, not lexical lemmas.

ParsedToken has no persistent metadata contract. We therefore keep original
orthographic word runs (eojeol) clickable, with punctuation and whitespace separate.
Unicode character categories define display boundaries only; Kiwi performs all
morphological analysis on the full original text, preserving sentence context.
Offsets are Python Unicode character indices, end exclusive. Overlapping Kiwi
spans are retained because contracted forms can share source characters.

The independent analysis API retains every Kiwi token, source offsets, normalized
forms, tags, lemmas, and the original Kiwi object. Lexical heads and grammatical
morphemes are projections, not replacements for surface text. Derived predicates
(e.g. 피곤 + 하/XSA) are composed using POS tags, not conjugation regex rules.
No grammatical proficiency detector or persistence is introduced.

Language definitions are a separate upstream git submodule. Lute has no language
configuration plugin discovery. A plugin CLI copies its bundled definition into
Lute's existing definition directory, idempotently and without overwriting a
conflicting file. This avoids core edits and submodule commits. Restart Lute after
installation; repeat the CLI after an upstream/package update if needed.

Sprint 2 seams: analyze(text), ordered morphemes and offsets for chunks; lexical
heads for a separate occurrence-to-concept association; existing term/repository
and reading services for a deliberately designed future persistence adapter.
Current Lute term statuses remain tied to surface forms.

Reference: Kiwi's official API exposes Token.lemma, POS tags and source spans:
https://bab2min.github.io/kiwipiepy/ . Its documented contractions can share spans;
observed zero-length copulas are also retained and attached to the containing unit.
The tested model is kiwipiepy 0.23.2 / kiwipiepy-model 0.23.0.
