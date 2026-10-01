"""Canonical Korean lexical identity without changing Kiwi or source text."""
from dataclasses import dataclass
from typing import Protocol
from ..analysis import lexical_heads


@dataclass(frozen=True)
class NormalizationMatch:
    """A deterministic replacement of adjacent morphological heads in one unit."""

    rule_id: str
    canonical: str
    consumed: int
    start: int
    end: int
    confidence: str = "deterministic"


class LexicalNormalizationRule(Protocol):
    """Stable, versioned rule boundary; new rules require independent evidence."""

    rule_id: str

    def match(self, unit, index) -> NormalizationMatch | None:
        ...


class JohahadaRule:
    """Recognize Kiwi's lexicalized 좋아하다 decomposition within one eojeol."""

    rule_id = "ko.lexical.johahada.v1"

    def match(self, unit, index):
        """Require exact POS/form sequence, original prefix and contiguous spans."""
        pieces = unit.morphemes[index : index + 3]
        if len(pieces) != 3:
            return None
        good, connective, auxiliary = pieces
        if tuple((m.form, m.pos) for m in pieces) != (
            ("좋", "VA"),
            ("어", "EC"),
            ("하", "VX"),
        ):
            return None
        if not (
            unit.start
            <= good.start
            < good.end
            == connective.start
            < connective.end
            == auxiliary.start
            < auxiliary.end
            <= unit.end
        ):
            return None
        # Morphology selected this slice; this guard prevents joining spaced predicates.
        prefix = unit.surface[good.start - unit.start : auxiliary.start - unit.start]
        if prefix != "좋아":
            return None
        return NormalizationMatch(self.rule_id, "좋아하다", 3, good.start, auxiliary.end)


class EojeRule:
    """Correct the attested IC+contracted pronoun misreading of 어제 only."""

    rule_id = "ko.lexical.eoje.v1"

    def match(self, unit, index):
        """Require the complete attested contraction and original unit boundary."""
        pieces = unit.morphemes[index : index + 3]
        if index != 0 or unit.surface != "어제" or len(pieces) != 3:
            return None
        if tuple((m.form, m.pos) for m in pieces) != (
            ("어", "IC"),
            ("저", "NP"),
            ("의", "JKG"),
        ):
            return None
        if [(m.start - unit.start, m.end - unit.start) for m in pieces] != [
            (0, 1),
            (1, 2),
            (1, 2),
        ]:
            return None
        return NormalizationMatch(self.rule_id, "어제", 3, unit.start, unit.end)


class LexicalizedExistentialRule:
    """Verified closed registry, never arbitrary noun + existential composition."""

    rule_id = "ko.lexical.existential-compound.v1"
    compounds = {"재미": "재미있다", "맛": "맛있다"}

    def match(self, unit, index):
        """Join only registered lexicalized predicates in contiguous source spans."""
        pieces = unit.morphemes[index : index + 2]
        if len(pieces) != 2:
            return None
        noun, predicate = pieces
        if (
            noun.form not in self.compounds
            or noun.pos != "NNG"
            or predicate.form != "있"
            or predicate.pos not in {"VA", "VV"}
        ):
            return None
        if (
            not unit.start
            <= noun.start
            < noun.end
            == predicate.start
            < predicate.end
            <= unit.end
        ):
            return None
        if (
            unit.surface[noun.start - unit.start : predicate.end - unit.start]
            != noun.form + "있"
        ):
            return None
        return NormalizationMatch(
            self.rule_id, self.compounds[noun.form], 2, noun.start, predicate.end
        )


@dataclass(frozen=True)
class NormalizedLexicalUnit:
    """Keep raw heads beside canonical identity and exact applied-rule provenance."""

    raw_heads: tuple
    canonical_heads: tuple
    matches: tuple

    def metadata(self):
        """Small stable JSON representation; raw morphology is stored separately."""
        return {
            "version": "ko.lexical.normalization.v1",
            "raw_heads": list(self.raw_heads),
            "canonical_heads": list(self.canonical_heads),
            "rules": [
                {
                    "id": m.rule_id,
                    "confidence": m.confidence,
                    "start": m.start,
                    "end": m.end,
                    "canonical": m.canonical,
                }
                for m in self.matches
            ],
        }


class KoreanLexicalNormalizer:
    """Explicit rule registry between raw Korean analysis and acquisition policy."""

    def __init__(self, rules=None):
        self.rules = (
            tuple(rules)
            if rules is not None
            else (JohahadaRule(), EojeRule(), LexicalizedExistentialRule())
        )
        ids = [r.rule_id for r in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("Normalization rule IDs must be unique")

    @property
    def version(self):
        """Include the active registry in the ingestion processing signature."""
        return "ko.lexical.normalization.v1:" + ",".join(r.rule_id for r in self.rules)

    def normalize(self, unit):
        """Project heads; never mutate the parser's unit or morphological objects."""
        heads, matches = [], []
        index = segment = 0
        while index < len(unit.morphemes):
            match = next(
                (
                    m
                    for rule in self.rules
                    if (m := rule.match(unit, index)) is not None
                ),
                None,
            )
            if match is None:
                index += 1
                continue
            if match.consumed <= 0 or index + match.consumed > len(unit.morphemes):
                raise ValueError(
                    "Normalization rule returned an invalid morphological span"
                )
            if not unit.start <= match.start < match.end <= unit.end:
                raise ValueError("Normalization rule returned an invalid source span")
            if match.rule_id not in {rule.rule_id for rule in self.rules}:
                raise ValueError("Normalization match must identify a registered rule")
            heads.extend(lexical_heads(unit.morphemes[segment:index]))
            heads.append(match.canonical)
            matches.append(match)
            index += match.consumed
            segment = index
        if not matches:
            heads = list(unit.lexical_heads)
        else:
            heads.extend(lexical_heads(unit.morphemes[segment:]))
        return NormalizedLexicalUnit(
            unit.lexical_heads, tuple(dict.fromkeys(heads)), tuple(matches)
        )
