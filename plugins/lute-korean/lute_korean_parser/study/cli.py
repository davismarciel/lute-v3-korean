"""Explicit actual study sessions for advanced local workflows and validation."""
import argparse
from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from ..ci.adapters import adapt_content, ADAPTERS
from .service import StudySessionService


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["start", "complete", "partial", "list", "show"]
    )
    parser.add_argument(
        "value", nargs="?", help="Content file for start; session ID otherwise"
    )
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--writable", action="store_true")
    parser.add_argument(
        "--activity",
        choices=["reading", "listening_with_transcript", "listening", "mixed"],
        default="reading",
    )
    parser.add_argument("--transcript-read", action="store_true")
    parser.add_argument("--request-key")
    parser.add_argument("--format", choices=["auto", *ADAPTERS], default="auto")
    parser.add_argument(
        "--kind",
        choices=["text", "tprs", "podcast", "dialogue", "subtitle"],
        default="text",
    )
    parser.add_argument(
        "--start", type=int, default=0, help="Zero-based inclusive first segment"
    )
    parser.add_argument("--end", type=int, help="Zero-based inclusive last segment")
    parser.add_argument(
        "--started-at", help="Explicit actual historical start, aware ISO time"
    )
    parser.add_argument(
        "--occurred-at", help="Explicit actual consumption time, aware ISO time"
    )
    parser.add_argument("--reference")
    args = parser.parse_args(argv)
    mutable = args.command in {"start", "complete", "partial"}
    if mutable and not args.writable:
        parser.error("Mutating commands require explicit --writable")
    if not args.database.is_file():
        parser.error("Database must already exist and be migrated")
    if args.command != "list" and not args.value:
        parser.error("Provide content file or session ID")
    engine = create_engine(
        URL.create(
            "sqlite",
            database=args.database.resolve().as_uri()
            + ("?mode=rw" if mutable else "?mode=ro"),
            query={"uri": "true"},
        )
    )
    try:
        with Session(engine) as session:
            service = StudySessionService(session)
            if args.command == "start":
                path = Path(args.value)
                with path.open(encoding="utf8", newline="") as handle:
                    text = handle.read()
                candidate = adapt_content(text, path.name, args.format, args.kind)
                result = service.start(
                    candidate,
                    args.activity,
                    args.request_key or str(uuid4()),
                    args.transcript_read,
                    external_reference=args.reference,
                    started_at=datetime.fromisoformat(args.started_at)
                    if args.started_at
                    else None,
                )
            elif args.command in {"complete", "partial"}:
                result = service.consume(
                    args.value,
                    args.start,
                    args.end,
                    completed=args.command == "complete",
                    occurred_at=datetime.fromisoformat(args.occurred_at)
                    if args.occurred_at
                    else None,
                )
            elif args.command == "list":
                result = service.list()
            else:
                result = service.show(args.value)
            if mutable:
                session.commit()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, OSError, SQLAlchemyError) as exc:
        parser.exit(1, f"Study action failed: {exc}\n")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
