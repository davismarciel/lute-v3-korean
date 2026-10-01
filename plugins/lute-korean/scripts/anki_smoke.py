"""Read-only manual smoke check against local AnkiConnect; no database is opened."""
import argparse
import json
from lute_korean_parser.anki.adapter import AnkiConnectSourceAdapter
from lute_korean_parser.anki.config import AnkiConfig
from lute_korean_parser.anki.sync import AnkiSyncService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    config = AnkiConfig.load(args.config)
    result = AnkiSyncService(None, AnkiConnectSourceAdapter(config), config).doctor()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
