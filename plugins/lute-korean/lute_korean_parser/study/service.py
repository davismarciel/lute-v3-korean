"""Explicit session lifecycle; opening/analyzing content is never study evidence."""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4
from sqlalchemy.sql.functions import count
from sqlalchemy import select, insert, update, func
from ..ci.models import CandidateContent, CandidateSegment
from ..knowledge.service import KnowledgeService, identity, encode_metadata, validate
from ..knowledge.ingestion import KnowledgeIngestionService
from ..knowledge.human import HumanEvidenceService
from ..knowledge import tables as knowledge_tables
from . import tables as t


def now():
    return datetime.now(timezone.utc)


@contextmanager
def atomic(session):
    """SAVEPOINT isolation without taking commit ownership from the caller."""
    conn = session.connection()
    if (
        conn.dialect.name == "sqlite"
        and not conn.connection.driver_connection.in_transaction
    ):
        conn.exec_driver_sql("BEGIN")
    with session.begin_nested():
        yield


class StudySessionService:
    """Stable content/segment provenance, distinct repeated sessions and exposures."""

    def __init__(self, session, parser=None):
        self.session = session
        self.knowledge = KnowledgeService(session)
        self.ingestion = KnowledgeIngestionService(session, parser=parser)

    def start(
        self,
        candidate,
        activity,
        request_key,
        transcript_read=False,
        external_reference=None,
        started_at=None,
        metadata=None,
    ):
        validate(
            activity,
            {"reading", "listening_with_transcript", "listening", "mixed"},
            "activity",
        )
        request_key = identity(request_key)
        if not candidate.segments:
            raise ValueError("Content needs at least one segment")
        if activity == "listening" and transcript_read:
            raise ValueError("Listening-only cannot claim transcript reading")
        transcript_read = activity in {"reading", "listening_with_transcript"} or bool(
            transcript_read
        )
        indices = [s.index for s in candidate.segments]
        if indices != list(range(len(indices))):
            raise ValueError("Study segments need consecutive indices")
        timestamp = started_at or now()
        if timestamp.tzinfo is None or timestamp > now():
            raise ValueError("Start time must be aware and not in the future")
        segments = json.dumps(
            [asdict(s) for s in candidate.segments], ensure_ascii=False, sort_keys=True
        )
        content_id = sha256(
            json.dumps(
                [candidate.original_hash, candidate.kind, candidate.format, segments]
            ).encode()
        ).hexdigest()
        with atomic(self.session):
            existing = (
                self.session.execute(
                    select(t.sessions).where(t.sessions.c.request_key == request_key)
                )
                .mappings()
                .first()
            )
            if existing:
                if (
                    existing["content_id"] != content_id
                    or existing["activity"] != activity
                    or bool(existing["transcript_read"]) != transcript_read
                ):
                    raise ValueError("Start key already belongs to a different session")
                return self.show(existing["id"])
            if not self.session.execute(
                select(t.contents.c.id).where(t.contents.c.id == content_id)
            ).first():
                self.session.execute(
                    insert(t.contents).values(
                        id=content_id,
                        content_hash=candidate.original_hash,
                        name=candidate.name,
                        kind=candidate.kind,
                        format=candidate.format,
                        segments=segments,
                        segment_count=len(candidate.segments),
                        created_at=now().isoformat(),
                    )
                )
            sid = str(uuid4())
            self.session.execute(
                insert(t.sessions).values(
                    id=sid,
                    content_id=content_id,
                    request_key=request_key,
                    activity=activity,
                    transcript_read=int(transcript_read),
                    status="started",
                    started_at=timestamp.isoformat(),
                    external_reference=external_reference,
                    metadata=encode_metadata(metadata),
                )
            )
        return self.show(sid)

    def show(self, session_id):
        row = (
            self.session.execute(
                select(
                    t.sessions,
                    t.contents.c.name,
                    t.contents.c.kind,
                    t.contents.c.format,
                    t.contents.c.content_hash,
                    t.contents.c.segments,
                )
                .join(t.contents, t.contents.c.id == t.sessions.c.content_id)
                .where(t.sessions.c.id == session_id)
            )
            .mappings()
            .first()
        )
        if row is None:
            raise KeyError("Study session not found")
        result = dict(row)
        result["segments"] = json.loads(result["segments"])
        result["metadata"] = json.loads(result["metadata"])
        result["consumed"] = list(
            self.session.execute(
                select(t.consumed)
                .where(t.consumed.c.session_id == session_id)
                .order_by(t.consumed.c.segment_index)
            ).mappings()
        )
        result["consumed"] = [dict(r) for r in result["consumed"]]
        result["observation_ids"] = list(
            self.session.execute(
                select(t.observations.c.evidence_id).where(
                    t.observations.c.session_id == session_id
                )
            ).scalars()
        )
        result["exposure_count"] = self.session.execute(
            select(count())
            .select_from(knowledge_tables.evidence)
            .where(
                knowledge_tables.evidence.c.event_key.like("study:" + session_id + ":%")
            )
        ).scalar_one()
        events = self.session.execute(
            select(knowledge_tables.evidence, knowledge_tables.items.c.identity)
            .join(
                t.observations,
                t.observations.c.evidence_id == knowledge_tables.evidence.c.id,
            )
            .join(
                knowledge_tables.items,
                knowledge_tables.items.c.id == knowledge_tables.evidence.c.item_id,
            )
            .where(t.observations.c.session_id == session_id)
            .order_by(knowledge_tables.evidence.c.occurred_at.desc())
            .limit(20)
        ).mappings()
        result["recent_observations"] = [
            dict(event, metadata=json.loads(event["metadata"])) for event in events
        ]
        return result

    def list(self, limit=100):
        """One aggregate history query, never one lookup per session/item."""
        consumed = (
            select(
                t.consumed.c.session_id,
                count().label("consumed_segments"),
                func.min(t.consumed.c.segment_index).label("first_segment"),
                func.max(t.consumed.c.segment_index).label("last_segment"),
            )
            .group_by(t.consumed.c.session_id)
            .subquery()
        )
        query = (
            select(
                t.sessions,
                t.contents.c.name,
                t.contents.c.kind,
                t.contents.c.segment_count,
                consumed.c.consumed_segments,
                consumed.c.first_segment,
                consumed.c.last_segment,
            )
            .join(t.contents, t.contents.c.id == t.sessions.c.content_id)
            .outerjoin(consumed, consumed.c.session_id == t.sessions.c.id)
            .order_by(t.sessions.c.started_at.desc())
            .limit(limit)
        )
        result = [dict(row) for row in self.session.execute(query).mappings()]
        for row in result:
            row["consumed_segments"] = row["consumed_segments"] or 0
            row["elapsed_seconds"] = (
                (
                    datetime.fromisoformat(row["completed_at"])
                    - datetime.fromisoformat(row["started_at"])
                ).total_seconds()
                if row["completed_at"]
                else None
            )
        return result

    def candidate(self, session_id):
        row = self.show(session_id)
        return CandidateContent(
            row["name"],
            row["format"],
            tuple(CandidateSegment(**s) for s in row["segments"]),
            row["content_hash"],
            row["kind"],
        )

    def consume(self, session_id, start=0, end=None, completed=True, occurred_at=None):
        """Inclusive segment range; exposure only for explicitly read Korean text."""
        row = self.show(session_id)
        end = len(row["segments"]) - 1 if end is None else end
        if (
            isinstance(start, bool)
            or isinstance(end, bool)
            or not isinstance(start, int)
            or not isinstance(end, int)
            or not 0 <= start <= end < len(row["segments"])
        ):
            raise ValueError("Choose a valid consumed segment range")
        timestamp = occurred_at or now()
        if (
            timestamp.tzinfo is None
            or timestamp > now()
            or timestamp < datetime.fromisoformat(row["started_at"])
        ):
            raise ValueError(
                "Consumption time must be aware, after start and not future"
            )
        already = {r["segment_index"] for r in row["consumed"]}
        wanted = set(range(start, end + 1))
        if row["status"] == "completed":
            if not wanted <= already:
                raise ValueError(
                    "Completed session is immutable; start a new study session"
                )
            return self.show(session_id)
        source_type = (
            "tprs"
            if row["kind"] == "tprs"
            else "podcast"
            if row["kind"] == "podcast"
            else "manual"
        )
        with atomic(self.session):
            for index in sorted(wanted - already):
                segment = row["segments"][index]
                text = segment["text"]
                policy_hash = sha256(
                    self.ingestion.processing_version.encode()
                ).hexdigest()
                reference = (
                    f"study-content:{row['content_id']}:segment:{index}:{policy_hash}"
                )
                if row["transcript_read"]:
                    ingested = self.ingestion.ingest(
                        text, reference, source_type=source_type, record_exposure=False
                    )
                    source_id = ingested["source_id"]
                    links = self.session.execute(
                        select(knowledge_tables.links)
                        .join(
                            knowledge_tables.occurrences,
                            knowledge_tables.occurrences.c.id
                            == knowledge_tables.links.c.occurrence_id,
                        )
                        .where(knowledge_tables.occurrences.c.source_id == source_id)
                    ).mappings()
                    for link in links:
                        self.knowledge.record_evidence(
                            link["item_id"],
                            "exposure",
                            dimension="reading",
                            occurrence_id=link["occurrence_id"],
                            occurred_at=timestamp,
                            event_key=f"study:{session_id}:{index}:{link['occurrence_id']}:{link['item_id']}",
                            metadata={
                                "study_session_id": session_id,
                                "segment_index": index,
                                "activity": row["activity"],
                                "directness": "indirect",
                                "scope": "context",
                                "association_basis": "verified_content",
                                "observation_basis": "explicit_study_consumption",
                            },
                        )
                else:
                    source_id = self.knowledge.ensure_source(
                        source_type, reference, text
                    )["id"]
                self.session.execute(
                    insert(t.consumed).values(
                        session_id=session_id,
                        segment_index=index,
                        source_id=source_id,
                        consumed_at=timestamp.isoformat(),
                    )
                )
            status = "completed" if completed else "partial"
            self.session.execute(
                update(t.sessions)
                .where(t.sessions.c.id == session_id)
                .values(
                    status=status,
                    completed_at=timestamp.isoformat() if completed else None,
                )
            )
        return self.show(session_id)

    def record_observation(self, session_id, document):
        """Associate explicit item-scoped human events, never mass recognition."""
        self.show(session_id)
        with atomic(self.session):
            result = HumanEvidenceService(self.session).apply(document)
            for eid in result["event_ids"]:
                if not self.session.execute(
                    select(t.observations).where(
                        t.observations.c.session_id == session_id,
                        t.observations.c.evidence_id == eid,
                    )
                ).first():
                    self.session.execute(
                        insert(t.observations).values(
                            session_id=session_id, evidence_id=eid
                        )
                    )
        return result
