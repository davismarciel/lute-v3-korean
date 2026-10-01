"""Versioned heuristic policy, never a statistical mastery probability."""
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math


@dataclass(frozen=True)
class LearnerStatePolicyV1:  # pylint: disable=too-many-instance-attributes
    """Conservative, configurable evidence interpretation and categorical gates."""

    version: str = "ko.learner-state.v1"
    exposure_weight: float = 0.35
    recognized_weight: float = 2.5
    produced_weight: float = 3.0
    confirmation_weight: float = 3.0
    missed_weight: float = 2.5
    indirect_factor: float = 0.4
    historical_factor: float = 0.35
    inferred_association_factor: float = 0.65
    unspecified_modality_factor: float = 0.4
    recency_floor: float = 0.6
    recency_half_life_days: float = 365.0
    review_saturation: float = 5.0
    review_positive_cap: float = 0.9
    review_negative_cap: float = 0.55
    review_lapse_boost: float = 1.5
    review_recovery_discount: float = 0.75
    review_recovery_limit: int = 3
    surface_bonus: float = 0.1
    surface_bonus_cap: float = 0.3
    high_confidence_events: int = 6
    hard_signal: float = 0.15
    good_signal: float = 0.6
    easy_signal: float = 0.8
    context_positive_cap: float = 3.0
    context_negative_cap: float = 2.5
    source_positive_cap: float = 6.0
    source_negative_cap: float = 5.0
    practice_threshold: float = 1.5
    consolidation_threshold: float = 6.0
    consolidation_sources: int = 2
    stale_relevance_threshold: float = 0.8
    consolidation_contexts: int = 3
    consolidation_recognition_contexts: int = 3
    indirect_recognition_contexts: int = 6
    recent_miss_days: float = 45.0
    consolidation_negative_ratio: float = 0.2
    high_confidence_contexts: int = 6
    medium_confidence_contexts: int = 3

    def __post_init__(self):
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("Policy version must be nonempty")
        for name, value in asdict(self).items():
            if name == "version":
                continue
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"Invalid policy parameter: {name}")
            if (
                name.endswith("contexts")
                or name
                in (
                    "consolidation_sources",
                    "high_confidence_events",
                    "review_recovery_limit",
                )
            ) and (not isinstance(value, int) or value < 1):
                raise ValueError(f"Context gate must be a positive integer: {name}")
        for name in [
            "indirect_factor",
            "historical_factor",
            "inferred_association_factor",
            "unspecified_modality_factor",
            "recency_floor",
            "consolidation_negative_ratio",
            "review_recovery_discount",
            "stale_relevance_threshold",
        ]:
            if getattr(self, name) > 1:
                raise ValueError(f"Policy fraction exceeds one: {name}")
        if self.consolidation_threshold <= self.practice_threshold:
            raise ValueError("Consolidation threshold must exceed practice threshold")

    @property
    def fingerprint(self):
        return sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()

    def recency(self, age_days):
        """Slow conservative attenuation, retaining most of established evidence."""
        return self.recency_floor + (1 - self.recency_floor) * 2 ** (
            -max(age_days, 0) / self.recency_half_life_days
        )

    def diminishing(self, events):
        """Bounded support; repeated events can never grow without limit."""
        return max(events, 0) / (max(events, 0) + self.review_saturation)
