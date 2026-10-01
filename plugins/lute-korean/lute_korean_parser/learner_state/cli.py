"""Inspect/calculate/compare/calibrate read-only suggestions, never apply them."""
import argparse
from datetime import datetime
import json
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from .engine import LearnerStateEngine
from .policy import LearnerStatePolicyV1
from .calibration import select_sample


def public_export(result, diagnostics=False):
    """Hide internal strength by default; keep categorical, provenance-rich output."""
    result = json.loads(json.dumps(result))
    if not diagnostics:
        items = result.get("items", [result] if "suggested_state" in result else [])
        for item in items:
            for state in item["suggested_state"].values():
                state["evidence_quality"].pop("positive_strength", None)
                state["evidence_quality"].pop("negative_strength", None)
    return result


def render(item):
    """Human inspection contains categories and explanation, never mastery percent."""
    lines = [item["identity"], f"Manual overall: {item['manual_state']['overall']}"]
    for dimension, state in item["suggested_state"].items():
        lines.append(
            f"{dimension}: manual={item['manual_state'][dimension] or 'unassessed'}; "
            f"suggested={state['status']} ({state['confidence']})"
        )
        lines.extend("  Reason: " + reason for reason in state["reasons"])
        lines.extend("  Warning: " + warning for warning in state["warnings"])
    summary = item["evidence"]
    lines.append(
        f"Evidence: {summary['occurrences']} occurrences; {summary['sources']} sources; "
        f"{summary['contexts']} contexts; {len(summary['surfaces'])} surfaces; "
        f"{summary['anki_notes']} Anki notes; {summary['anki_reviews']} indirect Anki events"
    )
    return "\n".join(lines)


def main(argv=None):
    """All commands open an existing database with SQLite mode=ro."""
    # Independent CLI flags are validated before opening the read-only database.
    # pylint: disable=too-many-branches
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["inspect", "calculate", "compare", "calibrate"]
    )
    parser.add_argument("identity", nargs="?")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--kind", choices=["lexical", "grammar", "chunk"])
    parser.add_argument(
        "--policy",
        type=Path,
        help="JSON policy overrides; fingerprint records all parameters",
    )
    parser.add_argument(
        "--as-of", help="Timezone-aware ISO timestamp, for reproducible calculations"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=25,
        help="Lexical sample size; all grammar patterns also included",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--export", type=Path)
    args = parser.parse_args(argv)
    if not args.database.is_file():
        parser.error("An existing migrated --database is required")
    if args.command == "inspect" and args.identity is None:
        parser.error("inspect requires identity or item ID")
    if args.command != "inspect" and args.identity is not None:
        parser.error("Identity is only accepted by inspect")
    if args.export and args.export.resolve() == args.database.resolve():
        parser.error("Export cannot overwrite the database")
    try:
        policy = (
            LearnerStatePolicyV1(**json.loads(args.policy.read_text(encoding="utf8")))
            if args.policy
            else LearnerStatePolicyV1()
        )
        as_of = datetime.fromisoformat(args.as_of) if args.as_of else None
        # URI quoting is handled by pathlib; Windows drive paths remain valid.
        engine = create_engine(
            URL.create(
                "sqlite",
                database=args.database.resolve().as_uri() + "?mode=ro",
                query={"uri": "true"},
            )
        )
        try:
            with Session(engine) as session:
                state = LearnerStateEngine(session, policy)
                if args.command == "inspect":
                    result = state.inspect(args.identity, args.kind, as_of)
                elif args.command == "compare":
                    result = state.compare(args.kind, as_of)
                elif args.command == "calibrate":
                    result = select_sample(state.calculate(as_of=as_of), args.count)
                else:
                    result = state.calculate(args.kind, as_of=as_of)
        finally:
            engine.dispose()
        result = public_export(result, args.diagnostics)
        output = json.dumps(result, ensure_ascii=False, indent=2)
        if args.export:
            args.export.write_text(output + "\n", encoding="utf8")
        if args.json or args.command != "inspect":
            print(output)
        else:
            print(render(result))
    except (ValueError, TypeError, OSError, SQLAlchemyError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
