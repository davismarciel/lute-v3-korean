"""Exercise app startup, predefined Korean, book import and surface term rendering."""
from io import BytesIO
from pathlib import Path
from lute.app_factory import create_app
from lute.db import db
from lute.book.model import Book
from lute.book.service import Service as BookService
from lute.models.repositories import BookRepository
from lute.models.language import Language
from lute.models.term import Term
from lute.read.render.service import Service as RenderService


def test_korean_reading_workflow(tmp_path, monkeypatch):
    import lute.language.service as language_module
    import lute_korean_parser.install as install_module

    # Use the bundled catalog entry without mutating the installed upstream
    # submodule. The installer itself is tested separately.
    definition = str(Path(install_module.__file__).with_name("definition.yaml"))
    original_glob = language_module.glob
    monkeypatch.setattr(
        language_module,
        "glob",
        lambda pattern: (
            original_glob(pattern) + [definition]
            if pattern.endswith("definition.yaml")
            else original_glob(pattern)
        ),
    )
    config = tmp_path / "config.yml"
    config.write_text(
        f"ENV: dev\nDATAPATH: {tmp_path.as_posix()}/data\nDBNAME: test_korean.db\n",
        encoding="utf8",
    )
    app = create_app(
        str(config), extra_config={"TESTING": True, "WTF_CSRF_ENABLED": False}
    )
    client = app.test_client()
    with app.app_context():
        assert client.get("/language/new/Korean").status_code == 200
        response = client.get("/language/load_predefined/Korean")
        assert response.status_code == 302
        language = db.session.query(Language).filter_by(name="Korean").one()
        text = "오늘 친구랑 같이 밥을 먹었어요.\n한국에 가면 많이 먹을 거예요."
        book = Book()
        book.title = "Korean transcription"
        book.language_id = language.id
        book.text_stream = BytesIO(text.encode("utf8"))
        book.text_stream_filename = "transcription.txt"
        BookService().import_book(book, db.session)
        saved = BookRepository(db.session).find_by_title(book.title, language.id)
        assert saved.texts[0].text == text
        assert client.get(f"/read/{saved.id}").status_code == 200
        assert client.get(f"/read/termform/{language.id}/먹었어요").status_code == 200
        term = Term(language, "먹었어요")
        term.translation = "ate"
        term.status = 2
        db.session.add(term)
        db.session.commit()
        assert term.token_count == 1
        renderer = RenderService(db.session)
        items = renderer.get_textitems(text, language)
        assert "".join(i.text for i in items).replace("¶", "\n") == text
        matches = renderer.find_all_Terms_in_string(text, language)
        assert any(t.id == term.id for t in matches)
        # Existing multiword terms remain possible for a later chunks layer.
        chunk = Term(language, "한국에 가면")
        db.session.add(chunk)
        db.session.commit()
        assert chunk.token_count > 1
        assert any(
            t.id == chunk.id for t in renderer.find_all_Terms_in_string(text, language)
        )
        assert language.parser.analyze("먹었어요").units[0].lemma == "먹다"
