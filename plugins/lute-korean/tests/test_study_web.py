"""Plugin Flask forms/routes with real services and fake external Anki only."""
import re
from pathlib import Path
from flask import Flask
import pytest
from test_study import session
from lute_korean_parser.study.web import init_app


@pytest.fixture
def app(session, tmp_path):
    raw = session.connection().connection.driver_connection
    raw.commit()
    raw.executescript(
        (
            Path(__file__).resolve().parents[3]
            / "lute/db/schema/migrations/20260930_02_korean_anki.sql"
        ).read_text()
    )
    root = Path(__file__).resolve().parents[3] / "lute"
    app = Flask(
        __name__,
        template_folder=str(root / "templates"),
        static_folder=str(root / "static"),
    )
    app.config.update(
        SECRET_KEY="fixture",
        DATAPATH=str(tmp_path),
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        KOREAN_STUDY_SESSION_FACTORY=lambda: session,
    )
    app.context_processor(
        lambda: {"user_settings": "{}", "user_hotkeys": "{}", "have_languages": True}
    )
    init_app(app)
    return app


def csrf(response):
    return re.search(rb'name="csrf_token" value="([^"]+)"', response.data)[1].decode()


def test_dashboard_and_knowledge_views_render_without_implicit_study(app, session):
    from lute_korean_parser.study.service import StudySessionService

    client = app.test_client()
    assert b"Your Korean study workspace" in client.get("/korean/").data
    assert client.get("/korean/knowledge").status_code == 200
    assert client.get("/korean/anki").status_code == 200
    assert StudySessionService(session).list() == []


def test_analyze_start_consume_refresh_and_export_end_to_end(app, session):
    from lute_korean_parser.knowledge.service import KnowledgeService

    client = app.test_client()
    form = client.get("/korean/analyze")
    response = client.post(
        "/korean/analyze",
        data={"csrf_token": csrf(form), "text": "한국에 가면 많이 먹을 거예요.", "kind": "tprs"},
    )
    assert response.status_code == 200
    assert "먹다" in response.text and "-(으)면" in response.text
    assert KnowledgeService(session).list_items() == []
    token = re.search(r'name="candidate_token" value="([^"]+)"', response.text)[1]
    key = re.search(r'name="request_key" value="([^"]+)"', response.text)[1]
    started = client.post(
        "/korean/sessions/start",
        data={
            "csrf_token": csrf(response),
            "candidate_token": token,
            "request_key": key,
            "activity": "reading",
        },
    )
    assert started.status_code == 303
    page = client.get(started.headers["Location"])
    assert "No consumption recorded yet" in page.text
    completed = client.post(
        started.headers["Location"] + "/consume",
        data={"csrf_token": csrf(page), "start": "0", "end": "0", "finish": "yes"},
    )
    assert completed.status_code == 303
    page = client.get(completed.headers["Location"])
    assert "completed" in page.text
    eat = KnowledgeService(session).get_lexical("먹다")
    assert all(
        e["evidence_type"] == "exposure"
        for e in KnowledgeService(session).list_evidence(eat["id"])
    )
    export = client.get("/korean/export/learner").get_json()
    assert export["export_kind"] == "teacher_learner_context"
    assert export["recent_study_sessions"]
    assert "raw_reviews" not in export
    refreshed = client.get("/korean/candidates/" + token)
    assert "Presented" in refreshed.text or "seen" in refreshed.text


def test_plugin_mutations_require_csrf_even_when_lute_global_protection_is_disabled(
    app,
):
    client = app.test_client()
    result = client.post("/korean/analyze", data={"text": "먹어요."})
    assert result.status_code == 400
    assert "safety check" in result.text


def test_compare_uploads_are_zero_write_and_podcast_does_not_claim_listening(
    app, session
):
    import io
    from lute_korean_parser.study.service import StudySessionService
    from lute_korean_parser.knowledge.service import KnowledgeService

    client = app.test_client()
    token = csrf(client.get("/korean/analyze"))
    response = client.post(
        "/korean/analyze",
        data={
            "csrf_token": token,
            "kind": "podcast",
            "files": [
                (io.BytesIO("먹어요.".encode()), "one.txt"),
                (io.BytesIO("가요.".encode()), "two.txt"),
            ],
        },
    )
    assert response.status_code == 200
    assert "Compare supplied inputs" in response.text
    links = re.findall(r'href="(/korean/candidates/[^"]+)"', response.text)
    page = client.get(links[0])
    assert "Listening: insufficient evidence" in page.text
    assert KnowledgeService(session).list_items() == []
    assert StudySessionService(session).list() == []


