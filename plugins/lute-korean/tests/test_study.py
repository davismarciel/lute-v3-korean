"""Explicit study lifecycle through its public service boundary."""
from pathlib import Path
import pytest
from test_representation_hardening import session as base_session
from lute_korean_parser.ci.adapters import adapt_content
from lute_korean_parser.knowledge.service import KnowledgeService


@pytest.fixture
def session(tmp_path):
    generator = base_session.__wrapped__(tmp_path)
    value = next(generator)
    raw = value.connection().connection.driver_connection
    raw.commit()
    raw.executescript(
        (
            Path(__file__).resolve().parents[3]
            / "lute/db/schema/migrations/20260930_04_korean_study.sql"
        ).read_text()
    )
    yield value
    generator.close()


def test_start_is_explicit_and_does_not_claim_exposure_or_recognition(session):
    from lute_korean_parser.study.service import StudySessionService

    service = StudySessionService(session)
    candidate = adapt_content("먹어요.\n가요.", name="dialogue")
    first = service.start(candidate, "reading", request_key="start-one")
    assert (
        service.start(candidate, "reading", request_key="start-one")["id"]
        == first["id"]
    )
    assert service.show(first["id"])["status"] == "started"
    assert KnowledgeService(session).list_items() == []
    assert first["content_hash"] == candidate.original_hash


def test_partial_consumption_only_exposes_selected_segment_and_restudy_reuses_source(
    session,
):
    from lute_korean_parser.study.service import StudySessionService

    service = StudySessionService(session)
    knowledge = KnowledgeService(session)
    candidate = adapt_content("먹어요.\n가요.", name="episode", kind="tprs")
    first = service.start(candidate, "listening_with_transcript", "first")
    partial = service.consume(first["id"], 0, 0, completed=False)
    assert partial["status"] == "partial"
    assert knowledge.get_lexical("가다") is None
    eat = knowledge.get_lexical("먹다")
    events = knowledge.list_evidence(eat["id"])
    assert len(events) == 1 and events[0]["evidence_type"] == "exposure"
    assert events[0]["dimension"] == "reading"
    again = service.consume(first["id"], 0, 0, completed=False)
    assert again["exposure_count"] == 1
    completed = service.consume(first["id"], 0, 1)
    assert completed["status"] == "completed"
    assert (
        service.consume(first["id"], 0, 1)["exposure_count"]
        == completed["exposure_count"]
    )
    second = service.start(candidate, "reading", "second")
    second = service.consume(second["id"], 0, 0)
    assert second["consumed"][0]["source_id"] == first_source(service, first["id"])
    assert len(knowledge.list_evidence(eat["id"])) == 2
    assert all(
        e["evidence_type"] == "exposure" for e in knowledge.list_evidence(eat["id"])
    )
    assert knowledge.get_item(eat["id"])["status"] == "unknown"


def first_source(service, sid):
    return service.show(sid)["consumed"][0]["source_id"]


@pytest.mark.parametrize(
    "activity,transcript_read", [("listening", False), ("mixed", False)]
)
def test_no_lexical_or_listening_recognition_is_invented_without_transcript_reading(
    session, activity, transcript_read
):
    from lute_korean_parser.study.service import StudySessionService

    service = StudySessionService(session)
    s = service.start(
        adapt_content("먹어요."),
        activity,
        "only-provenance",
        transcript_read=transcript_read,
    )
    result = service.consume(s["id"])
    assert len(result["consumed"]) == 1
    assert result["exposure_count"] == 0
    assert KnowledgeService(session).list_items() == []


def test_caller_can_rollback_entire_study_and_invalid_range_has_no_effect(session):
    from lute_korean_parser.study.service import StudySessionService

    service = StudySessionService(session)
    s = service.start(adapt_content("먹어요."), "reading", "rollback")
    with pytest.raises(ValueError):
        service.consume(s["id"], 0, 4)
    assert service.show(s["id"])["status"] == "started"
    service.consume(s["id"])
    session.rollback()
    assert service.list() == []
    assert KnowledgeService(session).list_items() == []


def test_session_observation_is_explicit_idempotent_skill_separated_and_keeps_manual_state(
    session,
):
    from lute_korean_parser.study.service import StudySessionService
    from lute_korean_parser.learner_state.engine import LearnerStateEngine
    from datetime import datetime, timezone

    service = StudySessionService(session)
    k = KnowledgeService(session)
    item = k.get_or_create_lexical("먹다")
    k.set_status(item["id"], "practicing", "reading")
    s = service.start(adapt_content("먹어요."), "reading", "observation")
    doc = {
        "item": "먹다",
        "kind": "lexical",
        "dimension": "reading",
        "event_type": "recognized",
        "directness": "direct",
        "source_reference": "study:" + s["id"],
        "context": "먹어요.",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "recorded_by": "learner",
    }
    assert service.record_observation(s["id"], doc)["created"] == 1
    assert service.record_observation(s["id"], doc)["skipped"] == 1
    assert len(service.show(s["id"])["observation_ids"]) == 1
    state = LearnerStateEngine(session).inspect("먹다")
    assert state["manual_state"]["reading"] == "practicing"
    assert state["suggested_state"]["listening"]["status"] == "unknown"
    with pytest.raises(ValueError):
        service.record_observation(s["id"], dict(doc, event_type="produced"))


