"""Transport-independent source snapshots; usable by a future offline adapter."""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class AnkiNoteSnapshot:
    """Content identity and current note fields, independent of transport."""

    note_id: int
    note_type: str
    fields: dict
    card_ids: tuple
    tags: tuple = ()
    modified: int | None = None


@dataclass(frozen=True)
class AnkiCardSnapshot:
    """A scheduled card and its direction/template metadata."""

    card_id: int
    note_id: int
    deck: str
    ordinal: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class AnkiReviewEvent:  # pylint: disable=too-many-instance-attributes
    """One raw review event, without a pedagogical interpretation."""

    review_id: int
    card_id: int
    rating: int
    interval: int
    previous_interval: int
    review_type: int
    duration_ms: int
    factor: int = 0
    usn: int = 0


class AnkiSourceAdapter(Protocol):
    """Read-only source contract for live or future offline adapters."""

    def health(self) -> dict:
        ...

    def find_notes(self, query: str) -> list[int]:
        ...

    def fetch_notes(self, note_ids) -> list[AnkiNoteSnapshot]:
        ...

    def fetch_cards(self, card_ids) -> list[AnkiCardSnapshot]:
        ...

    def fetch_reviews(self, cards, cursors, full=False) -> list[AnkiReviewEvent]:
        ...


class AnkiError(RuntimeError):
    """Transport/protocol failures abort synchronization without partial commits."""
