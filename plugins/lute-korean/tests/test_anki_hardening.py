"""Anki source-content validation with a fake read-only external boundary."""
from test_anki import (
    session,
    database,
    config,
    FakeAdapter,
    note,
    card,
    review,
    CountingParser,
)
from lute_korean_parser.anki.sync import AnkiSyncService


def test_anomalous_note_keeps_reviews_without_linguistic_evidence(session, config):
    text = "좋아요, porque você provavelmente encontrou mais 좋아해요, mas 좋다 aparece o tempo todo em pensamentos cotidianos."
    adapter = FakeAdapter([note(text=text)], [card()], [review()])
    parser = CountingParser()
    sync = AnkiSyncService(session, adapter, config, parser)
    preview = sync.preview()
    assert preview["content_anomalies"] == 1
    report = sync.sync()
    assert report["notes_anomalous"] == 1
    assert report["reviews_imported"] == 1
    assert parser.calls == 0
    assert sync.ingestion.knowledge.list_items() == []
    assert sync.sync()["notes_skipped"] == 1
    assert parser.calls == 0


import pytest
from sqlalchemy import select, func
from lute_korean_parser.anki import tables as a
from lute_korean_parser.knowledge import tables as k
from lute_korean_parser.anki.content import validate_korean_field


@pytest.mark.parametrize(
    "text", ["Eu gosto muito dessa comida.", "I really like this food.", ""]
)
def test_wrong_language_is_quarantined_and_dry_run_never_writes(session, config, text):
    adapter = FakeAdapter([note(text=text)], [card()], [review()])
    parser = CountingParser()
    sync = AnkiSyncService(session, adapter, config, parser)
    assert sync.sync(dry_run=True)["notes_anomalous"] == 1
    assert session.scalar(select(func.count()).select_from(k.sources)) == 0
    result = sync.sync()
    assert result["reviews_without_linguistic_association"] == 1
    assert session.scalar(select(func.count()).select_from(k.occurrences)) == 0
    assert session.scalar(select(func.count()).select_from(k.evidence)) == 0
    assert session.scalar(select(func.count()).select_from(a.reviews)) == 1
    assert parser.calls == 0


@pytest.mark.parametrize(
    "text",
    ["오늘 Netflix 봤어요.", "BTS를 좋아해요.", "YouTube Wi-Fi Netflix 2027 GPT Starbucks를 알아요."],
)
def test_foreign_names_do_not_quarantine_valid_korean(text):
    diagnostic = validate_korean_field(text)
    assert diagnostic["status"] == "warning"
    assert diagnostic["content_language_warning"]


def test_mixed_dialogue_tracks_korean_only(session, config):
    adapter = FakeAdapter(
        [note(text="Alguém: 한국 어때요? Eu: 생각보다 재미있어요.")], [card()], [review()]
    )
    sync = AnkiSyncService(session, adapter, config)
    result = sync.sync()
    assert result["notes_anomalous"] == 0
    assert result["content_language_warnings"] == 1
    assert sync.ingestion.knowledge.get_lexical("한국") is not None
    assert all(
        sync.ingestion.lexical_policy.is_korean(item["identity"])
        for item in sync.ingestion.knowledge.list_items("lexical")
    )


from dataclasses import replace
from lute_korean_parser.anki.config import NoteTypeMapping


def test_each_mapped_field_is_validated_separately(session, config):
    config = replace(config, mappings={"Core Korean": NoteTypeMapping(("KO", "PT"))})
    adapter = FakeAdapter([note()], [card()], [review()])
    sync = AnkiSyncService(session, adapter, config)
    assert sync.sync()["notes_anomalous"] == 1
    assert not sync.ingestion.knowledge.list_items()


def test_individual_analysis_failure_remains_isolated(session, config):
    class FailingParser(CountingParser):
        def analyze(self, text):
            if text == "분석 실패":
                raise ValueError("Deliberate analysis failure")
            return super().analyze(text)

    adapter = FakeAdapter(
        [note(), note(124, text="분석 실패", cards=(900,))],
        [card(), card(900, 124)],
        [review()],
    )
    sync = AnkiSyncService(session, adapter, config, FailingParser())
    report = sync.sync()
    assert report["error_count"] == 1
    assert report["notes_created"] == 1
    assert sync.ingestion.knowledge.get_lexical("먹다") is not None
