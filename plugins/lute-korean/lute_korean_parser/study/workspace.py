"""UI/CLI orchestration consumes existing policies and services without duplicating them."""
from collections import Counter
from dataclasses import dataclass
import json
from sqlalchemy.sql.functions import count
from sqlalchemy import select, func
from ..ci.snapshot import CILearnerSnapshot
from ..ci.analyzer import CIContentAnalyzer
from ..ci.export import compact_report
from ..knowledge.service import KnowledgeService
from ..knowledge.human import HumanEvidenceService
from ..knowledge.representation import KnowledgeRepresentationService
from ..knowledge import tables as k
from ..anki.config import AnkiConfig
from ..anki.adapter import AnkiConnectSourceAdapter
from ..anki.sync import AnkiSyncService
from ..anki import tables as a
from .service import StudySessionService


@dataclass(frozen=True)
class StudyExportLimits:
    """Presentation bounds are distinct from validated CI classification parameters."""

    compact_item_limit: int = 20
    compact_cluster_limit: int = 10
    compact_text_limit: int = 160


class KoreanStudyWorkspace:
    """Fresh batched snapshots per request; no automatic sync or status application."""

    def __init__(self, session):
        self.session = session

    def snapshot(self):
        return CILearnerSnapshot.load(self.session)

    def overview(self, snapshot=None):
        snapshot = snapshot or self.snapshot()
        counts = {
            kind: {
                dimension: dict(
                    Counter(
                        i["suggested_state"][dimension]["status"]
                        for (k, _), i in snapshot.items.items()
                        if k == kind
                    )
                )
                for dimension in ["reading", "listening", "production"]
            }
            for kind in ["lexical", "grammar", "chunk"]
        }
        return {
            "counts": counts,
            "snapshot": snapshot.provenance,
            "items": list(snapshot.items.values()),
            "dimension_available": {
                d: any(
                    i["suggested_state"][d]["status"] not in {"unknown", "future"}
                    or i["manual_state"].get(d) not in {None, "future"}
                    for i in snapshot.items.values()
                )
                for d in ["reading", "listening", "production"]
            },
        }

    def item(self, item_id):
        snapshot = self.snapshot()
        item = next((i for i in snapshot.items.values() if i["id"] == item_id), None)
        if item is None:
            raise KeyError("Knowledge item not found")
        knowledge = KnowledgeService(self.session)
        occurrences = knowledge.list_occurrences(item_id)
        recent = knowledge.list_evidence(item_id)[-20:][::-1]
        relations = [
            r
            for r in KnowledgeRepresentationService(self.session).list_relations()
            if item_id in {r["source_item_id"], r["target_item_id"]}
        ]
        names = {i["id"]: i["identity"] for i in snapshot.items.values()}
        return {
            "item": item,
            "role": snapshot.roles.get(item_id),
            "occurrences": occurrences[-30:],
            "recent_evidence": recent,
            "relations": [
                dict(
                    r,
                    source=names.get(r["source_item_id"]),
                    target=names.get(r["target_item_id"]),
                )
                for r in relations
            ],
        }

    def assess(self, item_id, dimension, status):
        KnowledgeService(self.session).set_status(item_id, status, dimension)

    def observe(self, document, study_session_id=None):
        if study_session_id:
            return StudySessionService(self.session).record_observation(
                study_session_id, document
            )
        return HumanEvidenceService(self.session).apply(document)

    def analyze(self, candidate, snapshot=None):
        return CIContentAnalyzer(self.session, snapshot=snapshot).analyze(candidate)

    def anki(self, config=None, adapter=None):
        config = config or AnkiConfig("local-anki", {})
        return AnkiSyncService(
            self.session, adapter or AnkiConnectSourceAdapter(config), config
        )

    def anki_status(self, config=None):
        config = config or AnkiConfig("local-anki", {})
        status = self.anki(config).status()
        status["counts"] = {
            name: self.session.execute(
                select(count())
                .select_from(table)
                .where(table.c.integration == config.source_identity)
            ).scalar_one()
            for name, table in [
                ("notes", a.notes),
                ("cards", a.cards),
                ("reviews", a.reviews),
            ]
        }
        return status

    def export_learner(self, size="compact"):
        """Separate manual/suggested/observed facts; never export raw card review logs."""
        if size not in {"compact", "default", "detailed"}:
            raise ValueError("Invalid export size")
        snapshot = self.snapshot()
        overview = self.overview(snapshot)
        limit = {"compact": 20, "default": 60, "detailed": len(snapshot.items)}[size]
        items = sorted(
            snapshot.items.values(),
            key=lambda i: (-i["evidence"]["occurrences"], i["identity"]),
        )

        def brief(i):
            return {
                "identity": i["identity"],
                "kind": i["type"],
                "manual_state": i["manual_state"],
                "suggested_state": {
                    d: {"status": s["status"], "confidence": s["confidence"]}
                    for d, s in i["suggested_state"].items()
                },
                "observed_summary": {
                    key: i["evidence"][key]
                    for key in [
                        "occurrences",
                        "contexts",
                        "source_types",
                        "anki_reviews",
                    ]
                },
            }

        query = (
            select(k.evidence, k.items.c.identity, k.items.c.kind)
            .join(k.items, k.items.c.id == k.evidence.c.item_id)
            .where(k.evidence.c.evidence_type != "exposure")
            .order_by(k.evidence.c.occurred_at.desc())
            .limit(100)
        )
        direct = []
        for row in self.session.execute(query).mappings():
            metadata = json.loads(row["metadata"])
            if metadata.get("directness") == "direct":
                direct.append(
                    {
                        "item": row["identity"],
                        "kind": row["kind"],
                        "dimension": row["dimension"],
                        "event_type": row["evidence_type"],
                        "context": (row["context"] or "")[:400],
                        "occurred_at": row["occurred_at"],
                        "source_reference": row["source_reference"],
                        "recorded_by": metadata.get("recorded_by"),
                    }
                )
            if len(direct) == (10 if size == "compact" else 30):
                break
        return {
            "schema_version": 1,
            "language": "ko",
            "export_kind": "teacher_learner_context",
            "size": size,
            "snapshot": snapshot.provenance,
            "summary": overview["counts"],
            "items": [brief(i) for i in items[:limit]],
            "grammar": [brief(i) for i in items if i["type"] == "grammar"],
            "recent_direct_evidence": direct,
            "recent_study_sessions": [
                {
                    key: row[key]
                    for key in [
                        "id",
                        "name",
                        "kind",
                        "activity",
                        "status",
                        "started_at",
                        "completed_at",
                    ]
                }
                for row in StudySessionService(self.session).list(
                    10 if size == "compact" else 30
                )
            ],
            "omitted_items": max(0, len(items) - limit),
            "limitations": [
                "Manual states are authoritative; suggestions are heuristic and distinct from observed events",
                "Anki reviews are indirect sentence-scoped, historically uncertain and modality unspecified",
                "No comprehension or listening ability follows from transcript fit or exposure",
                "Only five grammar detectors; lemma polysemy and incomplete compound/proper-name modeling",
            ],
        }

    def export_content(self, report, size="compact", include_korean=False):
        if size not in {"compact", "default", "detailed"}:
            raise ValueError("Invalid export size")
        if size == "detailed":
            result = dict(report)
        else:
            limits = (
                StudyExportLimits()
                if size == "compact"
                else StudyExportLimits(60, 20, 320)
            )
            result = compact_report(report, limits)
        if include_korean:
            result = dict(
                result,
                korean_segments=[
                    {
                        "index": s["index"],
                        "timestamp": s["timestamp"],
                        "text": s["text"],
                    }
                    for s in report["segments"]
                ],
            )
        return dict(
            result,
            export_kind="teacher_content_context",
            export_size=size,
            content_consumption_not_implied=True,
        )


def markdown_export(document):
    """Readable structured teacher context, preserving category distinctions."""
    return (
        "# Korean study context\n\nManual, suggested and observed evidence remain distinct.\n\n```json\n"
        + json.dumps(document, ensure_ascii=False, indent=2)
        + "\n```\n"
    )
