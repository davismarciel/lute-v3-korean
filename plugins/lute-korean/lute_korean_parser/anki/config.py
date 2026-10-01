"""Explicit field mapping and local source identity; no permanent guessed mapping."""
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
import ipaddress
import json
import hashlib
import yaml


@dataclass(frozen=True)
class NoteTypeMapping:
    """Explicit content, translation and context fields for one note type."""

    korean_fields: tuple
    translation_fields: tuple = ()
    metadata_fields: tuple = ()


@dataclass(frozen=True)
class AnkiConfig:  # pylint: disable=too-many-instance-attributes
    """Local connection, scope and stable collection identity."""

    source_identity: str
    mappings: dict
    endpoint: str = "http://127.0.0.1:8765"
    query: str = ""
    decks: tuple = ()
    note_types: tuple = ()
    profile: str | None = None
    batch_size: int = 200
    timeout: float = 20

    def __post_init__(self):
        if not self.source_identity.strip():
            raise ValueError("source_identity is required")
        url = urlparse(self.endpoint)
        try:
            local = (
                url.hostname == "localhost"
                or ipaddress.ip_address(url.hostname).is_loopback
            )
        except ValueError:
            local = False
        # Endpoint privacy constraints are validated together.
        # pylint: disable=too-many-boolean-expressions
        if (
            url.scheme != "http"
            or not local
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError(
                "Anki endpoint must be a local loopback HTTP URL without credentials"
            )
        if not 1 <= self.batch_size <= 500 or self.timeout <= 0:
            raise ValueError("Invalid batch_size or timeout")
        for name, mapping in self.mappings.items():
            if not name.strip() or not mapping.korean_fields:
                raise ValueError("Each mapping needs a note type and Korean fields")
            for fields in (
                mapping.korean_fields,
                mapping.translation_fields,
                mapping.metadata_fields,
            ):
                if isinstance(fields, str):
                    raise ValueError("Field mappings must be lists, not strings")
                if any(not isinstance(f, str) or not f.strip() for f in fields) or len(
                    set(fields)
                ) != len(fields):
                    raise ValueError("Field names must be nonempty and unique")

    def mapping_hash(self, note_type):
        """Hash the linguistic mapping independently of translation metadata."""
        mapping = self.mappings[note_type]
        payload = [mapping.korean_fields]
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False).encode()
        ).hexdigest()

    def search_query(self):
        """Combine configured scope using Anki search syntax."""

        def quoted(value):
            return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

        parts = [f"({self.query})"] if self.query else []
        for prefix, values in (("deck", self.decks), ("note", self.note_types)):
            if values:
                parts.append(
                    "(" + " or ".join(prefix + ":" + quoted(v) for v in values) + ")"
                )
        return " ".join(parts)

    @classmethod
    def load(cls, path):
        """Read and validate explicit YAML lists and mappings."""
        data = yaml.safe_load(Path(path).read_text(encoding="utf8"))
        if not isinstance(data, dict):
            raise ValueError("Configuration must be a YAML object")
        data = data.get("anki", data)
        if not isinstance(data, dict):
            raise ValueError("Anki configuration must be a YAML object")
        raw = data.pop("mappings", {})
        if not isinstance(raw, dict):
            raise ValueError("Mappings must be a YAML object")
        mappings = {}
        for name, mapping in raw.items():
            if not isinstance(mapping, dict) or any(
                not isinstance(v, list) for v in mapping.values()
            ):
                raise ValueError("Each note mapping requires lists of field names")
            mappings[name] = NoteTypeMapping(
                **{k: tuple(v) for k, v in mapping.items()}
            )
        for key in ("decks", "note_types"):
            if key in data:
                if not isinstance(data[key], list):
                    raise ValueError(f"{key} must be a YAML list")
                data[key] = tuple(data[key])
        return cls(mappings=mappings, **data)
