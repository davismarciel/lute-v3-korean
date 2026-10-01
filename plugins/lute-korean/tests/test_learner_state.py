"""Learner suggestions through public services; no Anki/Desktop dependency."""
from datetime import datetime, timezone
from test_anki import database, session  # noqa: F401
from lute_korean_parser.knowledge.service import KnowledgeService
from lute_korean_parser.learner_state.engine import LearnerStateEngine

NOW = datetime(2026, 9, 30, tzinfo=timezone.utc)


def test_exposure_is_presented_without_inventing_other_skills(session):
    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("먹다")
    for index in range(2):
        knowledge.record_evidence(
            item["id"], "exposure", context=f"Context {index}", occurred_at=NOW
        )
    state = LearnerStateEngine(session).inspect("먹다", as_of=NOW)
    assert state["suggested_state"]["reading"]["status"] == "presented"
    assert state["suggested_state"]["listening"]["status"] == "unknown"
    assert state["suggested_state"]["production"]["status"] == "unknown"
    assert knowledge.get_item(item["id"])["status"] == "unknown"


def test_direct_recognition_across_contexts_can_consolidate_and_preserves_manual(
    session,
):
    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("먹다")
    knowledge.set_status(item["id"], "practicing", "reading")
    for index in range(5):
        knowledge.record_evidence(
            item["id"],
            "recognized",
            context=f"Independent context {index}",
            source_reference=f"source:{index}",
            occurred_at=NOW,
            metadata={"directness": "direct", "scope": "item"},
        )
    state = LearnerStateEngine(session).inspect("먹다", as_of=NOW)
    assert state["suggested_state"]["reading"]["status"] == "consolidated"
    assert state["manual_state"]["reading"] == "practicing"
    assert knowledge.get_item(item["id"])["status"] == "unknown"
    assert state["suggested_state"]["production"]["status"] == "unknown"


import pytest
from datetime import timedelta
from test_anki import FakeAdapter, config, note, card, review, CountingParser
from lute_korean_parser.anki.sync import AnkiSyncService
from lute_korean_parser.knowledge.ingestion import KnowledgeIngestionService


def populate(knowledge, item, count=8, kind="recognized", dimension="reading", days=0):
    for index in range(count):
        knowledge.record_evidence(
            item["id"],
            kind,
            dimension=dimension,
            context=f"Context {index}",
            surface=f"Form {index}",
            source_reference=f"source:{index}",
            occurred_at=NOW - timedelta(days=days),
            metadata={"directness": "direct", "scope": "item"},
        )


def test_recent_direct_misses_indicate_practice_with_confidence(session):
    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("먹다")
    populate(knowledge, item)
    populate(knowledge, item, kind="missed")
    state = LearnerStateEngine(session).inspect("먹다", as_of=NOW)
    assert state["suggested_state"]["reading"]["status"] == "practicing"
    assert state["suggested_state"]["reading"]["confidence"] == "high"
    assert (
        state["suggested_state"]["reading"]["evidence_quality"]["negative_strength"] > 0
    )


def test_production_does_not_imply_reading_or_listening(session):
    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_chunk("잘 모르겠어요")
    populate(knowledge, item, kind="produced", dimension="production")
    state = LearnerStateEngine(session).inspect(item["id"], as_of=NOW)
    assert state["suggested_state"]["production"]["status"] == "consolidated"
    assert state["suggested_state"]["reading"]["status"] == "unknown"
    assert state["suggested_state"]["listening"]["status"] == "unknown"


def test_old_exposure_remains_presented_and_recent_recognition_is_stronger(session):
    knowledge = KnowledgeService(session)
    old = knowledge.get_or_create_lexical("근처")
    new = knowledge.get_or_create_lexical("먹다")
    populate(knowledge, old, count=1, kind="exposure", days=180)
    populate(knowledge, new, count=1, kind="exposure")
    engine = LearnerStateEngine(session)
    previous = engine.inspect(old["id"], as_of=NOW)["suggested_state"]["reading"]
    recent = engine.inspect(new["id"], as_of=NOW)["suggested_state"]["reading"]
    assert previous["status"] == "presented"
    assert (
        previous["evidence_quality"]["positive_strength"]
        < recent["evidence_quality"]["positive_strength"]
    )


