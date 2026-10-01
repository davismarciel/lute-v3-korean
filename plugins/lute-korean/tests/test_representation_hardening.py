"""Sprint 4.5: canonical provenance, overlap and observed human evidence."""
import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from lute_korean_parser.knowledge.ingestion import KnowledgeIngestionService
from lute_korean_parser.knowledge.service import KnowledgeService
from lute_korean_parser.knowledge.representation import KnowledgeRepresentationService
from lute_korean_parser.knowledge.human import HumanEvidenceService
from lute_korean_parser.learner_state.engine import LearnerStateEngine

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def session(tmp_path):
    path = tmp_path / "staging.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE texts(TxID INTEGER PRIMARY KEY)")
    for name in [
        "20260930_01_korean_knowledge.sql",
        "20260930_03_korean_representation.sql",
    ]:
        conn.executescript((ROOT / "lute/db/schema/migrations" / name).read_text())
    conn.close()
    engine = create_engine(f"sqlite:///{path}")
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.mark.parametrize(
    "text",
    [
        "어제 친구가 오늘 게임하고 싶다고 했어요.",
        "어제 뭐 했어요?",
        "어제 친구를 만났어요.",
        "저는 어제 집에 있었어요.",
        "어제는 피곤했어요.",
    ],
)
def test_eoje_never_supplies_pronoun_evidence(session, text):
    ingestion = KnowledgeIngestionService(session)
    ingestion.ingest(text, text)
    knowledge = ingestion.knowledge
    assert knowledge.get_lexical("어제")
    pronoun = knowledge.get_lexical("저")
    if pronoun:
        assert not any(
            "어제" in o["surface"] for o in knowledge.list_occurrences(pronoun["id"])
        )
    assert all(
        text[o["start"] : o["end"]] == o["surface"]
        for o in knowledge.list_occurrences(knowledge.get_lexical("어제")["id"])
    )


@pytest.mark.parametrize(
    "text", ["재미있어요.", "재미있는데", "재미있었어요.", "진짜 재미있어요.", "이 게임은 재미있는데 너무 어려워요."]
)
def test_compound_does_not_supply_existential_evidence(session, text):
    ingestion = KnowledgeIngestionService(session)
    ingestion.ingest(text, text)
    assert ingestion.knowledge.get_lexical("재미있다")
    assert ingestion.knowledge.get_lexical("있다") is None


@pytest.mark.parametrize(
    "text", ["집에 있어요.", "시간이 있어요.", "친구가 있어요.", "사람이 있는데요.", "한국에 있었어요.", "재미가 있어요."]
)
def test_independent_existential_is_preserved(session, text):
    ingestion = KnowledgeIngestionService(session)
    ingestion.ingest(text, text)
    assert ingestion.knowledge.get_lexical("있다")
    assert not ingestion.knowledge.get_lexical("재미있다")


def test_raw_split_and_offsets_preserved(session):
    ingestion = KnowledgeIngestionService(session)
    result = ingestion.ingest("재미있는데", "raw")
    occurrence = ingestion.knowledge.list_source_occurrences(result["source_id"])[0]
    normalization = occurrence["metadata"]["lexical_normalization"]
    assert normalization["raw_heads"] == ["재미", "있다"]
    assert normalization["canonical_heads"] == ["재미있다"]
    assert normalization["rules"][0]["id"] == "ko.lexical.existential-compound.v1"
    assert occurrence["surface"] == "재미있는데"


def test_overlap_is_scoped_and_does_not_merge_or_delete(session):
    ingestion = KnowledgeIngestionService(session)
    result = ingestion.ingest("먹고 싶어요.", "desire")
    rep = KnowledgeRepresentationService(session)
    resolution = rep.resolve_effective_items(result["source_id"], 0, len("먹고 싶어요."))
    assert {i["identity"] for i in resolution["raw_items"]} == {"먹다", "싶다", "-고 싶다"}
    assert {i["identity"] for i in resolution["effective_items"]} == {"먹다", "-고 싶다"}
    assert resolution["suppressed_overlap"][0]["identity"] == "싶다"
    assert ingestion.knowledge.get_lexical("싶다")
    # Lexical-only region has no contained construction: never suppress globally.
    assert (
        rep.resolve_effective_items(result["source_id"], 3, 6)["suppressed_overlap"]
        == []
    )


