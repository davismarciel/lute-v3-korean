"""Candidate content adapters and CI reports through public read-only interfaces."""
import pytest


def test_tprs_uses_original_subtitle_and_keeps_translation_as_metadata():
    from lute_korean_parser.ci.adapters import adapt_content

    content = adapt_content(
        "Time | Subtitle | Machine Translation\n00:01 | 오늘 밥을 먹었어요. | Today I ate food.\n00:05 | 한국에 가요. | I go to Korea.",
        format="tprs",
    )
    assert len(content.segments) == 2
    assert content.segments[0].text == "오늘 밥을 먹었어요."
    assert content.segments[0].timestamp == "00:01"
    assert content.segments[0].metadata["translation"] == "Today I ate food."
    assert "Today" not in "\n".join(segment.text for segment in content.segments)


from test_representation_hardening import session  # noqa: F401
from lute_korean_parser.knowledge.service import KnowledgeService


def test_candidate_uses_canonical_heads_and_scoped_overlap_without_creating_items(
    session,
):
    from lute_korean_parser.ci.analyzer import CIContentAnalyzer

    knowledge = KnowledgeService(session)
    for lemma in ["먹다", "좋아하다", "어제", "재미있다"]:
        item = knowledge.get_or_create_lexical(lemma)
        knowledge.set_status(item["id"], "practicing", "reading")
    before = knowledge.export()
    report = CIContentAnalyzer(session).analyze_text(
        "어제 친구가 오늘 게임하고 싶다고 했어요.\n재미있는데 좋아해요.\n먹고 싶어요."
    )
    assert {"먹다", "좋아하다", "어제", "재미있다"} <= {
        item["identity"] for item in report["lexical"]["items"]
    }
    desire = report["segments"][-1]
    assert "싶다" in {i["identity"] for i in desire["raw_items"]}
    assert "싶다" not in {i["identity"] for i in desire["effective_items"]}
    assert desire["suppressed_overlap"][0]["identity"] == "싶다"
    assert before == knowledge.export()


def test_familiar_fit_and_distributed_vs_clustered_novelty(session):
    from lute_korean_parser.ci.analyzer import CIContentAnalyzer

    knowledge = KnowledgeService(session)
    for lemma in ["오늘", "친구", "같이", "먹다", "보다", "좋아하다", "밥"]:
        item = knowledge.get_or_create_lexical(lemma)
        knowledge.set_status(item["id"], "practicing", "reading")
    analyzer = CIContentAnalyzer(session)
    assert analyzer.analyze_text("오늘 친구랑 같이 밥을 먹어요.")["summary"]["fit"] == "comfortable"
    distributed = analyzer.analyze_text(
        "\n".join(f"오늘 친구랑 같이 {noun} 먹어요." for noun in ["라면", "초밥", "김밥", "피자"])
    )
    clustered = analyzer.analyze_text(
        "오늘 친구랑 같이 라면 초밥 김밥 피자 먹어요.\n오늘 친구랑 같이 먹어요.\n오늘 친구랑 같이 먹어요.\n오늘 친구랑 같이 먹어요."
    )
    assert distributed["summary"]["fit"] == "productive"
    assert clustered["summary"]["fit"] in {"stretch", "dense"}
    assert (
        distributed["lexical"]["occurrence_distribution"]["untracked"]["count"]
        == clustered["lexical"]["occurrence_distribution"]["untracked"]["count"]
    )


@pytest.mark.parametrize(
    "format,text,expected_stamp,expected_id",
    [
        (
            "srt",
            "7\n00:00:01,000 --> 00:00:03,000\n<b>오늘</b> 밥을 먹어요.\n",
            "00:00:01,000",
            "7",
        ),
        (
            "vtt",
            "WEBVTT\n\nNOTE technical\nmetadata\n\ncue-seven\n00:01.000 --> 00:03.000 align:start\n<v 민수>오늘 밥을 먹어요.</v>\n",
            "00:01.000",
            "cue-seven",
        ),
        ("timestamp", "[00:01] 오늘 밥을 먹어요.", "00:01", "line:1"),
        (
            "tprs",
            "Time\tSubtitle\tMachine Translation\n00:01\t오늘 밥을 먹어요.\tToday I eat food.",
            "00:01",
            "tprs:2",
        ),
    ],
)
def test_formats_keep_cue_identity_timing_and_korean(
    format, text, expected_stamp, expected_id
):
    from lute_korean_parser.ci.adapters import adapt_content

    content = adapt_content(text, format=format)
    assert len(content.segments) == 1
    segment = content.segments[0]
    assert segment.text == "오늘 밥을 먹어요."
    assert segment.timestamp == expected_stamp
    assert segment.identity == expected_id
    assert segment.start_seconds == 1


