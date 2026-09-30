"""Lute adapter: keep eojeol clickable, with morphology available separately."""
from lute.parse.base import AbstractParser, ParsedToken
from .analysis import KoreanAnalyzer
from .boundaries import spans


class KoreanParser(AbstractParser):
    """Lossless orthographic reading adapter with a separate morphology API."""

    @classmethod
    def name(cls):
        return "Korean (Kiwi)"

    def analyze(self, text):
        return KoreanAnalyzer().analyze(text)

    def get_parsed_tokens(self, text, language):
        # Lute's paragraph protocol requires ¶; analysis offsets always refer
        # to the untouched original input, including CRLF.
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        tokens = []
        for start, end, word in spans(text):
            surface = text[start:end]
            paragraph = surface in ("\n", "¶")
            token = "¶" if paragraph else surface
            eos = paragraph or (not word and surface in language.regexp_split_sentences)
            tokens.append(ParsedToken(token, word, eos))
        return tokens
