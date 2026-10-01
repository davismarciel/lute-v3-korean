"""Explicit, atomic Anki sync; extraction, analysis and review evidence stay separate."""
import hashlib
from contextlib import contextmanager
import json
from datetime import datetime, timezone
from time import perf_counter
from urllib.parse import quote
from sqlalchemy import create_engine, text as sqltext, update
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import SQLAlchemyError
from . import tables as t
from .repository import AnkiRepository
from .extraction import extract_note, suggest_mapping, clean_field
from .models import AnkiError
from .content import POLICY_VERSION
from ..knowledge.service import encode_metadata
from ..knowledge.ingestion import KnowledgeIngestionService


def now():
    """UTC observation time; distinct from a review event timestamp."""
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def dry_session(session):
    """Copy only acquisition tables to RAM; never write the user's database."""
    engine = create_engine("sqlite://")
    raw = engine.raw_connection()
    schemas = session.execute(
        sqltext(
            "SELECT name, sql FROM sqlite_master WHERE name LIKE 'korean_%' "
            "AND sql IS NOT NULL AND type IN ('table','index') ORDER BY type DESC"
        )
    ).all()
    try:
        # Knowledge sources may reference Lute texts. Copy only their IDs into
        # an isolated parent stub so FK-enabled dry runs need no reader data.
        raw.execute("CREATE TABLE texts(TxID INTEGER PRIMARY KEY)")
        parent_ids = session.execute(
            sqltext(
                "SELECT DISTINCT lute_text_id FROM korean_knowledge_sources "
                "WHERE lute_text_id IS NOT NULL"
            )
        ).all()
        raw.executemany(
            "INSERT INTO texts(TxID) VALUES (?)", [tuple(r) for r in parent_ids]
        )
        for _, ddl in schemas:
            raw.execute(ddl)
        for name, _ in schemas:
            if name in (
                "korean_knowledge_items",
                "korean_knowledge_dimensions",
                "korean_knowledge_roles",
                "korean_knowledge_relations",
                "korean_knowledge_sources",
                "korean_knowledge_occurrences",
                "korean_knowledge_occurrence_items",
                "korean_knowledge_evidence",
                "korean_anki_integrations",
                "korean_anki_notes",
                "korean_anki_revisions",
                "korean_anki_cards",
                "korean_anki_reviews",
            ):
                rows = session.execute(sqltext(f'SELECT * FROM "{name}"')).all()
                if rows:
                    placeholders = ",".join("?" for _ in rows[0])
                    raw.executemany(
                        f'INSERT INTO "{name}" VALUES ({placeholders})',
                        [tuple(r) for r in rows],
                    )
        raw.commit()
    finally:
        raw.close()
    try:
        with Session(engine) as copy:
            yield copy
    finally:
        engine.dispose()


