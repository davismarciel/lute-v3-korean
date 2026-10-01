"""Repeatable Anki source fixtures; no Anki Desktop or real collection required."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from time import perf_counter
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine, event, select, func
from sqlalchemy.orm import Session
from lute_korean_parser.anki.models import (
    AnkiNoteSnapshot,
    AnkiCardSnapshot,
    AnkiReviewEvent,
    AnkiError,
)
from lute_korean_parser.anki.config import AnkiConfig, NoteTypeMapping
from lute_korean_parser.anki.extraction import clean_field, extract_note
from lute_korean_parser.anki.sync import AnkiSyncService
from lute_korean_parser.anki import tables as a
from lute_korean_parser.knowledge import tables as k
from lute_korean_parser.knowledge.service import KnowledgeService
from lute_korean_parser.parser import KoreanParser

ROOT = Path(__file__).resolve().parents[3]
BASE = 1700000000000
TEXT = "한국에 가면 많이 먹을 거예요."
MAPPING = NoteTypeMapping(("KO",), ("PT",), ("NOTAS",))


class FakeAdapter:
    def __init__(self, notes=None, cards=None, reviews=None):
        self.notes = {n.note_id: n for n in (notes or [])}
        self.cards = {c.card_id: c for c in (cards or [])}
        self.reviews = list(reviews or [])
        self.selected = set(self.notes)
        self.profile = "Fixture"
        self.calls = []
        self.failure = False

    def health(self):
        if self.failure:
            raise AnkiError("connection failed")
        return {"version": 6, "profile": self.profile}

    def find_notes(self, query):
        self.calls.append(("find_notes", query))
        return sorted(self.selected)

    def fetch_notes(self, ids):
        ids = list(ids)
        self.calls.append(("notes", ids))
        return [self.notes[i] for i in ids if i in self.notes]

    def fetch_cards(self, ids):
        ids = list(ids)
        self.calls.append(("cards", ids))
        return [self.cards[i] for i in ids if i in self.cards]

    def fetch_reviews(self, cards, cursors, full=False):
        ids = {c.card_id for c in cards}
        self.calls.append(("reviews", dict(cursors)))
        return [
            r
            for r in self.reviews
            if r.card_id in ids and (full or r.review_id > cursors.get(r.card_id, 0))
        ]


def note(
    nid=123, text=TEXT, cards=(456, 789), model="Core Korean", modified=1700000000
):
    return AnkiNoteSnapshot(
        nid,
        model,
        {"KO": text, "PT": "Meaning", "NOTAS": "restaurant"},
        cards,
        ("travel",),
        modified,
    )


def card(cid=456, nid=123, ordinal=0):
    return AnkiCardSnapshot(
        cid,
        nid,
        "Fixture deck",
        ordinal,
        {
            "queue": 0,
            "template_name": f"Card {ordinal}",
            "question_fields": ["KO"] if ordinal == 0 else ["PT"],
            "answer_fields": ["PT"] if ordinal == 0 else ["KO"],
        },
    )


def review(rid=BASE + 10000, cid=456, rating=3):
    return AnkiReviewEvent(rid, cid, rating, 4, 1, 1, 1200, 2500, 0)


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "anki.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE texts(TxID INTEGER PRIMARY KEY)")
    for migration in [
        "20260930_01_korean_knowledge.sql",
        "20260930_02_korean_anki.sql",
        "20260930_03_korean_representation.sql",
    ]:
        conn.executescript(
            (ROOT / "lute/db/schema/migrations" / migration).read_text(encoding="utf8")
        )
    conn.close()
    engine = create_engine(f"sqlite:///{path}")

    @event.listens_for(engine, "connect")
    def fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    yield engine
    engine.dispose()


@pytest.fixture
def session(database):
    with Session(database) as value:
        yield value


@pytest.fixture
def config():
    return AnkiConfig("fixture-source", {"Core Korean": MAPPING}, profile="Fixture")


@pytest.fixture
def adapter():
    return FakeAdapter(
        [note()],
        [card(), card(789, ordinal=1)],
        [
            review(BASE + 10000 + i, cid=456 if i % 2 == 0 else 789, rating=i + 1)
            for i in range(4)
        ],
    )


class CountingParser:
    def __init__(self):
        self.parser = KoreanParser()
        self.calls = 0

    def analyze(self, text):
        self.calls += 1
        return self.parser.analyze(text)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("오늘은 피곤해서 일찍 잘 거예요.", "오늘은 피곤해서 일찍 잘 거예요."),
        ("<div>오늘은 <b>피곤해서</b> 일찍 잘 거예요.</div>", "오늘은 피곤해서 일찍 잘 거예요."),
        ("[sound:korean123.mp3]오늘은 피곤해요.", "오늘은 피곤해요."),
        ("오늘은 피곤해요.<br>\n그래서 일찍 잘 거예요.", "오늘은 피곤해요.\n\n그래서 일찍 잘 거예요."),
        ("<script>bad()</script><div>오늘&nbsp;먹어요.</div><style>bad</style>", "오늘 먹어요."),
        ("{{c1::한국::country}}에 가요.", "한국에 가요."),
    ],
)
def test_cleanup(raw, expected):
    assert clean_field(raw) == expected


def test_mappings_audio_and_preview(session, adapter, config):
    adapter.notes[123] = note(text="[sound:test.mp3]" + TEXT)
    extracted, metadata = extract_note(adapter.notes[123], MAPPING)
    assert extracted == TEXT and metadata["has_audio"]
    service = AnkiSyncService(session, adapter, config)
    output = service.preview()
    assert output["notes_found"] == 1 and output["cards_found"] == 2
    assert output["unmapped"] == 0
    assert "한국" not in json.dumps(output, ensure_ascii=False)
    assert KnowledgeService(session).list_items() == []
    assert service.doctor()["ok"]
    other = AnkiSyncService(session, adapter, replace(config, mappings={}))
    assert other.preview()["unmapped"] == 1
    assert not other.doctor()["ok"]
    with pytest.raises(ValueError, match="mapping"):
        other.sync()


@pytest.mark.parametrize(
    "model,fields,mapping",
    [
        ("Core Korean", {"KO": TEXT, "PT": "Meaning", "NOTAS": "Notes"}, MAPPING),
        (
            "Basic",
            {"Front": TEXT, "Back": "Meaning"},
            NoteTypeMapping(("Front",), ("Back",)),
        ),
        (
            "Custom",
            {"Sentence": TEXT, "Translation": "Meaning", "Audio": "[sound:a.mp3]"},
            NoteTypeMapping(("Sentence",), ("Translation",), ("Audio",)),
        ),
    ],
)
def test_note_types(session, config, model, fields, mapping):
    n = AnkiNoteSnapshot(1, model, fields, (2,))
    source = FakeAdapter([n], [card(2, 1)])
    service = AnkiSyncService(
        session, source, replace(config, mappings={model: mapping})
    )
    assert service.sync()["notes_created"] == 1
    assert KnowledgeService(session).get_lexical("먹다") is not None


def test_existing_concept_reverse_cards_and_incremental(session, adapter, config):
    knowledge = KnowledgeService(session)
    eat = knowledge.get_or_create_lexical("먹다")
    knowledge.set_status(eat["id"], "practicing")
    parser = CountingParser()
    service = AnkiSyncService(session, adapter, config, parser)
    first = service.sync()
    assert first["notes_created"] == 1 and first["reviews_imported"] == 4
    assert parser.calls == 1
    assert knowledge.get_lexical("먹다")["id"] == eat["id"]
    assert knowledge.get_item(eat["id"])["status"] == "practicing"
    assert knowledge.list_surface_forms(eat["id"]) == ["먹을"]
    assert len(knowledge.list_evidence(eat["id"])) == 1
    assert len(knowledge.list_anki_reviews(eat["id"])) == 4
    assert session.execute(select(func.count()).select_from(a.reviews)).scalar() == 4
    assert (
        session.execute(select(func.count()).select_from(k.occurrences)).scalar() == 5
    )
    second = service.sync()
    assert (
        second["notes_skipped"] == 1
        and second["reviews_imported"] == 0
        and parser.calls == 1
    )
    assert service.sync(full_reviews=True)["reviews_skipped"] == 4
    assert parser.calls == 1
    adapter.reviews.append(review(BASE + 100000, 789, 4))
    assert service.sync()["reviews_imported"] == 1 and parser.calls == 1
    assert knowledge.get_item(eat["id"])["status"] == "practicing"
    summary = knowledge.anki_summary(eat["id"])
    assert {
        key: summary[key]
        for key in ("notes", "cards", "reviews", "again", "hard", "good", "easy")
    } == {
        "notes": 1,
        "cards": 2,
        "reviews": 5,
        "again": 1,
        "hard": 1,
        "good": 1,
        "easy": 2,
    }
    events = knowledge.list_anki_reviews(eat["id"])
    assert all(e["dimension"] is None and e["directness"] == "indirect" for e in events)
    assert all(e["metadata"]["modality"] == "unspecified" for e in events)


def test_required_eat_surface(session, config):
    knowledge = KnowledgeService(session)
    eat = knowledge.get_or_create_lexical("먹다")
    knowledge.set_status(eat["id"], "practicing")
    adapter = FakeAdapter(
        [note(text="오늘 친구랑 같이 밥을 먹었어요.")], [card(), card(789, ordinal=1)], [review()]
    )
    AnkiSyncService(session, adapter, config).sync()
    assert knowledge.list_surface_forms(eat["id"]) == ["먹었어요"]
    assert len(knowledge.list_evidence(eat["id"])) == 1
    assert knowledge.get_item(eat["id"])["status"] == "practicing"


def test_note_revision_keeps_old_reviews(session, adapter, config):
    parser = CountingParser()
    service = AnkiSyncService(session, adapter, config, parser)
    service.sync()
    old = session.execute(select(a.notes.c.source_id)).scalar_one()
    adapter.notes[123] = note(text="한국에 가면 친구랑 같이 많이 먹을 거예요.", modified=1700000100)
    adapter.reviews.append(review(BASE + 200000))
    second = service.sync()
    assert (
        second["notes_changed"] == 1
        and second["reviews_imported"] == 1
        and parser.calls == 2
    )
    current = session.execute(select(a.notes.c.source_id)).scalar_one()
    assert current != old
    assert session.execute(select(func.count()).select_from(a.revisions)).scalar() == 2
    rows = session.execute(select(a.reviews)).mappings().all()
    assert sum(r["source_id"] == old for r in rows) == 4
    assert sum(r["source_id"] == current for r in rows) == 1
    assert KnowledgeService(session).get_lexical("친구") is not None
    # Revert text: both source history and observed revision windows remain.
    adapter.notes[123] = note(modified=1700000300)
    adapter.reviews.append(review(BASE + 400000))
    service.sync()
    assert session.execute(select(func.count()).select_from(a.revisions)).scalar() == 3
    latest = session.execute(
        select(a.reviews.c.source_id).where(a.reviews.c.review_id == BASE + 400000)
    ).scalar_one()
    assert latest == old


def test_tags_decks_audio_suspension_and_missing(session, adapter, config):
    parser = CountingParser()
    service = AnkiSyncService(session, adapter, config, parser)
    service.sync()
    adapter.notes[123] = replace(adapter.notes[123], tags=("podcast",))
    adapter.cards[456] = replace(
        adapter.cards[456], deck="New deck", metadata={"queue": -1}
    )
    report = service.sync()
    assert parser.calls == 1 and report["notes_metadata_changed"] == 1
    states = {r["card_id"]: r for r in service.repository.rows(a.cards)}
    assert states[456]["state"] == "suspended" and states[456]["deck"] == "New deck"
    adapter.selected.clear()
    assert service.sync()["notes_out_of_scope"] == 1
    assert service.repository.rows(a.notes)[0]["state"] == "out_of_scope"
    adapter.notes.clear()
    adapter.cards.clear()
    assert service.sync()["notes_missing"] == 1
    assert service.repository.rows(a.notes)[0]["state"] == "missing"
    assert session.execute(select(func.count()).select_from(a.reviews)).scalar() == 4
    assert KnowledgeService(session).get_lexical("먹다") is not None


def test_failures_atomic_and_caller_rollback(session, adapter, config):
    service = AnkiSyncService(session, adapter, config)
    adapter.failure = True
    with pytest.raises(AnkiError):
        service.sync()
    assert KnowledgeService(session).list_items() == []
    adapter.failure = False
    adapter.reviews.append(replace(review(BASE + 20000), duration_ms=-1))
    with pytest.raises(AnkiError):
        service.sync()
    assert KnowledgeService(session).list_items() == []
    assert service.status()["last_success"] is None
    adapter.reviews.pop()
    service.sync()
    session.rollback()
    assert KnowledgeService(session).list_items() == []
    assert service.repository.rows(a.reviews) == []


def test_dry_run_never_writes_original(session, adapter, config):
    writes = []

    @event.listens_for(session.bind, "before_cursor_execute")
    def watch(_, __, statement, *___):
        if (
            statement.lstrip()
            .upper()
            .startswith(("INSERT", "UPDATE", "DELETE", "SAVEPOINT", "BEGIN"))
        ):
            writes.append(statement)

    parser = CountingParser()
    service = AnkiSyncService(session, adapter, config, parser)
    report = service.sync(dry_run=True)
    assert report["notes_created"] == 1 and report["reviews_imported"] == 4
    assert report["knowledge_created"] == {"lexical": 4, "grammar": 2, "chunk": 0}
    assert writes == []
    assert KnowledgeService(session).list_items() == []
    assert service.status()["last_success"] is None
    service.sync()
    report = service.sync(dry_run=True)
    assert report["notes_skipped"] == 1 and report["reviews_imported"] == 0


def test_individual_note_errors_and_invalid_mapping(session, adapter, config):
    adapter.notes[124] = note(124, text="", cards=(900,))
    adapter.cards[900] = card(900, 124)
    adapter.selected.add(124)
    result = AnkiSyncService(session, adapter, config).sync()
    assert result["notes_created"] == 2 and result["error_count"] == 0
    assert result["notes_anomalous"] == 1
    assert KnowledgeService(session).get_lexical("먹다") is not None
    adapter.notes[124] = replace(adapter.notes[124], fields={"Other": TEXT})
    with pytest.raises(ValueError, match="Invalid field mapping"):
        AnkiSyncService(session, adapter, config).sync()


def test_profile_identity_and_duplicate_conflicts(session, adapter, config):
    service = AnkiSyncService(session, adapter, config)
    adapter.reviews.append(adapter.reviews[0])
    report = service.sync()
    assert report["reviews_imported"] == 4 and report["reviews_skipped"] == 1
    adapter.reviews[0] = replace(adapter.reviews[0], rating=4)
    with pytest.raises(AnkiError, match="changed"):
        service.sync(full_reviews=True)
    adapter.profile = "Other"
    with pytest.raises(AnkiError, match="profile"):
        service.sync()


def test_optional_export_and_summary(session, adapter, config):
    service = AnkiSyncService(session, adapter, config)
    service.sync()
    knowledge = KnowledgeService(session)
    default = knowledge.export()
    assert all("anki" not in i for i in default["lexical"])
    enriched = knowledge.export(include_anki=True)
    eat = next(i for i in enriched["lexical"] if i["lemma"] == "먹다")
    assert eat["status"] == "unknown" and eat["anki"]["reviews"] == 4
    assert "anki_reviews" not in eat and eat["evidence_count"] == 1
    details = knowledge.export(include_anki=True, review_details=True)
    assert (
        len(next(i for i in details["lexical"] if i["lemma"] == "먹다")["anki_reviews"])
        == 4
    )
    assert default == knowledge.export()


def test_scale_1000_notes_40000_reviews(session, config):
    notes = [note(i, cards=(i * 2, i * 2 + 1)) for i in range(1000, 2000)]
    cards = [card(cid, n.note_id, cid % 2) for n in notes for cid in n.card_ids]
    reviews = [
        review(BASE + 10000 + i, c.card_id, (i % 4) + 1)
        for c in cards
        for i in range(20)
    ]
    adapter = FakeAdapter(notes, cards, reviews)
    parser = CountingParser()
    service = AnkiSyncService(session, adapter, config, parser)
    started = perf_counter()
    first = service.sync()
    elapsed = perf_counter() - started
    assert parser.calls == 1000 and first["reviews_imported"] == 40000
    assert len(KnowledgeService(session).list_items("lexical")) == 4
    second = service.sync()
    assert (
        parser.calls == 1000
        and second["notes_skipped"] == 1000
        and second["reviews_imported"] == 0
    )
    assert (
        session.execute(select(func.count()).select_from(a.reviews)).scalar() == 40000
    )
    print(
        f'Scale: 1000 notes, 2000 cards, 40000 reviews; first {elapsed:.3f}s, incremental {second["duration_seconds"]:.3f}s, 0 new Kiwi calls'
    )


def test_cli_sync_status_and_export(database, tmp_path, monkeypatch, capsys):
    from lute_korean_parser.anki import cli

    path = tmp_path / "anki.yml"
    path.write_text(
        """source_identity: fixture-source