def test_one_note_hundreds_of_good_reviews_cannot_consolidate(session, config):
    adapter = FakeAdapter(
        [note(text="오늘 먹었어요.")],
        [card()],
        [
            review(rid=int(NOW.timestamp() * 1000) - i, cid=456, rating=3)
            for i in range(300)
        ],
    )
    sync = AnkiSyncService(session, adapter, config)
    sync.sync()
    state = LearnerStateEngine(session).inspect("먹다", as_of=NOW + timedelta(days=1))
    assert state["evidence"]["anki_reviews"] == 300
    assert state["suggested_state"]["reading"]["status"] != "consolidated"
    assert state["suggested_state"]["listening"]["status"] == "unknown"
    assert state["evidence"]["historically_uncertain_reviews"] == 300
    assert state["suggested_state"]["reading"]["confidence"] != "high"


def test_again_is_not_an_individual_word_failure(session, config):
    adapter = FakeAdapter(
        [note(text="오늘 먹었어요.")],
        [card()],
        [review(rid=int(NOW.timestamp() * 1000), rating=1)],
    )
    AnkiSyncService(session, adapter, config).sync()
    state = LearnerStateEngine(session).inspect("먹다", as_of=NOW + timedelta(days=1))
    assert state["suggested_state"]["reading"]["status"] == "presented"
    assert (
        state["suggested_state"]["reading"]["evidence_quality"]["negative_strength"] > 0
    )
    assert (
        state["suggested_state"]["reading"]["evidence_quality"]["direct_contexts"] == 0
    )


def test_exposure_alone_never_consolidates_even_when_diverse(session):
    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_grammar("-(으)면")
    populate(knowledge, item, count=50, kind="exposure")
    state = LearnerStateEngine(session).inspect(item["id"], as_of=NOW)
    assert state["suggested_state"]["reading"]["status"] == "presented"


def test_manual_future_is_preserved_with_diagnostic_computed_state(session):
    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("먹다")
    populate(knowledge, item)
    knowledge.set_status(item["id"], "future")
    state = LearnerStateEngine(session).inspect(item["id"], as_of=NOW)
    assert state["suggested_state"]["reading"]["status"] == "future"
    assert state["suggested_state"]["reading"]["computed_status"] == "consolidated"
    assert knowledge.get_item(item["id"])["status"] == "future"


def test_default_lexical_engine_excludes_foreign_items(session):
    knowledge = KnowledgeService(session)
    knowledge.get_or_create_lexical("Netflix")
    assert LearnerStateEngine(session).calculate(as_of=NOW)["items"] == []


def test_identical_contexts_across_sources_do_not_inflate_diversity(session):
    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("먹다")
    for index in range(30):
        knowledge.record_evidence(
            item["id"],
            "recognized",
            context="오늘 밥을 먹었어요." if index % 2 else "  오늘  밥을 먹었어요! ",
            source_reference=f"source:{index}",
            occurred_at=NOW,
            metadata={"directness": "direct", "scope": "item"},
        )
    state = LearnerStateEngine(session).inspect(item["id"], as_of=NOW)
    assert state["evidence"]["contexts"] == 1
    assert state["suggested_state"]["reading"]["status"] != "consolidated"


def test_state_uses_canonical_johahada_without_new_parser_calls(session):
    parser = CountingParser()
    ingestion = KnowledgeIngestionService(session, parser=parser)
    ingestion.ingest("뭐 좋아해요?", "canonical")
    calls = parser.calls
    result = LearnerStateEngine(session).calculate(as_of=NOW + timedelta(days=1))
    assert parser.calls == calls
    assert "좋아하다" in {s["identity"] for s in result["items"]}
    assert "좋다" not in {s["identity"] for s in result["items"]}
    assert "하다" not in {s["identity"] for s in result["items"]}


def test_context_diversity_beats_four_more_repeated_reviews(session, config):
    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("근처")
    populate(knowledge, item, count=1)
    engine = LearnerStateEngine(session)
    before = engine.inspect(item["id"], as_of=NOW)["suggested_state"]["reading"][
        "evidence_quality"
    ]["positive_strength"]
    for index in range(1, 5):
        knowledge.record_evidence(
            item["id"],
            "recognized",
            context=f"Context {index}",
            source_reference=f"source:{index}",
            occurred_at=NOW,
            metadata={"directness": "direct", "scope": "item"},
        )
    after = engine.inspect(item["id"], as_of=NOW)["suggested_state"]["reading"][
        "evidence_quality"
    ]["positive_strength"]
    adapter = FakeAdapter(
        [note(text="오늘 먹었어요.")],
        [card()],
        [review(rid=int(NOW.timestamp() * 1000) - i, rating=3) for i in range(101)],
    )
    sync = AnkiSyncService(session, adapter, config)
    sync.sync()
    as_of = NOW + timedelta(days=1)
    repeated_before = engine.inspect("먹다", as_of=as_of)["suggested_state"]["reading"][
        "evidence_quality"
    ]["positive_strength"]
    adapter.reviews.extend(
        review(rid=int(NOW.timestamp() * 1000) + i + 1, rating=3) for i in range(4)
    )
    sync.sync()
    repeated_after = engine.inspect("먹다", as_of=as_of)["suggested_state"]["reading"][
        "evidence_quality"
    ]["positive_strength"]
    assert after - before > 10 * (repeated_after - repeated_before)


