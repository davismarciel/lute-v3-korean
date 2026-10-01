"""Plugin-owned server-rendered workspace; mutations are explicit CSRF-checked POSTs."""
from functools import wraps
from dataclasses import replace
from pathlib import Path
from secrets import token_urlsafe
import json
from uuid import uuid4
from flask import (
    Blueprint,
    current_app,
    render_template,
    request,
    redirect,
    url_for,
    session as browser_session,
    Response,
)
from flask_wtf.csrf import generate_csrf, validate_csrf, CSRFError
from wtforms.validators import ValidationError
from werkzeug.exceptions import RequestEntityTooLarge
from markupsafe import escape
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from ..ci.adapters import adapt_content, ADAPTERS
from ..ci.export import compare_reports
from ..knowledge.service import KnowledgeService
from ..anki.config import AnkiConfig
from ..anki.models import AnkiError
from .service import StudySessionService, now
from .workspace import KoreanStudyWorkspace, markdown_export
from .cache import CandidateCache

bp = Blueprint(
    "korean_study",
    __name__,
    url_prefix="/korean",
    template_folder="templates",
    static_folder="static",
)


def db_session():
    factory = current_app.config.get("KOREAN_STUDY_SESSION_FACTORY")
    if factory:
        return factory()
    from lute.db import db

    return db.session


def owner():
    if "korean_browser" not in browser_session:
        browser_session["korean_browser"] = token_urlsafe(24)
    return browser_session["korean_browser"]


def cache():
    return current_app.extensions["korean_candidates"]


