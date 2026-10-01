"""Ephemeral content DTOs, never database Sources or Occurrences."""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class CandidateSegment:
    """Clean linguistic text and the cue/line identity that supplied it."""

    index: int
    identity: str
    text: str
    timestamp: str | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class CandidateContent:
    """One proposed input; owning it does not mean it was studied."""

    name: str
    format: str
    segments: tuple[CandidateSegment, ...]
    original_hash: str
    kind: str = "text"
    warnings: tuple[str, ...] = ()


class ContentAdapter(Protocol):
    """Formats produce the same transport-independent candidate representation."""

    def segments(self, text: str) -> tuple[CandidateSegment, ...]:
        ...
