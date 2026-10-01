"""Pure acquisition projection shared by persistence and candidate analysis."""
from dataclasses import dataclass
from ..analysis import KoreanUnit


@dataclass(frozen=True)
class ProjectedLexicalUnit:
    """Bounded source unit and policy-selected heads, retaining raw normalization."""

    unit: KoreanUnit
    normalized: object
    heads: tuple
    non_korean: tuple = ()
    projection_rule: str | None = None

    def role(self, head):
        """Exactly the existing POS-supported annotation, not semantic NER."""
        return (
            "proper_noun"
            if any(m.lemma == head and m.pos == "NNP" for m in self.unit.morphemes)
            else "general"
        )


def project_lexical_units(analysis, normalized_units, policy, normalizer):
    """One NNP source span once; otherwise preserve orthographic acquisition units."""
    text = analysis.text
    spanning_names = {
        (m.start, m.end, m.lemma): m
        for m in analysis.morphemes
        if m.pos == "NNP"
        and policy.is_korean(m.lemma)
        and any(char.isspace() for char in text[m.start : m.end])
        and text[m.start : m.end] == m.form
    }
    for name in spanning_names.values():
        unit = KoreanUnit(
            text[name.start : name.end], name.start, name.end, (name,), (name.lemma,)
        )
        yield ProjectedLexicalUnit(
            unit,
            normalizer.normalize(unit),
            (name.lemma,),
            projection_rule="ko.projection.multiword-nnp.v1",
        )
    for unit, normalized in zip(analysis.units, normalized_units):
        heads = tuple(
            head
            for head in policy.heads(unit, normalized.canonical_heads)
            if not any(
                m.lemma == head and (m.start, m.end, m.lemma) in spanning_names
                for m in unit.morphemes
            )
        )
        foreign = tuple(
            h for h in normalized.canonical_heads if not policy.is_korean(h)
        )
        if heads or foreign:
            yield ProjectedLexicalUnit(unit, normalized, heads, foreign)