def test_workspace_uses_fresh_learner_state_after_explicit_manual_save(session):
    from lute_korean_parser.study.workspace import KoreanStudyWorkspace

    k = KnowledgeService(session)
    item = k.get_or_create_lexical("먹다")
    workspace = KoreanStudyWorkspace(session)
    candidate = adapt_content("먹어요.")
    before = workspace.analyze(candidate)
    assert before["lexical"]["items"][0]["bucket"] == "unassessed"
    workspace.assess(item["id"], "reading", "practicing")
    after = workspace.analyze(candidate)
    assert after["lexical"]["items"][0]["bucket"] == "familiar"
    assert (
        before["learner_snapshot"]["input_fingerprint"]
        != after["learner_snapshot"]["input_fingerprint"]
    )
    assert (
        before["learner_snapshot"]["evidence_fingerprint"]
        == after["learner_snapshot"]["evidence_fingerprint"]
    )
    assert before["policy"]["fingerprint"] == after["policy"]["fingerprint"]


def test_teacher_exports_are_bounded_distinguish_states_and_do_not_dump_reviews(
    session,
):
    from lute_korean_parser.study.workspace import KoreanStudyWorkspace, markdown_export
    from lute_korean_parser.study.service import StudySessionService
    import json

    k = KnowledgeService(session)
    for i in range(30):
        k.get_or_create_chunk("단어 " + str(i))
    workspace = KoreanStudyWorkspace(session)
    document = workspace.export_learner("compact")
    assert len(document["items"]) == 20 and document["omitted_items"] == 10
    assert (
        "manual_state" in document["items"][0]
        and "suggested_state" in document["items"][0]
    )
    assert "raw_reviews" not in json.dumps(document)
    report = workspace.analyze(adapt_content("먹고 싶어요."))
    compact = workspace.export_content(report, include_korean=True)
    assert compact["korean_segments"][0]["text"] == "먹고 싶어요."
    assert "Manual, suggested and observed" in markdown_export(document)
    assert StudySessionService(session).list() == []


def test_cli_requires_explicit_writable_mode_and_roundtrips_sessions(
    tmp_path, session, capsys
):
    from lute_korean_parser.study.cli import main

    path = tmp_path / "staging.db"
    session.commit()
    text = tmp_path / "content.txt"
    text.write_text("먹어요.")
    with pytest.raises(SystemExit):
        main(["start", str(text), "--database", str(path)])
    main(
        [
            "start",
            str(text),
            "--database",
            str(path),
            "--writable",
            "--request-key",
            "cli-one",
        ]
    )
    import json

    started = json.loads(capsys.readouterr().out)
    main(["complete", started["id"], "--database", str(path), "--writable"])
    completed = json.loads(capsys.readouterr().out)
    assert completed["status"] == "completed" and completed["exposure_count"] == 1
    main(["list", "--database", str(path)])
    assert json.loads(capsys.readouterr().out)[0]["id"] == started["id"]


def test_completed_subset_is_immutable_and_reopening_does_not_duplicate_exposure(
    session,
):
    from lute_korean_parser.study.service import StudySessionService

    service = StudySessionService(session)
    s = service.start(adapt_content("먹어요.\n가요."), "reading", "subset")
    done = service.consume(s["id"], 0, 0)
    with pytest.raises(ValueError):
        service.consume(s["id"], 0, 1)
    assert service.show(s["id"])["exposure_count"] == done["exposure_count"]
    assert KnowledgeService(session).get_lexical("가다") is None


def test_anki_is_never_initialized_or_contacted_by_learner_overview(session):
    from lute_korean_parser.study.workspace import KoreanStudyWorkspace
    from sqlalchemy import event

    k = KnowledgeService(session)
    for word in ["먹다", "가다", "있다", "좋아하다"]:
        k.get_or_create_lexical(word)
    verbs = []
    connection = session.connection()

    def observe(conn, cursor, statement, parameters, context, many):
        verbs.append(statement.strip().split()[0].upper())

    event.listen(connection, "before_cursor_execute", observe)
    try:
        view = KoreanStudyWorkspace(session).overview()
        assert len(view["items"]) == 4
        assert set(verbs) <= {"BEGIN", "SELECT", "PRAGMA"}
        assert verbs.count("SELECT") <= 12
    finally:
        event.remove(connection, "before_cursor_execute", observe)
