"""Operational Anki diagnosis and explicit, read-only-to-Anki synchronization."""
import argparse
import json
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from .adapter import AnkiConnectSourceAdapter
from .config import AnkiConfig
from .sync import AnkiSyncService
from .models import AnkiError
from ..knowledge.service import KnowledgeService


def main(argv=None):
    """Run explicit diagnosis, synchronization or saved-status inspection."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["doctor", "preview", "sync", "status"])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--full-reviews", action="store_true")
    parser.add_argument("--export", type=Path)
    parser.add_argument("--review-details", action="store_true")
    args = parser.parse_args(argv)
    if args.command in ("sync", "status") and (
        args.database is None or not args.database.is_file()
    ):
        parser.error("sync/status require an existing migrated --database")
    if args.command != "sync" and (
        args.dry_run or args.full_reviews or args.export or args.review_details
    ):
        parser.error("Sync flags require the sync command")
    if args.dry_run and args.export:
        parser.error("Dry-run does not write export files")
    try:
        config = AnkiConfig.load(args.config)
        adapter = AnkiConnectSourceAdapter(config)
        if args.command in ("doctor", "preview"):
            service = AnkiSyncService(None, adapter, config)
            result = getattr(service, args.command)()
        else:
            engine = create_engine(
                URL.create("sqlite", database=str(args.database.resolve()))
            )
            try:
                with Session(engine) as session, session.begin():
                    service = AnkiSyncService(session, adapter, config)
                    result = (
                        service.status()
                        if args.command == "status"
                        else service.sync(
                            dry_run=args.dry_run, full_reviews=args.full_reviews
                        )
                    )
                    exported = (
                        KnowledgeService(session).export(
                            include_anki=True, review_details=args.review_details
                        )
                        if args.export
                        else None
                    )
                if args.export:
                    args.export.write_text(
                        json.dumps(exported, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf8",
                    )
            finally:
                engine.dispose()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command == "doctor" and not result["ok"]:
            parser.exit(1)
    except (AnkiError, ValueError, SQLAlchemyError, OSError, TypeError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