def test_item_manual_save_and_observation_validation_do_not_apply_suggestions(
    app, session
):
    from lute_korean_parser.knowledge.service import KnowledgeService
    from datetime import datetime, timezone

    k = KnowledgeService(session)
    item = k.get_or_create_lexical("먹다")
    session.commit()
    client = app.test_client()
    url = "/korean/items/" + item["id"]
    page = client.get(url)
    assert page.status_code == 200
    saved = client.post(
        url + "/assessment",
        data={"csrf_token": csrf(page), "dimension": "reading", "status": "practicing"},
    )
    assert saved.status_code == 303
    page = client.get(url)
    event = {
        "csrf_token": csrf(page),
        "item_id": item["id"],
        "dimension": "reading",
        "event_type": "produced",
        "context": "먹어요.",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "recorded_by": "learner",
        "event_key": "real-factual-test",
    }
    assert client.post("/korean/observations", data=event).status_code == 400
    assert k.list_evidence(item["id"]) == []
    event["event_type"] = "recognized"
    assert client.post("/korean/observations", data=event).status_code == 303
    assert client.post("/korean/observations", data=event).status_code == 303
    assert len(k.list_evidence(item["id"])) == 1
    assert "Familiar / in practice" in client.get(url).text


def test_anki_preview_dry_run_and_incremental_sync_use_existing_read_only_adapter(
    app, session
):
    from test_anki import FakeAdapter, note, card, review

    config = Path(app.config["DATAPATH"]) / "korean-anki.yml"
    config.write_text(
        "anki:\n  source_identity: fixture\n  profile: Fixture\n  mappings:\n    Core Korean:\n      korean_fields: [KO]\n"
    )
    app.config["KOREAN_ANKI_ADAPTER"] = FakeAdapter(
        [note(cards=(456,))], [card()], [review()]
    )
    client = app.test_client()
    token = csrf(client.get("/korean/anki"))
    for action in ["preview", "dry_run"]:
        response = client.post(
            "/korean/anki", data={"csrf_token": token, "action": action}
        )
        assert response.status_code == 200
    from lute_korean_parser.knowledge.service import KnowledgeService

    assert KnowledgeService(session).list_items() == []
    synced = client.post("/korean/anki", data={"csrf_token": token, "action": "sync"})
    assert synced.status_code == 200
    assert KnowledgeService(session).get_lexical("먹다")
    assert (
        client.post(
            "/korean/anki", data={"csrf_token": token, "action": "sync"}
        ).status_code
        == 200
    )
    assert all(
        action[0] in {"find_notes", "notes", "cards", "reviews"}
        for action in app.config["KOREAN_ANKI_ADAPTER"].calls
    )


@pytest.mark.parametrize(
    "file_name,body", [("bad.txt", b"\xff\xfe"), ("bad.pdf", b"not text")]
)
def test_invalid_upload_is_friendly_without_writes(app, session, file_name, body):
    import io
    from lute_korean_parser.study.service import StudySessionService

    client = app.test_client()
    token = csrf(client.get("/korean/analyze"))
    result = client.post(
        "/korean/analyze",
        data={"csrf_token": token, "files": (io.BytesIO(body), file_name)},
    )
    assert result.status_code == 400 and "Traceback" not in result.text
    assert StudySessionService(session).list() == []


def test_candidate_is_private_to_its_browser_and_reports_do_not_cache_stale_state(
    app, session
):
    from lute_korean_parser.knowledge.service import KnowledgeService

    k = KnowledgeService(session)
    eat = k.get_or_create_lexical("먹다")
    session.commit()
    client = app.test_client()
    token = csrf(client.get("/korean/analyze"))
    response = client.post(
        "/korean/analyze", data={"csrf_token": token, "text": "먹어요."}
    )
    candidate = re.search(r'name="candidate_token" value="([^"]+)"', response.text)[1]
    other = app.test_client()
    assert other.get("/korean/candidates/" + candidate).status_code == 400
    k.set_status(eat["id"], "consolidated", "reading")
    session.commit()
    updated = client.get("/korean/candidates/" + candidate)
    assert "strong_familiar" in updated.text
    assert "Overall linguistic fit: comfortable" in updated.text


