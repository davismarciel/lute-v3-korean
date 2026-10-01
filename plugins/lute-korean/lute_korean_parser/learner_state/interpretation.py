"""Explicit quality/polarity and context identity, separate from classification."""
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
import unicodedata


def context_fingerprint(text):
    """Exact normalized context identity; no semantic-similarity claim."""
    text = unicodedata.normalize("NFKC", text or "").casefold()
    text = "".join(" " if unicodedata.category(c).startswith("P") else c for c in text)
    normalized = " ".join(text.split())
    return (
        sha256(normalized.encode()).hexdigest() if normalized else "unobserved-context"
    )


@dataclass(frozen=True)
class EvidenceQuality:
    """Independent quality axes; diversity is calculated over events later."""

    directness: str
    scope: str
    polarity: str
    temporal_relevance: float
    association_confidence: float
    modality_confidence: float


@dataclass(frozen=True)
class InterpretedEvidence:  # pylint: disable=too-many-instance-attributes
    """Preserve event/source provenance while exposing heuristic contributions."""

    event_id: str
    source_key: str
    source_type: str
    context_key: str
    context_observed: bool
    dimension: str | None
    occurred_at: datetime
    evidence_type: str
    positive: float
    negative: float
    recognition: bool
    quality: EvidenceQuality
    surface: str | None = None


class EvidenceInterpreter:
    """Treat Anki ratings as capped contextual signals, never word tests."""

    def __init__(self, policy):
        self.policy = policy

    def association(self, metadata):
        """Discount inferred historical source linkage without discarding events."""
        basis = metadata.get("association_basis")
        if basis in ("first_observed_snapshot", "historical_snapshot_uncertain"):
            return self.policy.historical_factor
        if basis == "observed_revision_modification_boundary":
            return self.policy.inferred_association_factor
        if basis in (None, "verified_content", "explicit_item"):
            return 1.0
        return self.policy.historical_factor

    def interpret(self, row, context, source_key, as_of, review=False):
        """Project explicit modality/scope/polarity, preserving event identity."""
        # Explicit quality axes remain separate, including missing modality.
        # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        occurred_at = datetime.fromisoformat(row["occurred_at"])
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise ValueError("Evidence timestamp must be timezone-aware")
        if (
            occurred_at > as_of
            or metadata.get("linguistic_association") == "withheld_content_anomaly"
        ):
            return None
        kind = "anki_review" if review else row["evidence_type"]
        scope = (
            "note_content"
            if review
            else metadata.get(
                "scope", "item" if kind == "manual_confirmation" else "context"
            )
        )
        direct = (
            not review
            and kind != "exposure"
            and metadata.get(
                "directness", "direct" if kind == "manual_confirmation" else "indirect"
            )
            == "direct"
            and scope in ("item", "knowledge_item")
        )
        dimension = None if review else row["dimension"]
        if metadata.get("modality") == "unspecified":
            dimension = None
        temporal = self.policy.recency((as_of - occurred_at).total_seconds() / 86400)
        association = self.association(metadata)
        modality = 1.0 if dimension else self.policy.unspecified_modality_factor
        positive = negative = 0.0
        recognition = (
            kind in ("recognized", "produced", "manual_confirmation") and not review
        )
        if review:
            rating = row["rating"]
            positive = {
                2: self.policy.hard_signal,
                3: self.policy.good_signal,
                4: self.policy.easy_signal,
            }.get(rating, 0.0)
            negative = (
                1.0 if rating == 1 else self.policy.hard_signal if rating == 2 else 0.0
            )
        else:
            weight = {
                "exposure": self.policy.exposure_weight,
                "recognized": self.policy.recognized_weight,
                "produced": self.policy.produced_weight,
                "manual_confirmation": self.policy.confirmation_weight,
                "missed": self.policy.missed_weight,
            }[kind]
            # Exposure is already deliberately weak; other contextual events are discounted.
            if not direct and kind != "exposure":
                weight *= self.policy.indirect_factor
            if kind == "missed":
                negative = weight
            else:
                positive = weight
        multiplier = temporal * association * modality
        polarity = (
            "mixed"
            if positive and negative
            else "negative"
            if negative
            else "positive"
            if positive
            else "neutral"
        )
        quality = EvidenceQuality(
            "direct" if direct else "indirect",
            scope,
            polarity,
            temporal,
            association,
            modality,
        )
        return InterpretedEvidence(
            str(row.get("event_key") or row.get("id")),
            source_key,
            "anki" if review else row["source_type"],
            context_fingerprint(context),
            bool((context or "").strip()),
            dimension,
            occurred_at,
            kind,
            positive * multiplier,
            negative * multiplier,
            recognition,
            quality,
            row.get("surface"),
        )
