import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from backend.analysis.updates import _run_scraper, _within_window, fetch_updates
from backend.scraper.src.mas_regulations_scraper import USER_AGENT


def test_run_scraper_uses_the_cli_browser_identity(tmp_path):
    playwright = MagicMock()
    browser = playwright.chromium.launch.return_value
    context = MagicMock()
    context.__enter__.return_value = playwright
    context.__exit__.return_value = False

    with (
        patch("playwright.sync_api.sync_playwright", return_value=context),
        patch(
            "backend.scraper.src.mas_regulations_scraper.fetch_listing_html",
            return_value="listing",
        ),
        patch("backend.scraper.src.mas_regulations_scraper.parse_listing", return_value=[]),
        patch("backend.scraper.src.mas_regulations_scraper.enrich_with_details"),
        patch("backend.scraper.src.mas_regulations_scraper.save_records"),
    ):
        _run_scraper(1, tmp_path / "mas.json")

    browser.new_page.assert_called_once_with(
        user_agent=USER_AGENT,
        ignore_https_errors=True,
    )


def test_within_window_includes_doc_on_cutoff_day():
    doc = {"date": date.today().strftime("%-d %B %Y")}
    assert _within_window(doc, date.today()) is True


def test_within_window_excludes_doc_before_cutoff():
    past = date.today() - timedelta(days=8)
    doc = {"date": past.strftime("%-d %B %Y")}
    assert _within_window(doc, date.today() - timedelta(days=7)) is False


def test_within_window_returns_false_for_missing_date():
    assert _within_window({}, date.today()) is False


@pytest.fixture
def mas_json(tmp_path):
    recent = (date.today() - timedelta(days=2)).strftime("%-d %B %Y")
    old = (date.today() - timedelta(days=30)).strftime("%-d %B %Y")
    data = {
        "documents": [
            {
                "url": "https://mas.gov.sg/doc1",
                "title": "Doc 1",
                "date": recent,
                "doc_type": "Circular",
                "topic": "AML",
                "tags": [],
                "applies_to": [],
                "related_items": [],
                "pdf_link": "https://mas.gov.sg/doc1.pdf",
            },
            {
                "url": "https://mas.gov.sg/doc2",
                "title": "Old Doc",
                "date": old,
                "doc_type": "Notice",
                "topic": "Tax",
                "tags": [],
                "applies_to": [],
                "related_items": [],
                "pdf_link": None,
            },
        ]
    }
    p = tmp_path / "mas.json"
    p.write_text(json.dumps(data))
    return p


@pytest.fixture
def disable_scraper():
    with patch("backend.analysis.updates._run_scraper"):
        yield


def _make_mock_session(existing):
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = existing
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = lambda s: mock_session
    mock_ctx.__exit__ = MagicMock(return_value=False)
    return mock_ctx


def _make_existing_doc():
    doc = MagicMock()
    doc.llm_summary = "cached summary"
    doc.id = "uuid-1"
    doc.title = "Doc 1"
    doc.date = date.today() - timedelta(days=2)
    doc.doc_type = "Circular"
    doc.topic = "AML"
    doc.tags = []
    doc.applies_to = []
    doc.source_url = "https://mas.gov.sg/doc1"
    doc.pdf_url = "https://mas.gov.sg/doc1.pdf"
    doc.llm_categories = ["Financial Services"]
    doc.llm_impact_check = "No impact"
    return doc


def test_fetch_updates_excludes_old_docs(mas_json, disable_scraper):
    mock_ctx = _make_mock_session(_make_existing_doc())
    with patch("backend.analysis.updates.get_session", return_value=mock_ctx):
        results = fetch_updates(7, json_path=mas_json)
    assert len(results) == 1
    assert results[0]["title"] == "Doc 1"


def test_fetch_updates_uses_cache_when_llm_summary_exists(mas_json, disable_scraper):
    mock_ctx = _make_mock_session(_make_existing_doc())
    with patch("backend.analysis.updates.get_session", return_value=mock_ctx), \
         patch("backend.analysis.updates.download_and_ocr") as mock_ocr:
        fetch_updates(7, json_path=mas_json)
    mock_ocr.assert_not_called()


def test_fetch_updates_processes_uncached_doc(mas_json, disable_scraper):
    processed = MagicMock()
    processed.llm_summary = "new summary"
    processed.llm_categories = ["AML"]
    processed.llm_impact_check = "Review required"

    saved = _make_existing_doc()
    saved.llm_summary = "new summary"

    call_count = 0

    def mock_get_session():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_mock_session(None)
        return _make_mock_session(saved)

    with patch("backend.analysis.updates.get_session", side_effect=mock_get_session), \
         patch("backend.analysis.updates.download_and_ocr", return_value="raw ocr text"), \
         patch("backend.analysis.updates.process_document", return_value=processed), \
         patch("backend.analysis.updates._upsert_document"):
        results = fetch_updates(7, json_path=mas_json)

    assert results[0]["llm_summary"] == "new summary"


def test_fetch_updates_returns_empty_when_json_missing(tmp_path, disable_scraper):
    results = fetch_updates(7, json_path=tmp_path / "nonexistent.json")
    assert results == []


def test_list_documents_returns_newest_database_documents(monkeypatch):
    from backend.analysis import updates

    first = _make_existing_doc()
    second = _make_existing_doc()
    second.id = "uuid-2"
    second.title = "Doc 2"

    query = MagicMock()
    query.order_by.return_value.limit.return_value.all.return_value = [first, second]
    session = MagicMock()
    session.query.return_value = query
    context = MagicMock()
    context.__enter__.return_value = session
    context.__exit__.return_value = False
    monkeypatch.setattr(updates, "get_session", lambda: context)

    results = updates.list_documents()

    ordering = query.order_by.call_args.args
    assert [str(expression) for expression in ordering] == [
        "documents.date DESC NULLS LAST",
        "documents.created_at DESC",
    ]
    query.order_by.return_value.limit.assert_called_once_with(50)
    assert [doc["title"] for doc in results] == ["Doc 1", "Doc 2"]
