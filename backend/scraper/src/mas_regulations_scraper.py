"""
MAS Regulations & Guidance Scraper
====================================
Scrapes https://www.mas.gov.sg/regulation/regulations-and-guidance
(the master listing of Circulars, Notices, Guidelines, Consultations,
FAQs, Monographs, etc. — ~1,400+ items).

Two stages:
  1. LISTING PASS  - loads the search page, switches "View" to "All" so
     every result renders in one go, and extracts: doc_type, date, title,
     url, summary, topic.
  2. DETAIL PASS   - visits each item's own page to pull the fields the
     listing card doesn't have: the PDF download link(s), the full tag
     list, "Applies to" entity types, and "Related to this Item" documents.

Output: one JSON file, one record per document, e.g.:
{
  "doc_type": "Circulars",
  "date": "04 September 2026",
  "title": "ID 10/26 MAS Response to the Consultation Paper on ...",
  "url": "https://www.mas.gov.sg/regulation/circulars/id10_26",
  "summary": "...",
  "topic": "Valuation and Capital",
  "effective_date": "01 July 2026",
  "tags": ["Valuation and Capital"],
  "applies_to": ["Direct Insurer (Life)", "Direct Insurer (General)", ...],
  "issued_pursuant_to_text": "Banking Act 1970 section 27 and section 55",
  "issued_pursuant_to": [
      {"section": "section 27", "url": "https://sso.agc.gov.sg/Act/BA1970?ProvIds=pr27-"},
      {"section": "section 55", "url": "https://sso.agc.gov.sg/Act/BA1970?ProvIds=pr55-"}
  ],
  "pdf_links": ["https://www.mas.gov.sg/-/media/.../id10_26.pdf"],
  "related_items": [
      {"title": "Notice FHC-N133 on ...", "url": "https://www.mas.gov.sg/regulation/notices/notice-fhc-n133", "doc_type": "Notices"}
  ]
}

Usage:
    pip install playwright beautifulsoup4
    playwright install chromium
    python mas_regulations_scraper.py                 # last 7 days only (default)
    python mas_regulations_scraper.py --days 30        # last 30 days
    python mas_regulations_scraper.py --days 0         # no date filter, all ~1,400+ items

Notes on scale:
    The detail pass visits every document's own page individually — that's
    ~1,400+ page loads for a full run. This script rate-limits itself
    (DETAIL_PAGE_DELAY_SECONDS) to be polite to MAS's servers and to avoid
    getting rate-limited or blocked. A full run will take a while; use
    --limit while testing, and consider running the full scrape overnight
    or splitting it across sessions.
"""

import argparse
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.mas.gov.sg"
LISTING_URL = f"{BASE_URL}/regulation/regulations-and-guidance"
OUTPUT_FILE = "backend/scraper/output/mas_regulations_and_guidance.json"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Delay between each detail-page fetch, to avoid hammering MAS's servers.
DETAIL_PAGE_DELAY_SECONDS = 1.0


def absolutize(href: str | None) -> str | None:
    if href and href.startswith("/"):
        return BASE_URL + href
    return href


