import json

from backend.scraper.src.mas_regulations_scraper import parse_detail, save_records


def test_parse_detail_extracts_effective_date_from_labelled_page_metadata():
    html = """
    <html><body>
      <div class="metadata-row">
        <span>Effective Date:</span>
        <span>01 July 2026</span>
      </div>
    </body></html>
    """

    detail = parse_detail(html)

    assert detail["effective_date"] == "01 July 2026"


def test_parse_detail_leaves_effective_date_empty_when_page_does_not_state_one():
    detail = parse_detail("<html><body><p>No commencement information.</p></body></html>")

    assert detail["effective_date"] is None


def test_save_records_creates_missing_output_directory(tmp_path):
    output_path = tmp_path / "scraper" / "output" / "records.json"

    save_records([{"title": "New notice"}], path=str(output_path))

    assert json.loads(output_path.read_text(encoding="utf-8"))["documents"] == [
        {"title": "New notice"}
    ]
