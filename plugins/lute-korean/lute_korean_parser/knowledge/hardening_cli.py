"""Explicit human imports and read-only integrity/overlap diagnostics."""
import argparse
import json
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from .human import HumanEvidenceService
from .representation import KnowledgeRepresentationService
from .ingestion import KnowledgeIngestionService


def evidence_main(argv=None):
    """No writes except an explicit apply command on an existing database."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["validate", "preview", "apply", "preview-human-calibration"]
    )
    parser.add_argument("file", nargs="?", type=Path)
    parser.add_argument("--database", type=Path)
    args = parser.parse_args(argv)
    if args.command == "preview-human-calibration":
        print(
            json.dumps(
                {
                    "candidates": [],
                    "writes": 0,
                    "warning": (
                        "No structured verified human observations supplied; "
                        "no events inferred."
                    ),
                }
            )
        )
        return
    if not args.file or not args.database or not args.database.is_file():
        parser.error("A JSON file and existing --database are required")
    engine = _engine(args.database, args.command == "apply")
    try:
        with Session(engine) as session:
            service = HumanEvidenceService(session)
            document = json.loads(args.file.read_text(encoding="utf8"))
            if args.command == "apply":
                with session.begin():
                    result = service.apply(document)
            else:
                result = service.preview(document)
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, SQLAlchemyError) as exc:
        parser.exit(1, str(exc) + "\n")
    finally:
        engine.dispose()


def _engine(path, writable=False):
    database = str(path.resolve()) if writable else path.resolve().as_uri() + "?mode=ro"
    return create_engine(
        URL.create(
            "sqlite", database=database, query={} if writable else {"uri": "true"}
        )
    )


def knowledge_main(argv=None):
    """Audit existing links, or inspect a pure morphological projection."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["audit-integrity", "inspect-overlap"])
    parser.add_argument("text", nargs="?")
    parser.add_argument("--database", type=Path)
    args = parser.parse_args(argv)
    if args.command == "audit-integrity":
        if not args.database or not args.database.is_file():
            parser.error("audit-integrity requires an existing --database")
        engine = _engine(args.database)
        with Session(engine) as session:
            result = KnowledgeRepresentationService(session).audit_integrity()
        engine.dispose()
    else:
        if not args.text:
            parser.error("inspect-overlap requires text")
        # A pure projection uses morphology-selected spans and a declared component,
        # identical to the persisted resolver's containment contract.
        projection = KnowledgeIngestionService(None).preview(args.text)
        grammar = [
            {"identity": p.pattern, "start": p.start, "end": p.end}
            for p in projection["grammar"]
        ]
        lexical = [
            {"identity": head, "start": unit.start, "end": unit.end}
            for unit, normalized in zip(
                projection["analysis"].units, projection["normalized"]
            )
            for head in projection["lexical"]
            if head in normalized.canonical_heads
        ]
        suppressed = [
            dict(item, reason="component_of tracked construction -고 싶다")
            for item in lexical
            if item["identity"] == "싶다"
            and any(
                p["identity"] == "-고 싶다"
                and p["start"] <= item["start"]
                and item["end"] <= p["end"]
                for p in grammar
            )
        ]
        result = {
            "raw_items": lexical + grammar,
            "effective_items": [
                x
                for x in lexical
                if not any(
                    x["identity"] == y["identity"] and x["start"] == y["start"]
                    for y in suppressed
                )
            ]
            + grammar,
            "suppressed_overlap": suppressed,
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
