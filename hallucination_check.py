"""hallucination_check.py — Lightweight grounding check for LLM summaries.

Purpose: catch the most damaging and most detectable failure mode in
regulatory-document summarization — the LLM inventing or transposing a
figure (a deadline, a retention period, a penalty amount) that isn't
actually in the source text. This is deliberately NOT another LLM call:
a second model can hallucinate its own judgement about the first model's
hallucination, costs money and latency on every document, and adds a
network dependency to what should be a cheap sanity check. Everything
here is a deterministic, offline function of two strings.

This is a coarse net, not a fact-checker: it cannot tell you a summary
correctly restates a number but attributes it to the wrong party, or that
a qualitative claim ("this significantly raises compliance risk") isn't
supported. It exists to catch the cheap, high-confidence case — a
fabricated number/date — and to flag summaries that drifted far enough
from the source's vocabulary to warrant a human look, not to replace one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Digit-bearing tokens (36, 7%, 24, 2026-09-05, ...) are the highest-stakes,
# exactly-matchable claims an LLM can hallucinate in a regulatory summary —
# a fabricated "30 days" instead of the source's "60 days" is far more
# consequential than a slightly different turn of phrase, and unlike free
# text, an exact digit match is cheap and unambiguous to verify.
_NUMBER_RE = re.compile(r"\d[\d,.:/-]*\d|\d")

# Small stopword list — just enough to keep the overlap ratio from being
# dominated by function words that appear in almost any English text and
# would make every summary look "grounded" regardless of content.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "by",
    "with", "is", "are", "was", "were", "be", "been", "being", "this",
    "that", "these", "those", "it", "its", "as", "at", "from", "must",
    "shall", "will", "would", "should", "may", "might", "which", "who",
    "whom", "not", "no", "any", "all", "such", "into", "under", "than",
    "then", "so", "if", "but", "has", "have", "had", "each", "their",
}


@dataclass
class HallucinationCheckResult:
    is_grounded: bool
    # Numbers/dates that appear in the summary but not anywhere in the
    # source text — the strongest single signal this check produces.
    unsupported_numbers: list[str] = field(default_factory=list)
    # Fraction of the summary's substantive (non-stopword) words that also
    # appear somewhere in the source. Low overlap suggests the summary
    # drifted onto content not actually present in the source.
    word_overlap_ratio: float = 0.0

    @property
    def notes(self) -> str:
        """Human-readable explanation, suitable for a log line or a
        reviewer-facing flag — never raised as an error, since this check
        is advisory, not a hard gate on publishing the summary."""
        if self.is_grounded:
            return "Summary numbers and vocabulary are grounded in the source text."
        parts = []
        if self.unsupported_numbers:
            parts.append(
                "Numbers in the summary not found in the source: "
                + ", ".join(self.unsupported_numbers)
            )
        parts.append(f"Vocabulary overlap with source: {self.word_overlap_ratio:.0%}.")
        return " ".join(parts)


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [word for word in words if word not in _STOPWORDS and len(word) > 2]


def check_summary_grounding(
    source_text: str,
    summary: str,
    *,
    overlap_threshold: float = 0.3,
) -> HallucinationCheckResult:
    """Flag likely hallucinations in `summary` relative to `source_text`.

    `source_text` should be exactly what the LLM was actually given (e.g.
    the truncated OCR text passed into the prompt) — checking against a
    fuller original the model never saw would unfairly flag correct
    summaries of the truncated portion, or unfairly clear a summary that
    invented something the model genuinely had no way to know.

    `overlap_threshold` is the minimum fraction of the summary's
    substantive vocabulary that must reappear in the source before the
    summary is considered on-topic; tune it down for very short summaries
    of long documents, where some paraphrase-driven vocabulary drift is
    expected even from an accurate summary.
    """
    source_numbers = set(_NUMBER_RE.findall(source_text))
    summary_numbers = _NUMBER_RE.findall(summary)
    unsupported = sorted({n for n in summary_numbers if n not in source_numbers})

    summary_tokens = _tokenize(summary)
    source_tokens = set(_tokenize(source_text))
    if summary_tokens:
        overlap_ratio = sum(1 for tok in summary_tokens if tok in source_tokens) / len(
            summary_tokens
        )
    else:
        overlap_ratio = 1.0  # an empty summary has nothing ungrounded to flag

    is_grounded = not unsupported and overlap_ratio >= overlap_threshold

    return HallucinationCheckResult(
        is_grounded=is_grounded,
        unsupported_numbers=unsupported,
        word_overlap_ratio=round(overlap_ratio, 4),
    )
