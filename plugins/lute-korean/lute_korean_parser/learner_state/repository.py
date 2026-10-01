"""One consistent batched snapshot; consumers never need acquisition SQL."""
from collections import defaultdict
from hashlib import sha256
import json
from sqlalchemy import select, inspect, or_
from ..knowledge import tables as k


class LearnerEvidenceRepository:
    """Read only, with a bounded query count independent of item count."""

    def __init__(self, session):
        self.session = session

    def resolve(self, value, kind=None):
        """Resolve an identity/UUID without loading other items' evidence."""
        query = select(k.items).where(
            or_(k.items.c.id == value, k.items.c.identity == value)
        )
        if kind is not None:
            if kind not in ("lexical", "grammar", "chunk"):
                raise ValueError(f"Invalid kind: {kind}")
            query = query.where(k.items.c.kind == kind)
        rows = self.session.execute(query).mappings().all()
        if len(rows) != 1:
            raise ValueError("Item not found or ambiguous; specify kind/ID")
        return rows[0]["id"]

    def snapshot(self, kind=None, item_id=None):
        """Read a bounded batch of acquisition tables, with optional Anki provenance."""
        # Keeping each table's rows explicit preserves provenance and avoids N+1.
        # pylint: disable=too-many-locals
        if kind is not None:
            if kind not in ("lexical", "grammar", "chunk"):
                raise ValueError(f"Invalid kind: {kind}")
        query = select(k.items).order_by(k.items.c.kind, k.items.c.identity)
        if kind:
            query = query.where(k.items.c.kind == kind)
        if item_id:
            query = query.where(k.items.c.id == item_id)
        items = [dict(row) for row in self.session.execute(query).mappings()]
        ids = [i["id"] for i in items]
        dimensions = [
            dict(row)
            for row in self.session.execute(
                select(k.dimensions).where(k.dimensions.c.item_id.in_(ids))
            ).mappings()
        ]
        occurrences = [
            dict(row)
            for row in self.session.execute(
                select(k.links.c.item_id, k.occurrences)
                .join(k.occurrences, k.occurrences.c.id == k.links.c.occurrence_id)
                .where(k.links.c.item_id.in_(ids))
            ).mappings()
        ]
        evidence = [
            dict(row)
            for row in self.session.execute(
                select(k.evidence).where(k.evidence.c.item_id.in_(ids))
            ).mappings()
        ]
        source_ids = {o["source_id"] for o in occurrences}
        sources = [
            dict(row)
            for row in self.session.execute(
                select(k.sources).where(k.sources.c.id.in_(source_ids))
            ).mappings()
        ]
        reviews, revisions, cards = [], [], []
        if inspect(self.session.connection()).has_table("korean_anki_reviews"):
            from ..anki import tables as a  # pylint: disable=import-outside-toplevel

            reviews = [
                dict(row)
                for row in self.session.execute(
                    select(a.reviews).where(a.reviews.c.source_id.in_(source_ids))
                ).mappings()
            ]
            revisions = [
                dict(row)
                for row in self.session.execute(
                    select(a.revisions).where(a.revisions.c.source_id.in_(source_ids))
                ).mappings()
            ]
            cards = [
                dict(row)
                for row in self.session.execute(
                    select(
                        a.revisions.c.source_id,
                        a.cards.c.integration,
                        a.cards.c.note_id,
                        a.cards.c.card_id,
                    )
                    .join(
                        a.cards,
                        (a.cards.c.integration == a.revisions.c.integration)
                        & (a.cards.c.note_id == a.revisions.c.note_id),
                    )
                    .where(a.revisions.c.source_id.in_(source_ids))
                    .distinct()
                ).mappings()
            ]
        raw = {
            "items": items,
            "dimensions": dimensions,
            "occurrences": occurrences,
            "evidence": evidence,
            "sources": sources,
            "reviews": reviews,
            "revisions": revisions,
            "cards": cards,
        }
        canonical = {
            key: sorted(rows, key=lambda row: json.dumps(row, sort_keys=True))
            for key, rows in raw.items()
        }
        fingerprint = sha256(
            json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        evidence_input = dict(canonical)
        evidence_input.pop("dimensions")
        evidence_input["items"] = [
            {key: row[key] for key in ("id", "kind", "identity")}
            for row in canonical["items"]
        ]
        evidence_fingerprint = sha256(
            json.dumps(evidence_input, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        grouped = {
            key: defaultdict(list)
            for key in [
                "dimensions",
                "occurrences",
                "evidence",
                "reviews",
                "revisions",
                "cards",
            ]
        }
        source_items = defaultdict(set)
        for key in ["dimensions", "occurrences", "evidence"]:
            for row in raw[key]:
                grouped[key][row["item_id"]].append(row)
                if key == "occurrences":
                    source_items[row["source_id"]].add(row["item_id"])
        for key in ["reviews", "revisions", "cards"]:
            for row in raw[key]:
                for iid in source_items[row["source_id"]]:
                    grouped[key][iid].append(row)
        return {
            "items": items,
            "sources": {s["id"]: s for s in sources},
            "grouped": grouped,
            "fingerprint": evidence_fingerprint,
            "input_fingerprint": fingerprint,
        }
