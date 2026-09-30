"""Lossless display segmentation, independent of morphological segmentation."""
import unicodedata


def is_word_character(char):
    """Letters, numbers and combining marks include Hangul and mixed scripts."""
    return unicodedata.category(char)[0] in "LNM"


def spans(text):
    """Yield source spans; keep word runs whole and all other characters verbatim."""
    start = 0
    while start < len(text):
        end = start + 1
        word = is_word_character(text[start])
        if word:
            while end < len(text) and is_word_character(text[end]):
                end += 1
        yield start, end, word
        start = end
