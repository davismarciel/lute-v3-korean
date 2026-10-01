"""Public acquisition API. The caller owns the session and commits explicitly."""
import hashlib
import json
import unicodedata
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.sqlite import insert
from . import tables as t

KINDS = {"lexical", "grammar", "chunk"}
STATUSES = {"unknown", "presented", "practicing", "consolidated", "future"}
DIMENSIONS = {"reading", "listening", "production"}
SOURCE_TYPES = {"lute_text", "tprs", "anki", "conversation", "podcast", "manual"}
EVIDENCE_TYPES = {"exposure", "recognized", "produced", "missed", "manual_confirmation"}


def validate(value, allowed, label):
    """Validate a controlled domain value before writing."""
    if value not in allowed:
        raise ValueError(f"Invalid {label}: {value}")
    return value


def identity(value):
    """Normalize identity keys without changing source surfaces."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Identity/reference must be nonempty text")
    return unicodedata.normalize("NFC", value.strip())


def encode_metadata(value):
    """Encode a small JSON object, rejecting oversized model dumps."""
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError("Metadata must be an object")
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    if len(encoded.encode("utf8")) > 8192:
        raise ValueError("Metadata exceeds the 8 KiB limit")
    return encoded


class KnowledgeService:  # pylint: disable=too-many-public-methods
    """Item identity, status, occurrences, evidence and export without consumer SQL."""

    def __init__(self, session):
        self.session = session

    def _one(self, table, *conditions):
        row = self.session.execute(select(table).where(*conditions)).mappings().first()
        return dict(row) if row else None

    def _ensure(self, table, keys, values):
        self.session.execute(
            insert(table)
            .values(**values)
            .on_conflict_do_nothing(index_elements=list(keys))
        )
        return self._one(table, *(table.c[k] == values[k] for k in keys))

    def get_item(self, item_id):
        """Get an item by stable ID or raise KeyError."""
        item = self._one(t.items, t.items.c.id == item_id)
        if item is None:
            raise KeyError(item_id)
        return item

    def find_item(self, kind, value):
        """Find an item by its kind and canonical identity."""
        validate(kind, KINDS, "kind")
        return self._one(
            t.items, t.items.c.kind == kind, t.items.c.identity == identity(value)
        )

    def get_or_create(self, kind, value):
        """Reuse the unique kind/identity pair, initially unknown."""
        validate(kind, KINDS, "kind")
        return self._ensure(
            t.items,
            ("kind", "identity"),
            {
                "id": str(uuid4()),
                "kind": kind,
                "identity": identity(value),
                "status": "unknown",
            },
        )

    def get_lexical(self, lemma):
        """Find a lexical concept by lemma."""
        return self.find_item("lexical", lemma)

    def get_or_create_lexical(self, lemma):
        """Reuse or create a lexical concept by lemma."""
        return self.get_or_create("lexical", lemma)

    def get_or_create_grammar(self, pattern):
        """Reuse or create an explicitly selected grammar pattern."""
        return self.get_or_create("grammar", pattern)

    def get_or_create_chunk(self, text):
        """Reuse or create a manually selected chunk."""
        return self.get_or_create("chunk", text)

    def find_chunk(self, text):
        """Find a chunk without creating it."""
        return self.find_item("chunk", text)

    def list_items(self, kind=None):
        """List items in stable kind and identity order."""
        query = select(t.items).order_by(t.items.c.kind, t.items.c.identity)
        if kind is not None:
            validate(kind, KINDS, "kind")
            query = query.where(t.items.c.kind == kind)
        return [dict(r) for r in self.session.execute(query).mappings()]

    def list_chunks(self):
        """List deliberately tracked chunks."""
        return self.list_items("chunk")

    def set_status(self, item_id, status, dimension=None):
        """Set a manual overall or dimensional status; never infer it from evidence."""
        self.get_item(item_id)
        validate(status, STATUSES, "status")
        if dimension is None:
            self.session.execute(
                update(t.items).where(t.items.c.id == item_id).values(status=status)
            )
        else:
            validate(dimension, DIMENSIONS, "dimension")
            stmt = insert(t.dimensions).values(
                item_id=item_id, dimension=dimension, status=status
            )
            self.session.execute(
                stmt.on_conflict_do_update(
                    index_elements=["item_id", "dimension"], set_={"status": status}
                )
            )
        return self.get_item(item_id)

    def update_chunk(self, item_id, text=None, status=None):
        """Edit a chunk while preserving its stable ID."""
        if self.get_item(item_id)["kind"] != "chunk":
            raise ValueError("Only chunks can be edited")
        if status is not None:
            validate(status, STATUSES, "status")
        if text is not None:
            self.session.execute(
                update(t.items)
                .where(t.items.c.id == item_id)
                .values(identity=identity(text))
            )
        if status is not None:
            self.set_status(item_id, status)
        return self.get_item(item_id)

    def delete_chunk(self, item_id):
        """Remove a chunk and its associations, preserving constituent concepts."""
        if self.get_item(item_id)["kind"] != "chunk":
            raise ValueError("Only chunks can be deleted")
        # Explicit cleanup also works with Lute connections that do not enable FKs.
        for table in (t.evidence, t.dimensions, t.links):
            self.session.execute(delete(table).where(table.c.item_id == item_id))
        self.session.execute(delete(t.items).where(t.items.c.id == item_id))

    def ensure_source(self, source_type, reference, content, lute_text_id=None):
        """Reuse an immutable source revision or reject changed content."""
        validate(source_type, SOURCE_TYPES, "source type")
        reference = identity(reference)
        if not isinstance(content, str):
            raise ValueError("Source content must be text")
        values = {
            "id": str(uuid4()),
            "source_type": source_type,
            "reference": reference,
            "content_hash": hashlib.sha256(content.encode("utf8")).hexdigest(),
            "content": content,
            "lute_text_id": lute_text_id,
        }
        existing = self._one(
            t.sources,
            t.sources.c.source_type == source_type,
            t.sources.c.reference == reference,
        )
        if existing and (
            existing["content_hash"] != values["content_hash"]
            or existing["lute_text_id"] != lute_text_id
        ):
            raise ValueError("Source changed: use a new revision reference")
        source = self._ensure(t.sources, ("source_type", "reference"), values)
        if (
            source["content_hash"] != values["content_hash"]
            or source["lute_text_id"] != lute_text_id
        ):
            raise ValueError("Source changed: use a new revision reference")
        return source

    def ensure_occurrence(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, source_id, start, end, context_start=None, context_end=None, metadata=None
    ):
        """Retain a source span, including foreign units with no knowledge item."""
        source = self._one(t.sources, t.sources.c.id == source_id)
        if source is None:
            raise KeyError(source_id)
        if (
            not isinstance(start, int)
            or not isinstance(end, int)
            or not 0 <= start < end <= len(source["content"])
        ):
            raise ValueError("Invalid occurrence offsets")
        context_start = start if context_start is None else context_start
        context_end = end if context_end is None else context_end
        if (
            not 0
            <= context_start
            <= start
            < end
            <= context_end
            <= len(source["content"])
        ):
            raise ValueError("Invalid context offsets")
        values = {
            "id": str(uuid4()),
            "source_id": source_id,
            "start": start,
            "end": end,
            "surface": source["content"][start:end],
            "context_start": context_start,
            "context_end": context_end,
            "metadata": encode_metadata(metadata),
        }
        occurrence = self._ensure(t.occurrences, ("source_id", "start", "end"), values)
        return occurrence

    def associate_occurrence(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        item_id,
        source_id,
        start,
        end,
        context_start=None,
        context_end=None,
        metadata=None,
    ):
        """Attach a retained span to an item without changing its surface."""
        self.get_item(item_id)
        occurrence = self.ensure_occurrence(
            source_id, start, end, context_start, context_end, metadata
        )
        self._ensure(
            t.links,
            ("occurrence_id", "item_id"),
            {"occurrence_id": occurrence["id"], "item_id": item_id},
        )
        return occurrence

    def list_source_occurrences(self, source_id):
        """Inspect retained morphology, including untracked foreign/numeric spans."""
        source = self._one(t.sources, t.sources.c.id == source_id)
        if source is None:
            raise KeyError(source_id)
        query = (
            select(t.occurrences)
            .where(t.occurrences.c.source_id == source_id)
            .order_by(t.occurrences.c.start, t.occurrences.c.end)
        )
        result = []
        for row in self.session.execute(query).mappings():
            entry = dict(row)
            entry["metadata"] = json.loads(entry["metadata"])
            entry["context"] = source["content"][
                entry["context_start"] : entry["context_end"]
            ]
            result.append(entry)
        return result

    def list_occurrences(self, item_id):
        """Return source spans and contexts for an item without raw model objects."""
        self.get_item(item_id)
        query = (
            select(
                t.occurrences,
                t.sources.c.source_type,
                t.sources.c.reference,
                t.sources.c.content,
            )
            .join(t.links, t.links.c.occurrence_id == t.occurrences.c.id)
            .join(t.sources, t.sources.c.id == t.occurrences.c.source_id)
            .where(t.links.c.item_id == item_id)
            .order_by(
                t.sources.c.source_type,
                t.sources.c.reference,
                t.occurrences.c.start,
                t.occurrences.c.end,
            )
        )
        result = []
        for row in self.session.execute(query).mappings():
            entry = dict(row)
            content = entry.pop("content")
            entry["context"] = content[entry["context_start"] : entry["context_end"]]
            entry["metadata"] = json.loads(entry["metadata"])
            result.append(entry)
        return result

    def list_surface_forms(self, item_id):
        """List distinct observed surfaces for an item."""
        return sorted({o["surface"] for o in self.list_occurrences(item_id)})

    def record_evidence(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        self,
        item_id,
        evidence_type,
        dimension="reading",
        source_type=None,
        source_reference=None,
        occurrence_id=None,
        surface=None,
        context=None,
        occurred_at=None,
        metadata=None,
        event_key=None,
    ):
        """Record a skill-specific event, optionally deduplicated by event key."""
        self.get_item(item_id)
        validate(evidence_type, EVIDENCE_TYPES, "evidence type")
        validate(dimension, DIMENSIONS, "dimension")
        if occurrence_id is not None:
            occurrence = self._one(t.occurrences, t.occurrences.c.id == occurrence_id)
            link = self._one(
                t.links,
                t.links.c.occurrence_id == occurrence_id,
                t.links.c.item_id == item_id,
            )
            if occurrence is None or link is None:
                raise ValueError("Occurrence must be associated with this item")
            source = self._one(t.sources, t.sources.c.id == occurrence["source_id"])
            if source_type is not None and source_type != source["source_type"]:
                raise ValueError("Evidence source does not match occurrence")
            if source_reference is not None and source_reference != source["reference"]:
                raise ValueError("Evidence reference does not match occurrence")
            source_type, source_reference = source["source_type"], source["reference"]
            # Occurrence owns the surface/context; do not duplicate source text.
            if surface is not None or context is not None:
                raise ValueError(
                    "Occurrence evidence derives surface/context from the occurrence"
                )
        source_type = source_type or "manual"
        source_reference = identity(source_reference or "manual")
        validate(source_type, SOURCE_TYPES, "source type")
        timestamp = datetime.now(timezone.utc) if occurred_at is None else occurred_at
        if (
            not isinstance(timestamp, datetime)
            or timestamp.tzinfo is None
            or timestamp.utcoffset() is None
        ):
            raise ValueError("occurred_at must be a timezone-aware datetime")
        values = {
            "id": str(uuid4()),
            "item_id": item_id,
            "occurrence_id": occurrence_id,
            "evidence_type": evidence_type,
            "source_type": source_type,
            "source_reference": source_reference,
            "dimension": dimension,
            "surface": surface,
            "context": context,
            "occurred_at": timestamp.astimezone(timezone.utc).isoformat(),
            "metadata": encode_metadata(metadata),
            "event_key": identity(event_key) if event_key else None,
        }
        if event_key:
            existing = self._one(
                t.evidence, t.evidence.c.event_key == values["event_key"]
            )
            if existing:
                comparable = set(values) - {"id", "occurred_at"}
                if occurred_at is not None:
                    comparable.add("occurred_at")
                if any(existing[k] != values[k] for k in comparable):
                    raise ValueError("Event key already belongs to different evidence")
                return existing
            persisted = self._ensure(t.evidence, ("event_key",), values)
            comparable = set(values) - {"id", "occurred_at"}
            if occurred_at is not None:
                comparable.add("occurred_at")
            if any(persisted[k] != values[k] for k in comparable):
                raise ValueError("Event key already belongs to different evidence")
            return persisted
        self.session.execute(insert(t.evidence).values(**values))
        return values

    def list_evidence(self, item_id):
        """Return events with surfaces and contexts derived from their occurrences."""
        self.get_item(item_id)
        result = []
        occurrences = {o["id"]: o for o in self.list_occurrences(item_id)}
        query = (
            select(t.evidence)
            .where(t.evidence.c.item_id == item_id)
            .order_by(t.evidence.c.occurred_at, t.evidence.c.id)
        )
        for row in self.session.execute(query).mappings():
            entry = dict(row)
            entry["metadata"] = json.loads(entry["metadata"])
            occurrence = occurrences.get(entry["occurrence_id"])
            if occurrence:
                entry["surface"], entry["context"] = (
                    occurrence["surface"],
                    occurrence["context"],
                )
            result.append(entry)
        return result

    def export(
        self,
        include_anki=False,
        review_details=False,
        include_learner_state=False,
        learner_policy=None,
        as_of=None,
    ):  # pylint: disable=too-many-locals,too-many-arguments,too-many-positional-arguments
        """Stable public JSON structure with batched summaries, no raw database blobs."""
        # Optional integrations remain deferred so default export is independent.
        # pylint: disable=import-outside-toplevel
        if review_details and not include_anki:
            raise ValueError("Review details require include_anki")
        learner = None
        if not include_learner_state and (
            learner_policy is not None or as_of is not None
        ):
            raise ValueError("Learner policy/as_of require include_learner_state")
        if include_learner_state:
            from ..learner_state.engine import (
                LearnerStateEngine,
            )  # pylint: disable=import-outside-toplevel

            learner = LearnerStateEngine(self.session, learner_policy).export(
                as_of=as_of
            )
        anki = {}
        if include_anki:
            # Optional integration modules are loaded only when requested.
            from ..anki.repository import (
                summaries,
            )  # pylint: disable=import-outside-toplevel

            anki = summaries(self.session)
        result = {
            "schema_version": 1,
            "language": "ko",
            "lexical": [],
            "grammar": [],
            "chunks": [],
        }
        learner_items = {i["id"]: i for i in learner["items"]} if learner else {}
        if learner:
            result["learner_state"] = {
                key: value for key, value in learner.items() if key != "items"
            }
        surfaces, counts, skills, dimension_status = {}, {}, {}, {}
        query = select(t.links.c.item_id, t.occurrences.c.surface).join(
            t.occurrences, t.occurrences.c.id == t.links.c.occurrence_id
        )
        for item_id, surface in self.session.execute(query):
            surfaces.setdefault(item_id, set()).add(surface)
        for item_id, evidence_type, dimension in self.session.execute(
            select(
                t.evidence.c.item_id, t.evidence.c.evidence_type, t.evidence.c.dimension
            )
        ):
            counter = counts.setdefault(item_id, {})
            counter[evidence_type] = counter.get(evidence_type, 0) + 1
            counter = skills.setdefault(item_id, {})
            counter[dimension] = counter.get(dimension, 0) + 1
        for item_id, dimension, status in self.session.execute(select(t.dimensions)):
            dimension_status.setdefault(item_id, {})[dimension] = status
        for item in self.list_items():
            item_id = item["id"]
            summary = counts.get(item_id, {})
            entry = {
                "id": item_id,
                "type": item["kind"],
                "status": item["status"],
                "surfaces": sorted(surfaces.get(item_id, set())),
                "evidence_count": sum(summary.values()),
                "evidence_summary": dict(sorted(summary.items())),
                "dimensions": {
                    d: {
                        "status": dimension_status.get(item_id, {}).get(d),
                        "evidence_count": skills.get(item_id, {}).get(d, 0),
                    }
                    for d in sorted(DIMENSIONS)
                },
            }
            key = {"lexical": "lemma", "grammar": "pattern", "chunk": "text"}[
                item["kind"]
            ]
            entry[key] = item["identity"]
            if item_id in learner_items:
                state = learner_items[item_id]
                entry.update(
                    manual_state=state["manual_state"],
                    suggested_state=state["suggested_state"],
                    suggested_overall=state["suggested_overall"],
                    learner_evidence=state["evidence"],
                    comparison=state["comparison"],
                )
            if include_anki:
                entry["anki"] = anki.get(
                    item_id,
                    {
                        "notes": 0,
                        "cards": 0,
                        "reviews": 0,
                        "again": 0,
                        "hard": 0,
                        "good": 0,
                        "easy": 0,
                        "other": 0,
                        "last_review": None,
                        "directness": "indirect",
                        "scope": "note_content",
                    },
                )
                if review_details:
                    entry["anki_reviews"] = self.list_anki_reviews(item_id)
            result[{"chunk": "chunks"}.get(item["kind"], item["kind"])].append(entry)
        return result

    def list_anki_reviews(self, item_id):
        """Return canonical indirect events related through their source occurrences."""
        self.get_item(item_id)
        from ..anki.repository import (
            item_reviews,
        )  # pylint: disable=import-outside-toplevel

        return item_reviews(self.session, item_id)

    def anki_summary(self, item_id):
        """Informational note/card/review counts, independent of manual status."""
        self.get_item(item_id)
        from ..anki.repository import (
            summaries,
        )  # pylint: disable=import-outside-toplevel

        return summaries(self.session).get(
            item_id,
            {
                "notes": 0,
                "cards": 0,
                "reviews": 0,
                "again": 0,
                "hard": 0,
                "good": 0,
                "easy": 0,
                "other": 0,
                "last_review": None,
                "directness": "indirect",
                "scope": "note_content",
            },
        )
