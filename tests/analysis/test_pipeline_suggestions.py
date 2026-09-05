from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import pipeline
from backend.db.models import Base, Document


def test_upsert_returns_saved_document():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        saved = pipeline._upsert_document(
            session,
            {
                "url": "https://mas.example/rule",
                "title": "Rule",
                "tags": [],
                "applies_to": [],
                "related_items": [],
            },
            "Section 1. New duty.",
            None,
        )
        session.flush()

        assert isinstance(saved, Document)
        assert saved.ocr_text == "Section 1. New duty."
    finally:
        session.close()


def test_suggestion_failure_does_not_escape(monkeypatch, caplog):
    @contextmanager
    def fake_session():
        yield object()

    monkeypatch.setattr(pipeline, "get_session", fake_session)
    monkeypatch.setattr(
        pipeline,
        "analyze_regulatory_document",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("model offline")),
        raising=False,
    )

    pipeline._generate_suggestions_safely("00000000-0000-0000-0000-000000000001")

    assert "Suggestion generation failed" in caplog.text
