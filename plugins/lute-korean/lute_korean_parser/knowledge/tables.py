"""SQLAlchemy mappings for migration-owned tables; no global ORM registration."""
from sqlalchemy import Column, Integer, MetaData, String, Table

metadata = MetaData()


def table(name, *columns):
    return Table("korean_knowledge_" + name, metadata, *columns)


items = table(
    "items",
    Column("id", String, primary_key=True),
    Column("kind", String),
    Column("identity", String),
    Column("status", String),
)
dimensions = table(
    "dimensions",
    Column("item_id", String, primary_key=True),
    Column("dimension", String, primary_key=True),
    Column("status", String),
)
sources = table(
    "sources",
    Column("id", String, primary_key=True),
    Column("source_type", String),
    Column("reference", String),
    Column("content_hash", String),
    Column("content", String),
    Column("lute_text_id", Integer),
)
occurrences = table(
    "occurrences",
    Column("id", String, primary_key=True),
    Column("source_id", String),
    Column("start", Integer),
    Column("end", Integer),
    Column("surface", String),
    Column("context_start", Integer),
    Column("context_end", Integer),
    Column("metadata", String),
)
links = table(
    "occurrence_items",
    Column("occurrence_id", String, primary_key=True),
    Column("item_id", String, primary_key=True),
)
evidence = table(
    "evidence",
    Column("id", String, primary_key=True),
    Column("item_id", String),
    Column("occurrence_id", String),
    Column("evidence_type", String),
    Column("source_type", String),
    Column("source_reference", String),
    Column("dimension", String),
    Column("surface", String),
    Column("context", String),
    Column("occurred_at", String),
    Column("metadata", String),
    Column("event_key", String),
)

roles = table(
    "roles",
    Column("item_id", String, primary_key=True),
    Column("role", String),
    Column("origin", String),
    Column("metadata", String),
)
relations = table(
    "relations",
    Column("source_item_id", String, primary_key=True),
    Column("target_item_id", String, primary_key=True),
    Column("relation_type", String, primary_key=True),
    Column("metadata", String),
)