def test_roles_manual_override_and_status_unchanged(session):
    ingestion = KnowledgeIngestionService(session)
    ingestion.ingest("스타로드 부산 서울 한국", "names")
    item = ingestion.knowledge.get_lexical("스타로드")
    rep = KnowledgeRepresentationService(session)
    assert rep.set_role(item["id"], "proper_noun")["role"] == "proper_noun"
    rep.set_role(item["id"], "unknown")
    assert rep.set_role(item["id"], "general", "kiwi")["role"] == "unknown"
    assert ingestion.knowledge.get_item(item["id"])["status"] == "unknown"


def event(item="먹다", index=0, **kwargs):
    return dict(
        item=item,
        dimension="reading",
        event_type="recognized",
        directness="direct",
        source_reference=f"human-calibration:{index}",
        context=f"Independent context {index}",
        occurred_at="2026-09-30T00:00:00+00:00",
        recorded_by="synthetic observer",
        **kwargs,
    )


def test_human_preview_idempotency_policy_and_skill_separation(session):
    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("먹다")
    knowledge.set_status(item["id"], "practicing", "reading")
    for index in range(3):
        for evidence_type in ("exposure", "recognized"):
            knowledge.record_evidence(
                item["id"],
                evidence_type,
                context=f"Independent context {index}",
                source_reference=f"prior:{index}",
                occurred_at=datetime(2026, 9, 30, tzinfo=timezone.utc),
            )
    before = LearnerStateEngine(session).inspect(
        "먹다", as_of=datetime(2026, 9, 30, 12, tzinfo=timezone.utc)
    )
    assert before["suggested_state"]["reading"]["status"] == "practicing"
    assert before["suggested_state"]["reading"]["confidence"] == "medium"
    service = HumanEvidenceService(session)
    document = {"events": [event(index=i) for i in range(8)]}
    assert service.preview(document)["writes"] == 0
    assert len(knowledge.list_evidence(item["id"])) == 6
    assert service.apply(document)["created"] == 8
    assert service.apply(document)["skipped"] == 8
    state = LearnerStateEngine(session).inspect(
        "먹다", as_of=datetime(2026, 9, 30, 12, tzinfo=timezone.utc)
    )
    assert state["suggested_state"]["reading"]["status"] == "consolidated"
    assert state["manual_state"]["reading"] == "practicing"
    assert state["suggested_state"]["listening"]["status"] == "unknown"
    assert state["suggested_state"]["production"]["status"] == "unknown"


@pytest.mark.parametrize(
    "changes",
    [
        {"dimension": "listening", "event_type": "produced"},
        {"occurred_at": "2026-09-30"},
        {"directness": "direct", "scope": "context"},
        {"item": "nonexistent"},
    ],
)
def test_human_invalid_input_writes_nothing(session, changes):
    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("먹다")
    payload = event()
    payload.update(changes)
    with pytest.raises(ValueError):
        HumanEvidenceService(session).apply(payload)
    assert knowledge.list_evidence(item["id"]) == []


def test_human_caller_rollback(session):
    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("먹다")
    session.commit()
    HumanEvidenceService(session).apply(event())
    session.rollback()
    assert knowledge.list_evidence(item["id"]) == []


def test_policy_file_is_frozen():
    from lute_korean_parser.learner_state.policy import LearnerStatePolicyV1

    assert (
        LearnerStatePolicyV1().fingerprint
        == "94819404fd433591b54a9cc1e5b132065c7f35bbe19bc1f88077dcfcef0f24f3"
    )
    assert (
        hashlib.sha256(
            (
                ROOT / "plugins/lute-korean/lute_korean_parser/learner_state/policy.py"
            ).read_bytes()
        ).hexdigest()
        == "7849d57654f21f617a403e1838c15b41e2ab1b22583a308b77b89d135569d8a6"
    )