profile: Fixture
mappings:
  Core Korean:
    korean_fields: [KO]
    translation_fields: [PT]
    metadata_fields: [NOTAS]
""",
        encoding="utf8",
    )
    fake = FakeAdapter([note()], [card(), card(789, ordinal=1)], [review()])
    monkeypatch.setattr(cli, "AnkiConnectSourceAdapter", lambda _: fake)
    args = ["--config", str(path), "--database", str(database.url.database)]
    cli.main(["sync", *args, "--dry-run"])
    assert json.loads(capsys.readouterr().out)["notes_created"] == 1
    with Session(database) as check:
        assert check.scalar(select(func.count()).select_from(a.notes)) == 0
    export = tmp_path / "knowledge.json"
    cli.main(["sync", *args, "--export", str(export)])
    assert json.loads(capsys.readouterr().out)["reviews_imported"] == 1
    assert any(
        i["anki"]["reviews"] == 1 for i in json.loads(export.read_text())["lexical"]
    )
    fake.failure = True  # status is purely local.
    cli.main(["status", *args])
    assert json.loads(capsys.readouterr().out)["last_success"]


def test_card_removed_mapping_changed_and_unknown_dimensions(session, adapter, config):
    parser = CountingParser()
    service = AnkiSyncService(session, adapter, config, parser)
    service.sync()
    adapter.cards.pop(789)
    adapter.notes[123] = replace(adapter.notes[123], card_ids=(456,))
    service.sync()
    assert (
        next(r for r in service.repository.rows(a.cards) if r["card_id"] == 789)[
            "state"
        ]
        == "missing"
    )
    assert parser.calls == 1
    # An explicit mapping change creates a new revision, even with identical text.
    adapter.notes[123] = replace(
        adapter.notes[123], fields={**adapter.notes[123].fields, "Sentence": TEXT}
    )
    changed = replace(
        config,
        mappings={"Core Korean": NoteTypeMapping(("Sentence",), ("PT",), ("NOTAS",))},
    )
    AnkiSyncService(session, adapter, changed, parser).sync()
    assert parser.calls == 2
    assert session.scalar(select(func.count()).select_from(a.revisions)) == 2
    for item in KnowledgeService(session).list_items():
        assert item["status"] == "unknown"
    exported = KnowledgeService(session).export()
    for item in exported["lexical"] + exported["grammar"]:
        assert all(skill["status"] is None for skill in item["dimensions"].values())


def test_two_profiles_same_ids_have_separate_events_shared_items(
    session, adapter, config
):
    first = AnkiSyncService(session, adapter, config)
    first.sync()
    second = AnkiSyncService(
        session, adapter, replace(config, source_identity="another-source")
    )
    second.sync()
    knowledge = KnowledgeService(session)
    lexical = knowledge.get_lexical("먹다")
    summary = knowledge.anki_summary(lexical["id"])
    assert summary["notes"] == 2 and summary["cards"] == 4 and summary["reviews"] == 8
    assert session.scalar(select(func.count()).select_from(a.reviews)) == 8
    assert (
        len({r["event_key"] for r in knowledge.list_anki_reviews(lexical["id"])}) == 8
    )


def test_anki_migration_through_real_lute_startup(tmp_path):
    from lute.app_factory import create_app
    from lute.db import db
    from sqlalchemy import text

    cfg = tmp_path / "config.yml"
    cfg.write_text(
        f"ENV: dev\nDBNAME: test_anki_migration.db\nDATAPATH: {tmp_path}/data\n"
    )
    for _ in range(2):
        app = create_app(str(cfg), extra_config={"TESTING": True})
        with app.app_context():
            assert (
                db.session.execute(
                    text(
                        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name LIKE 'korean_anki_%'"
                    )
                ).scalar()
                == 5
            )
            assert db.session.execute(text("PRAGMA foreign_key_check")).all() == []


def test_database_failure_rolls_back_entire_sync(session, adapter, config, database):
    from sqlalchemy.exc import OperationalError

    service = AnkiSyncService(session, adapter, config)

    def fail_reviews(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO korean_anki_reviews"):
            raise OperationalError(
                statement, parameters, RuntimeError("synthetic database failure")
            )

    event.listen(database, "before_cursor_execute", fail_reviews)
    try:
        with pytest.raises(OperationalError):
            service.sync()
    finally:
        event.remove(database, "before_cursor_execute", fail_reviews)
    assert session.scalar(select(func.count()).select_from(a.notes)) == 0
    assert session.scalar(select(func.count()).select_from(k.items)) == 0
    assert service.status()["last_success"] is None


def test_multiple_surfaces_do_not_multiply_review_counts(session, config):
    fake = FakeAdapter(
        [note(text="먹어요. 많이 먹었어요. 먹으면 먹고.")], [card(), card(789, ordinal=1)], [review()]
    )
    service = AnkiSyncService(session, fake, config)
    service.sync()
    knowledge = KnowledgeService(session)
    eat = knowledge.get_lexical("먹다")
    assert len(knowledge.list_occurrences(eat["id"])) == 4
    assert knowledge.anki_summary(eat["id"])["reviews"] == 1
    assert len(knowledge.list_anki_reviews(eat["id"])) == 1


def test_anki_sync_bookkeeping_changes_do_not_duplicate_reviews(
    session, adapter, config
):
    service = AnkiSyncService(session, adapter, config)
    service.sync()
    adapter.reviews = [replace(r, usn=42) for r in adapter.reviews]
    report = service.sync(full_reviews=True)
    assert report["reviews_imported"] == 0 and report["reviews_skipped"] == 4
    assert session.scalar(select(func.count()).select_from(a.reviews)) == 4
