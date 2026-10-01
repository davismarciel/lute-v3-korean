"""Public Korean acquisition seams, independent of an Anki connection."""
from test_knowledge import session, database  # noqa: F401
from lute_korean_parser.knowledge.ingestion import KnowledgeIngestionService


def test_johahada_is_one_concept_without_changing_raw_analysis(session):
    service = KnowledgeIngestionService(session)
    text = "뭐 좋아해요?"
    projected = service.preview(text)
    raw = next(u for u in projected["analysis"].units if u.surface == "좋아해요")
    assert raw.lexical_heads == ("좋다", "하다")
    assert "좋아하다" in projected["lexical"]
    assert "좋다" not in projected["lexical"] and "하다" not in projected["lexical"]
    service.ingest(text, "regression:johahada")
    item = service.knowledge.get_lexical("좋아하다")
    occurrence = service.knowledge.list_occurrences(item["id"])[0]
    assert occurrence["surface"] == "좋아해요"
    assert occurrence["metadata"]["lexical_normalization"]["raw_heads"] == ["좋다", "하다"]
    assert occurrence["metadata"]["lexical_normalization"]["canonical_heads"] == [
        "좋아하다"
    ]
    assert (
        occurrence["metadata"]["lexical_normalization"]["rules"][0]["id"]
        == "ko.lexical.johahada.v1"
    )


def test_foreign_content_has_no_korean_items_but_preserves_source_metadata(session):
    service = KnowledgeIngestionService(session)
    for idx, text in enumerate(
        ["Eu gosto muito dessa comida.", "I really like this food."]
    ):
        result = service.ingest(text, f"foreign:{idx}")
        assert result["item_ids"] == [] and result["evidence_ids"] == []
    result = service.ingest("오늘 Netflix 봤어요.", "mixed:netflix")
    assert set(service.preview("오늘 Netflix 봤어요.")["lexical"]) == {"오늘", "보다"}
    occurrences = service.knowledge.list_source_occurrences(result["source_id"])
    foreign = next(o for o in occurrences if o["surface"] == "Netflix")
    assert foreign["metadata"]["non_korean_heads"] == ["Netflix"]
    assert service.knowledge.get_lexical("Netflix") is None


import pytest
from lute_korean_parser.knowledge.normalization import (
    KoreanLexicalNormalizer,
    JohahadaRule,
)


@pytest.mark.parametrize(
    "text",
    [
        "좋아해요",
        "좋아했어요",
        "좋아하면",
        "좋아해서",
        "좋아하고",
        "좋아하는",
        "좋아할 거예요",
        "좋아할 것 같아요",
        "BTS를 좋아해요.",
    ],
)
def test_conjugations_reuse_canonical_identity_and_status(session, text):
    service = KnowledgeIngestionService(session)
    existing = service.knowledge.get_or_create_lexical("좋아하다")
    service.knowledge.set_status(existing["id"], "practicing")
    result = service.ingest(text, "positive:" + text)
    assert existing["id"] in result["item_ids"]
    assert service.knowledge.get_lexical("좋아하다")["status"] == "practicing"
    assert service.knowledge.get_lexical("좋다") is None
    assert service.knowledge.get_lexical("하다") is None
    assert service.knowledge.get_lexical("BTS") is None
    assert service.parser.analyze(text).text == text


@pytest.mark.parametrize(
    "text, expected",
    [
        ("좋아요.", "좋다"),
        ("날씨가 좋아요.", "좋다"),
        ("좋아서 다시 왔어요.", "좋다"),
        ("이게 더 좋은 것 같아요.", "좋다"),
        ("운동해요.", "운동하다"),
        ("공부해요.", "공부하다"),
        ("뭐 해요?", "하다"),
        ("좋아 하세요.", "좋다"),
    ],
)
def test_independent_predicates_are_not_fused(session, text, expected):
    service = KnowledgeIngestionService(session)
    lexical = service.preview(text)["lexical"]
    assert expected in lexical
    assert "좋아하다" not in lexical


def test_registry_can_be_disabled_without_changing_raw_analysis(session):
    service = KnowledgeIngestionService(session, normalizer=KoreanLexicalNormalizer([]))
    assert set(service.preview("뭐 좋아해요?")["lexical"]) >= {"좋다", "하다"}
    with pytest.raises(ValueError, match="unique"):
        KoreanLexicalNormalizer([JohahadaRule(), JohahadaRule()])


from pathlib import Path
import json

REAL_CASES = json.loads(
    (Path(__file__).parent / "fixtures/johahada_regressions.json").read_text(
        encoding="utf8"
    )
)


@pytest.mark.parametrize("case", REAL_CASES, ids=lambda case: str(case["note_id"]))
def test_observed_collection_decompositions(session, case):
    service = KnowledgeIngestionService(session)
    projected = service.preview(case["text"])
    normalized = [
        service.normalizer.normalize(unit) for unit in projected["analysis"].units
    ]
    assert any("좋아하다" in unit.canonical_heads for unit in normalized)
    for unit in normalized:
        if unit.matches:
            assert unit.canonical_heads == ("좋아하다",)
            assert unit.raw_heads == ("좋다", "하다")
    service.ingest(case["text"], "real-regression:" + str(case["note_id"]))
    assert service.knowledge.get_lexical("좋아하다") is not None


from dataclasses import replace


def test_rule_requires_pos_adjacency_and_source_composition(session):
    service = KnowledgeIngestionService(session)
    unit = next(
        u for u in service.preview("뭐 좋아해요?")["analysis"].units if u.surface == "좋아해요"
    )
    assert service.normalizer.normalize(unit).matches
    for modified in [
        replace(unit, surface="좋어해요"),
        replace(
            unit,
            morphemes=(
                unit.morphemes[0],
                replace(unit.morphemes[1], tag="EF"),
                *unit.morphemes[2:],
            ),
        ),
        replace(
            unit,
            morphemes=(
                unit.morphemes[0],
                replace(unit.morphemes[1], start=unit.morphemes[1].start + 1),
                *unit.morphemes[2:],
            ),
        ),
    ]:
        assert not service.normalizer.normalize(modified).matches


def test_generic_conjugations_share_identity_across_sources(session):
    service = KnowledgeIngestionService(session)
    existing = service.knowledge.get_or_create_lexical("좋아하다")
    for index, text in enumerate(["좋아하면", "좋아해서", "뭐 좋아해요?"]):
        result = service.ingest(
            text,
            f"context:{index}",
            source_type=["tprs", "podcast", "conversation"][index],
        )
        assert existing["id"] in result["item_ids"]
    assert len(service.knowledge.list_occurrences(existing["id"])) == 3
