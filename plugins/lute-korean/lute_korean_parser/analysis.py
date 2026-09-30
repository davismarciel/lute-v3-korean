"""Contextual Kiwi analysis without changing the original reading text."""
from bisect import bisect_right
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Optional, Tuple
from kiwipiepy import Kiwi
from .boundaries import spans


@lru_cache(maxsize=1)
def default_kiwi():
    """Share the expensive model across short-lived Lute parser instances."""
    return Kiwi(num_workers=1)


@dataclass(frozen=True)
class Morpheme:
    """One Kiwi token, including normalized form and its original source span."""

    form: str
    tag: str
    start: int
    end: int
    lemma: str
    raw: Any = field(repr=False, compare=False)

    @property
    def pos(self):
        return self.tag.split("-", 1)[0]

    @property
    def is_grammatical(self):
        return self.pos.startswith(("J", "E", "XS")) or self.pos in ("VCP", "VCN")


@dataclass(frozen=True)
class KoreanUnit:
    """Original orthographic unit with all attached morphological evidence."""

    surface: str
    start: int
    end: int
    morphemes: Tuple[Morpheme, ...]
    lexical_heads: Tuple[str, ...]

    @property
    def lemma(self) -> Optional[str]:
        """Primary head for simple units; all heads remain available for compounds."""
        return self.lexical_heads[0] if self.lexical_heads else None

    @property
    def lexical_tokens(self):
        return tuple(m for m in self.morphemes if not m.is_grammatical)

    @property
    def grammatical_tokens(self):
        return tuple(m for m in self.morphemes if m.is_grammatical)

    @property
    def pos_tags(self):
        return tuple(m.tag for m in self.morphemes)


@dataclass(frozen=True)
class KoreanAnalysis:
    """Original text, display units and every morpheme in analysis order."""

    text: str
    units: Tuple[KoreanUnit, ...]
    morphemes: Tuple[Morpheme, ...]


def lexical_heads(morphemes):
    """Project lexical lemmas, combining POS-marked derivational predicates."""
    heads = []
    for m in morphemes:
        if m.pos in ("XSV", "XSA") and heads:
            heads[-1] += m.form + "다"
        elif not m.is_grammatical and m.pos not in {
            "SF",
            "SP",
            "SS",
            "SSO",
            "SSC",
            "SE",
            "SO",
            "SW",
            "SB",
        }:
            heads.append(m.lemma)
        elif m.pos in ("VCP", "VCN"):
            heads.append(m.lemma)
    return tuple(heads)


class KoreanAnalyzer:
    """Analyze original text once, retaining unassigned tokens and overlapping spans."""

    def __init__(self, kiwi=None):
        self._kiwi = kiwi

    def analyze(self, text: str) -> KoreanAnalysis:
        """Analyze full context without normalization or dropping Kiwi tokens."""
        kiwi = self._kiwi if self._kiwi is not None else default_kiwi()
        morphemes = tuple(
            Morpheme(t.form, t.tag, t.start, t.start + t.len, t.lemma, t)
            for t in kiwi.tokenize(text)
        )
        word_spans = [(start, end) for start, end, word in spans(text) if word]
        starts = [start for start, _ in word_spans]
        assigned = [[] for _ in word_spans]
        # Index word starts to avoid scanning every morpheme for every unit.
        # Zero-length copulas belong to the unit containing their position.
        for m in morphemes:
            index = max(0, bisect_right(starts, m.start) - 1)
            while index < len(word_spans):
                start, end = word_spans[index]
                if start >= m.end and (m.start != m.end or start != m.start):
                    break
                if (m.start < end and m.end > start) or (
                    m.start == m.end and start <= m.start < end
                ):
                    assigned[index].append(m)
                index += 1
        units = tuple(
            KoreanUnit(
                text[start:end], start, end, tuple(members), lexical_heads(members)
            )
            for (start, end), members in zip(word_spans, assigned)
        )
        return KoreanAnalysis(text, units, morphemes)