class AnkiSyncService:
    """The caller owns commit/rollback. One canonical row per actual review event."""

    def __init__(self, session, adapter, config, parser=None):
        self.session = session
        self.adapter = adapter
        self.config = config
        self.repository = (
            AnkiRepository(session, config.source_identity)
            if session is not None
            else None
        )
        self.ingestion = KnowledgeIngestionService(session, parser=parser)

    def _snapshot(self):
        health = self.adapter.health()
        if self.config.profile is not None and health["profile"] != self.config.profile:
            raise AnkiError("Active Anki profile differs from configured profile")
        ids = self.adapter.find_notes(self.config.search_query())
        notes = self.adapter.fetch_notes(ids)
        if len({n.note_id for n in notes}) != len(notes):
            raise AnkiError("Duplicate note IDs in snapshot")
        notes = [
            n
            for n in notes
            if not self.config.note_types or n.note_type in self.config.note_types
        ]
        cards = self.adapter.fetch_cards(cid for n in notes for cid in n.card_ids)
        by_note = {n.note_id: n for n in notes}
        cards = [
            c
            for c in cards
            if c.note_id in by_note
            and c.card_id in by_note[c.note_id].card_ids
            and (not self.config.decks or c.deck in self.config.decks)
        ]
        # A card-less note can be previewed but is not an in-scope review source.
        return health, notes, cards

    def preview(self):  # pylint: disable=too-many-locals
        """Discover fields and redacted samples without opening a database."""
        health, notes, cards = self._snapshot()
        types = {}
        samples = []
        unmapped = 0
        problems = []
        content_warnings = []
        content_anomalies = 0
        for note in notes:
            entry = types.setdefault(
                note.note_type,
                {"notes": 0, "fields": sorted(note.fields), "mapping": None},
            )
            entry["notes"] += 1
            mapping = self.config.mappings.get(note.note_type)
            if mapping is None:
                unmapped += 1
            else:
                entry["mapping"] = {
                    "korean_fields": mapping.korean_fields,
                    "translation_fields": mapping.translation_fields,
                    "metadata_fields": mapping.metadata_fields,
                }
                try:
                    _, metadata = extract_note(note, mapping)
                    diagnostic = metadata["content_validation"]
                    if diagnostic["content_language_warning"]:
                        content_warnings.append(
                            {"note_type": note.note_type, "diagnostic": diagnostic}
                        )
                    if diagnostic["status"] == "anomalous":
                        content_anomalies += 1
                        reasons = ", ".join(diagnostic["reasons"])
                        problems.append(
                            f"Content anomaly in {note.note_type}: {reasons}"
                        )
                except ValueError as exc:
                    problems.append(str(exc))
            # Default samples show structure/length, never collection text or IDs.
            if len(samples) < 5:
                samples.append(
                    {
                        "note_type": note.note_type,
                        "fields": {
                            name: {"characters": len(clean_field(raw))}
                            for name, raw in note.fields.items()
                        },
                    }
                )
        return {
            "connection": health,
            "notes_found": len(notes),
            "cards_found": len(cards),
            "note_types": types,
            "suggestions": suggest_mapping(notes),
            "unmapped": unmapped,
            "samples": samples,
            "problems": problems[:20],
            "content_warnings": len(content_warnings),
            "content_anomalies": content_anomalies,
            "content_language_warnings": content_warnings[:20],
        }

    def doctor(self):
        """Validate connectivity, active profile, query and explicit mappings."""
        result = self.preview()
        result["ok"] = (
            not result["unmapped"]
            and not result["problems"]
            and bool(self.config.mappings)
        )
        return result

    def status(self):
        """Return the last committed operational report without network access."""
        return self.repository.status()

    def sync(self, dry_run=False, full_reviews=False):
        """Collect and ingest atomically; never commit the caller transaction."""
        # The orchestration retains one transaction and its counters in one scope.
        # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        if dry_run:
            with dry_session(self.session) as copy:
                report = AnkiSyncService(
                    copy, self.adapter, self.config, parser=self.ingestion.parser
                ).sync(full_reviews=full_reviews)
                report["dry_run"] = True
                return report
        started = perf_counter()
        health, notes, cards = self._snapshot()
        selected_note_ids = {c.note_id for c in cards}
        notes = [n for n in notes if n.note_id in selected_note_ids]
        previous_status = self.status()
        if previous_status.get("profile") not in (None, health["profile"]):
            raise AnkiError("Source identity belongs to another Anki profile")
        previous_notes = {row["note_id"]: row for row in self.repository.rows(t.notes)}
        previous_cards = {row["card_id"]: row for row in self.repository.rows(t.cards)}
        extracted, extraction_errors = self._prepare_notes(notes, cards)
        missing_notes = set(previous_notes) - {n.note_id for n in notes}
        outside_notes = (
            {n.note_id for n in self.adapter.fetch_notes(sorted(missing_notes))}
            if missing_notes
            else set()
        )
        missing_cards = set(previous_cards) - {c.card_id for c in cards}
        outside_cards = (
            {c.card_id for c in self.adapter.fetch_cards(sorted(missing_cards))}
            if missing_cards
            else set()
        )
        cursors = {
            cid: row["review_cursor"]
            for cid, row in previous_cards.items()
            if row["state"] in ("active", "suspended")
        }
        review_events = self.adapter.fetch_reviews(cards, cursors, full=full_reviews)
        if self.adapter.health()["profile"] != health["profile"]:
            raise AnkiError("Anki profile changed during snapshot collection")
        report = {
            "dry_run": dry_run,
            "notes_inspected": len(notes),
            "notes_created": 0,
            "notes_changed": 0,
            "notes_skipped": 0,
            "notes_metadata_changed": 0,
            "notes_anomalous": 0,
            "notes_analyzed": 0,
            "content_language_warnings": 0,
            "content_diagnostics": [],
            "reviews_without_linguistic_association": 0,
            "reviews_imported": 0,
            "reviews_skipped": 0,
            "notes_missing": len(missing_notes - outside_notes),
            "notes_out_of_scope": len(outside_notes),
            "cards_missing": len(missing_cards - outside_cards),
            "errors": [],
            "knowledge_created": {"lexical": 0, "grammar": 0, "chunk": 0},
        }
        # All network work precedes writes. Savepoints retain caller transaction ownership.
        connection = self.session.connection()
        if (
            connection.dialect.name == "sqlite"
            and not connection.connection.driver_connection.in_transaction
        ):
            connection.exec_driver_sql("BEGIN")
        with self.session.begin_nested():
            observed = now()
            self.repository.upsert(
                t.integrations,
                ("identity",),
                {
                    "identity": self.config.source_identity,
                    "profile": health["profile"],
                    "last_success": previous_status["last_success"],
                    "report": json.dumps(report),
                },
            )
            old_items = {i["id"] for i in self.ingestion.knowledge.list_items()}
            for nid in sorted(missing_notes):
                self.session.execute(
                    update(t.notes)
                    .where(
                        t.notes.c.integration == self.config.source_identity,
                        t.notes.c.note_id == nid,
                    )
                    .values(state="out_of_scope" if nid in outside_notes else "missing")
                )
            for cid in sorted(missing_cards):
                self.session.execute(
                    update(t.cards)
                    .where(
                        t.cards.c.integration == self.config.source_identity,
                        t.cards.c.card_id == cid,
                    )
                    .values(state="out_of_scope" if cid in outside_cards else "missing")
                )
            for note in notes:
                previous = previous_notes.get(note.note_id)
                if note.note_id in extraction_errors:
                    self._note_error(
                        note, previous, extraction_errors[note.note_id], report
                    )
                    continue
                text, metadata, digest, mapping_hash = extracted[note.note_id]
                diagnostic = metadata["content_validation"]
                anomalous = diagnostic["status"] == "anomalous"
                report["notes_anomalous"] += int(anomalous)
                report["content_language_warnings"] += int(
                    diagnostic["content_language_warning"]
                )
                if (
                    diagnostic["content_language_warning"]
                    and len(report["content_diagnostics"]) < 20
                ):
                    report["content_diagnostics"].append(
                        {
                            "note_id": note.note_id,
                            "status": diagnostic["status"],
                            "reasons": diagnostic["reasons"],
                        }
                    )
                unchanged = (
                    previous
                    and previous["source_id"]
                    and previous["content_hash"] == digest
                    and previous["mapping_hash"] == mapping_hash
                )
                try:
                    with self.session.begin_nested():
                        source_id = previous["source_id"] if unchanged else None
                        if not unchanged:
                            reference = (
                                f"anki:{quote(self.config.source_identity, safe='')}:"
                                f"note:{note.note_id}:revision:{digest}:{mapping_hash}"
                            )
                            # Ingestion receives no review interpretation or statuses.
                            if anomalous:
                                # Retain content/reviews without linguistic associations.
                                source_id = self.ingestion.knowledge.ensure_source(
                                    "anki", reference, text
                                )["id"]
                            else:
                                source_id = self.ingestion.ingest(
                                    text, reference, source_type="anki"
                                )["source_id"]
                                report["notes_analyzed"] += 1
                        self.repository.upsert(
                            t.notes,
                            ("integration", "note_id"),
                            {
                                "integration": self.config.source_identity,
                                "note_id": note.note_id,
                                "source_id": source_id,
                                "content_hash": digest,
                                "mapping_hash": mapping_hash,
                                "modified": note.modified,
                                "state": "active",
                                "metadata": encode_metadata(metadata),
                            },
                        )
                        revision = {
                            "integration": self.config.source_identity,
                            "note_id": note.note_id,
                            "source_id": source_id,
                            "observed_at": observed,
                            "effective_from": note.modified * 1000
                            if note.modified
                            else None,
                            "metadata": encode_metadata(metadata),
                        }
                        if not unchanged:
                            self.session.execute(insert(t.revisions).values(**revision))
                    if unchanged:
                        report["notes_skipped"] += 1
                        report["notes_metadata_changed"] += int(
                            previous["metadata"] != encode_metadata(metadata)
                        )
                    else:
                        report[
                            "notes_changed"
                            if previous and previous["source_id"]
                            else "notes_created"
                        ] += 1
                except SQLAlchemyError:  # pylint: disable=try-except-raise
                    # Database failures must abort, rather than become note errors.
                    raise
                except (ValueError, RuntimeError) as exc:
                    self._note_error(note, previous, str(exc), report)
            note_rows = {row["note_id"]: row for row in self.repository.rows(t.notes)}
            for card in cards:
                self.repository.upsert(
                    t.cards,
                    ("integration", "card_id"),
                    {
                        "integration": self.config.source_identity,
                        "card_id": card.card_id,
                        "note_id": card.note_id,
                        "deck": card.deck,
                        "ordinal": card.ordinal,
                        "state": "suspended"
                        if card.metadata.get("queue") == -1
                        else "active",
                        "review_cursor": previous_cards.get(card.card_id, {}).get(
                            "review_cursor", 0
                        ),
                        "metadata": encode_metadata(card.metadata),
                    },
                )
            self._import_reviews(cards, note_rows, review_events, report)
            watermark = max([0, *(e.review_id for e in review_events)])
            for card in cards:
                note = note_rows[card.note_id]
                cursor = (
                    max(cursors.get(card.card_id, 0), watermark)
                    if note["state"] == "active"
                    else cursors.get(card.card_id, 0)
                )
                self.session.execute(
                    update(t.cards)
                    .where(
                        t.cards.c.integration == self.config.source_identity,
                        t.cards.c.card_id == card.card_id,
                    )
                    .values(review_cursor=cursor)
                )
            for item in self.ingestion.knowledge.list_items():
                if item["id"] not in old_items:
                    report["knowledge_created"][item["kind"]] += 1
            report["duration_seconds"] = round(perf_counter() - started, 3)
            report["error_count"] = len(report["errors"])
            report["errors"] = report["errors"][:20]
            self.repository.upsert(
                t.integrations,
                ("identity",),
                {
                    "identity": self.config.source_identity,
                    "profile": health["profile"],
                    "last_success": observed,
                    "report": encode_metadata(report),
                },
            )
        return report

    def _prepare_notes(self, notes, cards):
        """Validate all mappings before writing; collect isolated content errors."""
        decks_by_note = {}
        for card in cards:
            decks_by_note.setdefault(card.note_id, set()).add(card.deck)
        extracted = {}
        extraction_errors = {}
        for note in notes:
            mapping = self.config.mappings.get(note.note_type)
            if mapping is None:
                raise ValueError(
                    f"No explicit mapping for {note.note_type}; preview and configure first"
                )
            required = (
                *mapping.korean_fields,
                *mapping.translation_fields,
                *mapping.metadata_fields,
            )
            if any(f not in note.fields for f in required):
                raise ValueError(f"Invalid field mapping for {note.note_type}")
            try:
                text, metadata = extract_note(note, mapping)
                metadata.update(
                    note_type=note.note_type,
                    tags=list(note.tags),
                    card_ids=list(note.card_ids),
                    decks=sorted(decks_by_note.get(note.note_id, ())),
                    modified=note.modified,
                    korean_fields=list(mapping.korean_fields),
                    processing_version=self.ingestion.processing_version,
                )
                encode_metadata(metadata)
                extracted[note.note_id] = (
                    text,
                    metadata,
                    hashlib.sha256(text.encode()).hexdigest(),
                    hashlib.sha256(
                        (
                            self.config.mapping_hash(note.note_type)
                            + self.ingestion.processing_version
                            + POLICY_VERSION
                        ).encode()
                    ).hexdigest(),
                )
            except ValueError as exc:
                extraction_errors[note.note_id] = str(exc)
        return extracted, extraction_errors

    def _import_reviews(self, cards, note_rows, review_events, report):
        """Persist each actual card review once, retaining immutable provenance."""
        # Raw event fields and source identity are validated together.
        # pylint: disable=too-many-locals
        existing = {
            (r["card_id"], r["review_id"]): r for r in self.repository.rows(t.reviews)
        }
        revision_rows = self.repository.rows(t.revisions)
        revisions_by_note = {}
        for revision in revision_rows:
            revisions_by_note.setdefault(revision["note_id"], []).append(revision)
        cards_by_id = {c.card_id: c for c in cards}
        values = {}
        for event in review_events:
            card = cards_by_id.get(event.card_id)
            if card is None:
                raise AnkiError("Adapter returned a review for an unselected card")
            note = note_rows.get(card.note_id)
            if not note or note["state"] != "active" or not note["source_id"]:
                report["reviews_skipped"] += 1
                continue
            key = (event.card_id, event.review_id)
            if key in values:
                old = values[key]
                if any(
                    old[name] != getattr(event, name)
                    for name in (
                        "rating",
                        "interval",
                        "previous_interval",
                        "review_type",
                        "duration_ms",
                        "factor",
                        "usn",
                    )
                ):
                    raise AnkiError("Conflicting duplicate review in snapshot")
                report["reviews_skipped"] += 1
                continue
            raw = {
                name: getattr(event, name)
                for name in (
                    "rating",
                    "interval",
                    "previous_interval",
                    "review_type",
                    "duration_ms",
                    "factor",
                    "usn",
                )
            }
            if event.review_id <= 0 or event.duration_ms < 0:
                raise AnkiError("Invalid review ID or duration")
            if key in existing:
                # USN is sync bookkeeping, not immutable review semantics.
                if any(
                    existing[key][name] != value
                    for name, value in raw.items()
                    if name != "usn"
                ):
                    raise AnkiError(
                        "Previously imported review changed; "
                        "full reconciliation requires explicit policy"
                    )
                report["reviews_skipped"] += 1
                continue
            revision, basis = self._review_revision(
                event, revisions_by_note[card.note_id]
            )
            withheld = (
                json.loads(revision["metadata"])
                .get("content_validation", {})
                .get("status")
                == "anomalous"
            )
            report["reviews_without_linguistic_association"] += int(withheld)
            row = dict(
                raw,
                integration=self.config.source_identity,
                card_id=event.card_id,
                review_id=event.review_id,
                note_id=card.note_id,
                source_id=revision["source_id"],
                event_key=(
                    f"anki:{quote(self.config.source_identity, safe='')}:"
                    f"card:{event.card_id}:review:{event.review_id}"
                ),
                occurred_at=datetime.fromtimestamp(
                    event.review_id / 1000, timezone.utc
                ).isoformat(),
                metadata=encode_metadata(
                    {
                        "directness": "indirect",
                        "scope": "note_content",
                        "modality": "unspecified",
                        "association_basis": basis,
                        "linguistic_association": "withheld_content_anomaly"
                        if withheld
                        else "source_occurrences",
                        "card": card.metadata,
                        "ordinal": card.ordinal,
                    }
                ),
            )
            if key in values and values[key] != row:
                raise AnkiError("Conflicting duplicate review in snapshot")
            values[key] = row
        pending = list(values.values())
        for start in range(0, len(pending), 500):
            self.session.execute(insert(t.reviews), pending[start : start + 500])
        report["reviews_imported"] = len(pending)

    def _note_error(self, note, previous, message, report):
        report["errors"].append({"note_id": note.note_id, "message": message[:200]})
        values = (
            dict(previous)
            if previous
            else {
                "integration": self.config.source_identity,
                "note_id": note.note_id,
                "source_id": None,
                "content_hash": None,
                "mapping_hash": None,
                "modified": note.modified,
                "metadata": "{}",
            }
        )
        values["state"] = "error"
        self.repository.upsert(t.notes, ("integration", "note_id"), values)

    @staticmethod
    def _review_revision(event, revisions):
        ordered = sorted(revisions, key=lambda r: r["observed_at"])
        if len(ordered) == 1:
            return ordered[0], "first_observed_snapshot"
        applicable = [
            r
            for r in ordered
            if (
                r["effective_from"]
                or int(datetime.fromisoformat(r["observed_at"]).timestamp() * 1000)
            )
            <= event.review_id
        ]
        if applicable:
            return (
                max(
                    applicable,
                    key=lambda r: r["effective_from"]
                    or int(datetime.fromisoformat(r["observed_at"]).timestamp() * 1000),
                ),
                "observed_revision_modification_boundary",
            )
        return ordered[0], "historical_snapshot_uncertain"