def test_missing_context_does_not_fabricate_independence(session):
    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("먹다")
    for i in range(20):
        knowledge.record_evidence(
            item["id"],
            "manual_confirmation",
            source_reference=f"source:{i}",
            occurred_at=NOW,
        )
    state = LearnerStateEngine(session).inspect(item["id"], as_of=NOW)
    assert state["suggested_state"]["reading"]["status"] != "consolidated"
    assert state["evidence"]["contexts"] == 0


def test_future_dated_evidence_and_naive_clock_are_rejected_or_ignored(session):
    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("먹다")
    knowledge.record_evidence(
        item["id"], "recognized", occurred_at=NOW + timedelta(days=1)
    )
    engine = LearnerStateEngine(session)
    assert (
        engine.inspect(item["id"], as_of=NOW)["suggested_state"]["reading"]["status"]
        == "unknown"
    )
    with pytest.raises(ValueError, match="timezone"):
        engine.calculate(as_of=NOW.replace(tzinfo=None))


def test_few_strong_confirmations_can_have_low_classification_confidence(session):
    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("먹다")
    populate(knowledge, item, count=3, kind="manual_confirmation")
    state = LearnerStateEngine(session).inspect(item["id"], as_of=NOW)[
        "suggested_state"
    ]["reading"]
    assert state["status"] == "consolidated"
    assert state["confidence"] == "low"


from pathlib import Path
import json
from sqlalchemy import event
from lute_korean_parser.learner_state.cli import main
from lute_korean_parser.learner_state.policy import LearnerStatePolicyV1
from lute_korean_parser.learner_state.calibration import select_sample


def test_export_is_optional_backward_compatible_and_versioned(session):
    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("먹다")
    populate(knowledge, item)
    baseline = knowledge.export()
    assert "learner_state" not in baseline
    exported = knowledge.export(include_learner_state=True, as_of=NOW)
    assert exported["lexical"][0]["status"] == "unknown"
    assert (
        exported["lexical"][0]["suggested_state"]["reading"]["status"] == "consolidated"
    )
    assert (
        "positive_strength"
        not in exported["lexical"][0]["suggested_state"]["reading"]["evidence_quality"]
    )
    assert exported["learner_state"]["policy_version"] == "ko.learner-state.v1"
    assert knowledge.export() == baseline


def test_policy_changes_are_auditable_and_do_not_change_historical_evidence(session):
    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("먹다")
    populate(knowledge, item)
    baseline = knowledge.list_evidence(item["id"])
    a = LearnerStateEngine(session).calculate(as_of=NOW)
    b = LearnerStateEngine(
        session,
        LearnerStatePolicyV1(
            version="ko.learner-state.v2", consolidation_threshold=100
        ),
    ).calculate(as_of=NOW)
    assert a["policy_fingerprint"] != b["policy_fingerprint"]
    assert a["items"][0]["suggested_state"]["reading"]["status"] == "consolidated"
    assert b["items"][0]["suggested_state"]["reading"]["status"] == "practicing"
    assert knowledge.list_evidence(item["id"]) == baseline


@pytest.mark.parametrize(
    "params",
    [
        {"historical_factor": 2},
        {"exposure_weight": float("nan")},
        {"review_saturation": 0},
        {"consolidation_contexts": 1.5},
        {"consolidation_threshold": 1},
    ],
)
def test_invalid_policies_fail_explicitly(params):
    with pytest.raises(ValueError):
        LearnerStatePolicyV1(**params)


