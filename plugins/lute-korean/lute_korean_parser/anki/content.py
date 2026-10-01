"""Conservative source-field diagnostics, separate from Korean morphology."""
import unicodedata

POLICY_VERSION = "anki.korean-content.v1"


def is_hangul(char):
    """Count Hangul syllables and jamo without rewriting source text."""
    return (
        "\uac00" <= char <= "\ud7a3"
        or "\u1100" <= char <= "\u11ff"
        or "\u3130" <= char <= "\u318f"
    )


def validate_korean_field(text):
    """Warn on mixed scripts; quarantine dominant Latin prose, not a brand token."""
    letters = [c for c in text if c.isalpha()]
    hangul = sum(is_hangul(c) for c in letters)
    latin = sum("LATIN" in unicodedata.name(c, "") for c in letters)
    words = ["".join(c for c in token if c.isalpha()) for token in text.split()]
    latin_words = [
        w for w in words if w and all("LATIN" in unicodedata.name(c, "") for c in w)
    ]
    lowercase = sum(w.islower() for w in latin_words)
    ratio = latin / max(len(letters), 1)
    reasons = []
    if not hangul:
        reasons.append("no_hangul")
    if latin:
        reasons.append("foreign_script_present")
    dominant = ratio >= 0.70 and len(latin_words) >= 8 and lowercase >= 6
    if dominant:
        reasons.append("dominant_latin_prose")
    status = (
        "anomalous" if not hangul or dominant else ("warning" if latin else "valid")
    )
    return {
        "version": POLICY_VERSION,
        "status": status,
        "content_language_warning": status != "valid",
        "reasons": reasons,
        "hangul_letters": hangul,
        "latin_letters": latin,
        "latin_ratio": round(ratio, 4),
        "latin_words": len(latin_words),
        "lowercase_latin_words": lowercase,
    }


def validate_fields(fields):
    """Any invalid explicitly mapped Korean field quarantines the whole note."""
    details = {name: validate_korean_field(text) for name, text in fields.items()}
    statuses = {entry["status"] for entry in details.values()}
    status = (
        "anomalous"
        if "anomalous" in statuses
        else ("warning" if "warning" in statuses else "valid")
    )
    return {
        "version": POLICY_VERSION,
        "status": status,
        "content_language_warning": status != "valid",
        "reasons": sorted(
            {reason for entry in details.values() for reason in entry["reasons"]}
        ),
        "fields": details,
    }