def test_many_names_are_visible_without_dominating_fit_and_audio_is_not_listening(
    session,
):
    from lute_korean_parser.ci.analyzer import CIContentAnalyzer

    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("가다")
    knowledge.set_status(item["id"], "practicing", "reading")
    report = CIContentAnalyzer(session).analyze_text(
        "서울 부산 대구 인천 홍대 성수동 도쿄 오사카에 가요.", kind="podcast"
    )
    assert report["summary"]["fit"] != "dense"
    assert report["lexical"]["proper_names"]["items"]
    assert report["summary"]["transcript_fit"] == report["summary"]["fit"]
    assert report["summary"]["listening_fit"] == "insufficient_evidence"


def test_explicit_unknown_grammar_elevates_fit_without_claiming_complete_grammar(
    session,
):
    from lute_korean_parser.ci.analyzer import CIContentAnalyzer

    knowledge = KnowledgeService(session)
    for lemma in ["시간", "있다", "먹다"]:
        item = knowledge.get_or_create_lexical(lemma)
        knowledge.set_status(item["id"], "consolidated", "reading")
    knowledge.get_or_create_grammar("-(으)면")
    report = CIContentAnalyzer(session).analyze_text("시간이 있으면 먹어요.")
    assert report["summary"]["fit"] in {"productive", "stretch", "dense"}
    assert report["grammar"]["items"][0]["bucket"] == "unassessed"
    assert report["grammar"]["untracked_constructions_may_exist"] is True


def test_reading_assessment_wins_over_overall_future_and_default_unknown_is_not_human(
    session,
):
    from lute_korean_parser.ci.analyzer import CIContentAnalyzer

    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("먹다")
    knowledge.set_status(item["id"], "future")
    knowledge.set_status(item["id"], "practicing", "reading")
    deferred = knowledge.get_or_create_lexical("밥")
    knowledge.set_status(deferred["id"], "future")
    report = CIContentAnalyzer(session).analyze_text("밥을 먹어요.")
    by_name = {i["identity"]: i for i in report["lexical"]["items"]}
    assert by_name["먹다"]["bucket"] == "familiar"
    assert by_name["먹다"]["state_origin"] == "manual_reading"
    assert by_name["밥"]["bucket"] == "deferred"
    assert knowledge.get_item(item["id"])["status"] == "future"


def test_foreign_content_and_ambiguous_tables_remain_diagnosable(session):
    from lute_korean_parser.ci.analyzer import CIContentAnalyzer
    from lute_korean_parser.ci.adapters import adapt_content

    report = CIContentAnalyzer(session).analyze_text("Eu gosto muito dessa comida.")
    assert report["lexical"]["items"] == []
    assert report["summary"]["fit"] is None
    assert report["segments"][0]["foreign_surfaces"]
    content = adapt_content("Time | Korean | Translation\n00:01 | 한국어 | English")
    assert content.format == "plain"
    assert any("Ambiguous" in warning for warning in content.warnings)


def test_presented_opportunities_recycling_and_ranked_untracked_items(session):
    from lute_korean_parser.ci.analyzer import CIContentAnalyzer
    from datetime import datetime, timezone

    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("먹다")
    knowledge.set_status(item["id"], "practicing", "reading")
    noun = knowledge.get_or_create_lexical("밥")
    knowledge.record_evidence(
        noun["id"], "exposure", occurred_at=datetime(2026, 9, 30, tzinfo=timezone.utc)
    )
    report = CIContentAnalyzer(session).analyze_text("밥을 먹어요.\n초밥을 먹어요.\n초밥을 먹었어요.")
    assert report["recycling"][0]["identity"] == "먹다"
    assert report["presented_opportunities"][0]["identity"] == "밥"
    novelty = next(i for i in report["novelties"] if i["identity"] == "초밥")
    assert novelty["count"] == 2
    assert novelty["contexts"] == 2
    assert novelty["tracked"] is False


