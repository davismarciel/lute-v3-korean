"""Additive, migration-owned study tables; no core ORM registration."""
from sqlalchemy import Column, Integer, MetaData, String, Table

metadata = MetaData()


def table(name, columns):
    return Table(
        "korean_study_" + name,
        metadata,
        *[Column(name, type_, primary_key=pk) for name, type_, pk in columns]
    )


contents = table(
    "contents",
    [
        (n, Integer if n == "segment_count" else String, n == "id")
        for n in [
            "id",
            "content_hash",
            "name",
            "kind",
            "format",
            "segments",
            "segment_count",
            "created_at",
        ]
    ],
)
sessions = table(
    "sessions",
    [
        (n, Integer if n == "transcript_read" else String, n == "id")
        for n in [
            "id",
            "content_id",
            "request_key",
            "activity",
            "transcript_read",
            "status",
            "started_at",
            "completed_at",
            "external_reference",
            "metadata",
        ]
    ],
)
consumed = table(
    "consumed_segments",
    [
        ("session_id", String, True),
        ("segment_index", Integer, True),
        ("source_id", String, False),
        ("consumed_at", String, False),
    ],
)
observations = table(
    "observations", [("session_id", String, True), ("evidence_id", String, True)]
)
