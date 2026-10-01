"""Analyze/compare local candidates using read-only Knowledge SQLite."""
import argparse
import json
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from .analyzer import CIContentAnalyzer
from .adapters import ADAPTERS
from .export import compact_report, compare_reports


def main(argv=None):
    """No migrations, Sources, Evidence, item creation, or Anki operations."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["analyze", "compare"])
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--text", help="Direct Unicode text, exclusive with files")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--format", choices=["auto", *ADAPTERS], default="auto")
    parser.add_argument(
        "--kind",
        choices=["text", "podcast", "dialogue", "tprs", "subtitle"],
        default="text",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--export", type=Path)
    parser.add_argument("--as-of", help="Timezone-aware learner snapshot clock")
    args = parser.parse_args(argv)
    if not args.database.is_file():
        parser.error("--database must be an existing migrated staging database")
    if args.command == "analyze" and (
        (len(args.files) != 1 and args.text is None)
        or (args.files and args.text is not None)
    ):
        parser.error("Analyze requires one file or --text")
    if args.command == "compare" and (len(args.files) < 2 or args.text is not None):
        parser.error("Compare requires at least two files")
    if any(not path.is_file() for path in args.files):
        parser.error("Every candidate file must exist locally")
    if args.export:
        protected = [args.database, *args.files]
        if any(
            args.export.resolve() == path.resolve()
            or (args.export.exists() and args.export.samefile(path))
            for path in protected
        ):
            parser.error("Export cannot overwrite the database or candidate input")
        if str(args.export.resolve()) in {
            str(args.database.resolve()) + suffix
            for suffix in ["-wal", "-shm", "-journal"]
        }:
            parser.error("Export cannot overwrite a database sidecar")
    engine = create_engine(
        URL.create(
            "sqlite",
            database=args.database.resolve().as_uri() + "?mode=ro",
            query={"uri": "true"},
        )
    )
    try:
        as_of = datetime.fromisoformat(args.as_of) if args.as_of else None
        with Session(engine) as session:
            analyzer = CIContentAnalyzer(session, as_of=as_of)
            inputs = []
            if args.text is not None:
                inputs.append(("direct text", args.text))
            else:
                for path in args.files:
                    with path.open(encoding="utf8", newline="") as handle:
                        inputs.append((str(path), handle.read()))
            reports = [
                analyzer.analyze_text(
                    text, name=name, format=args.format, kind=args.kind
                )
                for name, text in inputs
            ]
            if args.compact:
                reports = [
                    compact_report(report, analyzer.policy) for report in reports
                ]
            result = (
                reports[0] if args.command == "analyze" else compare_reports(reports)
            )
        if args.export:
            args.export.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
            )
        if args.json or args.compact:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "compare":
            print(
                "CONTENT | FIT | CONFIDENCE | SUPPORTED COVERAGE | UNTRACKED COVERAGE | DENSE SEGMENTS"
            )
            for row in result["candidates"]:
                print(
                    f"{row['content']} | {row['fit']} | {row['confidence']} | {row['supported_lexical_occurrence_coverage']:.1%} | {row['untracked_lexical_occurrence_coverage']:.1%} | {row['dense_segment_ratio']:.1%}"
                )
        else:
            print(
                f"{result['summary']['fit']} / {result['summary']['confidence']} — {result['summary']['assessment']}"
            )
            for reason in result["summary"]["reasons"]:
                print("Reason: " + reason)
            for row in result["novelties"]:
                print(
                    f"{row['identity']}: {row['bucket']}; {row['count']} occurrences; {row['contexts']} contexts"
                )
            for warning in result["warnings"]:
                print("Warning: " + warning)
    except (OSError, ValueError, SQLAlchemyError) as exc:
        parser.exit(1, str(exc) + "\n")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
