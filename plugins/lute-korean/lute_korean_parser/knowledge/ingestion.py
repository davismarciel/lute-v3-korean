"""Explicit ingestion: linguistic analysis -> persistent acquisition evidence."""
from bisect import bisect_right
from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import version
import unicodedata
from ..parser import KoreanParser
from .detectors import DEFAULT_DETECTORS, detect_patterns
from .normalization import KoreanLexicalNormalizer
from .projection import project_lexical_units
from .representation import KnowledgeRepresentationService
from .service import KnowledgeService, validate, DIMENSIONS


@dataclass(frozen=True)
class LexicalPolicy:
    """Keep content heads; grammatical scaffolding remains occurrence metadata."""

    excluded_pos: tuple = ("NNB", "VCP", "VCN", "SN")

    version = "ko.lexical.eligibility.v1"

    @staticmethod
    def is_korean(head):
        """Track Hangul lexical identities; retain other scripts as source metadata."""
        letters = [c for c in unicodedata.normalize("NFC", head) if c.isalpha()]
        return bool(letters) and all(
            "\uac00" <= c <= "\ud7a3"
            or "\u1100" <= c <= "\u11ff"
            or "\u3130" <= c <= "\u318f"
            for c in letters
        )

    def heads(self, unit, canonical_heads=None):
        """Apply content-word policy without discarding source morphology."""
        excluded = {m.lemma for m in unit.morphemes if m.pos in self.excluded_pos}
        return tuple(
            dict.fromkeys(
                h
                for h in (
                    unit.lexical_heads if canonical_heads is None else canonical_heads
                )
                if h not in excluded and self.is_korean(h)
            )
        )


def compact_morphology(unit):
    """JSON-safe useful fields only; never serialize Kiwi raw model objects."""
    return {
        "morphemes": [
            {
                "form": m.form,
                "pos": m.tag,
                "lemma": m.lemma,
                "start": m.start,
                "end": m.end,
            }
            for m in unit.morphemes
        ]
    }


