"""Explicit roles and span-scoped overlap, without pedagogical weighting."""
import json
from sqlalchemy import select, update, inspect
from . import tables as t
from .service import KnowledgeService, encode_metadata, validate


class KnowledgeRepresentationService:
    """Keep relationships distinct from evidence, identity and manual status."""

    def __init__(self, session):
        self.session = session
        self.knowledge = KnowledgeService(session)

    def available(self):
        """Old unmigrated clients can continue reading their existing knowledge."""
        return inspect(self.session.connection()).has_table(t.roles.name)

    def set_role(self, item_id, role, origin="manual", metadata=None):
        """An automatic annotation never overwrites an explicit override."""
        item = self.knowledge.get_item(item_id)
        if item["kind"] != "lexical":
            raise ValueError("Lexical roles apply only to lexical items")
        validate(role, {"general", "proper_noun", "foreign_name", "unknown"}, "role")
        validate(origin, {"manual", "kiwi"}, "role origin")
        existing = self.knowledge._one(t.roles, t.roles.c.item_id == item_id)
        if (
            existing
            and origin != "manual"
            and (existing["origin"] == "manual" or existing["role"] == "proper_noun")
        ):
            return existing
        values = dict(
            item_id=item_id,
            role=role,
            origin=origin,
            metadata=encode_metadata(metadata),
        )
        if existing:
            self.session.execute(
                update(t.roles).where(t.roles.c.item_id == item_id).values(**values)
            )
            return values
        return self.knowledge._ensure(t.roles, ("item_id",), values)

    def relate(
        self,
        source_item_id,
        target_item_id,
        relation_type="component_of",
        metadata=None,
    ):
        """Record an explicit directed relation; no identities are merged."""
        self.knowledge.get_item(source_item_id)
        self.knowledge.get_item(target_item_id)
        validate(relation_type, {"component_of"}, "relation")
        if source_item_id == target_item_id:
            raise ValueError("Self relations are invalid")
        return self.knowledge._ensure(
            t.relations,
            ("source_item_id", "target_item_id", "relation_type"),
            dict(
                source_item_id=source_item_id,
                target_item_id=target_item_id,
                relation_type=relation_type,
                metadata=encode_metadata(metadata),
            ),
        )

    def list_roles(self):
        """Batch role metadata, keeping manual overrides visible to consumers."""
        return [
            dict(row, metadata=json.loads(row["metadata"]))
            for row in self.session.execute(select(t.roles)).mappings()
        ]

    def list_relations(self):
        """Batch explicit relations without loading individual items."""
        return [
            dict(row, metadata=json.loads(row["metadata"]))
            for row in self.session.execute(select(t.relations)).mappings()
        ]

    def resolve_effective_items(self, source_id, start, end):
        """Suppress only component occurrences contained in a realized construction."""
        source = self.knowledge._one(t.sources, t.sources.c.id == source_id)
        if source is None or not 0 <= start < end <= len(source["content"]):
            raise ValueError("Invalid source region")
        query = (
            select(
                t.items.c.id,
                t.items.c.identity,
                t.items.c.kind,
                t.occurrences.c.id.label("occurrence_id"),
                t.occurrences.c.start,
                t.occurrences.c.end,
            )
            .select_from(
                t.links.join(t.items, t.items.c.id == t.links.c.item_id).join(
                    t.occurrences, t.occurrences.c.id == t.links.c.occurrence_id
                )
            )
            .where(
                t.occurrences.c.source_id == source_id,
                t.occurrences.c.start >= start,
                t.occurrences.c.end <= end,
            )
        )
        rows = [dict(r) for r in self.session.execute(query).mappings()]
        relations = (
            self.session.execute(select(t.relations)).mappings().all()
            if self.available()
            else []
        )
        return resolve_effective_rows(rows, relations)

    def audit_integrity(self):
        """Batched reproducible checks; findings are diagnostics, never repairs."""
        rows = self.session.execute(
            select(
                t.items.c.identity, t.items.c.kind, t.occurrences, t.sources.c.content
            )
            .select_from(
                t.links.join(t.items, t.items.c.id == t.links.c.item_id)
                .join(t.occurrences, t.occurrences.c.id == t.links.c.occurrence_id)
                .join(t.sources, t.sources.c.id == t.occurrences.c.source_id)
            )
            .where(t.items.c.kind == "lexical")
        ).mappings()
        findings = []
        for row in rows:
            meta = json.loads(row["metadata"])
            canonical = meta.get("lexical_normalization", {}).get("canonical_heads", [])
            reason = None
            severity = "important"
            if row["content"][row["start"] : row["end"]] != row["surface"]:
                reason = "Source/span/surface mismatch"
                severity = "critical"
            elif any(
                m["start"] < row["start"] or m["end"] > row["end"]
                for m in meta.get("morphemes", [])
            ):
                reason = "Raw lexical subspan crosses unit boundary"
            elif canonical and row["identity"] not in canonical:
                reason = "Link absent from recorded canonical heads"
                severity = "critical"
            elif row["identity"] == "저" and row["surface"] == "어제":
                reason = "Pronoun absorbs adverb"
                severity = "critical"
            elif row["identity"] == "있다" and row["surface"].startswith(("재미있", "맛있")):
                reason = "Lexicalized predicate decomposed"
                severity = "critical"
            elif len(meta.get("eligible_heads", canonical)) > 1:
                reason = (
                    "Multiple canonical heads in one unit: inspect compound/auxiliary"
                )
                severity = "expected Kiwi behavior"
            if reason:
                findings.append(
                    {
                        "item": row["identity"],
                        "surface": row["surface"],
                        "occurrence_id": row["id"],
                        "severity": severity,
                        "reason": reason,
                        "raw_heads": meta.get("lexical_normalization", {}).get(
                            "raw_heads", []
                        ),
                    }
                )
        return findings


def resolve_effective_rows(rows, relations):
    """Pure containment resolution; caller supplies one source/segment region."""
    suppressed = []
    effective = []
    for row in rows:
        cover = next(
            (
                target
                for relation in relations
                if relation["source_item_id"] == row["id"]
                for target in rows
                if target["id"] == relation["target_item_id"]
                and target["kind"] == "grammar"
                and target["start"] <= row["start"]
                and row["end"] <= target["end"]
            ),
            None,
        )
        if cover:
            suppressed.append(
                dict(
                    row,
                    covered_by=cover["id"],
                    covered_by_occurrence_id=cover["occurrence_id"],
                    covering_span=[cover["start"], cover["end"]],
                    reason=f"component_of tracked construction {cover['identity']}",
                )
            )
        else:
            effective.append(row)
    return {
        "raw_items": rows,
        "effective_items": effective,
        "suppressed_overlap": suppressed,
    }


# Attested construction components apply even before a candidate item is tracked.
CONSTRUCTION_COMPONENTS = (
    ("lexical", "싶다", "grammar", "-고 싶다", "ko.overlap.desire.v1"),
)
