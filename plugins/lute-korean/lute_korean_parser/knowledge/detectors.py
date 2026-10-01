"""Conservative, independent detectors consuming Kiwi forms and POS, not substrings."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DetectedPattern:
    """A bounded grammar match with a detector provenance label."""

    pattern: str
    start: int
    end: int
    detector: str


class GrammarPatternDetector(Protocol):
    """Extension point for independent pedagogical constructions."""

    def detect(self, analysis):
        """Return bounded DetectedPattern values."""


def predicate(morpheme):
    """Recognize predicate or predicate-deriving POS tags."""
    return morpheme.pos in ("VV", "VA", "VX", "XSV", "XSA", "VCP", "VCN")


def unit_at(analysis, position):
    """Find the orthographic unit containing a source position."""
    return next((u for u in analysis.units if u.start <= position < u.end), None)


class EndingDetector:
    """Require a predicate in the same unit before a selected connecting ending."""

    def __init__(self, pattern, endings):
        self.pattern = pattern
        self.endings = endings

    def detect(self, analysis):
        """Detect supported constructions from ordered morphemes and POS."""
        found = []
        for unit in analysis.units:
            for index, m in enumerate(unit.morphemes):
                if (
                    m.pos == "EC"
                    and m.form in self.endings
                    and any(predicate(p) for p in unit.morphemes[:index])
                ):
                    found.append(
                        DetectedPattern(self.pattern, unit.start, unit.end, "ending-v1")
                    )
        return found


class DesireDetector:
    """Require adjacent 고/EC + 싶/VX within one uninterrupted construction."""

    def detect(self, analysis):
        """Detect supported constructions from ordered morphemes and POS."""
        found = []
        ms = analysis.morphemes
        for i in range(1, len(ms) - 1):
            m, following = ms[i : i + 2]
            if (
                m.form != "고"
                or m.pos != "EC"
                or following.lemma != "싶다"
                or following.pos != "VX"
            ):
                continue
            unit = unit_at(analysis, m.start)
            last = unit_at(analysis, following.start)
            if (
                unit
                and last
                and predicate(ms[i - 1])
                and analysis.text[m.end : following.start].strip(" \t") == ""
            ):
                found.append(
                    DetectedPattern("-고 싶다", unit.start, last.end, "desire-v1")
                )
        return found


class FutureDetector:
    """Require attributive ㄹ + 거/NNB + copula + polite 예요/EF."""

    def detect(self, analysis):
        """Detect supported constructions from ordered morphemes and POS."""
        found = []
        ms = analysis.morphemes
        for i in range(1, len(ms) - 3):
            ending, noun, copula, polite = ms[i : i + 4]
            if not (
                ending.pos == "ETM"
                and ending.form in ("ᆯ", "ㄹ", "을")
                and predicate(ms[i - 1])
                and noun.pos == "NNB"
                and noun.form == "거"
                and copula.pos == "VCP"
                and polite.pos == "EF"
                and polite.form == "예요"
            ):
                continue
            first = unit_at(analysis, ending.start)
            last = unit_at(analysis, polite.start)
            if (
                first
                and last
                and analysis.text[ending.end : noun.start].strip(" \t") == ""
            ):
                found.append(
                    DetectedPattern("-(으)ㄹ 거예요", first.start, last.end, "future-v1")
                )
        return found


DEFAULT_DETECTORS = (
    EndingDetector("-(으)면", {"면", "으면"}),
    EndingDetector("-아/어서", {"아서", "어서"}),
    EndingDetector("-는데", {"는데", "은데", "ᆫ데", "ㄴ데"}),
    DesireDetector(),
    FutureDetector(),
)


def detect_patterns(analysis, detectors=DEFAULT_DETECTORS):
    """Return stable, deduplicated detections from the selected detector policy."""
    detections = {
        (d.pattern, d.start, d.end): d
        for detector in detectors
        for d in detector.detect(analysis)
    }
    return tuple(
        detections[key] for key in sorted(detections, key=lambda k: (k[1], k[2], k[0]))
    )
