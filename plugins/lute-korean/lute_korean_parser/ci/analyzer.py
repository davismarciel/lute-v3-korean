"""Read-only linguistic-fit reports; a candidate is not a studied Source."""
from collections import Counter, defaultdict
from dataclasses import asdict
from ..knowledge.ingestion import KnowledgeIngestionService
from ..knowledge.projection import project_lexical_units
from ..knowledge.representation import resolve_effective_rows
from ..learner_state.interpretation import context_fingerprint
from .adapters import adapt_content
from .snapshot import CILearnerSnapshot
from .policy import CIAnalysisPolicyV1, BUCKETS, SUPPORTED, WEAK


def distribution(items):
    """Descriptive occurrence ratios; never knowledge/mastery percentages."""
    counts = Counter(item["bucket"] for item in items)
    total = len(items)
    return {
        bucket: {
            "count": counts[bucket],
            "ratio": counts[bucket] / total if total else 0,
        }
        for bucket in BUCKETS
    }


def clusters(segments, minimum_level):
    """Exact consecutive segment ranges, no semantic similarity."""
    result = []
    current = []
    for segment in segments:
        if segment["load"]["level"] >= minimum_level:
            current.append(segment)
        elif current:
            result.append(current)
            current = []
    if current:
        result.append(current)
    return [
        {
            "start_index": group[0]["index"],
            "end_index": group[-1]["index"],
            "length": len(group),
            "start_timestamp": group[0]["timestamp"],
            "end_timestamp": group[-1]["timestamp"],
        }
        for group in result
    ]


