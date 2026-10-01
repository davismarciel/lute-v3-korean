"""Versioned descriptive linguistic-load heuristics, never mastery probability."""
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
import math

BUCKETS = ("strong_familiar", "familiar", "seen", "deferred", "unassessed", "untracked")
SUPPORTED = {"strong_familiar", "familiar"}
WEAK = {"deferred", "unassessed", "untracked"}


@dataclass(frozen=True)
class CIAnalysisPolicyV1:
    """Explicit thresholds combine concentration, diversity, grammar and support."""

    version: str = "ko.ci-analysis.v1"
    strong_familiar_weight: float = 0.0
    familiar_weight: float = 0.0
    seen_weight: float = 0.45
    deferred_weight: float = 1.2
    unassessed_weight: float = 1.0
    untracked_weight: float = 1.0
    proper_noun_factor: float = 0.25
    proper_noun_segment_cap: float = 0.75
    grammar_factor: float = 1.5
    low_confidence_support_penalty: float = 0.15
    support_uncertainty_segment_cap: float = 0.3
    light_threshold: float = 0.2
    stretch_threshold: float = 1.5
    segment_dense_threshold: float = 3.0
    segment_dense_ratio: float = 0.45
    segment_absolute_dense: float = 6.0
    fit_dense_segment_ratio: float = 0.35
    fit_dense_streak: int = 3
    fit_stretch_segment_ratio: float = 0.3
    fit_weak_unique_ratio: float = 0.4
    fit_low_support_ratio: float = 0.65
    fit_weak_grammar_ratio: float = 0.5
    fit_grammar_mean_load: float = 0.6
    medium_confidence_ratio: float = 0.5
    high_confidence_ratio: float = 0.75
    manual_confidence: str = "medium"
    hardest_limit: int = 10
    novelty_limit: int = 20
    compact_item_limit: int = 20
    compact_cluster_limit: int = 10
    compact_text_limit: int = 160

    def __post_init__(self):
        for key, value in asdict(self).items():
            if key in {"version", "manual_confidence"}:
                continue
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError("Policy parameters must be nonnegative numbers")
        for key in [
            "fit_dense_streak",
            "hardest_limit",
            "novelty_limit",
            "compact_item_limit",
            "compact_cluster_limit",
            "compact_text_limit",
        ]:
            if not isinstance(getattr(self, key), int) or getattr(self, key) < 1:
                raise ValueError("Policy counts must be positive integers")
        if self.proper_noun_factor == 0:
            raise ValueError("Proper name influence must remain positive")
        if self.manual_confidence not in {"low", "medium", "high"}:
            raise ValueError("Invalid manual confidence")
        for key in [
            "fit_dense_segment_ratio",
            "segment_dense_ratio",
            "fit_stretch_segment_ratio",
            "fit_weak_unique_ratio",
            "fit_low_support_ratio",
            "fit_weak_grammar_ratio",
            "medium_confidence_ratio",
            "high_confidence_ratio",
            "proper_noun_factor",
        ]:
            if getattr(self, key) > 1:
                raise ValueError("Policy ratio exceeds one")

    @property
    def fingerprint(self):
        """Record exact parameter identity alongside the version label."""
        return sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()

    def weight(self, bucket):
        """Heuristic load units; not statistical probabilities."""
        return getattr(self, bucket + "_weight")

    def match_state(self, item):
        """Explicit reading assessment wins; default overall unknown is not one."""
        if item is None:
            return {
                "tracked": False,
                "status": None,
                "bucket": "untracked",
                "confidence": "low",
                "state_origin": "absent_item",
                "manual_state": None,
                "suggested_state": None,
                "learner_warnings": [],
            }
        manual = item["manual_state"]
        suggested = item["suggested_state"]["reading"]
        if manual.get("reading") is not None:
            status = manual["reading"]
            origin = "manual_reading"
            confidence = self.manual_confidence
        elif manual.get("overall") == "future":
            status = "future"
            origin = "manual_deferment"
            confidence = self.manual_confidence
        else:
            status = suggested["status"]
            origin = "suggested_reading"
            confidence = suggested["confidence"]
        buckets = {
            "consolidated": "strong_familiar",
            "practicing": "familiar",
            "presented": "seen",
            "future": "deferred",
            "unknown": "unassessed",
        }
        return {
            "tracked": True,
            "status": status,
            "bucket": buckets[status],
            "confidence": confidence,
            "state_origin": origin,
            "manual_state": manual,
            "suggested_state": suggested,
            "learner_warnings": suggested["warnings"],
        }

    def segment_load(self, items):
        """One morphological span is not automatically multiple independent novelties."""
        general = {}
        names = {}
        grammar = []
        uncertainty = 0
        for item in items:
            weight = self.weight(item["bucket"])
            if item["kind"] == "chunk":
                continue
            if item["kind"] == "grammar":
                grammar.append(weight * self.grammar_factor)
            else:
                groups = (
                    names
                    if item["role"] in {"proper_noun", "foreign_name"}
                    else general
                )
                key = (item["start"], item["end"])
                groups[key] = max(groups.get(key, 0), weight)
            if item["bucket"] in SUPPORTED and item["confidence"] == "low":
                uncertainty += self.low_confidence_support_penalty
        name_load = min(
            self.proper_noun_segment_cap, sum(names.values()) * self.proper_noun_factor
        )
        novelty = sum(general.values()) + name_load + sum(grammar)
        load = novelty + min(uncertainty, self.support_uncertainty_segment_cap)
        denominator = (
            len(general)
            + len(names) * self.proper_noun_factor
            + len(grammar) * self.grammar_factor
        )
        ratio = load / denominator if denominator else 0
        if load >= self.segment_absolute_dense or (
            load >= self.segment_dense_threshold and ratio >= self.segment_dense_ratio
        ):
            level = 3
        elif load >= self.stretch_threshold:
            level = 2
        elif load > self.light_threshold:
            level = 1
        else:
            level = 0
        return {
            "level": level,
            "label": ("familiar", "light_novelty", "productive_stretch", "dense")[
                level
            ],
            "heuristic_load": round(load, 4),
            "novelty_load": round(novelty, 4),
            "weighted_density": round(ratio, 4),
            "proper_noun_load": round(name_load, 4),
            "support_uncertainty": round(
                min(uncertainty, self.support_uncertainty_segment_cap), 4
            ),
        }

    def fit(self, segments, general_items, grammar_items):
        """No single coverage threshold determines suitability."""
        valid = [s for s in segments if s["effective_items"]]
        if not valid:
            return None
        count = len(valid)
        dense = sum(s["load"]["level"] == 3 for s in valid)
        stretch = sum(s["load"]["level"] >= 2 for s in valid)
        streak = longest = 0
        for segment in segments:
            streak = streak + 1 if segment["load"]["level"] == 3 else 0
            longest = max(longest, streak)
        if (
            dense / count >= self.fit_dense_segment_ratio
            or longest >= self.fit_dense_streak
        ):
            return "dense"
        unique = {i["identity"]: i for i in general_items}
        weak_unique = (
            sum(i["bucket"] in WEAK for i in unique.values()) / len(unique)
            if unique
            else 0
        )
        support = (
            sum(i["bucket"] in SUPPORTED for i in general_items) / len(general_items)
            if general_items
            else 0
        )
        weak_grammar = (
            sum(i["bucket"] in WEAK for i in grammar_items) / len(grammar_items)
            if grammar_items
            else 0
        )
        mean = sum(s["load"]["heuristic_load"] for s in valid) / count
        if (
            dense
            or stretch / count >= self.fit_stretch_segment_ratio
            or (
                weak_unique >= self.fit_weak_unique_ratio
                and support < self.fit_low_support_ratio
            )
            or (
                weak_grammar >= self.fit_weak_grammar_ratio
                and mean >= self.fit_grammar_mean_load
            )
        ):
            return "stretch"
        if any(s["load"]["novelty_load"] > self.light_threshold for s in valid):
            return "productive"
        return "comfortable"