def test_config_validation_rejects_remote_endpoint_and_preserves_prior_file(app):
    path = Path(app.config["DATAPATH"]) / "korean-anki.yml"
    client = app.test_client()
    token = csrf(client.get("/korean/anki"))
    payload = "source_identity: local\nendpoint: http://127.0.0.1:8765\nmappings: {}\n"
    assert (
        client.post(
            "/korean/anki",
            data={"csrf_token": token, "action": "config", "configuration": payload},
        ).status_code
        == 303
    )
    before = path.read_bytes()
    bad = payload.replace("127.0.0.1", "example.com")
    assert (
        client.post(
            "/korean/anki",
            data={"csrf_token": token, "action": "config", "configuration": bad},
        ).status_code
        == 400
    )
    assert path.read_bytes() == before


def test_anki_connection_failure_has_friendly_message_without_exposure(app, session):
    from test_anki import FakeAdapter
    from lute_korean_parser.knowledge.service import KnowledgeService

    fake = FakeAdapter()
    fake.failure = True
    app.config["KOREAN_ANKI_ADAPTER"] = fake
    client = app.test_client()
    token = csrf(client.get("/korean/anki"))
    response = client.post(
        "/korean/anki", data={"csrf_token": token, "action": "preview"}
    )
    assert response.status_code == 400
    assert "Keep Anki and AnkiConnect open" in response.text
    assert KnowledgeService(session).list_items() == []


def test_malformed_subtitle_fallback_warning_is_visible(app):
    import io

    client = app.test_client()
    token = csrf(client.get("/korean/analyze"))
    response = client.post(
        "/korean/analyze",
        data={
            "csrf_token": token,
            "format": "srt",
            "files": (io.BytesIO("not a cue\n먹어요.".encode()), "malformed.srt"),
        },
    )
    assert response.status_code == 200
    assert "Input formatting needs review" in response.text


def test_get_views_and_exports_issue_no_database_writes(app, session):
    from sqlalchemy import event

    verbs = []
    connection = session.connection()

    def observe(conn, cursor, statement, parameters, context, many):
        verbs.append(statement.strip().split()[0].upper())

    event.listen(connection, "before_cursor_execute", observe)
    try:
        client = app.test_client()
        for path in [
            "/korean/",
            "/korean/knowledge",
            "/korean/analyze",
            "/korean/history",
            "/korean/anki",
            "/korean/export",
            "/korean/export/learner",
        ]:
            assert client.get(path).status_code == 200
        assert set(verbs) <= {"SELECT", "PRAGMA", "BEGIN"}
    finally:
        event.remove(connection, "before_cursor_execute", observe)


def test_unmigrated_database_reports_next_step_without_running_migrations(
    app, tmp_path
):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    engine = create_engine("sqlite:///" + str(tmp_path / "unmigrated.db"))
    with Session(engine) as empty:
        app.config["KOREAN_STUDY_SESSION_FACTORY"] = lambda: empty
        response = app.test_client().get("/korean/")
        assert response.status_code == 503
        assert "additive migrations" in response.text
    engine.dispose()


def test_unavailable_database_is_friendly_and_does_not_create_a_file(app, tmp_path):
    missing = tmp_path / "missing.db"
    app.config["DATABASE"] = str(missing)
    response = app.test_client().get("/korean/")
    assert response.status_code == 503 and not missing.exists()
    assert "database unavailable" in response.text


def test_long_transcript_pagination_global_filter_and_lazy_diagnostic(app, session):
    from lute_korean_parser.knowledge.service import KnowledgeService

    client = app.test_client()
    form = client.get("/korean/analyze")
    response = client.post(
        "/korean/analyze",
        data={
            "csrf_token": csrf(form),
            "text": "\n".join(["오늘 밥을 먹었어요."] * 205),
        },
    )
    assert response.status_code == 200
    assert response.text.count('class="study-segment"') == 200
    token = re.search(r'name="candidate_token" value="([^"]+)"', response.text)[1]
    base = "/korean/candidates/" + token
    second = client.get(base + "?page=2")
    assert second.status_code == 200
    assert second.text.count('class="study-segment"') == 5
    filtered = client.get(base + "?filter=dense")
    assert filtered.status_code == 200
    diagnostic = client.get(base + "/segments/204")
    assert diagnostic.status_code == 200
    assert "raw_items" in diagnostic.text and "먹다" in diagnostic.text
    assert KnowledgeService(session).list_items() == []
    assert client.get(base + "?filter=invalid").status_code == 400
    assert client.get(base + "/segments/999").status_code == 400
