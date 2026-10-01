"""Read-only diagnostic by default; explicit --persist and --database for writes."""
import argparse
import json
import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from .ingestion import KnowledgeIngestionService
from .service import DIMENSIONS, KnowledgeService


def main(argv=None):
    """Run diagnosis, or explicitly persist into an existing migrated database."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", nargs="?")
    parser.add_argument(
        "--file", type=Path, help="UTF-8 transcript (exclusive with text)"
    )
    parser.add_argument("--persist", action="store_true")
    parser.add_argument(
        "--database", type=Path, help="Existing, migrated Lute SQLite database"
    )
    parser.add_argument(
        "--source-reference", help="Stable source revision key for persistence"
    )
    parser.add_argument("--dimension", choices=sorted(DIMENSIONS), default="reading")
    parser.add_argument(
        "--export", type=Path, help="Write knowledge JSON after persistence"
    )
    args = parser.parse_args(argv)
    if (args.text is None) == (args.file is None):
        parser.error("Provide exactly one of text or --file")
    if args.persist and (args.database is None or not args.source_reference):
        parser.error("--persist requires --database and --source-reference")
    if not args.persist and (
        args.database is not None or args.source_reference or args.export
    ):
        parser.error("Database, source-reference and export require --persist")
    if args.persist and not args.database.is_file():
        parser.error("--database must be an existing migrated Lute database")
    try:
        if args.file:
            with args.file.open("r", encoding="utf8", newline="") as source_file:
                text = source_file.read()
        else:
            text = args.text
        if not args.persist:
            projected = KnowledgeIngestionService(None).preview(text)
            print("LEXICAL")
            for lemma in projected["lexical"]:
                print(lemma)
            print("\nGRAMMAR")
            for pattern in dict.fromkeys(d.pattern for d in projected["grammar"]):
                print(pattern)
            return
        engine = create_engine(
            URL.create("sqlite", database=str(args.database.resolve()))
        )
        try:
            with Session(engine) as session, session.begin():
                ingestion = KnowledgeIngestionService(session)
                result = ingestion.ingest(
                    text, args.source_reference, dimension=args.dimension
                )
                exported = KnowledgeService(session).export()
            if args.export:
                args.export.write_text(
                    json.dumps(exported, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf8",
                )
            print(json.dumps(result, ensure_ascii=False, indent=2))
        finally:
            engine.dispose()
    except (OSError, ValueError, SQLAlchemyError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main(sys.argv[1:])