@pytest.mark.parametrize("text", ["저는 학교에 가요.", "제가 해요.", "저도 좋아요.", "저보다 커요."])
def test_pronouns_are_not_canonicalized_as_adverb(session, text):
    ingestion = KnowledgeIngestionService(session)
    ingestion.ingest(text, text)
    assert ingestion.knowledge.get_lexical("저")
    assert not ingestion.knowledge.get_lexical("어제")


def test_human_misses_and_production_stay_in_observed_dimension(session):
    knowledge = KnowledgeService(session)
    knowledge.get_or_create_grammar("-는데")
    knowledge.get_or_create_lexical("먹다")
    payload = event("-는데")
    payload["event_type"] = "missed"
    HumanEvidenceService(session).apply(payload)
    state = LearnerStateEngine(session).inspect(
        "-는데", as_of=datetime(2026, 9, 30, 12, tzinfo=timezone.utc)
    )
    assert state["suggested_state"]["reading"]["status"] == "practicing"
    assert state["suggested_state"]["listening"]["status"] == "unknown"
    payload = event()
    payload.update(event_type="produced", dimension="production")
    HumanEvidenceService(session).apply(payload)
    state = LearnerStateEngine(session).inspect(
        "먹다", as_of=datetime(2026, 9, 30, 12, tzinfo=timezone.utc)
    )
    assert state["suggested_state"]["reading"]["status"] == "unknown"
    assert state["suggested_state"]["production"]["status"] != "unknown"


def test_human_conflicting_event_rolls_back_entire_import(session):
    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("먹다")
    service = HumanEvidenceService(session)
    payload = event(event_key="human:one")
    service.apply(payload)
    changed = event(event_key="human:one")
    changed["context"] = "Changed observation"
    with pytest.raises(ValueError):
        service.apply({"events": [event(index=9), changed]})
    assert len(knowledge.list_evidence(item["id"])) == 1


def test_cli_preview_is_read_only_and_no_calibration_is_invented(
    session, tmp_path, capsys
):
    from lute_korean_parser.knowledge.hardening_cli import evidence_main, knowledge_main

    knowledge = KnowledgeService(session)
    knowledge.get_or_create_lexical("먹다")
    session.commit()
    path = Path(session.bind.url.database)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    file = tmp_path / "human.json"
    file.write_text(__import__("json").dumps(event()))
    evidence_main(["preview", str(file), "--database", str(path)])
    assert '"writes": 0' in capsys.readouterr().out
    knowledge_main(["audit-integrity", "--database", str(path)])
    assert before == hashlib.sha256(path.read_bytes()).hexdigest()
    evidence_main(["preview-human-calibration"])
    assert '"candidates": []' in capsys.readouterr().out


def test_relationship_self_guard_and_idempotency(session):
    knowledge = KnowledgeService(session)
    component = knowledge.get_or_create_lexical("싶다")
    target = knowledge.get_or_create_grammar("-고 싶다")
    rep = KnowledgeRepresentationService(session)
    with pytest.raises(ValueError):
        rep.relate(component["id"], component["id"])
    rep.relate(component["id"], target["id"])
    rep.relate(component["id"], target["id"])
    assert len(rep.list_relations()) == 1


@pytest.mark.parametrize(
    "text,name",
    ["저는 카니예 웨스트예요.|카니예 웨스트".split("|"), "캡틴 아메리카를 좋아해요.|캡틴 아메리카".split("|")],
)
def test_multiword_proper_name_has_one_complete_occurrence(session, text, name):
    ingestion = KnowledgeIngestionService(session)
    ingestion.ingest(text, "multiword")
    item = ingestion.knowledge.get_lexical(name)
    occurrences = ingestion.knowledge.list_occurrences(item["id"])
    assert len(occurrences) == 1
    occurrence = occurrences[0]
    assert occurrence["surface"] == name
    assert text[occurrence["start"] : occurrence["end"]] == name
    assert len(ingestion.knowledge.list_evidence(item["id"])) == 1
    assert KnowledgeRepresentationService(session).audit_integrity() == []
