"""Observable Korean behavior with the real Kiwi model and Lute contract."""
from pathlib import Path
from types import SimpleNamespace
import pytest
import yaml
from lute.models.language import Language
from lute.parse.base import ParsedToken
from lute.parse.registry import init_parser_plugins, get_parser
from lute_korean_parser.analysis import KoreanAnalyzer
from lute_korean_parser.parser import KoreanParser
from lute_korean_parser.install import install_definition


SENTENCES = [
    "시간이 있으면 공부할 거예요.",
    "오늘은 피곤해서 일찍 잘 거예요.",
    "한국에 가면 많이 먹을 거예요.",
    "죄송한데 잘 못 알아들었어요.",
    "이거 먹어 보고 싶은데 많이 매워요?",
    "양고기 집에 가서 양고기를 먹었어요.",
]


@pytest.fixture(scope="module")
def analyzer():
    return KoreanAnalyzer()


@pytest.fixture
def language():
    import lute_korean_parser.install as module

    definition = Path(module.__file__).with_name("definition.yaml")
    return Language.from_dict(yaml.safe_load(definition.read_text(encoding="utf8")))


@pytest.mark.parametrize(
    "surface,lemma",
    [
        ("먹어요", "먹다"),
        ("먹었어요", "먹다"),
        ("가요", "가다"),
        ("갔어요", "가다"),
        ("있어요", "있다"),
        ("없어요", "없다"),
        ("피곤해서", "피곤하다"),
        ("먹으면", "먹다"),
        ("먹어서", "먹다"),
        ("먹고", "먹다"),
    ],
)
def test_predicates(analyzer, surface, lemma):
    unit = analyzer.analyze(surface).units[0]
    assert unit.surface == surface
    assert unit.lemma == lemma
    assert unit.grammatical_tokens


@pytest.mark.parametrize(
    "surface,head,particle",
    [
        ("한국에", "한국", "에"),
        ("집에서", "집", "에서"),
        ("저는", "저", "는"),
        ("친구랑", "친구", "랑"),
        ("밥을", "밥", "을"),
    ],
)
def test_particles(analyzer, surface, head, particle):
    unit = analyzer.analyze(surface).units[0]
    assert unit.surface == surface and unit.lemma == head
    assert any(
        m.form == particle and m.pos.startswith("J") for m in unit.grammatical_tokens
    )


@pytest.mark.parametrize(
    "text",
    SENTENCES
    + [
        "오늘 친구랑 같이 밥을 먹었어요.",
        "  한국에\t가요!  Python3와 café 123을 읽어요…🙂\n끝.",
        "한글 ㄱㄴ 한글ABC123",
        "",
        "!?",
        "말해 주세요",
    ],
)
def test_lossless_tokens(text, language):
    ParsedToken.reset_counters()
    tokens = KoreanParser().get_parsed_tokens(text, language)
    assert "".join(t.token for t in tokens).replace("¶", "\n") == text
    assert [t.order for t in tokens] == list(range(1, len(tokens) + 1))
    if text == "오늘 친구랑 같이 밥을 먹었어요.":
        assert [t.token for t in tokens if t.is_word] == [
            "오늘",
            "친구랑",
            "같이",
            "밥을",
            "먹었어요",
        ]
    if text == "!?":
        assert all(t.is_end_of_sentence and not t.is_word for t in tokens)


def test_paragraph_protocol(language):
    ParsedToken.reset_counters()
    tokens = KoreanParser().get_parsed_tokens("가요.\r\n\n와요?", language)
    assert "".join(t.token for t in tokens) == "가요.¶¶와요?"
    assert [t.sentence_number for t in tokens] == [0, 0, 1, 2, 3, 3]


@pytest.mark.parametrize("text", SENTENCES)
def test_context_analysis(analyzer, text):
    result = analyzer.analyze(text)
    assert result.text == text
    assert [u.surface for u in result.units] == text.rstrip(".?").split()
    for u in result.units:
        assert text[u.start : u.end] == u.surface
        assert u.morphemes
    assert all(0 <= m.start <= m.end <= len(text) for m in result.morphemes)
    assert all(m.raw.form == m.form for m in result.morphemes)