def test_real_tprs_title_and_seconds_units_are_not_linguistic_content():
    from lute_korean_parser.ci.adapters import adapt_content

    source = "TPRS Korean for beginners ep1\nTime\tSubtitle\tMachine Translation\n2s\t자, 여러분 안녕하세요.\tOkay, hello everyone.\n1m 13s\t한국에 가요.\tI go to Korea."
    content = adapt_content(source, name="tprs_1.txt")
    assert content.format == "tprs"
    assert len(content.segments) == 2
    assert content.segments[0].start_seconds == 2
    assert content.segments[1].start_seconds == 73
    assert content.segments[0].text == "자, 여러분 안녕하세요."
    assert (
        content.segments[0].metadata["transcript_title"]
        == "TPRS Korean for beginners ep1"
    )


def test_cli_analyze_compare_and_compact_export_are_read_only(
    session, tmp_path, capsys
):
    import hashlib, json
    from pathlib import Path
    from lute_korean_parser.ci.cli import main

    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("먹다")
    knowledge.set_status(item["id"], "practicing", "reading")
    session.commit()
    database = Path(session.bind.url.database)
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    source = tmp_path / "input.txt"
    source.write_text("먹고 싶어요.\n먹었어요.", encoding="utf8")
    export = tmp_path / "report.json"
    main(
        [
            "analyze",
            str(source),
            "--database",
            str(database),
            "--compact",
            "--export",
            str(export),
        ]
    )
    report = json.loads(export.read_text())
    assert report["summary"]["listening_fit"] == "insufficient_evidence"
    assert report["policy"]["version"] == "ko.ci-analysis.v1"
    assert "raw_items" not in export.read_text()
    capsys.readouterr()
    main(["compare", str(source), str(source), "--database", str(database), "--json"])
    compared = json.loads(capsys.readouterr().out)
    assert len(compared["candidates"]) == 2
    assert before == hashlib.sha256(database.read_bytes()).hexdigest()
    with pytest.raises(SystemExit):
        main(
            [
                "analyze",
                str(source),
                "--database",
                str(database),
                "--export",
                str(database),
            ]
        )
    assert before == hashlib.sha256(database.read_bytes()).hexdigest()


def test_korean_translation_and_title_never_enter_candidate_knowledge(session):
    from lute_korean_parser.ci.analyzer import CIContentAnalyzer

    text = (
        "여행 수업 제목\nTime\tSubtitle\tMachine Translation\n2s\t먹어요.\t번역에는 서울과 부산이 들어갑니다."
    )
    report = CIContentAnalyzer(session).analyze_text(text)
    assert {item["identity"] for item in report["lexical"]["items"]} == {"먹다"}
    assert report["segments"][0]["metadata"]["translation"] == "번역에는 서울과 부산이 들어갑니다."


def test_coverage_reports_occurrences_and_unique_items_separately(session):
    from lute_korean_parser.ci.analyzer import CIContentAnalyzer

    knowledge = KnowledgeService(session)
    item = knowledge.get_or_create_lexical("먹다")
    knowledge.set_status(item["id"], "practicing", "reading")
    report = CIContentAnalyzer(session).analyze_text("먹어요. 먹었어요. 먹어요. 라면.")
    assert report["lexical"]["occurrence_distribution"]["familiar"]["count"] == 3
    assert report["lexical"]["unique_distribution"]["familiar"]["count"] == 1
    assert report["lexical"]["unique_distribution"]["untracked"]["count"] == 1
    assert report["lexical"]["supported_coverage"] == 0.75


