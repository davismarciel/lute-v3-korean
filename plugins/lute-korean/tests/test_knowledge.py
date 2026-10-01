"""Persistent acquisition behavior, real Kiwi and explicit detector policy."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine, event, select, func
from sqlalchemy.orm import Session
from lute_korean_parser.parser import KoreanParser
from lute_korean_parser.knowledge import tables as t
from lute_korean_parser.knowledge.service import KnowledgeService, STATUSES
from lute_korean_parser.knowledge.ingestion import (
    KnowledgeIngestionService,
    LexicalPolicy,
)
from lute_korean_parser.knowledge.detectors import detect_patterns, DEFAULT_DETECTORS
from lute_korean_parser.knowledge.cli import main

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "lute/db/schema/migrations/20260930_01_korean_knowledge.sql"
SENTENCES = [
    ("시간이 있으면 공부할 거예요.", {"시간", "있다", "공부하다"}, {"-(으)면", "-(으)ㄹ 거예요"}),
    ("오늘은 피곤해서 일찍 잘 거예요.", {"오늘", "피곤하다", "일찍", "자다"}, {"-아/어서", "-(으)ㄹ 거예요"}),
    ("한국에 가면 많이 먹을 거예요.", {"한국", "가다", "많이", "먹다"}, {"-(으)면", "-(으)ㄹ 거예요"}),
    ("죄송한데 잘 못 알아들었어요.", {"죄송하다", "잘", "못", "알아듣다"}, {"-는데"}),
    ("이거 먹어 보고 싶은데 많이 매워요?", {"이거", "먹다", "보다", "싶다", "맵다"}, {"-고 싶다", "-는데"}),
    ("양고기 집에 가서 양고기를 먹었어요.", {"양고기", "집", "가다", "먹다"}, {"-아/어서"}),
]


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "knowledge.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE texts (TxID INTEGER PRIMARY KEY)")
    conn.executescript(MIGRATION.read_text(encoding="utf8"))
    conn.close()
    engine = create_engine(f"sqlite:///{path}")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    yield engine
    engine.dispose()


@pytest.fixture
def session(database):
    with Session(database) as session:
        yield session


@pytest.mark.parametrize(
    "forms,lemma",
    [
        (["먹어요", "먹었어요", "먹으면", "먹어서", "먹고"], "먹다"),
        (["가요", "갔어요", "가면", "가서"], "가다"),
        (["한국", "한국에", "한국은", "한국에서"], "한국"),
        (["피곤해요", "피곤해서"], "피곤하다"),
    ],
)
def test_lexical_identity(session, forms, lemma):
    ingestion = KnowledgeIngestionService(session)
    for i, form in enumerate(forms):
        ingestion.ingest(form, f"identity:{i}")
    service = ingestion.knowledge
    item = service.get_lexical(lemma)
    assert item["status"] == "unknown"
    assert service.list_surface_forms(item["id"]) == sorted(forms)
    assert len(service.list_evidence(item["id"])) == len(forms)
    assert [i["identity"] for i in service.list_items("lexical")] == [lemma]
    assert all(o["surface"] in forms for o in service.list_occurrences(item["id"]))


@pytest.mark.parametrize("text,lexical,grammar", SENTENCES)
def test_required_sentences(session, text, lexical, grammar):
    ingestion = KnowledgeIngestionService(session)
    ingestion.ingest(text, "sentence")
    service = ingestion.knowledge
    assert lexical <= {i["identity"] for i in service.list_items("lexical")}
    assert grammar == {i["identity"] for i in service.list_items("grammar")}
    for item in service.list_items():
        assert item["status"] == "unknown"
        for occurrence in service.list_occurrences(item["id"]):
            assert (
                text[occurrence["start"] : occurrence["end"]] == occurrence["surface"]
            )
            assert occurrence["context"] == text
    if "먹었어요" in text:
        metadata = service.list_occurrences(service.get_lexical("먹다")["id"])[0][
            "metadata"
        ]
        assert any(m["form"] == "었" and m["pos"] == "EP" for m in metadata["morphemes"])


@pytest.mark.parametrize(
    "index,text,expected",
    [
        (0, "가면 먹어요.", True),
        (0, "가면을 썼어요.", False),
        (1, "집에 가서 먹어요.", True),
        (1, "서점에서 책을 봐요.", False),
        (2, "죄송한데 기다려 주세요.", True),
        (2, "그런데 오늘은 쉬어요.", False),
        (3, "먹고 싶어요.", True),
        (3, "먹고. 싶어요.", False),
        (3, "먹고\n싶어요.", False),
        (3, "먹고 있어요.", False),
        (4, "갈 거예요.", True),
        (4, "먹을 것이 있어요.", False),
        (4, "먹을. 거예요.", False),
        (4, "먹을\n거예요.", False),
    ],
)
def test_independent_detectors(index, text, expected):
    analysis = KoreanParser().analyze(text)
    assert bool(DEFAULT_DETECTORS[index].detect(analysis)) == expected


def test_policy_and_particle_metadata(session):
    ingestion = KnowledgeIngestionService(session, detectors=())
    ingestion.ingest("한국에 가면 먹어요.", "particles")
    service = ingestion.knowledge
    assert service.list_items("grammar") == []
    occurrence = service.list_occurrences(service.get_lexical("한국")["id"])[0]
    assert any(
        m["form"] == "에" and m["pos"] == "JKB"
        for m in occurrence["metadata"]["morphemes"]
    )
    assert service.find_item("grammar", "에") is None
    projected = KnowledgeIngestionService(
        session, lexical_policy=LexicalPolicy(())
    ).preview("거예요")
    assert "거" in projected["lexical"] and "이다" in projected["lexical"]


def test_reprocessing_and_status_preservation(session):
    ingestion = KnowledgeIngestionService(session)
    text = SENTENCES[2][0]
    first = ingestion.ingest(text, "revision:1")
    service = ingestion.knowledge
    go = service.get_lexical("가다")
    condition = service.find_item("grammar", "-(으)면")
    service.set_status(go["id"], "consolidated")
    service.set_status(condition["id"], "practicing")
    before = service.export()
    assert ingestion.ingest(text, "revision:1") == first
    assert service.export() == before
    ingestion.ingest("시간이 있으면 친구랑 같이 갈 거예요.", "revision:2")
    assert service.get_lexical("가다") == dict(go, status="consolidated")
    assert service.find_item("grammar", "-(으)면") == dict(condition, status="practicing")
    assert len(service.list_evidence(go["id"])) == 2
    assert service.list_surface_forms(go["id"]) == ["가면", "갈"]
    ingestion.ingest(text, "revision:1", dimension="listening")
    assert len(service.list_evidence(go["id"])) == 3
    assert service.get_lexical("가다")["status"] == "consolidated"


def test_changed_source_is_explicit_and_atomic(session):
    ingestion = KnowledgeIngestionService(session)
    ingestion.ingest("먹어요.", "immutable")
    session.commit()
    before = ingestion.knowledge.export()
    with pytest.raises(ValueError, match="revision"):
        ingestion.ingest("가요.", "immutable")
    assert ingestion.knowledge.export() == before
    assert ingestion.knowledge.get_lexical("가다") is None
    ingestion.ingest("가요.", "immutable:v2")
    assert ingestion.knowledge.get_lexical("가다") is not None


def test_partial_ingestion_rolls_back(session, monkeypatch):
    ingestion = KnowledgeIngestionService(session)
    session.commit()

    def fail(_):
        raise RuntimeError("write failed")

    monkeypatch.setattr(ingestion.knowledge, "get_or_create_grammar", fail)
    with pytest.raises(RuntimeError):
        ingestion.ingest(SENTENCES[2][0], "failure")
    assert ingestion.knowledge.list_items() == []
    assert session.execute(select(func.count()).select_from(t.sources)).scalar() == 0
    assert (
        session.execute(select(func.count()).select_from(t.occurrences)).scalar() == 0
    )


def test_reload_manual_evidence_and_dimensions(database):
    with Session(database) as session:
        service = KnowledgeService(session)
        item = service.get_or_create_lexical("먹다")
        service.set_status(item["id"], "practicing")
        service.set_status(item["id"], "consolidated", "reading")
        evidence = service.record_evidence(
            item["id"],
            "recognized",
            dimension="listening",
            source_type="podcast",
            source_reference="episode:1",
            surface="먹었어요",
            context="많이 먹었어요.",
            occurred_at=datetime(2026, 9, 30, tzinfo=timezone.utc),
            metadata={"position_seconds": 42},
            event_key="podcast:event:1",
        )
        session.commit()
    with Session(database) as session:
        service = KnowledgeService(session)
        assert service.get_lexical("먹다") == dict(item, status="practicing")
        events = service.list_evidence(item["id"])
        assert events[0]["id"] == evidence["id"]
        assert events[0]["surface"] == "먹었어요"
        assert events[0]["metadata"] == {"position_seconds": 42}
        entry = service.export()["lexical"][0]
        assert entry["dimensions"]["reading"]["status"] == "consolidated"
        assert entry["dimensions"]["listening"] == {"status": None, "evidence_count": 1}
        assert entry["status"] == "practicing"


@pytest.mark.parametrize("status", sorted(STATUSES))
def test_manual_status_only(session, status):
    service = KnowledgeService(session)
    item = service.get_or_create_lexical("먹다")
    service.set_status(item["id"], status)
    for _ in range(12):
        service.record_evidence(item["id"], "exposure")
    assert service.get_item(item["id"])["status"] == status


def test_chunk_crud_and_occurrence(session):
    ingestion = KnowledgeIngestionService(session)
    ingestion.ingest(SENTENCES[0][0], "chunk-text")
    service = ingestion.knowledge
    source = service.ensure_source("manual", "chunk-text", SENTENCES[0][0])
    chunk = service.get_or_create_chunk("시간이 있으면")
    assert service.find_chunk("시간이 있으면") == chunk
    assert service.get_or_create_chunk("시간이 있으면") == chunk
    occurrence = service.associate_occurrence(
        chunk["id"], source["id"], 0, 7, 0, len(source["content"])
    )
    service.record_evidence(
        chunk["id"], "manual_confirmation", occurrence_id=occurrence["id"]
    )
    assert service.list_surface_forms(chunk["id"]) == ["시간이 있으면"]
    assert service.list_evidence(chunk["id"])[0]["context"] == source["content"]
    service.update_chunk(chunk["id"], status="consolidated")
    assert service.list_chunks()[0]["status"] == "consolidated"
    service.delete_chunk(chunk["id"])
    assert service.list_chunks() == []
    assert service.get_lexical("있다") is not None
    assert service.find_item("grammar", "-(으)면") is not None
    assert (
        session.execute(
            select(func.count())
            .select_from(t.evidence)
            .where(t.evidence.c.item_id == chunk["id"])
        ).scalar()
        == 0
    )


def test_event_idempotency_and_relationship_validation(session):
    service = KnowledgeService(session)
    item = service.get_or_create_chunk("잘 모르겠어요")
    first = service.record_evidence(item["id"], "recognized", event_key="manual:1")
    assert (
        service.record_evidence(item["id"], "recognized", event_key="manual:1") == first
    )
    with pytest.raises(ValueError, match="different evidence"):
        service.record_evidence(item["id"], "missed", event_key="manual:1")
    source = service.ensure_source("manual", "chunk", "잘 모르겠어요")
    occurrence = service.associate_occurrence(
        item["id"], source["id"], 0, len(source["content"])
    )
    other = service.get_or_create_lexical("먹다")
    with pytest.raises(ValueError, match="associated"):
        service.record_evidence(other["id"], "exposure", occurrence_id=occurrence["id"])
    with pytest.raises(ValueError, match="source"):
        service.record_evidence(
            item["id"], "exposure", occurrence_id=occurrence["id"], source_type="anki"
        )


@pytest.mark.parametrize(
    "operation",
    [
        lambda s, i: s.set_status(i, "known"),
        lambda s, i: s.record_evidence(i, "seen"),
        lambda s, i: s.record_evidence(i, "exposure", dimension="all"),
        lambda s, i: s.record_evidence(i, "exposure", source_type="other"),
        lambda s, i: s.record_evidence(i, "exposure", occurred_at=datetime.now()),
        lambda s, i: s.record_evidence(i, "exposure", metadata={"blob": "x" * 9000}),
        lambda s, i: s.get_or_create_chunk(" "),
    ],
)
def test_invalid_values(session, operation):
    service = KnowledgeService(session)
    item = service.get_or_create_lexical("먹다")
    with pytest.raises(ValueError):
        operation(service, item["id"])


def test_export_stability_and_private_data(session):
    ingestion = KnowledgeIngestionService(session)
    ingestion.ingest(SENTENCES[2][0], "export")
    service = ingestion.knowledge
    service.get_or_create_chunk("시간이 있으면")
    first = service.export()
    assert first == json.loads(json.dumps(first, ensure_ascii=False))
    assert first["schema_version"] == 1 and first["language"] == "ko"
    assert {e["lemma"] for e in first["lexical"]} == {"한국", "가다", "많이", "먹다"}
    assert all(e["id"] and e["evidence_count"] == 1 for e in first["lexical"])
    assert "content_hash" not in json.dumps(first) and "morphemes" not in json.dumps(
        first
    )
    session.commit()
    assert service.export() == first


def test_diagnostic_has_no_db_and_explicit_persistence(database, capsys, tmp_path):
    main([SENTENCES[2][0]])
    output = capsys.readouterr().out
    assert "LEXICAL\n한국\n가다\n많이\n먹다" in output
    assert "-(으)면" in output
    assert not (tmp_path / "unexpected.db").exists()
    path = Path(database.url.database)
    export = tmp_path / "export.json"
    main(
        [
            SENTENCES[2][0],
            "--persist",
            "--database",
            str(path),
            "--source-reference",
            "cli:1",
            "--export",
            str(export),
        ]
    )
    first = json.loads(export.read_text(encoding="utf8"))
    main(
        [
            SENTENCES[2][0],
            "--persist",
            "--database",
            str(path),
            "--source-reference",
            "cli:1",
            "--export",
            str(export),
        ]
    )
    assert json.loads(export.read_text(encoding="utf8")) == first
    with pytest.raises(SystemExit):
        main(["가요", "--persist"])
    with pytest.raises(SystemExit):
        main(["가요", "--database", str(path)])


def test_transcript_analyzed_once_and_reprocessing(session):
    real = KoreanParser()
    calls = []

    def analyze(text):
        calls.append(text)
        return real.analyze(text)

    ingestion = KnowledgeIngestionService(
        session, parser=SimpleNamespace(analyze=analyze)
    )
    text = "\n".join(SENTENCES[i % 6][0] for i in range(200))
    started = perf_counter()
    first = ingestion.ingest(text, "transcript:200")
    elapsed = perf_counter() - started
    assert len(calls) == 1
    assert len(first["occurrence_ids"]) > 900
    assert ingestion.ingest(text, "transcript:200") == first
    assert len(calls) == 2
    assert len(ingestion.knowledge.list_items("lexical")) < 40
    print(
        f'200-line transcript: {len(text)} characters, {len(first["occurrence_ids"])} occurrences, {elapsed:.3f}s'
    )


def test_existing_database_migration_and_constraints(tmp_path):
    from lute.db.setup.migrator import SqliteMigrator

    migrations = tmp_path / "migrations"
    repeatable = tmp_path / "repeatable"
    migrations.mkdir()
    repeatable.mkdir()
    (migrations / MIGRATION.name).write_text(MIGRATION.read_text(encoding="utf8"))
    conn = sqlite3.connect(tmp_path / "existing.db")
    conn.executescript(
        """
    PRAGMA foreign_keys=ON;
    CREATE TABLE _migrations(filename TEXT PRIMARY KEY);
    CREATE TABLE texts(TxID INTEGER PRIMARY KEY);
    CREATE TABLE words(WoID INTEGER PRIMARY KEY, WoStatus INTEGER);
    INSERT INTO texts VALUES (1);
    INSERT INTO words VALUES (1, 4);
    """
    )
    migrator = SqliteMigrator(str(migrations), str(repeatable))
    assert migrator.has_migrations(conn)
    migrator.do_migration(conn)
    assert not migrator.has_migrations(conn)
    migrator.do_migration(conn)
    assert conn.execute("SELECT * FROM words").fetchall() == [(1, 4)]
    assert conn.execute("SELECT * FROM texts").fetchall() == [(1,)]
    assert conn.execute("SELECT COUNT(*) FROM _migrations").fetchone() == (1,)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO korean_knowledge_items VALUES ('x','lexical','먹다','known')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO korean_knowledge_dimensions VALUES ('missing','reading','unknown')"
        )
    conn.rollback()
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    conn.close()


def test_item_types_coexist_and_source_types_supported(session):
    service = KnowledgeService(session)
    lexical = service.get_or_create_lexical("가다")
    chunk = service.get_or_create_chunk("가다")
    assert lexical["id"] != chunk["id"]
    for source_type in [
        "lute_text",
        "tprs",
        "anki",
        "conversation",
        "podcast",
        "manual",
    ]:
        service.record_evidence(
            lexical["id"],
            "manual_confirmation",
            source_type=source_type,
            source_reference="test",
        )
    assert len(service.list_evidence(lexical["id"])) == 6


def test_occurrence_validation_and_small_metadata(session):
    service = KnowledgeService(session)
    item = service.get_or_create_chunk("한국에")
    source = service.ensure_source("manual", "source", "한국에 가면")
    for start, end in [(-1, 2), (0, 100), (2, 2)]:
        with pytest.raises(ValueError):
            service.associate_occurrence(item["id"], source["id"], start, end)
    with pytest.raises(ValueError):
        service.associate_occurrence(item["id"], source["id"], 0, 3, context_start=1)
    assert (
        session.execute(select(func.count()).select_from(t.occurrences)).scalar() == 0
    )


def test_ingestion_does_not_commit_callers_transaction(database):
    with Session(database) as session:
        ingestion = KnowledgeIngestionService(session)
        ingestion.ingest(SENTENCES[2][0], "rollback")
        assert ingestion.knowledge.get_lexical("가다") is not None
        session.rollback()
    with Session(database) as session:
        assert KnowledgeService(session).list_items() == []
        assert (
            session.execute(select(func.count()).select_from(t.sources)).scalar() == 0
        )


def test_file_diagnostic_preserves_original_crlf(database, tmp_path):
    transcript = tmp_path / "transcript.txt"
    text = "한국에 가면 많이 먹을 거예요.\r\n먹었어요.\r\n"
    transcript.write_bytes(text.encode("utf8"))
    main(
        [
            "--file",
            str(transcript),
            "--persist",
            "--database",
            str(database.url.database),
            "--source-reference",
            "crlf",
        ]
    )
    with Session(database) as session:
        source = session.execute(
            select(t.sources.c.content).where(t.sources.c.reference == "crlf")
        ).scalar_one()
        assert source == text


def test_explicit_evidence_timestamp_conflict(session):
    service = KnowledgeService(session)
    item = service.get_or_create_lexical("먹다")
    service.record_evidence(
        item["id"],
        "recognized",
        occurred_at=datetime(2026, 9, 30, tzinfo=timezone.utc),
        event_key="timestamp",
    )
    with pytest.raises(ValueError, match="different evidence"):
        service.record_evidence(
            item["id"],
            "recognized",
            occurred_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            event_key="timestamp",
        )


def test_dialogue_transcript(session):
    transcript = Path(__file__).with_name("fixtures") / "korean_dialogue.txt"
    text = transcript.read_text(encoding="utf8")
    assert len(text.splitlines()) == 64
    started = perf_counter()
    ingestion = KnowledgeIngestionService(session)
    result = ingestion.ingest(text, "manual:dialogue:1")
    elapsed = perf_counter() - started
    assert len(result["occurrence_ids"]) > 300
    assert ingestion.knowledge.get_lexical("먹다") is not None
    assert ingestion.knowledge.get_lexical("가다") is not None
    assert ingestion.knowledge.get_lexical("피곤하다") is not None
    assert all(i["status"] == "unknown" for i in ingestion.knowledge.list_items())
    print(
        f'64-line dialogue: {len(text)} characters, {len(result["occurrence_ids"])} occurrences, {elapsed:.3f}s'
    )
