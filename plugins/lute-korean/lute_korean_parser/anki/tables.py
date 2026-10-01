"""Mappings for migration-owned Anki provenance and operational state."""
from sqlalchemy import Column, Integer, String, Table
from ..knowledge.tables import metadata


def table(name, *columns):
    return Table("korean_anki_" + name, metadata, *columns)


def text(name, primary=False):
    return Column(name, String, primary_key=primary)


def integer(name, primary=False):
    return Column(name, Integer, primary_key=primary)


integrations = table(
    "integrations",
    text("identity", True),
    text("profile"),
    text("last_success"),
    text("report"),
)
notes = table(
    "notes",
    text("integration", True),
    integer("note_id", True),
    text("source_id"),
    text("content_hash"),
    text("mapping_hash"),
    integer("modified"),
    text("state"),
    text("metadata"),
)
revisions = table(
    "revisions",
    text("integration", True),
    integer("note_id", True),
    text("source_id"),
    text("observed_at", True),
    integer("effective_from"),
    text("metadata"),
)
cards = table(
    "cards",
    text("integration", True),
    integer("card_id", True),
    integer("note_id"),
    text("deck"),
    integer("ordinal"),
    text("state"),
    integer("review_cursor"),
    text("metadata"),
)
reviews = table(
    "reviews",
    text("integration", True),
    integer("card_id", True),
    integer("review_id", True),
    integer("note_id"),
    text("source_id"),
    text("event_key"),
    text("occurred_at"),
    integer("rating"),
    integer("interval"),
    integer("previous_interval"),
    integer("review_type"),
    integer("duration_ms"),
    integer("factor"),
    integer("usn"),
    text("metadata"),
)