class KnowledgeIngestionService:  # pylint: disable=too-many-instance-attributes
    """Analyze once per operation, deduplicate, and leave commit to the caller."""

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        session,
        parser=None,
        detectors=DEFAULT_DETECTORS,
        lexical_policy=None,
        normalizer=None,
    ):
        self.session = session
        self.knowledge = KnowledgeService(session)
        self.parser = parser if parser is not None else KoreanParser()
        self.detectors = detectors
        self.lexical_policy = lexical_policy or LexicalPolicy()
        self.normalizer = normalizer or KoreanLexicalNormalizer()
        self.representation = (
            KnowledgeRepresentationService(session) if session is not None else None
        )
        self._representation_available = None

    @property
    def processing_version(self):
        """Analysis policy identity; changed policies require explicit new revisions."""
        return (
            "kiwi-knowledge-v3:ko.projection.multiword-nnp.v1:"
            + self.normalizer.version
            + ":"
            + self.lexical_policy.version
            + ":"
            + ",".join(self.lexical_policy.excluded_pos)
        )

    def preview(self, text):
        """Diagnostic analysis has no persistence side effects."""
        analysis = self.parser.analyze(text)
        return self.project(analysis)

    def project(self, analysis):
        """Expose policy-selected items while retaining the original analysis."""
        normalized = tuple(self.normalizer.normalize(unit) for unit in analysis.units)
        return {
            "analysis": analysis,
            "normalized": normalized,
            "lexical": tuple(
                dict.fromkeys(
                    h
                    for u, n in zip(analysis.units, normalized)
                    for h in self.lexical_policy.heads(u, n.canonical_heads)
                )
            ),
            "grammar": detect_patterns(analysis, self.detectors),
        }

    def ingest(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        self,
        text,
        source_reference,
        source_type="manual",
        dimension="reading",
        lute_text_id=None,
        record_exposure=True,
    ):
        """Persist one analyzed source revision atomically without committing the session."""
        validate(dimension, DIMENSIONS, "dimension")
        projected = self.preview(text)
        analysis = projected["analysis"]
        boundaries = sorted(
            {0, len(text)}
            | {m.end for m in analysis.morphemes if m.pos == "SF"}
            | {i + 1 for i, char in enumerate(text) if char in "\r\n"}
        )

        def context(start, end):
            first = max(0, bisect_right(boundaries, start) - 1)
            last = min(len(boundaries) - 1, bisect_right(boundaries, end - 1))
            return boundaries[first], boundaries[last]

        if self._representation_available is None:
            self._representation_available = self.representation.available()
        item_ids = set()
        occurrence_ids = set()
        evidence_ids = set()
        # SAVEPOINT prevents partial ingestion if any projection or write fails.
        # Callers can combine several source ingestions in their own transaction.
        connection = self.session.connection()
        # sqlite3 legacy transaction mode does not BEGIN before SAVEPOINT.
        # Without this, releasing a first savepoint can commit behind the caller.
        if (
            connection.dialect.name == "sqlite"
            and not connection.connection.driver_connection.in_transaction
        ):
            connection.exec_driver_sql("BEGIN")
        with self.session.begin_nested():
            source = self.knowledge.ensure_source(
                source_type, source_reference, text, lute_text_id
            )

            def attach(item, start, end, metadata):
                cstart, cend = context(start, end)
                occurrence = self.knowledge.associate_occurrence(
                    item["id"], source["id"], start, end, cstart, cend, metadata
                )
                event = None
                if record_exposure:
                    event = self.knowledge.record_evidence(
                        item["id"],
                        "exposure",
                        dimension=dimension,
                        occurrence_id=occurrence["id"],
                        metadata={"detector": metadata["detector"]}
                        if "detector" in metadata
                        else None,
                        event_key=f"ingest-v1:{occurrence['id']}:{item['id']}:{dimension}",
                    )
                item_ids.add(item["id"])
                occurrence_ids.add(occurrence["id"])
                if event is not None:
                    evidence_ids.add(event["id"])

            for projection in project_lexical_units(
                analysis, projected["normalized"], self.lexical_policy, self.normalizer
            ):
                unit, normalized = projection.unit, projection.normalized
                heads, non_korean = projection.heads, list(projection.non_korean)
                if not heads and not non_korean:
                    continue
                metadata = compact_morphology(unit)
                metadata.update(
                    analysis_version="kiwi-knowledge-v3",
                    lexical_normalization=normalized.metadata(),
                    eligible_heads=list(heads),
                    non_korean_heads=non_korean,
                    kiwi_version=version("kiwipiepy"),
                )
                if projection.projection_rule:
                    metadata["projection_rule"] = projection.projection_rule
                if not heads:
                    cstart, cend = context(unit.start, unit.end)
                    retained = self.knowledge.ensure_occurrence(
                        source["id"], unit.start, unit.end, cstart, cend, metadata
                    )
                    occurrence_ids.add(retained["id"])
                for head in heads:
                    item = self.knowledge.get_or_create_lexical(head)
                    role = projection.role(head)
                    if self._representation_available:
                        self.representation.set_role(
                            item["id"],
                            role,
                            origin="kiwi",
                            metadata={"rule": "ko.role.pos.v1"},
                        )
                    attach(
                        item,
                        unit.start,
                        unit.end,
                        metadata,
                    )
            for detected in projected["grammar"]:
                attach(
                    self.knowledge.get_or_create_grammar(detected.pattern),
                    detected.start,
                    detected.end,
                    {"detector": detected.detector},
                )
            if self._representation_available:
                for detected in projected["grammar"]:
                    if detected.pattern == "-고 싶다":
                        component = self.knowledge.get_lexical("싶다")
                        construction = self.knowledge.find_item("grammar", "-고 싶다")
                        if component and component["id"] in item_ids:
                            self.representation.relate(
                                component["id"],
                                construction["id"],
                                metadata={"rule": "ko.overlap.desire.v1"},
                            )
        return {
            "source_id": source["id"],
            "item_ids": sorted(item_ids),
            "occurrence_ids": sorted(occurrence_ids),
            "evidence_ids": sorted(evidence_ids),
        }

    def ingest_lute_text(self, text_id, dimension="reading"):
        """Opt-in page adapter; immutable source revision retains evidence after edits."""
        from lute.models.book import Text  # pylint: disable=import-outside-toplevel

        page = self.session.get(Text, text_id)
        if page is None:
            raise KeyError(text_id)
        if page.book.language.parser_type != "lute_korean":
            raise ValueError("Only Korean (Kiwi) pages can be ingested")
        text = page.text
        digest = sha256(text.encode("utf8")).hexdigest()
        policy_digest = sha256(self.processing_version.encode("utf8")).hexdigest()
        return self.ingest(
            text,
            f"text:{text_id}:{digest}:{policy_digest}",
            source_type="lute_text",
            dimension=dimension,
            lute_text_id=text_id,
        )
