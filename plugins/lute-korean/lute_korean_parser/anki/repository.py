"""Anki state persistence and item-level views of canonical review evidence."""
import json
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from . import tables as t
from ..knowledge import tables as k


class AnkiRepository:
    """Persistence operations scoped to one collection identity."""

    def __init__(self, session, integration):
        self.session = session
        self.integration = integration

    def rows(self, table):
        column = table.c.identity if table is t.integrations else table.c.integration
        return [
            dict(row)
            for row in self.session.execute(
                select(table).where(column == self.integration)
            ).mappings()
        ]

    def upsert(self, table, keys, values):
        statement = insert(table).values(**values)
        self.session.execute(
            statement.on_conflict_do_update(
                index_elements=list(keys),
                set_={k: v for k, v in values.items() if k not in keys},
            )
        )

    def status(self):
        """Return the last committed synchronization report."""
        rows = self.rows(t.integrations)
        if not rows:
            return {
                "integration": self.integration,
                "last_success": None,
                "report": None,
            }
        row = rows[0]
        return {
            "integration": row["identity"],
            "profile": row["profile"],
            "last_success": row["last_success"],
            "report": json.loads(row["report"]),
        }


def review_query(item_id=None):
    """Select canonical events via distinct source/item associations."""
    association = (
        select(k.occurrences.c.source_id)
        .join(k.links, k.links.c.occurrence_id == k.occurrences.c.id)
        .distinct()
    )
    if item_id is not None:
        association = association.where(k.links.c.item_id == item_id)
    return select(t.reviews).where(t.reviews.c.source_id.in_(association))


def item_reviews(session, item_id):
    """Expose sentence-level evidence with unspecified modality."""
    result = []
    for row in session.execute(
        review_query(item_id).order_by(t.reviews.c.review_id, t.reviews.c.card_id)
    ).mappings():
        value = dict(row)
        value["metadata"] = json.loads(value["metadata"])
        value.update(
            evidence_type="anki_review",
            source_type="anki",
            dimension=None,
            directness="indirect",
            scope="note_content",
        )
        result.append(value)
    return result


def summaries(session):
    """Batched distinct event counts; shared source-item spans never multiply reviews."""
    source_items = (
        select(k.occurrences.c.source_id, k.links.c.item_id)
        .join(k.links, k.links.c.occurrence_id == k.occurrences.c.id)
        .distinct()
        .subquery()
    )
    query = select(
        source_items.c.item_id,
        t.reviews.c.integration,
        t.reviews.c.card_id,
        t.reviews.c.review_id,
        t.reviews.c.note_id,
        t.reviews.c.rating,
        t.reviews.c.occurred_at,
    ).join(t.reviews, t.reviews.c.source_id == source_items.c.source_id)
    result = {}
    # Include notes/cards with exposure but zero reviews as well.
    exposed = (
        select(source_items.c.item_id, t.revisions.c.integration, t.revisions.c.note_id)
        .join(t.revisions, t.revisions.c.source_id == source_items.c.source_id)
        .distinct()
    )
    for item_id, integration, note_id in session.execute(exposed):
        entry = result.setdefault(
            item_id,
            {
                "notes": set(),
                "cards": set(),
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
        entry["notes"].add((integration, note_id))
    card_rows = (
        select(source_items.c.item_id, t.cards.c.integration, t.cards.c.card_id)
        .join(t.revisions, t.revisions.c.source_id == source_items.c.source_id)
        .join(
            t.cards,
            (t.cards.c.integration == t.revisions.c.integration)
            & (t.cards.c.note_id == t.revisions.c.note_id),
        )
        .distinct()
    )
    for item_id, integration, card_id in session.execute(card_rows):
        result[item_id]["cards"].add((integration, card_id))
    for (
        item_id,
        integration,
        card_id,
        _review_id,
        note_id,
        rating,
        occurred_at,
    ) in session.execute(query):
        entry = result[item_id]
        entry["cards"].add((integration, card_id))
        entry["reviews"] += 1
        entry[{1: "again", 2: "hard", 3: "good", 4: "easy"}.get(rating, "other")] += 1
        entry["last_review"] = max(entry["last_review"] or occurred_at, occurred_at)
    return {
        item_id: dict(entry, notes=len(entry["notes"]), cards=len(entry["cards"]))
        for item_id, entry in result.items()
    }