def test_calibration_and_compare_use_no_manual_labels_to_fit_policy(session):
    knowledge = KnowledgeService(session)
    for index in range(30):
        item = knowledge.get_or_create_lexical("단어" + str(index))
        populate(knowledge, item, count=(index % 8) + 1)
    grammar = knowledge.get_or_create_grammar("-(으)면")
    populate(knowledge, grammar)
    engine = LearnerStateEngine(session)
    initial = engine.calculate(as_of=NOW)
    selected = select_sample(initial, 25)
    for item in knowledge.list_items():
        knowledge.set_status(item["id"], "consolidated", "reading")
    recalculated = engine.calculate(as_of=NOW)
    assert {s["id"]: s["suggested_state"] for s in initial["items"]} == {
        s["id"]: s["suggested_state"] for s in recalculated["items"]
    }
    assert [s["id"] for s in selected["items"]] == [
        s["id"] for s in select_sample(recalculated, 25)["items"]
    ]
    assert len(selected["items"]) == 26
    assert "manual == suggested" in engine.compare(as_of=NOW)["comparison_summary"]


def test_cli_read_only_export_inspect_and_negative_pattern_identity(
    database, session, tmp_path, capsys
):
    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_grammar("-(으)면")
    populate(knowledge, item)
    session.commit()
    path = Path(database.url.database)
    before = path.read_bytes()
    main(
        ["inspect", "--database", str(path), "--as-of", NOW.isoformat(), "--", "-(으)면"]
    )
    assert "consolidated" in capsys.readouterr().out
    export = tmp_path / "state.json"
    main(
        [
            "calculate",
            "--database",
            str(path),
            "--as-of",
            NOW.isoformat(),
            "--export",
            str(export),
        ]
    )
    assert json.loads(export.read_text())["policy_version"] == "ko.learner-state.v1"
    assert path.read_bytes() == before
    with pytest.raises(SystemExit):
        main(["calculate", "--database", str(path), "--export", str(path)])


def test_batch_calculation_does_not_issue_per_item_queries(session, database):
    knowledge = KnowledgeService(session)
    for index in range(20):
        knowledge.get_or_create_lexical("단어" + str(index))
    statements = []

    def capture(conn, cursor, statement, params, ctx, many):
        statements.append(statement)

    event.listen(database, "before_cursor_execute", capture)
    try:
        LearnerStateEngine(session).calculate(as_of=NOW)
    finally:
        event.remove(database, "before_cursor_execute", capture)
    assert sum(s.lstrip().upper().startswith("SELECT") for s in statements) <= 9
    assert not any(
        s.lstrip().upper().startswith(("UPDATE", "INSERT", "DELETE"))
        for s in statements
    )


from lute_korean_parser.learner_state.interpretation import EvidenceInterpreter


def test_historical_reviews_have_lower_quality_and_unspecified_modality():
    interpreter = EvidenceInterpreter(LearnerStatePolicyV1())
    row = {
        "event_key": "review:1",
        "occurred_at": NOW.isoformat(),
        "rating": 3,
        "metadata": {"association_basis": "first_observed_snapshot"},
    }
    uncertain = interpreter.interpret(row, "오늘 먹어요.", "source", NOW, review=True)
    certified = interpreter.interpret(
        dict(row, metadata={"association_basis": "verified_content"}),
        "오늘 먹어요.",
        "source",
        NOW,
        review=True,
    )
    assert uncertain.positive < certified.positive
    assert uncertain.quality.association_confidence == 0.35
    assert uncertain.quality.directness == "indirect"
    assert uncertain.dimension is None


def test_same_ratings_different_sequence_retains_contextual_lapse(session, config):
    notes = [
        note(text="밥을 먹어요.", cards=(456,)),
        note(124, text="물을 마셔요.", cards=(457,)),
    ]
    cards = [card(), card(457, 124)]
    base = int(NOW.timestamp() * 1000) - 10000
    reviews = [review(base + i, 456, 3 if i < 5 else 1) for i in range(6)]
    reviews += [review(base + i, 457, 1 if i == 0 else 3) for i in range(6)]
    AnkiSyncService(session, FakeAdapter(notes, cards, reviews), config).sync()
    engine = LearnerStateEngine(session)
    lapse = engine.inspect("먹다", as_of=NOW + timedelta(days=1))["suggested_state"][
        "reading"
    ]
    recovered = engine.inspect("마시다", as_of=NOW + timedelta(days=1))["suggested_state"][
        "reading"
    ]
    assert (
        lapse["evidence_quality"]["negative_strength"]
        > recovered["evidence_quality"]["negative_strength"]
    )
    assert lapse["status"] != "unknown"


