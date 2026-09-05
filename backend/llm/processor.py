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
    hallucination_flag: bool = False
    hallucination_notes: str = ""


def _apply_grounding(processed: ProcessedDoc, source_text: str) -> ProcessedDoc:
    check = check_summary_grounding(source_text, processed.llm_summary)
    processed.hallucination_flag = not check.is_grounded
    processed.hallucination_notes = check.notes
    return processed


def _parse_response(raw: str) -> ProcessedDoc:
    """Parse and validate the structured fields returned by the LLM."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("LLM response must be a JSON object")

    return ProcessedDoc(
        llm_summary=str(parsed.get("summary", "")),
        llm_categories=[
            category
            for category in parsed.get("categories", [])
            if category in STANDARD_TAGS
        ],
        llm_impact_check=str(parsed.get("impact_check", "")),
    )


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
        '  "impact_check": string, impact-check content only; omit the heading and effective date\n\n'
        "Return only the JSON object, no markdown fences or additional text."
    )

    try:
        raw = chat(user_prompt, system=PROMPT)
        processed = _apply_grounding(_parse_response(raw), truncated_ocr)
        logger.info("Successfully processed document: %s", title or url)
        return processed
    except (json.JSONDecodeError, AttributeError, KeyError, TypeError, ValueError):
        logger.warning(
            "Malformed LLM JSON response for document %s; retrying once",
            title or url,
        )
        repair_prompt = (
            "Your previous response was malformed or did not match the required JSON "
            "object. Return a complete replacement containing exactly summary, "
            "categories, and impact_check. Return only valid JSON."
        )
        repaired = chat(
            repair_prompt,
            system=PROMPT,
            history=[
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": raw},
            ],
        )
        try:
            processed = _apply_grounding(_parse_response(repaired), truncated_ocr)
        except (json.JSONDecodeError, AttributeError, KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "Failed to obtain valid LLM JSON after retry for document: %s",
                title or url,
            )
            raise ValueError("LLM did not return valid JSON after retry") from exc

        logger.info("Successfully processed document after retry: %s", title or url)
        return processed