def render(template, **values):
    report = values.get("report")
    if report:
        segment_filter = request.args.get("filter", "all")
        predicates = {
            "all": lambda s: True,
            "difficult": lambda s: s["load"]["level"] >= 2,
            "dense": lambda s: s["load"]["level"] == 3,
            "novelty": lambda s: s["load"]["novelty_load"] > 0,
        }
        if segment_filter not in predicates:
            raise ValueError("Invalid segment filter")
        selected = [s for s in report["segments"] if predicates[segment_filter](s)]
        page_size = 200
        pages = max(1, (len(selected) + page_size - 1) // page_size)
        page = min(pages, max(1, int(request.args.get("page", "1"))))
        saved = values.get("study_session")
        if saved:
            base = url_for(".study", session_id=saved["id"])
            diagnostic = url_for(
                ".session_segment", session_id=saved["id"], index=0
            ).rsplit("/", 1)[0]
        else:
            base = url_for(".candidate", token=values["token"])
            diagnostic = url_for(
                ".candidate_segment", token=values["token"], index=0
            ).rsplit("/", 1)[0]
        values.update(
            display_segments=selected[(page - 1) * page_size : page * page_size],
            segment_filter=segment_filter,
            segment_page=page,
            segment_pages=pages,
            matching_segments=len(selected),
            report_url=base,
            diagnostic_url=diagnostic,
        )
    return render_template(
        "korean/" + template + ".html",
        timestamp=now().isoformat(),
        event_key=str(uuid4()),
        **values,
    )


@bp.before_request
def protect():
    if request.endpoint == "korean_study.static":
        return
    database = current_app.config.get("DATABASE")
    if database and not Path(database).is_file():
        return unavailable_database("The configured database file is unavailable."), 503
    if request.method == "POST":
        if request.content_length and request.content_length > 16 * 1024 * 1024:
            raise RequestEntityTooLarge()
        request.max_form_memory_size = 2_100_000
        request.max_form_parts = 30
        try:
            validate_csrf(
                request.form.get("csrf_token"),
                secret_key=current_app.config["KOREAN_CSRF_SECRET"],
            )
        except ValidationError as exc:
            raise CSRFError(str(exc)) from exc
    required = [
        "korean_knowledge_items",
        "korean_knowledge_roles",
        "korean_anki_integrations",
        "korean_study_sessions",
        "korean_study_contents",
        "korean_study_consumed_segments",
        "korean_study_observations",
    ]
    schema = inspect(db_session().connection())
    if not all(schema.has_table(table) for table in required):
        return (
            render(
                "error",
                message="The Korean database needs its additive migrations. Restart the updated Lute installation after backing up your database.",
                detail="Required Knowledge, Anki, representation or study tables are unavailable.",
            ),
            503,
        )


@bp.context_processor
def context():
    return {
        "korean_csrf": lambda: generate_csrf(
            secret_key=current_app.config["KOREAN_CSRF_SECRET"]
        )
    }


def mutation(function):
    @wraps(function)
    def handle(*args, **kwargs):
        try:
            result = function(*args, **kwargs)
            db_session().commit()
            return result
        except Exception:
            db_session().rollback()
            raise

    return handle


def unavailable_database(detail):
    """No template context queries when the core database itself cannot be opened."""
    return Response(
        "<h1>Korean database unavailable</h1><p>Check its location, permissions and migrations.</p><details><summary>Technical details</summary><pre>"
        + str(escape(detail))
        + "</pre></details>",
        mimetype="text/html",
    )


@bp.errorhandler(RequestEntityTooLarge)
@bp.errorhandler(TypeError)
@bp.errorhandler(ValueError)
@bp.errorhandler(KeyError)
@bp.errorhandler(AnkiError)
@bp.errorhandler(SQLAlchemyError)
@bp.errorhandler(OSError)
@bp.errorhandler(UnicodeError)
def friendly_error(error):
    db_session().rollback()
    if isinstance(error, SQLAlchemyError):
        return unavailable_database(str(error)), 503
    current_app.logger.warning("Korean study action failed: %s", error)
    message = "The action could not be completed. Check the input and try again."
    if isinstance(error, RequestEntityTooLarge):
        message = (
            "The upload is too large. Choose up to 8 UTF-8 files of at most 2 MB each."
        )
    if isinstance(error, AnkiError):
        message = "Anki is unavailable or rejected the request. Keep Anki and AnkiConnect open on the configured local endpoint."
    elif isinstance(error, UnicodeError):
        message = (
            "The file must contain UTF-8 text. Save it as UTF-8 and upload it again."
        )
    elif isinstance(error, SQLAlchemyError):
        message = "The Korean database is unavailable or incompatible. Check its location and migrations."
    elif isinstance(error, KeyError):
        message = "The requested item, session or temporary candidate is unavailable."
    return (
        render("error", message=message, detail=str(error)),
        400 if not isinstance(error, SQLAlchemyError) else 503,
    )


@bp.errorhandler(CSRFError)
def csrf_error(error):
    return (
        render(
            "error",
            message="This form expired or failed its safety check. Reload the page before saving.",
            detail=error.description,
        ),
        400,
    )


@bp.route("/")
def home():
    workspace = KoreanStudyWorkspace(db_session())
    return render(
        "home",
        overview=workspace.overview(),
        anki=workspace.anki_status(config()),
        recent=cache().recent(owner()),
    )


@bp.route("/knowledge")
def knowledge():
    overview = KoreanStudyWorkspace(db_session()).overview()
    kind = request.args.get("kind", "")
    state = request.args.get("state", "")
    query = request.args.get("q", "").casefold()
    items = [
        i
        for i in overview["items"]
        if (not kind or i["type"] == kind)
        and query in i["identity"].casefold()
        and (
            not state
            or (
                state == "no_manual"
                and all(
                    i["manual_state"].get(d) is None
                    for d in ["reading", "listening", "production"]
                )
            )
            or i["suggested_state"]["reading"]["status"] == state
            or i["manual_state"].get("reading") == state
        )
    ]
    return render("knowledge", items=items, kind=kind, state=state, query=query)


@bp.route("/items/<item_id>")
def item(item_id):
    return render("item", **KoreanStudyWorkspace(db_session()).item(item_id))


@bp.post("/items/<item_id>/assessment")
@mutation
def assessment(item_id):
    KoreanStudyWorkspace(db_session()).assess(
        item_id, request.form["dimension"], request.form["status"]
    )
    return redirect(url_for(".item", item_id=item_id), 303)


def observation_document():
    item = KnowledgeService(db_session()).get_item(request.form["item_id"])
    return {
        "item": item["identity"],
        "kind": item["kind"],
        "dimension": request.form["dimension"],
        "event_type": request.form["event_type"],
        "directness": "direct",
        "scope": "item",
        "source_type": "conversation",
        "source_reference": request.form.get("source_reference")
        or "manual-study-observation",
        "context": request.form.get("context", ""),
        "occurred_at": request.form["occurred_at"],
        "recorded_by": request.form.get("recorded_by", "learner"),
        "notes": request.form.get("notes", ""),
        "event_key": "ui-observation:" + request.form["event_key"],
    }


@bp.post("/observations")
@mutation
def observe():
    document = observation_document()
    sid = request.form.get("study_session_id") or None
    KoreanStudyWorkspace(db_session()).observe(document, sid)
    return redirect(
        url_for(".study", session_id=sid)
        if sid
        else url_for(".item", item_id=request.form["item_id"]),
        303,
    )


def inputs():
    files = request.files.getlist("files")
    entries = []
    text = request.form.get("text", "")
    if text.strip():
        entries.append((request.form.get("name") or "Pasted Korean text", text))
    for file in files:
        if not file.filename:
            continue
        if Path(file.filename).suffix.casefold() not in {".txt", ".srt", ".vtt"}:
            raise ValueError("Choose TXT, SRT or VTT files")
        raw = file.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Each file must be at most 2 MB")
        entries.append(
            (Path(file.filename.replace("\\", "/")).name, raw.decode("utf-8-sig"))
        )
    if not entries:
        raise ValueError("Paste Korean text or choose a local file")
    if len(entries) > 8 or any(len(text.encode()) > 2_000_000 for _, text in entries):
        raise ValueError("Choose at most 8 candidates, each up to 2 MB")
    return [
        adapt_content(
            text,
            name=name,
            format=request.form.get("format", "auto"),
            kind=request.form.get("kind", "text"),
        )
        for name, text in entries
    ]


@bp.route("/analyze", methods=["GET", "POST"])
def analyze():
    if request.method == "GET":
        return render("analyze", formats=["auto", *ADAPTERS])
    candidates = inputs()
    workspace = KoreanStudyWorkspace(db_session())
    snapshot = workspace.snapshot()
    reports = [workspace.analyze(c, snapshot=snapshot) for c in candidates]
    tokens = [
        cache().put(
            owner(),
            c,
            {
                "fit": r["summary"]["fit"],
                "confidence": r["summary"]["confidence"],
                "analyzed_at": r["learner_snapshot"]["as_of"],
            },
        )
        for c, r in zip(candidates, reports)
    ]
    if len(reports) == 1:
        return render(
            "report",
            report=reports[0],
            token=tokens[0],
            study_session=None,
            input_warnings=candidates[0].warnings,
        )
    compared = compare_reports(reports)
    by_name = {id(r): token for r, token in zip(reports, tokens)}
    for row in compared["candidates"]:
        row["token"] = by_name[id(row["report"])]
    return render("compare", comparison=compared)


@bp.route("/candidates/<token>")
def candidate(token):
    content = cache().get(owner(), token)["content"]
    return render(
        "report",
        report=KoreanStudyWorkspace(db_session()).analyze(content),
        token=token,
        study_session=None,
        input_warnings=content.warnings,
    )


def segment_diagnostic(content, index):
    if index < 0 or index >= len(content.segments):
        raise ValueError("Segment is unavailable")
    report = KoreanStudyWorkspace(db_session()).analyze(
        replace(content, segments=(content.segments[index],))
    )
    return render("segment", segment=report["segments"][0])


@bp.get("/candidates/<token>/segments/<int:index>")
def candidate_segment(token, index):
    return segment_diagnostic(cache().get(owner(), token)["content"], index)


@bp.get("/sessions/<session_id>/segments/<int:index>")
def session_segment(session_id, index):
    return segment_diagnostic(
        StudySessionService(db_session()).candidate(session_id), index
    )


@bp.post("/sessions/start")
@mutation
def start():
    content = cache().get(owner(), request.form["candidate_token"])["content"]
    result = StudySessionService(db_session()).start(
        content,
        request.form["activity"],
        request.form["request_key"],
        transcript_read=request.form.get("transcript_read") == "yes",
        external_reference=request.form.get("external_reference") or None,
    )
    return redirect(url_for(".study", session_id=result["id"]), 303)


@bp.route("/history")
def history():
    return render("history", sessions=StudySessionService(db_session()).list())


@bp.route("/sessions/<session_id>")
def study(session_id):
    service = StudySessionService(db_session())
    session = service.show(session_id)
    report = KoreanStudyWorkspace(db_session()).analyze(service.candidate(session_id))
    tracked = {
        row["item_id"]: row["identity"]
        for segment in report["segments"]
        for row in segment["effective_items"]
        if row["tracked"]
    }
    return render("study", study_session=session, report=report, tracked=tracked)


@bp.route("/sessions/<session_id>/candidate")
def reopen(session_id):
    content = StudySessionService(db_session()).candidate(session_id)
    report = KoreanStudyWorkspace(db_session()).analyze(content)
    token = cache().put(
        owner(),
        content,
        {
            "fit": report["summary"]["fit"],
            "confidence": report["summary"]["confidence"],
        },
    )
    return render(
        "report",
        report=report,
        token=token,
        study_session=None,
        input_warnings=content.warnings,
    )


@bp.post("/sessions/<session_id>/consume")
@mutation
def consume(session_id):
    StudySessionService(db_session()).consume(
        session_id,
        int(request.form["start"]),
        int(request.form["end"]),
        completed=request.form.get("finish") == "yes",
    )
    return redirect(url_for(".study", session_id=session_id), 303)


def config_path():
    return Path(
        current_app.config.get("KOREAN_ANKI_CONFIG")
        or Path(current_app.config["DATAPATH"]) / "korean-anki.yml"
    )


def config():
    return (
        AnkiConfig.load(config_path())
        if config_path().is_file()
        else AnkiConfig("local-anki", {})
    )


@bp.route("/anki", methods=["GET", "POST"])
def anki():
    workspace = KoreanStudyWorkspace(db_session())
    result = None
    if request.method == "POST":
        action = request.form.get("action")
        if action == "config":
            from tempfile import mkstemp
            import os

            payload = request.form.get("configuration", "")
            if len(payload) > 32000:
                raise ValueError("Configuration is too large")
            # Validate through the existing loader before replacing local settings.
            path = config_path()
            fd, temp_path = mkstemp(suffix=".yml", dir=path.parent)
            os.close(fd)
            temporary = Path(temp_path)
            try:
                temporary.write_text(payload, encoding="utf8")
                AnkiConfig.load(temporary)
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
            return redirect(url_for(".anki"), 303)
        service = workspace.anki(
            config(), current_app.config.get("KOREAN_ANKI_ADAPTER")
        )
        if action in {"preview", "doctor"}:
            result = getattr(service, action)()
        elif action in {"dry_run", "sync", "full"}:
            if not config().mappings:
                raise ValueError("Save explicit field mappings before syncing")
            try:
                result = service.sync(
                    dry_run=action == "dry_run", full_reviews=action == "full"
                )
                if action != "dry_run":
                    db_session().commit()
            except Exception:
                db_session().rollback()
                raise
        else:
            raise ValueError("Unknown Anki action")
    configuration = (
        config_path().read_text(encoding="utf8")
        if config_path().is_file()
        else 'anki:\n  source_identity: local-anki\n  endpoint: http://127.0.0.1:8765\n  query: ""\n  mappings: {}\n'
    )
    return render(
        "anki",
        status=workspace.anki_status(config()),
        configuration=configuration,
        mapped=bool(config().mappings),
        result=result,
    )


@bp.route("/export")
def export_screen():
    return render("export")


@bp.route("/export/learner")
def export_learner():
    return download(
        KoreanStudyWorkspace(db_session()).export_learner(
            request.args.get("size", "compact")
        ),
        "learner-context",
    )


@bp.route("/export/session/<session_id>")
def export_session(session_id):
    workspace = KoreanStudyWorkspace(db_session())
    report = workspace.analyze(StudySessionService(db_session()).candidate(session_id))
    return download(
        workspace.export_content(
            report,
            request.args.get("size", "compact"),
            request.args.get("korean") == "yes",
        ),
        "study-context",
    )


@bp.route("/export/content/<token>")
def export_content(token):
    content = cache().get(owner(), token)["content"]
    workspace = KoreanStudyWorkspace(db_session())
    document = workspace.export_content(
        workspace.analyze(content),
        request.args.get("size", "compact"),
        request.args.get("korean") == "yes",
    )
    return download(document, "study-context")


def download(document, name):
    markdown = request.args.get("format") == "markdown"
    body = (
        markdown_export(document)
        if markdown
        else json.dumps(document, ensure_ascii=False, indent=2)
    )
    return Response(
        body,
        mimetype="text/markdown" if markdown else "application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{name}.{ "md"if markdown else"json"}"'
        },
    )


def init_app(app):
    """No DB writes/migrations on registration; missing schema gets a friendly page."""
    app.config.setdefault("KOREAN_CSRF_SECRET", token_urlsafe(48))
    app.extensions["korean_candidates"] = CandidateCache()
    app.register_blueprint(bp)
    return [{"label": "Korean Study", "url": "/korean/"}]