class CIContentAnalyzer:
    """Load one batched snapshot; reuse Kiwi and pure representation per segment."""

    def __init__(self, session, parser=None, snapshot=None, policy=None, as_of=None):
        self.snapshot = snapshot or CILearnerSnapshot.load(session, as_of)
        self.projection = KnowledgeIngestionService(None, parser=parser)
        self.policy = policy or CIAnalysisPolicyV1()

    def analyze_text(self, text, name="candidate", format="auto", kind="text"):
        """Direct Unicode input follows the same adapters as CLI files."""
        return self.analyze(adapt_content(text, name, format, kind))

    def _match(self, row):
        item = self.snapshot.items.get((row["kind"], row["identity"]))
        selected = self.policy.match_state(item)
        role = (
            self.snapshot.roles.get(item["id"], {}).get(
                "role", row.get("role", "general")
            )
            if item
            else row.get("role", "general")
        )
        return dict(row, **selected, item_id=item["id"] if item else None, role=role)

    def analyze(self, content):
        """No candidate persistence, SQL per segment, or consumer reanalysis."""
        segments = []
        effective = []
        warning_set = set(content.warnings)
        parser_calls = 0
        for segment in content.segments:
            projected = self.projection.preview(segment.text)
            parser_calls += 1
            rows = []
            foreign = []
            morphology = []
            representation_warnings = []
            for unit in project_lexical_units(
                projected["analysis"],
                projected["normalized"],
                self.projection.lexical_policy,
                self.projection.normalizer,
            ):
                if len(unit.heads) > 1:
                    representation_warnings.append(
                        "Multiple lexical heads in one span; load uses the maximum component novelty, not an independent sum"
                    )
                if any(m.pos == "VX" for m in unit.unit.morphemes):
                    representation_warnings.append(
                        "Auxiliary morphology may need untracked construction interpretation"
                    )
                foreign.extend(
                    {
                        "identity": head,
                        "surface": unit.unit.surface,
                        "start": unit.unit.start,
                        "end": unit.unit.end,
                    }
                    for head in unit.non_korean
                )
                for head in unit.heads:
                    row = {
                        "id": "lexical:" + head,
                        "kind": "lexical",
                        "identity": head,
                        "start": unit.unit.start,
                        "end": unit.unit.end,
                        "surface": unit.unit.surface,
                        "role": unit.role(head),
                        "normalization": unit.normalized.metadata(),
                        "projection_rule": unit.projection_rule,
                        "occurrence_id": f"{segment.index}:{unit.unit.start}:{unit.unit.end}:lexical:{head}",
                    }
                    rows.append(self._match(row))
            for pattern in projected["grammar"]:
                rows.append(
                    self._match(
                        {
                            "id": "grammar:" + pattern.pattern,
                            "kind": "grammar",
                            "identity": pattern.pattern,
                            "start": pattern.start,
                            "end": pattern.end,
                            "surface": segment.text[pattern.start : pattern.end],
                            "detector": pattern.detector,
                            "occurrence_id": f"{segment.index}:{pattern.start}:{pattern.end}:grammar:{pattern.pattern}",
                        }
                    )
                )
            for morpheme in projected["analysis"].morphemes:
                if morpheme.is_grammatical:
                    morphology.append(
                        {
                            "form": morpheme.form,
                            "pos": morpheme.tag,
                            "start": morpheme.start,
                            "end": morpheme.end,
                        }
                    )
            resolution = resolve_effective_rows(rows, self.snapshot.relations)
            # VX inside the explicitly modeled desire construction is covered;
            # remaining auxiliaries still need an honest granularity warning.
            if resolution["suppressed_overlap"] and all(
                m.lemma == "싶다"
                for m in projected["analysis"].morphemes
                if m.pos == "VX"
            ):
                representation_warnings = [
                    w for w in representation_warnings if not w.startswith("Auxiliary")
                ]
            load = self.policy.segment_load(resolution["effective_items"])
            reasons = [
                f"{sum(i['kind']=='lexical' and i['role'] not in {'proper_noun','foreign_name'} and i['bucket'] in WEAK for i in resolution['effective_items'])} untracked/unassessed/deferred general lexical links",
                f"{sum(i['bucket']=='seen' for i in resolution['effective_items'])} previously presented links",
                f"{sum(i['kind']=='grammar' and i['bucket'] in WEAK for i in resolution['effective_items'])} weak detected tracked-grammar links",
            ]
            if any(
                i["role"] in {"proper_noun", "foreign_name"}
                for i in resolution["effective_items"]
            ):
                reasons.append(
                    "Proper names remain visible with reduced, capped segment influence"
                )
            record = {
                "index": segment.index,
                "identity": segment.identity,
                "text": segment.text,
                "timestamp": segment.timestamp,
                "start_seconds": segment.start_seconds,
                "end_seconds": segment.end_seconds,
                "metadata": segment.metadata,
                "offset_basis": "clean_segment_text",
                "load": load,
                "reasons": reasons,
                "warnings": sorted(set(representation_warnings)),
                "foreign_surfaces": foreign,
                "morphology": morphology,
                **resolution,
            }
            segments.append(record)
            warning_set.update(representation_warnings)
            effective.extend(
                dict(
                    row,
                    segment_index=segment.index,
                    context_fingerprint=context_fingerprint(segment.text),
                    timestamp=segment.timestamp,
                )
                for row in resolution["effective_items"]
            )
        lexical = [i for i in effective if i["kind"] == "lexical"]
        grammar = [i for i in effective if i["kind"] == "grammar"]
        general = [
            i for i in lexical if i["role"] not in {"proper_noun", "foreign_name"}
        ]
        names = [i for i in lexical if i["role"] in {"proper_noun", "foreign_name"}]
        unique = {i["identity"]: i for i in lexical}
        grouped = self._groups(effective, segments)
        fit = self.policy.fit(segments, general, grammar)
        confidence = self._confidence(lexical + grammar, warning_set)
        if fit is None:
            warning_set.add(
                "No eligible Korean knowledge occurrences: linguistic fit is unavailable"
            )
        warning_set.update(
            [
                "Coverage describes candidate occurrences, not demonstrated comprehension or mastery",
                "Untracked means absent from the Knowledge Model, not definitely unknown to the learner",
                "Tracked grammar coverage includes only five detectors; untracked constructions may exist",
                "Lemma-oriented matching cannot distinguish new senses of a familiar word (polysemy)",
                "Transcript/text analysis does not establish listening comprehension or audio difficulty",
            ]
        )
        dense = clusters(segments, 3)
        difficult = clusters(segments, 2)
        totals = distribution(lexical)
        supported = sum(totals[b]["ratio"] for b in SUPPORTED)
        seen = supported + totals["seen"]["ratio"]
        load_counts = Counter(s["load"]["level"] for s in segments)
        reasons = [
            f"{supported:.1%} of effective lexical links are familiar/strong_familiar; {seen:.1%} previously seen",
            f"{len({i['identity']for i in general if i['bucket']in WEAK})} unique untracked/unassessed/deferred general lexical identities",
            f"{load_counts[0]+load_counts[1]}/{len(segments)} segments have load 0–1; {load_counts[3]} dense segments",
            f'{len(dense)} dense clusters; longest difficult cluster {max((c["length"]for c in difficult),default=0)}',
            f"{len(grammar)} detected tracked grammar occurrences; proper names reported separately",
        ]
        summary = {
            "fit": fit,
            "confidence": confidence,
            "assessment": "transcript_linguistic_fit"
            if content.kind == "podcast"
            else "reading_linguistic_fit",
            "listening_fit": "insufficient_evidence",
            "reasons": reasons,
            "segment_load_distribution": {
                str(level): load_counts[level] for level in range(4)
            },
            "dense_segment_ratio": load_counts[3] / len(segments) if segments else 0,
            "dense_clusters": dense,
            "difficult_clusters": difficult,
            "longest_difficult_cluster": max(
                (c["length"] for c in difficult), default=0
            ),
            "total_novelty_load": sum(s["load"]["novelty_load"] for s in segments),
        }
        if content.kind == "podcast":
            summary["transcript_fit"] = fit
        hardest = sorted(
            segments,
            key=lambda s: (
                -s["load"]["level"],
                -s["load"]["heuristic_load"],
                s["index"],
            ),
        )[: self.policy.hardest_limit]
        novelty = [
            g
            for g in grouped
            if (
                g["kind"] == "lexical"
                and g["role"] not in {"proper_noun", "foreign_name"}
                and g["bucket"] in WEAK | {"seen"}
            )
            or (g["kind"] == "grammar" and g["status"] != "consolidated")
        ]
        recycling = [g for g in grouped if g["status"] == "practicing"]
        return {
            "schema_version": 1,
            "content": {
                "name": content.name,
                "format": content.format,
                "kind": content.kind,
                "original_hash": content.original_hash,
                "segments": len(segments),
            },
            "policy": {
                "version": self.policy.version,
                "parameters": asdict(self.policy),
                "fingerprint": self.policy.fingerprint,
            },
            "learner_snapshot": self.snapshot.provenance,
            "processing_version": self.projection.processing_version,
            "summary": summary,
            "lexical": {
                "occurrence_distribution": totals,
                "unique_distribution": distribution(list(unique.values())),
                "supported_coverage": supported,
                "previously_seen_coverage": seen,
                "items": [g for g in grouped if g["kind"] == "lexical"],
                "general_novelty": {
                    "occurrence_distribution": distribution(general),
                    "unique_distribution": distribution(
                        list({i["identity"]: i for i in general}.values())
                    ),
                },
                "proper_names": {
                    "occurrence_distribution": distribution(names),
                    "items": [
                        g
                        for g in grouped
                        if g["role"] in {"proper_noun", "foreign_name"}
                    ],
                },
            },
            "grammar": {
                "label": "tracked grammar coverage",
                "occurrence_distribution": distribution(grammar),
                "unique_distribution": distribution(
                    list({i["identity"]: i for i in grammar}.values())
                ),
                "items": [g for g in grouped if g["kind"] == "grammar"],
                "untracked_constructions_may_exist": True,
            },
            "segments": segments,
            "hardest_segments": hardest,
            "novelties": novelty[: self.policy.novelty_limit],
            "recycling": recycling,
            "presented_opportunities": [g for g in grouped if g["bucket"] == "seen"],
            "chunks": {
                "items": [],
                "warning": "Automatic chunk mining is disabled; candidate chunk matching is not implemented",
            },
            "warnings": sorted(warning_set),
            "diagnostics": {"kiwi_calls": parser_calls, "candidate_persistence": False},
        }

    def _groups(self, items, segments):
        by_index = {segment["index"]: segment for segment in segments}
        grouped = defaultdict(list)
        for item in items:
            grouped[(item["kind"], item["identity"])].append(item)
        result = []
        for (kind, identity), rows in grouped.items():
            first = rows[0]
            indices = sorted({row["segment_index"] for row in rows})
            result.append(
                {
                    key: first[key]
                    for key in [
                        "kind",
                        "identity",
                        "item_id",
                        "tracked",
                        "role",
                        "bucket",
                        "status",
                        "confidence",
                        "state_origin",
                        "manual_state",
                        "suggested_state",
                    ]
                }
                | {
                    "count": len(rows),
                    "contexts": len({row["context_fingerprint"] for row in rows}),
                    "segment_indices": indices,
                    "surfaces": sorted({row["surface"] for row in rows}),
                    "sample": {
                        "segment_index": indices[0],
                        "timestamp": by_index[indices[0]]["timestamp"],
                        "text": by_index[indices[0]]["text"],
                    },
                }
            )
        return sorted(
            result,
            key=lambda g: (
                -g["count"],
                -g["contexts"],
                g["role"] in {"proper_noun", "foreign_name"},
                g["bucket"] not in WEAK,
                g["kind"],
                g["identity"],
            ),
        )

    def _confidence(self, items, warnings):
        if not items:
            return "low"
        denominator = sum(
            self.policy.proper_noun_factor
            if i["role"] in {"proper_noun", "foreign_name"}
            else 1
            for i in items
        )
        medium = (
            sum(
                (
                    self.policy.proper_noun_factor
                    if i["role"] in {"proper_noun", "foreign_name"}
                    else 1
                )
                for i in items
                if i["confidence"] in {"medium", "high"}
            )
            / denominator
        )
        high = (
            sum(
                (
                    self.policy.proper_noun_factor
                    if i["role"] in {"proper_noun", "foreign_name"}
                    else 1
                )
                for i in items
                if i["confidence"] == "high"
            )
            / denominator
        )
        uncertain = any(
            any(
                "indirect" in warning or "Historical" in warning
                for warning in i["learner_warnings"]
            )
            for i in items
        )
        if uncertain:
            warnings.add(
                "Learner state includes indirect Anki/contextual evidence and uncertain historical associations; fit confidence is capped at medium"
            )
        if high >= self.policy.high_confidence_ratio and not uncertain and not warnings:
            return "high"
        return "medium" if medium >= self.policy.medium_confidence_ratio else "low"
