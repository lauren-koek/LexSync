import json
import logging
from dataclasses import dataclass, field

from llm.client import chat
from llm.prompts.newsletter_prompt import PROMPT

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
        return ProcessedDoc(
            llm_summary=summary,
            llm_categories=categories,
            llm_impact_check=impact_check,
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning("Failed to parse LLM JSON response for document: %s", title or url)
        return ProcessedDoc(
            llm_summary=raw,
            llm_categories=[],
            llm_impact_check="",
        )
