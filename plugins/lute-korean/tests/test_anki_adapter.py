"""AnkiConnect protocol tests with local fake transport, including HTTP batching."""
from pathlib import Path
import json
from dataclasses import replace
import pytest
import requests
from lute_korean_parser.anki.adapter import AnkiConnectSourceAdapter
from lute_korean_parser.anki.config import AnkiConfig, NoteTypeMapping
from lute_korean_parser.anki.models import AnkiError
from lute_korean_parser.anki.cli import main


class Transport:
    def __init__(self):
        self.calls = []
        self.failure = None
        self.error = None
        self.redirect = False

    def post(self, endpoint, json, timeout, allow_redirects):
        if self.failure:
            raise requests.ConnectionError(self.failure)
        self.calls.append((json["action"], json["params"]))
        action = json["action"]
        params = json["params"]
        if action == "version":
            value = 6
        elif action == "getActiveProfile":
            value = "Fixture"
        elif action == "findNotes":
            value = [1, 2, 3, 4, 5]
        elif action == "notesInfo":
            value = [
                {
                    "noteId": i,
                    "modelName": "Basic",
                    "tags": [],
                    "mod": 1700000000,
                    "cards": [i * 2, i * 2 + 1],
                    "fields": {
                        "Front": {"value": "한국에 가면 많이 먹을 거예요."},
                        "Back": {"value": "Meaning"},
                    },
                }
                for i in params["notes"]
            ]
        elif action == "cardsInfo":
            value = [
                {
                    "cardId": i,
                    "note": i // 2,
                    "ord": i % 2,
                    "modelName": "Basic",
                    "deckName": "Fixture",
                    "queue": 0,
                }
                for i in params["cards"]
            ]
        elif action == "modelTemplates":
            value = {
                "Forward": {"Front": "{{Front}}", "Back": "{{FrontSide}} {{Back}}"},
                "Reverse": {"Front": "{{Back}}", "Back": "{{Front}}"},
            }
        elif action == "getReviewsOfCards":
            value = {
                str(i): [
                    {
                        "id": 1700000010000 + i,
                        "ease": 3,
                        "ivl": 4,
                        "lastIvl": 1,
                        "type": 1,
                        "time": 1000,
                        "factor": 2500,
                        "usn": 0,
                    }
                ]
                for i in params["cards"]
            }
        elif action == "cardReviews":
            value = [
                [1700000020000 + i, i, 0, 4, 7, 4, 2500, 2000, 1] for i in range(2, 12)
            ]
        else:
            raise AssertionError(action)
        return Response(
            {"result": value, "error": self.error}, 302 if self.redirect else 200
        )


class Response:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def test_readonly_transport_batching_and_incremental_reviews():
    config = AnkiConfig(
        "fixture",
        {"Basic": NoteTypeMapping(("Front",), ("Back",))},
        batch_size=2,
        profile="Fixture",
    )
    transport = Transport()
    adapter = AnkiConnectSourceAdapter(config, transport)
    assert adapter.health() == {"version": 6, "profile": "Fixture"}
    ids = adapter.find_notes("note:Basic")
    notes = adapter.fetch_notes(ids)
    cards = adapter.fetch_cards(cid for n in notes for cid in n.card_ids)
    reviews = adapter.fetch_reviews(cards, {})
    assert len(notes) == 5 and len(cards) == 10 and len(reviews) == 10
    assert len([c for c in transport.calls if c[0] == "notesInfo"]) == 3
    assert len([c for c in transport.calls if c[0] == "cardsInfo"]) == 5
    assert len([c for c in transport.calls if c[0] == "modelTemplates"]) == 1
    assert len([c for c in transport.calls if c[0] == "getReviewsOfCards"]) == 5
    assert cards[1].metadata["question_fields"] == ["Back"]
    assert cards[1].metadata["answer_fields"] == ["Front"]
    assert adapter.fetch_reviews(cards, {c.card_id: 1700000015000 for c in cards})
    assert transport.calls[-1] == (
        "cardReviews",
        {"deck": "Fixture", "startID": 1700000015000},
    )
    assert not transport.trust_env
    with pytest.raises(AnkiError, match="read-only"):
        adapter._call("addNote")


def test_transport_failures_redirects_and_profile():
    config = AnkiConfig("test", {})
    transport = Transport()
    adapter = AnkiConnectSourceAdapter(config, transport)
    transport.failure = "not running"
    with pytest.raises(AnkiError, match="failed"):
        adapter.health()
    transport.failure = None
    transport.error = "query invalid"
    with pytest.raises(AnkiError, match="query invalid"):
        adapter.find_notes("invalid")
    transport.error = None
    transport.redirect = True
    with pytest.raises(AnkiError, match="redirect"):
        adapter.health()
    transport.redirect = False
    with pytest.raises(AnkiError, match="profile"):
        AnkiConnectSourceAdapter(replace(config, profile="Other"), transport).health()


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://example.com",
        "http://192.168.1.2:8765",
        "http://user:pass@localhost:8765",
        "http://localhost:8765?a=b",
    ],
)
def test_external_endpoints_rejected(endpoint):
    with pytest.raises(ValueError):
        AnkiConfig("fixture", {}, endpoint=endpoint)


def test_config_query_and_field_validation(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        """anki:
  source_identity: fixture
  query: tag:travel
  decks: [Deck A, Deck B]
  note_types: [Basic]
  mappings:
    Basic:
      korean_fields: [Front]
      translation_fields: [Back]
"""
    )
    config = AnkiConfig.load(path)
    assert config.mappings["Basic"].korean_fields == ("Front",)
    assert (
        config.search_query()
        == '(tag:travel) (deck:"Deck A" or deck:"Deck B") (note:"Basic")'
    )
    with pytest.raises(ValueError):
        AnkiConfig("fixture", {"Basic": NoteTypeMapping(())})


def test_cli_preview_doctor_and_sync_flags(tmp_path, monkeypatch, capsys):
    import lute_korean_parser.anki.cli as module

    config = tmp_path / "config.yml"
    config.write_text(
        """source_identity: fixture
mappings:
  Basic:
    korean_fields: [Front]
    translation_fields: [Back]
"""
    )
    monkeypatch.setattr(
        module,
        "AnkiConnectSourceAdapter",
        lambda config: AnkiConnectSourceAdapter(config, Transport()),
    )
    main(["preview", "--config", str(config)])
    assert json.loads(capsys.readouterr().out)["notes_found"] == 5
    main(["doctor", "--config", str(config)])
    assert json.loads(capsys.readouterr().out)["ok"]
    with pytest.raises(SystemExit):
        main(["sync", "--config", str(config)])
    with pytest.raises(SystemExit):
        main(["preview", "--config", str(config), "--dry-run"])


def test_config_rejects_scalar_fields(tmp_path):
    path = tmp_path / "bad.yml"
    path.write_text(
        "source_identity: fixture\nmappings:\n  Basic:\n    korean_fields: Front\n"
    )
    with pytest.raises(ValueError, match="lists"):
        AnkiConfig.load(path)
