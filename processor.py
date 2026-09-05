import json
import logging
from dataclasses import dataclass, field

from backend.llm.client import chat
from backend.llm.hallucination_check import check_summary_grounding
from backend.llm.prompts.newsletter_prompt import PROMPT

logger = logging.getLogger(__name__)

STANDARD_TAGS = [
    "AI",
    "Data Protection",
    "Financial Services",
    "Tax",
    "Corporate",
    "Employment",
    "Cybersecurity",
    "Digital Assets",
    "Consumer Protection",
    "Dispute Resolution",
    "Intellectual Property",
    "Competition",
    "General",
]

_OCR_CHAR_LIMIT = 6000


@dataclass
class ProcessedDoc:
    llm_summary: str
    llm_categories: list[str] = field(default_factory=list)
    llm_impact_check: str = ""
    # Set by check_summary_grounding() against the exact text the LLM saw —
    # True means the summary contains a number/date not present in the
    # source, or drifted vocabulary far enough from it to warrant a human
    # look. This is advisory, never blocks the summary from being saved.
    hallucination_flag: bool = False
    hallucination_notes: str = ""


def process_document(doc: dict, ocr_text: str) -> ProcessedDoc:
    title = doc.get("title", "")
    date = doc.get("date", "")
    doc_type = doc.get("doc_type", "")
    url = doc.get("url", "")

    logger.info("Processing document: %s", title or url)

    truncated_ocr = ocr_text[:_OCR_CHAR_LIMIT]

    user_prompt = (
        f"Title: {title}\n"
        f"Date: {date}\n"
        f"Document type: {doc_type}\n"
        f"URL: {url}\n\n"
        f"Document text (may be truncated):\n{truncated_ocr}\n\n"
        "Respond with a JSON object containing exactly three fields:\n"
        '  "summary": string, 80-150 words, objective voice\n'
        f'  "categories": array of strings, each must be one of: {json.dumps(STANDARD_TAGS)}\n'
        '  "impact_check": string, the IMPACT CHECK block\n\n'
        "Return only the JSON object, no markdown fences or additional text."
    )

    raw = chat(user_prompt, system=PROMPT)

    try:
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```", 2)[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        parsed = json.loads(cleaned)
        summary = str(parsed.get("summary", ""))
        categories = [c for c in parsed.get("categories", []) if c in STANDARD_TAGS]
        impact_check = str(parsed.get("impact_check", ""))
        logger.info("Successfully processed document: %s", title or url)

        # Check against truncated_ocr, not the full ocr_text — that's the
        # exact text the LLM was given, so grounding is judged against what
        # it could actually have known, not against content it never saw.
        check = check_summary_grounding(truncated_ocr, summary)
        if not check.is_grounded:
            logger.warning(
                "Possible hallucination in summary for %s: %s", title or url, check.notes
            )
        return ProcessedDoc(
            llm_summary=summary,
            llm_categories=categories,
            llm_impact_check=impact_check,
            hallucination_flag=not check.is_grounded,
            hallucination_notes=check.notes,
        )
    except (json.JSONDecodeError, AttributeError, KeyError, TypeError, ValueError):
        logger.warning("Failed to parse LLM JSON response for document: %s", title or url)
        return ProcessedDoc(
            llm_summary=raw,
            llm_categories=[],
            llm_impact_check="",
        )
