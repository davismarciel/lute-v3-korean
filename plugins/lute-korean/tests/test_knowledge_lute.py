"""Integration with real Lute database migrations and the opt-in page adapter."""
from pathlib import Path
from hashlib import sha256
import yaml
import pytest
from sqlalchemy import select, text as sqltext
from lute.app_factory import create_app
from lute.db import db
from lute.models.language import Language
from lute.models.book import Book, Text
from lute.models.term import Term
from lute_korean_parser.knowledge.ingestion import KnowledgeIngestionService
from lute_korean_parser.knowledge.service import KnowledgeService
from lute_korean_parser.knowledge import tables as t


def test_lute_page_ingestion_and_revisions(tmp_path):
    import lute_korean_parser.install as install_module

    config = tmp_path / "config.yml"
    config.write_text(
        f"ENV: dev\nDBNAME: test_knowledge.db\nDATAPATH: {tmp_path.as_posix()}/data\n"
    )
    app = create_app(
        str(config), extra_config={"TESTING": True, "WTF_CSRF_ENABLED": False}
    )
    with app.app_context():
        definition = Path(install_module.__file__).with_name("definition.yaml")
        language = Language.from_dict(
            yaml.safe_load(definition.read_text(encoding="utf8"))
        )
        db.session.add(language)
        db.session.commit()
        book = Book()
        book.title = "Korean knowledge test"
        book.language = language
        page = Text(book, "한국에 가면 많이 먹을 거예요.")
        db.session.add(book)
        db.session.add(page)
        db.session.commit()
        ingestion = KnowledgeIngestionService(db.session)
        assert (
            ingestion.knowledge.list_items() == []
        )  # No implicit import/reading writes.
        before = page.text
        first = ingestion.ingest_lute_text(page.id)
        source = (
            db.session.execute(
                select(t.sources).where(t.sources.c.id == first["source_id"])
            )
            .mappings()
            .one()
        )
        assert source["reference"].endswith(
            sha256(ingestion.processing_version.encode()).hexdigest()
        )
        db.session.commit()
        assert ingestion.ingest_lute_text(page.id) == first
        service = KnowledgeService(db.session)
        go = service.get_lexical("가다")
        service.set_status(go["id"], "consolidated")
        condition = service.find_item("grammar", "-(으)면")
        service.set_status(condition["id"], "practicing")
        term = Term(language, "가면")
        term.status = 1
        db.session.add(term)
        db.session.commit()
        assert page.text == before
        assert term.status == 1
        assert app.test_client().get(f"/read/{book.id}").status_code == 200
        assert (
            app.test_client().get(f"/read/termform/{language.id}/가면").status_code == 200
        )
        assert term.status == 1
        page.text = "시간이 있으면 친구랑 같이 갈 거예요."
        db.session.commit()
        second = ingestion.ingest_lute_text(page.id)
        db.session.commit()
        assert second["source_id"] != first["source_id"]
        assert service.get_lexical("가다")["id"] == go["id"]
        assert service.get_item(go["id"])["status"] == "consolidated"
        assert len(service.list_evidence(go["id"])) == 2
        old_occurrence = next(
            o
            for o in service.list_occurrences(go["id"])
            if o["source_id"] == first["source_id"]
        )
        assert old_occurrence["surface"] == "가면"
        assert old_occurrence["context"] == before
        other = Language()
        other.name = "Other language"
        db.session.add(other)
        other_book = Book()
        other_book.title = "Other"
        other_book.language = other
        other_page = Text(other_book, "hello")
        db.session.add_all([other_book, other_page])
        db.session.commit()
        with pytest.raises(ValueError, match="Only Korean"):
            ingestion.ingest_lute_text(other_page.id)
        # Core deletion can detach Lute references, retaining acquisition history.
        db.session.execute(sqltext("PRAGMA foreign_keys=ON"))
        db.session.execute(sqltext("DELETE FROM texts WHERE TxID=:id"), {"id": page.id})
        db.session.commit()
        assert (
            db.session.execute(
                select(t.sources.c.lute_text_id).where(
                    t.sources.c.id == first["source_id"]
                )
            ).scalar()
            is None
        )
        assert service.get_item(go["id"])["status"] == "consolidated"