@pytest.mark.parametrize(
    "text,form",
    [
        (SENTENCES[0], "으면"),
        (SENTENCES[1], "어서"),
        (SENTENCES[2], "면"),
        (SENTENCES[3], "었"),
        (SENTENCES[4], "은데"),
        (SENTENCES[5], "었"),
    ],
)
def test_grammar_retained(analyzer, text, form):
    assert any(
        m.form == form and m.is_grammatical for m in analyzer.analyze(text).morphemes
    )


def test_desire_and_future(analyzer):
    desire = analyzer.analyze("먹어 보고 싶어요")
    assert "싶다" in [h for u in desire.units for h in u.lexical_heads]
    assert any(m.form == "고" for m in desire.morphemes)
    future = analyzer.analyze(SENTENCES[0])
    assert any(m.pos == "ETM" for m in future.morphemes)
    assert any(u.surface == "거예요" for u in future.units)


def test_past_polite_and_contraction(analyzer):
    result = analyzer.analyze("먹었어요")
    assert any(m.form == "었" and m.pos == "EP" for m in result.morphemes)
    assert any(m.form == "어요" and m.pos == "EF" for m in result.morphemes)
    contracted = analyzer.analyze("갔어요")
    assert contracted.units[0].lemma == "가다"
    assert len(contracted.morphemes) >= 3


def test_foreign_text_and_offsets(analyzer):
    text = "Python3와 café에서 123을 봐요.\r\n🙂"
    result = analyzer.analyze(text)
    assert result.text == text
    assert [u.surface for u in result.units] == ["Python3와", "café에서", "123을", "봐요"]
    assert all(text[u.start : u.end] == u.surface for u in result.units)
    assert result.morphemes


def test_no_analysis_preserves_unknown():
    empty = SimpleNamespace(tokenize=lambda text: [])
    result = KoreanAnalyzer(empty).analyze("낯선ABC123")
    unit = result.units[0]
    assert unit.surface == "낯선ABC123" and unit.lemma is None
    assert unit.lexical_heads == () and result.morphemes == ()


def test_model_error_is_not_hidden():
    class Broken:
        def tokenize(self, text):
            raise RuntimeError("model failed")

    with pytest.raises(RuntimeError, match="model failed"):
        KoreanAnalyzer(Broken()).analyze("먹어요")


def test_registry_and_definition(language):
    init_parser_plugins()
    assert isinstance(get_parser("lute_korean"), KoreanParser)
    assert language.name == "Korean" and language.is_supported
    assert language.character_substitutions == ""
    assert language.get_parsed_tokens("먹었어요")[0].token == "먹었어요"
    assert language.parser.analyze("먹었어요").units[0].lemma == "먹다"


def test_install_definition(tmp_path):
    target = install_definition(tmp_path)
    assert target.exists()
    assert install_definition(tmp_path) == target
    target.write_text("custom", encoding="utf8")
    with pytest.raises(FileExistsError):
        install_definition(tmp_path)
    assert target.read_text() == "custom"


def test_zero_length_copula_kept(analyzer):
    result = analyzer.analyze("거예요")
    assert all(m in result.units[0].morphemes for m in result.morphemes)
    assert any(m.pos == "VCP" for m in result.units[0].grammatical_tokens)


def test_foreign_lexical_heads(analyzer):
    result = analyzer.analyze("Python 123")
    assert result.units[0].lemma.lower() == "python"
    assert result.units[1].lemma == "123"


def test_unfamiliar_input_real_kiwi(analyzer, language):
    text = "뛟쀍XYZ123"
    result = analyzer.analyze(text)
    assert result.units[0].surface == text
    assert result.text == text
    assert (
        "".join(t.token for t in KoreanParser().get_parsed_tokens(text, language))
        == text
    )


def test_no_word_analysis_and_original_newlines(analyzer):
    for text in ["", "!?🙂", "\r\n\t"]:
        result = analyzer.analyze(text)
        assert result.text == text and result.units == ()