def test_synthetic_indirect_anki_familiarity_has_conservative_confidence(session):
    from lute_korean_parser.ci.analyzer import CIContentAnalyzer
    from test_anki import FakeAdapter, AnkiConfig, MAPPING, note, card, review, BASE
    from lute_korean_parser.anki.sync import AnkiSyncService

    # This seam uses the real sync and engine with a fake external Anki transport.
    raw = session.connection().connection.driver_connection
    raw.commit()
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[3]
        / "lute/db/schema/migrations/20260930_02_korean_anki.sql"
    )
    raw.executescript(migration.read_text())
    phrases = ["오늘 밥을 먹어요.", "친구랑 밥을 먹어요.", "집에서 밥을 먹어요."]
    notes = [note(i + 1, text=text, cards=(i + 11,)) for i, text in enumerate(phrases)]
    cards = [card(i + 11, nid=i + 1) for i in range(3)]
    reviews = [
        review(BASE + 10000 + i * 100 + j, cid=i + 11)
        for i in range(3)
        for j in range(40)
    ]
    config = AnkiConfig("ci-fixture", {"Core Korean": MAPPING}, profile="Fixture")
    AnkiSyncService(session, FakeAdapter(notes, cards, reviews), config).sync(
        full_reviews=True
    )
    report = CIContentAnalyzer(session).analyze_text("밥을 먹어요.")
    assert report["summary"]["confidence"] in {"low", "medium"}
    assert any("indirect" in warning for warning in report["warnings"])


def test_multiword_names_use_one_candidate_span_and_overlap_does_not_cross_sentences(
    session,
):
    from lute_korean_parser.ci.analyzer import CIContentAnalyzer

    report = CIContentAnalyzer(session).analyze_text("캡틴 아메리카를 좋아해요.\n먹고 싶어요.\n싶다.")
    name = next(i for i in report["lexical"]["items"] if i["identity"] == "캡틴 아메리카")
    assert name["count"] == 1
    assert name["surfaces"] == ["캡틴 아메리카"]
    assert name["role"] == "proper_noun"
    assert any(i["identity"] == "싶다" for i in report["segments"][2]["effective_items"])
    assert not report["segments"][2]["suppressed_overlap"]


def test_dense_cluster_detection_and_hardest_segment_limit(session):
    from lute_korean_parser.ci.analyzer import CIContentAnalyzer

    report = CIContentAnalyzer(session).analyze_text(
        "\n".join(["맛집 근처 예약 계산 메뉴 주문 가격 안내."] * 12)
    )
    assert report["summary"]["fit"] == "dense"
    assert report["summary"]["longest_difficult_cluster"] == 12
    assert len(report["hardest_segments"]) == 10
    assert report["summary"]["dense_clusters"][0]["start_index"] == 0
    assert report["summary"]["dense_clusters"][0]["end_index"] == 11


@pytest.mark.parametrize(
    "parameters",
    [
        {"seen_weight": float("nan")},
        {"grammar_factor": float("inf")},
        {"hardest_limit": 1.5},
        {"compact_item_limit": 0},
        {"proper_noun_factor": 0},
    ],
)
def test_policy_rejects_invalid_numeric_parameters(parameters):
    from lute_korean_parser.ci.policy import CIAnalysisPolicyV1

    with pytest.raises(ValueError):
        CIAnalysisPolicyV1(**parameters)


def test_candidate_nonsequential_segment_indices_are_preserved(session):
    from lute_korean_parser.ci.analyzer import CIContentAnalyzer
    from lute_korean_parser.ci.models import CandidateContent, CandidateSegment

    candidate = CandidateContent(
        "custom", "plain", (CandidateSegment(7, "cue:7", "오늘 먹어요."),), "hash"
    )
    report = CIContentAnalyzer(session).analyze(candidate)
    assert report["lexical"]["items"][0]["sample"]["segment_index"] == 7


def test_analyze_and_compare_never_emit_database_writes_or_per_segment_queries(session):
    from sqlalchemy import event
    from lute_korean_parser.ci.analyzer import CIContentAnalyzer
    from lute_korean_parser.ci.export import compact_report, compare_reports

    statements = []
    connection = session.connection()

    def observe(conn, cursor, statement, parameters, context, many):
        statements.append(statement.strip().split()[0].upper())

    event.listen(connection, "before_cursor_execute", observe)
    try:
        analyzer = CIContentAnalyzer(session)
        snapshot_statements = len(statements)
        report = analyzer.analyze_text("먹고 싶어요.\n" * 100)
        compare_reports([report, compact_report(report, analyzer.policy)])
        assert len(statements) == snapshot_statements
        assert set(statements) <= {"SELECT", "PRAGMA", "BEGIN"}
        assert report["diagnostics"]["kiwi_calls"] == 100
    finally:
        event.remove(connection, "before_cursor_execute", observe)