def parse_date(date_str: str | None):
    """Parses listing-page dates like '04 September 2026' into a date object.
    Returns None if the string doesn't match (so filtering skips it safely)."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%d %B %Y").date()
    except ValueError:
        return None


def filter_last_n_days(records: list[dict], days: int) -> list[dict]:
    cutoff = datetime.now(UTC).date() - timedelta(days=days)
    kept = []
    for r in records:
        d = parse_date(r.get("date"))
        if d is not None and d >= cutoff:
            kept.append(r)
    return kept


# ---------------------------------------------------------------------------
# Stage 1: listing pass
# ---------------------------------------------------------------------------

def fetch_listing_html(page) -> str:
    """Load the listing page and switch page size to 'All' so every result
    renders in a single pass."""
    page.goto(LISTING_URL, wait_until="networkidle", timeout=60_000)
    page.wait_for_timeout(2_000)
    page.select_option("#rows_sort", "All")
    page.wait_for_timeout(8_000)  # give the ~1,400 results time to render
    return page.content()


def parse_listing(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".mas-search-page__results-list .mas-search-card")

    records = []
    for card in cards:
        tag_el = card.select_one(".mas-tag__text")
        date_el = card.select_one(".mas-search-card__meta .ts\\:xs")
        title_link = card.select_one(".ola-field-title a")
        summary_el = card.select_one(".mas-search-card__body p")
        topic_link = card.select_one(".mas-search-card__footer a .mas-link__text")

        records.append(
            {
                "doc_type": tag_el.get_text(strip=True) if tag_el else None,
                "date": date_el.get_text(strip=True) if date_el else None,
                "title": title_link.get_text(strip=True) if title_link else None,
                "url": absolutize(title_link["href"]) if title_link else None,
                "summary": summary_el.get_text(strip=True) if summary_el else None,
                "topic": topic_link.get_text(strip=True) if topic_link else None,
            }
        )
    return records


# ---------------------------------------------------------------------------
# Stage 2: detail pass (per-document enrichment)
# ---------------------------------------------------------------------------

def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    # Keep commencement as source metadata instead of asking the LLM to infer
    # it from document text.
    effective_date = None
    effective_label = soup.find(
        string=lambda s: s and s.strip().lower() == "effective date:"
    )
    if effective_label and effective_label.parent:
        container = effective_label.parent.parent
        if container:
            full_text = container.get_text(" ", strip=True)
            effective_date = full_text.split(":", 1)[-1].strip() or None

    # PDF download link(s) — some documents (e.g. consultations) have
    # multiple attachments (main paper + annexes).
    pdf_links = []
    for a in soup.select("a[href]"):
        href = a["href"]
        if ".pdf" in href.lower():
            full = absolutize(href)
            if full not in pdf_links:
                pdf_links.append(full)

    # Full tag list (topics), from the tag icon row near the title.
    tags = []
    tag_icon = soup.select_one(".mas-glyphs-tag")
    if tag_icon:
        tag_row = tag_icon.find_parent(["div"])
        if tag_row:
            tags = [a.get_text(strip=True) for a in tag_row.select("a")]

    # "Applies to" entity types.
    applies_to = []
    applies_label = soup.find(string=lambda s: s and s.strip() == "Applies to:")
    if applies_label:
        applies_container = applies_label.parent.parent if applies_label.parent else None
        if applies_container:
            applies_to = [a.get_text(strip=True) for a in applies_container.select("a")]

    # "Issued pursuant to" — the empowering Act/section(s) this instrument is
    # made under, each an external link to the specific statute section on SSO.
    # The label reads e.g. "Issued pursuant to: Banking Act 1970 section 27 and
    # section 55"; we capture the plain text plus each section's hyperlink.
    issued_pursuant_to_text = None
    issued_pursuant_to = []
    issued_label = soup.find(string=lambda s: s and s.strip() == "Issued pursuant to:")
    if issued_label:
        issued_container = issued_label.parent.parent if issued_label.parent else None
        if issued_container:
            # Full readable text of the clause (Act name + sections), minus the label.
            full_text = issued_container.get_text(" ", strip=True)
            issued_pursuant_to_text = full_text.replace("Issued pursuant to:", "").strip() or None
            for a in issued_container.select("a[href]"):
                label = a.get_text(strip=True)
                if not label:
                    continue
                issued_pursuant_to.append({"section": label, "url": absolutize(a["href"])})

    # "Related to this Item" documents.
    related_items = []
    related_container = soup.select_one(".related-to-this-regulation-listing")
    if related_container:
        for card in related_container.select(".mas-search-card"):
            r_tag = card.select_one(".mas-tag__text")
            r_title_link = card.select_one("a")
            if r_title_link:
                related_items.append(
                    {
                        "doc_type": r_tag.get_text(strip=True) if r_tag else None,
                        "title": r_title_link.get_text(strip=True),
                        "url": absolutize(r_title_link["href"]),
                    }
                )

    return {
        "effective_date": effective_date,
        "pdf_links": pdf_links,
        "tags": tags,
        "applies_to": applies_to,
        "issued_pursuant_to_text": issued_pursuant_to_text,
        "issued_pursuant_to": issued_pursuant_to,
        "related_items": related_items,
    }


def enrich_with_details(page, records: list[dict]) -> None:
    """Visits each record's own page and merges in PDF links, tags,
    applies_to, and related_items. Mutates records in place."""
    total = len(records)
    for i, record in enumerate(records, 1):
        if not record.get("url"):
            continue
        try:
            page.goto(record["url"], wait_until="networkidle", timeout=30_000)
            page.wait_for_timeout(1_000)
            detail = parse_detail(page.content())
            record.update(detail)
            print(f"[{i}/{total}] OK  {record['title'][:70]}")
        except Exception as e:
            print(f"[{i}/{total}] FAILED  {record.get('url')}  ({e})")
            record.update({
                "effective_date": None, "pdf_links": [], "tags": [], "applies_to": [],
                "issued_pursuant_to_text": None, "issued_pursuant_to": [],
                "related_items": [],
            })
        time.sleep(DETAIL_PAGE_DELAY_SECONDS)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def save_records(records: list[dict], path: str = OUTPUT_FILE) -> None:
    payload = {
        "scraped_at": datetime.now(UTC).isoformat(),
        "source": LISTING_URL,
        "count": len(records),
        "documents": records,
    }
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Scrape MAS Regulations and Guidance")
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Only enrich the first N documents (for testing). Omit for a full run."
    )
    parser.add_argument(
        "--skip-details", action="store_true",
        help="Only do the listing pass (fast) — skip PDF links / tags / related items."
    )
    parser.add_argument(
        "--days", type=int, default=7,
        help="Only keep documents dated within the last N days (default: 7). Use --days 0 to disable this filter and keep everything."
    )
    args = parser.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=USER_AGENT, ignore_https_errors=True)

        print("Fetching listing page (this loads ~1,400+ results)...")
        listing_html = fetch_listing_html(page)
        records = parse_listing(listing_html)
        print(f"Found {len(records)} documents in the listing.")

        if args.days > 0:
            before = len(records)
            records = filter_last_n_days(records, args.days)
            print(f"Filtered to last {args.days} day(s): {len(records)} of {before} documents.")

        if args.limit:
            records = records[: args.limit]
            print(f"Limiting detail pass to first {len(records)} documents.")

        if not args.skip_details:
            print("Visiting each document's page for PDF links, tags, and related items...")
            enrich_with_details(page, records)

        browser.close()

    save_records(records)
    print(f"Saved {len(records)} records to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