def test_surface_diversity_is_bounded_support_not_independent_contexts(session):
    knowledge = KnowledgeService(session)
    first = knowledge.get_or_create_lexical("먹다")
    second = knowledge.get_or_create_lexical("마시다")
    for item, varied in [(first, True), (second, False)]:
        for index in range(3):
            knowledge.record_evidence(
                item["id"],
                "recognized",
                context=f"Context {index}",
                surface=f"Form {index}" if varied else "Same form",
                source_reference=f"context:{index}",
                occurred_at=NOW,
                metadata={"directness": "direct", "scope": "item"},
            )
    engine = LearnerStateEngine(session)
    varied = engine.inspect(first["id"], as_of=NOW)["suggested_state"]["reading"][
        "evidence_quality"
    ]
    uniform = engine.inspect(second["id"], as_of=NOW)["suggested_state"]["reading"][
        "evidence_quality"
    ]
    assert varied["contexts"] == uniform["contexts"] == 3
    assert varied["positive_strength"] > uniform["positive_strength"]
    assert varied["positive_strength"] - uniform["positive_strength"] <= 0.3


def test_evidence_fingerprint_does_not_depend_on_manual_status(session):
    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("먹다")
    populate(knowledge, item)
    engine = LearnerStateEngine(session)
    initial = engine.calculate(as_of=NOW)
    knowledge.set_status(item["id"], "practicing", "reading")
    final = engine.calculate(as_of=NOW)
    assert initial["evidence_fingerprint"] == final["evidence_fingerprint"]
    assert initial["input_fingerprint"] != final["input_fingerprint"]


def test_engine_works_without_anki_tables(tmp_path):
    import sqlite3
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    path = tmp_path / "generic.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE texts(TxID INTEGER PRIMARY KEY)")
    migration = (
        Path(__file__).resolve().parents[3]
        / "lute/db/schema/migrations/20260930_01_korean_knowledge.sql"
    )
    connection.executescript(migration.read_text())
    connection.close()
    engine = create_engine(f"sqlite:///{path}")
    try:
        with Session(engine) as session:
            item = KnowledgeService(session).get_or_create_chunk("잘 모르겠어요")
            state = LearnerStateEngine(session).inspect(item["id"], as_of=NOW)
            assert state["suggested_state"]["reading"]["status"] == "unknown"
    finally:
        engine.dispose()


def test_many_exposures_do_not_make_one_recognition_high_confidence(session):
    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("먹다")
    populate(knowledge, item, count=8, kind="exposure")
    populate(knowledge, item, count=1)
    state = LearnerStateEngine(session).inspect(item["id"], as_of=NOW)[
        "suggested_state"
    ]["reading"]
    assert state["confidence"] != "high"


def test_reverse_cards_and_same_source_forms_cannot_multiply_consolidation(
    session, config
):
    base = int(NOW.timestamp() * 1000)
    reviews = [review(base - i, 456, 3) for i in range(100)]
    reviews += [review(base - i, 789, 4) for i in range(100)]
    adapter = FakeAdapter(
        [note(text="먹어요. 먹었어요. 먹으면 먹고 싶어요.")], [card(), card(789, 123, 1)], reviews
    )
    AnkiSyncService(session, adapter, config).sync()
    state = LearnerStateEngine(session).inspect("먹다", as_of=NOW + timedelta(days=1))
    assert state["evidence"]["anki_notes"] == 1 and state["evidence"]["anki_cards"] == 2
    assert state["evidence"]["anki_reviews"] == 200
    assert len(state["evidence"]["surfaces"]) > 1
    assert state["suggested_state"]["reading"]["status"] != "consolidated"
    assert (
        state["suggested_state"]["reading"]["evidence_quality"]["positive_strength"]
        <= 6
    )


def test_single_source_does_not_supply_unbounded_strength(session):
    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("먹다")
    for index in range(100):
        knowledge.record_evidence(
            item["id"],
            "recognized",
            context=f"Context {index}",
            surface=f"Form {index}",
            source_reference="one-source",
            occurred_at=NOW,
            metadata={"directness": "direct", "scope": "item"},
        )
    state = LearnerStateEngine(session).inspect(item["id"], as_of=NOW)[
        "suggested_state"
    ]["reading"]
    assert state["evidence_quality"]["positive_strength"] <= 6


def test_dimensional_future_does_not_visibly_reappear_as_overall_consolidation(session):
    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("먹다")
    populate(knowledge, item)
    knowledge.set_status(item["id"], "future", "reading")
    state = LearnerStateEngine(session).inspect(item["id"], as_of=NOW)
    assert state["suggested_state"]["reading"]["status"] == "future"
    assert state["suggested_overall"]["status"] == "future"
    assert state["manual_state"]["overall"] == "unknown"
