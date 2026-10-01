"""Remove presentation/media markup while retaining natural Korean source text."""
import hashlib
import re
from bs4 import BeautifulSoup
from .content import validate_fields


def clean_field(raw):
    """Remove presentation markup and keep readable linguistic content."""
    soup = BeautifulSoup(raw, "html.parser")
    for element in soup(["script", "style"]):
        element.decompose()
    for element in soup.find_all("br"):
        element.replace_with("\n")
    for element in soup.find_all(["div", "p", "li"]):
        element.insert_after("\n")
    text = soup.get_text().replace("\xa0", " ")
    text = re.sub(r"\[sound:[^\]]*\]", "", text)
    # Presentation markup only, never Korean morphology or lexical rewriting.
    text = re.sub(r"\{\{c\d+::(.*?)(?:::[^{}]*)?\}\}", r"\1", text, flags=re.DOTALL)
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def has_hangul(text):
    """Identify whether a mapped field contains Korean writing."""
    return any(
        "\uac00" <= c <= "\ud7a3"
        or "\u1100" <= c <= "\u11ff"
        or "\u3130" <= c <= "\u318f"
        for c in text
    )


def extract_note(note, mapping):
    """Extract explicit Korean fields and small provenance metadata."""
    required = (
        *mapping.korean_fields,
        *mapping.translation_fields,
        *mapping.metadata_fields,
    )
    missing = [name for name in required if name not in note.fields]
    if missing:
        raise ValueError(
            f"Note type {note.note_type} missing configured fields: {missing}"
        )
    cleaned_fields = {
        name: clean_field(note.fields[name]) for name in mapping.korean_fields
    }
    text = "\n".join(cleaned_fields.values()).strip()
    return text, {
        "content_validation": validate_fields(cleaned_fields),
        "has_audio": any(
            "[sound:" in value
            or BeautifulSoup(value, "html.parser").find("audio") is not None
            for value in note.fields.values()
        ),
        "translations": {
            name: clean_field(note.fields[name]) for name in mapping.translation_fields
        },
        "fields": {
            name: clean_field(note.fields[name]) for name in mapping.metadata_fields
        },
        "raw_korean_hashes": {
            name: hashlib.sha256(note.fields[name].encode()).hexdigest()
            for name in mapping.korean_fields
        },
    }


def suggest_mapping(notes):
    """Report field Hangul sample counts without persisting a mapping."""
    suggestions = {}
    for note in notes:
        stats = suggestions.setdefault(note.note_type, {})
        for name, raw in note.fields.items():
            counts = stats.setdefault(name, {"samples": 0, "hangul": 0})
            counts["samples"] += 1
            counts["hangul"] += int(has_hangul(clean_field(raw)))
    return suggestions


def template_fields(template):
    """Preserve template field references without inferring a skill."""
    return sorted(
        {
            m.split(":")[-1].strip()
            for m in re.findall(r"\{\{([^{}]+)\}\}", template)
            if not m.startswith(("#", "/", "^")) and m != "FrontSide"
        }
    )
