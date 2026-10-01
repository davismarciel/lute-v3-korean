"""Factual human observations: validate/preview first, explicitly apply second."""
import hashlib
import json
from datetime import datetime, timezone
from sqlalchemy import select
from .service import KnowledgeService, DIMENSIONS, validate, identity, encode_metadata
from . import tables as t


class HumanEvidenceService:
    """Caller owns commit/rollback; no manual assessment is ever applied."""

    def __init__(self, session):
        self.session = session
        self.knowledge = KnowledgeService(session)

    def preview(self, document):
        """Require actual observation time/recorder, never infer events from chats."""
        events = (
            document.get("events", [document])
            if isinstance(document, dict)
            else document
        )
        if not isinstance(events, list):
            raise ValueError("Expected an event object or events list")
        result = []
        items = self.knowledge.list_items()
        for event in events:
            if not isinstance(event, dict):
                raise ValueError("Each event must be an object")
            required = {
                "item",
                "dimension",
                "event_type",
                "directness",
                "source_reference",
                "context",
                "occurred_at",
                "recorded_by",
            }
            if not required <= event.keys():
                raise ValueError(
                    "Missing factual fields: "
                    + ",".join(sorted(required - event.keys()))
                )
            allowed = required | {"kind", "scope", "source_type", "notes", "event_key"}
            if event.keys() - allowed:
                raise ValueError("Unsupported human evidence fields")
            validate(event["dimension"], DIMENSIONS, "dimension")
            validate(
                event["event_type"],
                {"recognized", "produced", "missed", "manual_confirmation"},
                "human evidence type",
            )
            validate(event["directness"], {"direct", "indirect"}, "directness")
            if event["event_type"] == "produced" and event["dimension"] != "production":
                raise ValueError("Produced evidence requires production dimension")
            scope = event.get(
                "scope", "item" if event["directness"] == "direct" else "context"
            )
            validate(scope, {"item", "context"}, "scope")
            if event["directness"] == "direct" and scope != "item":
                raise ValueError("Direct evidence requires item scope")
            candidates = [
                i
                for i in items
                if i["identity"] == identity(event["item"])
                and (event.get("kind") is None or event["kind"] == i["kind"])
            ]
            if len(candidates) != 1:
                raise ValueError("Item must exist and be unambiguous; specify kind")
            timestamp = datetime.fromisoformat(event["occurred_at"])
            if (
                timestamp.tzinfo is None
                or timestamp.utcoffset() is None
                or timestamp > datetime.now(timezone.utc)
            ):
                raise ValueError(
                    "Observation timestamp must be aware and not in the future"
                )
            source_type = event.get("source_type", "conversation")
            validate(source_type, {"conversation", "manual", "tprs"}, "human source")
            notes = event.get("notes", "")
            if not isinstance(notes, str):
                raise ValueError("Notes must be text")
            values = dict(
                item_id=candidates[0]["id"],
                evidence_type=event["event_type"],
                dimension=event["dimension"],
                source_type=source_type,
                source_reference=identity(event["source_reference"]),
                context=identity(event["context"]),
                occurred_at=timestamp.astimezone(timezone.utc).isoformat(),
                metadata={
                    "directness": event["directness"],
                    "scope": scope,
                    "association_basis": "explicit_item",
                    "recorded_by": identity(event["recorded_by"]),
                    "notes": notes,
                    "human_evidence_version": "ko.human.v1",
                },
            )
            encode_metadata(values["metadata"])
            digest = hashlib.sha256(
                json.dumps(values, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
            values["event_key"] = identity(event.get("event_key", "human-v1:" + digest))
            result.append(values)
        return {"events": result, "writes": 0}

    def apply(self, document):
        """Atomic validated import, deduplicated by stable factual event identity."""
        events = self.preview(document)["events"]
        connection = self.session.connection()
        if (
            connection.dialect.name == "sqlite"
            and not connection.connection.driver_connection.in_transaction
        ):
            connection.exec_driver_sql("BEGIN")
        imported = []
        created = 0
        with self.session.begin_nested():
            for values in events:
                existing = self.session.execute(
                    select(t.evidence.c.id).where(
                        t.evidence.c.event_key == values["event_key"]
                    )
                ).first()
                payload = dict(values)
                payload["occurred_at"] = datetime.fromisoformat(payload["occurred_at"])
                imported.append(self.knowledge.record_evidence(**payload)["id"])
                created += existing is None
        return {
            "event_ids": imported,
            "created": created,
            "skipped": len(events) - created,
        }
