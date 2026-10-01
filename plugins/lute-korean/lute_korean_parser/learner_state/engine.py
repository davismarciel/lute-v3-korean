"""On-demand learner suggestions without writes or automatic status application."""
from collections import defaultdict, Counter
from dataclasses import asdict
from datetime import datetime, timezone
from .policy import LearnerStatePolicyV1
from .repository import LearnerEvidenceRepository
from .interpretation import EvidenceInterpreter, context_fingerprint
from ..knowledge.ingestion import LexicalPolicy

DIMENSIONS = ("reading", "listening", "production")
ORDER = {"unknown": 0, "presented": 1, "practicing": 2, "consolidated": 3}


class LearnerStateEngine:
    """Read one consistent snapshot, calculate and explain without fitting manual state."""

    def __init__(self, session, policy=None):
        self.repository = LearnerEvidenceRepository(session)
        self.policy = policy or LearnerStatePolicyV1()
        self.interpreter = EvidenceInterpreter(self.policy)

    def calculate(self, kind=None, item_id=None, as_of=None):
        """Recompute a consistent snapshot with fixed policy/time and zero writes."""
        as_of = as_of or datetime.now(timezone.utc)
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        connection = self.repository.session.connection()
        if (
            connection.dialect.name == "sqlite"
            and not connection.connection.driver_connection.in_transaction
        ):
            connection.exec_driver_sql("BEGIN")
        snapshot = self.repository.snapshot(kind, item_id)
        states = []
        for item in snapshot["items"]:
            if item["kind"] == "lexical" and not LexicalPolicy.is_korean(
                item["identity"]
            ):
                continue
            states.append(self._item(item, snapshot, as_of))
        return {
            "schema_version": 1,
            "language": "ko",
            "policy_version": self.policy.version,
            "policy_fingerprint": self.policy.fingerprint,
            "policy": asdict(self.policy),
            "as_of": as_of.isoformat(),
            "evidence_fingerprint": snapshot["fingerprint"],
            "input_fingerprint": snapshot["input_fingerprint"],
            "items": states,
        }

    def inspect(self, value, kind=None, as_of=None):
        """Resolve one canonical identity and inspect only its linked evidence."""
        item_id = self.repository.resolve(value, kind)
        result = self.calculate(kind, item_id=item_id, as_of=as_of)
        if not result["items"]:
            raise ValueError("Foreign identity is not an eligible Korean lexical item")
        return dict(
            result["items"][0],
            policy_version=result["policy_version"],
            policy_fingerprint=result["policy_fingerprint"],
            as_of=result["as_of"],
            evidence_fingerprint=result["evidence_fingerprint"],
        )

    def _item(self, item, snapshot, as_of):
        # Item/source/event DTOs are deliberately kept distinct for provenance.
        # pylint: disable=too-many-locals
        grouped = snapshot["grouped"]
        iid = item["id"]
        occurrences = grouped["occurrences"][iid]
        by_occ = {o["id"]: o for o in occurrences}
        source_map = snapshot["sources"]
        logical = {
            r["source_id"]: f"anki:{r['integration']}:note:{r['note_id']}"
            for r in grouped["revisions"][iid]
        }
        for source in source_map.values():
            logical.setdefault(
                source["id"],
                f"lute_text:{source['lute_text_id']}"
                if source["source_type"] == "lute_text"
                and source["lute_text_id"] is not None
                else source["source_type"] + ":" + source["reference"],
            )

        def context(occurrence):
            return source_map[occurrence["source_id"]]["content"][
                occurrence["context_start"] : occurrence["context_end"]
            ]

        events = []
        for row in grouped["evidence"][iid]:
            occ = by_occ.get(row["occurrence_id"])
            text = context(occ) if occ else row["context"]
            key = (
                logical[occ["source_id"]]
                if occ
                else row["source_type"] + ":" + row["source_reference"]
            )
            event = self.interpreter.interpret(
                dict(row, surface=occ["surface"] if occ else row["surface"]),
                text,
                key,
                as_of,
            )
            if event:
                events.append(event)
        review_events = []
        for row in grouped["reviews"][iid]:
            # A card tests its content as a whole, not every sentence containing this item.
            event = self.interpreter.interpret(
                row,
                source_map[row["source_id"]]["content"],
                logical[row["source_id"]],
                as_of,
                review=True,
            )
            if event:
                review_events.append(event)
        manual = {"overall": item["status"], **{d: None for d in DIMENSIONS}}
        manual.update({r["dimension"]: r["status"] for r in grouped["dimensions"][iid]})
        suggested = {}
        for dimension in DIMENSIONS:
            lane = [e for e in events if e.dimension == dimension]
            # Unspecified review support is contextual only. It supports a reading
            # lane that already has real reading evidence; never asserts its modality.
            contextual = review_events if dimension == "reading" and lane else []
            state = self._dimension(lane, contextual, as_of, dimension)
            if manual["overall"] == "future" or manual[dimension] == "future":
                state = dict(
                    state,
                    computed_status=state["status"],
                    status="future",
                    origin="manual_deferment",
                )
                state["reasons"].append(
                    "Manual future decision retained; computed status is diagnostic only"
                )
            else:
                state["origin"] = "evidence_suggestion"
            suggested[dimension] = state
        ratings = Counter(
            r["rating"]
            for r in grouped["reviews"][iid]
            if datetime.fromisoformat(r["occurred_at"]) <= as_of
        )
        sources = {o["source_id"] for o in occurrences}
        contexts = {context_fingerprint(context(o)) for o in occurrences}
        contexts.update(e.context_key for e in events if e.context_observed)
        context_observed = contexts - {"unobserved-context"}
        summary = {
            "events": len(events),
            "occurrences": len(by_occ),
            "sources": len(sources),
            "logical_sources": len(
                {logical[s] for s in sources} | {e.source_key for e in events}
            ),
            "contexts": len(context_observed),
            "source_types": sorted(
                {source_map[s]["source_type"] for s in sources}
                | {e.source_type for e in events}
            ),
            "surfaces": sorted({o["surface"] for o in occurrences}),
            "anki_notes": len(
                {(r["integration"], r["note_id"]) for r in grouped["revisions"][iid]}
            ),
            "anki_cards": len(
                {(r["integration"], r["card_id"]) for r in grouped["cards"][iid]}
            ),
            "anki_reviews": len(review_events),
            "anki_ratings": {
                "again": ratings[1],
                "hard": ratings[2],
                "good": ratings[3],
                "easy": ratings[4],
            },
            "last_review": max(
                (r.occurred_at.isoformat() for r in review_events), default=None
            ),
            "historically_uncertain_reviews": sum(
                e.quality.association_confidence < 1 for e in review_events
            ),
            "unspecified_modality_events": sum(e.dimension is None for e in events)
            + len(review_events),
        }
        computed_overall = max(
            (suggested[d] for d in DIMENSIONS),
            key=lambda state: ORDER.get(
                state.get("computed_status", state["status"]), -1
            ),
        )
        active = [state for state in suggested.values() if state["status"] != "future"]
        overall = (
            max(active, key=lambda state: ORDER[state["status"]])
            if active
            else computed_overall
        )
        deferred = manual["overall"] == "future" or (
            any(state["status"] == "future" for state in suggested.values())
            and not any(state["status"] != "unknown" for state in active)
        )
        overall_status = overall["status"]
        if overall_status == "unknown" and (events or review_events):
            overall_status = "presented"
        overall = {
            "status": "future" if deferred else overall_status,
            "confidence": overall["confidence"],
            "reasons": [
                "Strongest non-deferred observed dimension; no skill transfer is implied"
            ],
            "warnings": [
                "Overall unknown may be a default, not an explicit manual assessment"
            ],
        }
        if deferred:
            overall["computed_status"] = computed_overall.get(
                "computed_status", computed_overall["status"]
            )
            overall["reasons"].append(
                "Manual deferment remains visible; calculated underlying state is diagnostic only"
            )
        comparison = {
            d: self._comparison(manual[d], suggested[d]["status"]) for d in DIMENSIONS
        }
        comparison["overall"] = self._comparison(manual["overall"], overall["status"])
        return {
            "suggested_overall": overall,
            "id": iid,
            "type": item["kind"],
            "identity": item["identity"],
            "manual_state": manual,
            "suggested_state": suggested,
            "evidence": summary,
            "comparison": comparison,
        }

    def _dimension(self, events, reviews, as_of, dimension):
        # All gates and contributions are explicit; thresholds live in the policy.
        # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        policy = self.policy
        contributions = defaultdict(lambda: [0.0, 0.0])
        review_groups = defaultdict(list)
        for event in reviews:
            review_groups[(event.source_key, event.context_key)].append(event)
        for key, rows in review_groups.items():
            # Weighted signal counts retain rating/sequence recency, then saturate.
            positive = policy.review_positive_cap * policy.diminishing(
                sum(e.positive for e in rows)
            )
            ordered = sorted(rows, key=lambda e: (e.occurred_at, e.event_id))
            recovery = 0
            for event in reversed(ordered):
                if event.quality.polarity != "positive":
                    break
                recovery += 1
            factor = (
                policy.review_lapse_boost
                if ordered[-1].quality.polarity == "negative"
                else policy.review_recovery_discount
                ** min(recovery, policy.review_recovery_limit)
            )
            negative = policy.review_negative_cap * policy.diminishing(
                sum(e.negative for e in rows) * factor
            )
            contributions[key][0] += positive
            contributions[key][1] += negative
        for event in events:
            contributions[(event.source_key, event.context_key)][0] += event.positive
            contributions[(event.source_key, event.context_key)][1] += event.negative
        per_source = defaultdict(lambda: [0.0, 0.0])
        per_context = defaultdict(lambda: [0.0, 0.0])
        # Independent aggregate ceilings avoid assigning duplicate contexts to
        # whichever source happened to sort first. Both ceilings must be respected.
        for (source, context), values in contributions.items():
            for index, cap in enumerate(
                (policy.context_positive_cap, policy.context_negative_cap)
            ):
                amount = min(values[index], cap)
                per_context[context][index] += amount
                per_source[source][index] += amount
        positive = min(
            sum(min(v[0], policy.source_positive_cap) for v in per_source.values()),
            sum(min(v[0], policy.context_positive_cap) for v in per_context.values()),
        )
        negative = min(
            sum(min(v[1], policy.source_negative_cap) for v in per_source.values()),
            sum(min(v[1], policy.context_negative_cap) for v in per_context.values()),
        )
        contexts = {e.context_key for e in events if e.context_observed}
        source_keys = {e.source_key for e in events}
        recognized = {
            e.context_key
            for e in events
            if e.recognition and e.positive > 0 and e.context_observed
        }
        direct = {
            e.context_key
            for e in events
            if e.recognition
            and e.positive > 0
            and e.context_observed
            and e.quality.directness == "direct"
        }
        recent_direct_misses = [
            e
            for e in events
            if e.negative > 0
            and e.quality.directness == "direct"
            and (as_of - e.occurred_at).total_seconds() / 86400
            <= policy.recent_miss_days
        ]
        surfaces = {e.surface for e in events if e.surface}
        if len(contexts) > 1 and (recognized or reviews):
            # Only positive-bearing sources/contexts can supply bonus headroom.
            source_headroom = sum(
                max(0, policy.source_positive_cap - v[0])
                for v in per_source.values()
                if v[0] > 0
            )
            context_headroom = sum(
                max(0, policy.context_positive_cap - v[0])
                for v in per_context.values()
                if v[0] > 0
            )
            positive += min(
                policy.surface_bonus_cap,
                policy.surface_bonus * max(len(surfaces) - 1, 0),
                source_headroom,
                context_headroom,
            )
        status = "unknown" if not events else "presented"
        support = bool(recognized or reviews)
        if events and (
            (support and positive >= policy.practice_threshold) or recent_direct_misses
        ):
            status = "practicing"
        qualified = (
            len(direct) >= policy.consolidation_recognition_contexts
            or len(recognized) >= policy.indirect_recognition_contexts
        )
        diverse = len(contexts) >= policy.consolidation_contexts and (
            len(source_keys) >= policy.consolidation_sources
            or len(direct) >= policy.consolidation_recognition_contexts
        )
        if (
            qualified
            and diverse
            and positive >= policy.consolidation_threshold
            and negative <= positive * policy.consolidation_negative_ratio
            and not recent_direct_misses
        ):
            status = "consolidated"
        association = min(
            (e.quality.association_confidence for e in events + reviews), default=1
        )
        confidence = "low"
        if (
            recognized
            and len(contexts) >= policy.medium_confidence_contexts
            and len(events) >= policy.high_confidence_events
        ):
            confidence = "medium"
        if (
            recognized
            and len(recognized) >= policy.high_confidence_contexts
            and association >= policy.inferred_association_factor
        ):
            confidence = "high"
        if (
            not recognized
            and support
            and len(contexts) >= policy.medium_confidence_contexts
        ):
            confidence = "medium"
        reliable_direct = {
            e.context_key
            for e in events
            if e.recognition
            and e.context_observed
            and e.quality.directness == "direct"
            and e.quality.association_confidence >= policy.inferred_association_factor
        }
        if (
            association < policy.inferred_association_factor
            and confidence == "high"
            and len(reliable_direct) < policy.high_confidence_contexts
        ):
            confidence = "medium"
        reasons = [
            f"{len(events)} dimension-specific events; {len(contexts)} distinct "
            f"contexts; {len(source_keys)} logical sources",
            f"{len(direct)} directly recognized/used contexts; "
            f"{len(recognized)} total recognition/use contexts",
            f"{len(surfaces)} observed surface forms; "
            "conservative temporal weighting retains older exposure",
        ]
        warnings = []
        if not events:
            warnings.append(f"No observed {dimension} evidence")
        if events and not recognized:
            warnings.append(
                "Exposure is not proof of comprehension; consolidation is gated on recognition/use"
            )
        if reviews:
            reasons.append(
                f"{len(reviews)} sentence-level Anki events provide capped contextual support"
            )
            warnings.append(
                "Anki reviews are indirect, note scoped and modality unspecified; "
                "not individual word successes"
            )
        if association < 1:
            warnings.append(
                "Historical/inferred associations reduce evidence strength and confidence"
            )
        if recent_direct_misses:
            reasons.append(
                f"{len(recent_direct_misses)} recent direct misses prevent consolidation"
            )
        if negative:
            reasons.append(
                "Negative evidence retained; indirect failures do not imply this item is unknown"
            )
        if (
            events
            and max(e.quality.temporal_relevance for e in events)
            < policy.stale_relevance_threshold
        ):
            warnings.append(
                "Evidence is old; conservative recency retains exposure but lowers freshness"
            )
            if confidence == "high":
                confidence = "medium"
        if any(not e.context_observed for e in events):
            warnings.append("Missing context text cannot provide context diversity")
        return {
            "status": status,
            "confidence": confidence,
            "reasons": reasons,
            "warnings": warnings,
            "evidence_quality": {
                "events": len(events),
                "direct_contexts": len(direct),
                "recognition_contexts": len(recognized),
                "contexts": len(contexts),
                "sources": len(source_keys),
                "surface_count": len(surfaces),
                "positive_strength": round(positive, 6),
                "negative_strength": round(negative, 6),
                "association_confidence_floor": association,
                "source_types": sorted({e.source_type for e in events + reviews}),
                "indirect_contextual_support_events": len(reviews),
                "temporal_relevance_range": [
                    min(
                        (e.quality.temporal_relevance for e in events + reviews),
                        default=0,
                    ),
                    max(
                        (e.quality.temporal_relevance for e in events + reviews),
                        default=0,
                    ),
                ],
                "modality_observed_events": len(events),
                "polarity": dict(Counter(e.quality.polarity for e in events + reviews)),
                "score_semantics": "heuristic evidence strength, not probability",
            },
        }

    @staticmethod
    def _comparison(manual, suggested):
        if manual is None:
            return "no manual"
        if manual == suggested:
            return "manual == suggested"
        if manual == "future" or suggested == "future":
            return "manual deferment"
        return (
            "manual > suggested"
            if ORDER[manual] > ORDER[suggested]
            else "manual < suggested"
        )

    def compare(self, kind=None, as_of=None):
        result = self.calculate(kind=kind, as_of=as_of)
        return dict(
            result,
            comparison_summary=dict(
                Counter(
                    value for i in result["items"] for value in i["comparison"].values()
                )
            ),
        )

    def export(self, kind=None, as_of=None, diagnostics=False):
        """JSON-ready suggested state; internal strengths require explicit diagnostics."""
        result = self.calculate(kind=kind, as_of=as_of)
        if not diagnostics:
            for item in result["items"]:
                for state in item["suggested_state"].values():
                    state["evidence_quality"].pop("positive_strength", None)
                    state["evidence_quality"].pop("negative_strength", None)
        return result
