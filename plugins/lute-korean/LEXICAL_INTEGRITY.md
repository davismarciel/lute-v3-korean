# Lexical integrity and construction overlap

## Boundary

Raw Kiwi analysis → versioned lexical normalization → eligibility → Knowledge
Items, bounded Occurrences and Evidence. Reading surfaces, parser tokens, raw
morphology and LearnerStatePolicyV1 are unchanged.

The normalizer registry now contains:

- `ko.lexical.johahada.v1`: the existing contiguous 좋아하다 rule.
- `ko.lexical.eoje.v1`: only an entire `어제` unit misread as `어/IC + 저/NP +
  의/JKG`, with exact relative spans `(0,1),(1,2),(1,2)`. This is an attested
  context-dependent morphological ambiguity, not a broken offset. Normal 어제
  and pronoun contractions retain raw analysis.
- `ko.lexical.existential-compound.v1`: verified closed entries 재미있다 and
  맛있다. Require contiguous NNG noun + 있/VA or VV, and matching original
  source spelling within one unit. Arbitrary nouns, particles and whitespace
  never trigger composition. Native unsplit Kiwi predicates need no rule.

Occurrences retain raw heads, canonical heads, rule IDs/spans, all compact raw
morphemes, surface and source offsets. Rules do not rewrite the analyzer output.

## Roles

`KnowledgeRepresentationService.set_role(item_id, role, origin="manual")`
records `general`, `proper_noun`, `foreign_name` or `unknown` in an additive table.
Automatic `ko.role.pos.v1` annotates an exact NNP lexical head as proper_noun;
other eligible heads default to general. This is a POS classification, not NER,
not a pedagogical priority, and not proof that every name was detected. Manual
overrides win; an observed proper-noun annotation is not downgraded by a later
ambiguous POS analysis. Latin names remain unlinked metadata by the existing
eligibility policy. Roles do not alter manual or suggested status.

## Relationships and effective items

An additive `korean_knowledge_relations` table records directed `component_of`
relations and small rule metadata. Initially only `싶다 → -고 싶다` is generated,
and only when that construction and its lexical component are actually linked.
The other four patterns use endings or excluded bound nouns/copula and need no
lexical suppression. The lexical and grammatical items remain independent.

```python
from lute_korean_parser.knowledge.representation import KnowledgeRepresentationService
representation = KnowledgeRepresentationService(session)
representation.list_roles()
representation.list_relations()
representation.resolve_effective_items(source_id, start, end)
```

The requested region must contain the complete selected occurrences. A component
is suppressed only if a linked grammar occurrence in the same Source actually
contains its span. A relation alone never suppresses the item globally. The
result reports `raw_items`, `effective_items`, `suppressed_overlap`, occurrence
IDs, spans, covering item and reason. Repeated occurrences remain separate;
consumers decide their own counting units. No difficulty/novelty score exists.

For `먹고 싶어요`, raw links are 먹다, 싶다 and -고 싶다; effective links are 먹다
and -고 싶다. A lexical-only region retains 싶다. Chunk overlap and untracked
auxiliary constructions are not automatically suppressed.

## Read-only diagnosis

```sh
lute-korean-knowledge audit-integrity --database staging.db
lute-korean-knowledge inspect-overlap '먹고 싶어요'
```

Audit checks every lexical link for canonical membership, source/surface offsets,
raw subspan bounds, the attested contaminations and multiple eligible heads.
It never repairs records. Morphological contractions and compositional multi-head
units require human interpretation, not blanket spelling comparisons.

## Migration and reconciliation

`20260930_03_korean_representation.sql` adds only roles and relations, with foreign
keys, uniqueness and self-relation guards. Normal Lute startup applies the
project's migration mechanism. No core Term/status/text table is changed.
Unmigrated Knowledge clients still ingest existing data without role/relation
annotations; migrate before using the new APIs. A clean staging rebuild exercises
the current pipeline. Its item UUIDs differ from old staging UUIDs by design.

Processing signatures include the normalization registry. An explicit sync of an
existing database creates new immutable revisions, preserving old associations;
it does **not** repair prior erroneous links or certify historical review text.
Before CI use, prefer a reviewed clean rebuild, or an explicit reconciliation
that maps old kind/identity to new identities, preserves manual assessments and
human Evidence, and archives old revisions with their qualification. No such
historical rewrite or principal database rebuild is performed automatically.

See [LEXICAL_INTEGRITY_AUDIT.md](LEXICAL_INTEGRITY_AUDIT.md) and
[SPRINT_4_5_VALIDATION.md](SPRINT_4_5_VALIDATION.md).

### Multiword proper-name spans

`ko.projection.multiword-nnp.v1` projects a raw NNP token containing whitespace
and matching its complete original source span exactly once, even when the reader
attaches that same token to two visual units. The Knowledge Occurrence uses the
full name span, retains its raw NNP morphology and projection ID, and leaves
particles/copula in the unchanged source/parser analysis. The real captured
examples are 캡틴 아메리카 and 카니예 웨스트. Ordinary nouns, spaced predicates and
unverified spellings do not trigger this projection. This changes occurrence
projection, not lemma identity or reading tokenization; processing identity moves
to `kiwi-knowledge-v3` so an old version is never silently reused.
