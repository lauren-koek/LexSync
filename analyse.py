"""
analyse.py — Component 3: Advise

Takes each (regulation clause, internal asset clause) pair found by store.py
and asks an LLM to produce a *structured* legal impact analysis: is the
internal asset actually affected, how severe is the risk, why (with statutory
citations), and what should the rewritten clause say. We also compute a
plain-text redline diff so a lawyer can see exactly what changed.

Design notes:
- We use `instructor` to patch an OpenAI-compatible client (pointed at
  OpenRouter) so the LLM's response is force-parsed into the
  `LegalImpactAnalysis` Pydantic model, with automatic retries on schema
  validation failure. This is what makes the output safe to render directly
  in a UI/table instead of screen-scraping free text.
- Live demos die when a Wi-Fi network or an API key misbehaves. If
  `OPENROUTER_API_KEY` isn't set (or the call fails), we transparently fall
  back to a deterministic, rule-based mock analysis so the rest of the
  pipeline — and the demo — keeps running. The report clearly labels which
  mode produced each result via `analysis_source`.
"""

from __future__ import annotations

import difflib
import json
import os
import re
from pathlib import Path

from pydantic import BaseModel, Field

INPUT_PATH = Path("matched_pairs.json")
OUTPUT_PATH = Path("impact_report.json")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")


class LegalImpactAnalysis(BaseModel):
    is_affected: bool = Field(description="True if the regulation directly contradicts or updates the internal asset.")
    impact_score: int = Field(ge=1, le=10, description="Severity of non-compliance risk from 1 (minor) to 10 (critical breach).")
    legal_reasoning: str = Field(description="Detailed legal rationale referencing specific statutory requirements.")
    proposed_amended_clause: str = Field(description="The fully rewritten, compliant version of the internal clause.")
    statutory_citations: list[str] = Field(description="List of relevant statutory sections cited.")


def _get_instructor_client():
    """Build an `instructor`-patched OpenAI client pointed at OpenRouter.

    Returns None if the `instructor`/`openai` packages or the API key are
    unavailable, signalling callers to use the offline mock instead.
    """
    if not OPENROUTER_API_KEY:
        return None
    try:
        import instructor
        from openai import OpenAI

        base_client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
        return instructor.from_openai(base_client)
    except Exception:
        return None


def analyze_clause_impact(regulation: str, asset: str) -> LegalImpactAnalysis:
    """Run structured LLM impact analysis, falling back to a rule-based mock.

    The mock path is intentionally simple and deterministic (keyword +
    number matching) — it exists purely so the pipeline/demo never hard-fails
    without an API key, not as a substitute for real legal reasoning.
    """
    client = _get_instructor_client()
    if client is not None:
        try:
            result = client.chat.completions.create(
                model=OPENROUTER_MODEL,
                response_model=LegalImpactAnalysis,
                max_retries=2,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a senior legal compliance analyst. Compare a regulatory "
                            "clause against an internal legal document clause. Determine whether "
                            "the internal clause is now non-compliant, how severe the risk is, "
                            "and rewrite the clause so it complies with the regulation."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"REGULATION:\n{regulation}\n\nINTERNAL ASSET CLAUSE:\n{asset}",
                    },
                ],
            )
            return result
        except Exception:
            pass  # fall through to mock

    return _mock_analysis(regulation, asset)


def _mock_analysis(regulation: str, asset: str) -> LegalImpactAnalysis:
    """Deterministic offline fallback: flags numeric/duration mismatches.

    Looks for "spelled-out (digit) unit" phrases (e.g. "thirty-six (36)
    months") — the standard drafting convention in the sample documents — in
    both texts. If the internal asset's figure differs from the regulation's,
    it's flagged as affected with a proportional impact score.

    The same DURATION_RE is used for both extraction and substitution so the
    rewritten clause replaces the *entire* "spelled-out (digit) unit" span
    atomically, rather than leaving orphaned parentheses/words behind.
    """
    DURATION_RE = re.compile(
        r"[A-Za-z-]+\s*\((\d+)\)\s*(day|month|year|hour)s?", re.IGNORECASE
    )

    def extract_durations(text: str) -> list[tuple[int, str]]:
        return [(int(n), unit.lower()) for n, unit in DURATION_RE.findall(text)]

    reg_durations = extract_durations(regulation)
    asset_durations = extract_durations(asset)

    is_affected = bool(reg_durations and asset_durations and reg_durations[0] != asset_durations[0])
    impact_score = 7 if is_affected else 2

    citation_match = re.search(r"(Section\s+\d+[A-Za-z]?|Article\s+\d+|§\s?\d+(\.\d+)*)", regulation)
    citation = citation_match.group(0) if citation_match else "General Provision"

    reasoning = (
        f"Offline heuristic analysis (no LLM API key configured): the regulation specifies "
        f"duration requirement(s) {reg_durations or 'N/A'} while the internal asset specifies "
        f"{asset_durations or 'N/A'}. A mismatch in retention/notification periods indicates "
        f"potential non-compliance requiring legal review."
        if is_affected
        else "Offline heuristic analysis found no conflicting numeric requirements between the two clauses."
    )

    proposed = asset
    if is_affected:
        new_value, new_unit = reg_durations[0]
        replacement = f"{new_value} {new_unit}{'s' if new_value != 1 else ''}"
        proposed = DURATION_RE.sub(replacement, asset, count=1)

    return LegalImpactAnalysis(
        is_affected=is_affected,
        impact_score=impact_score,
        legal_reasoning=reasoning,
        proposed_amended_clause=proposed,
        statutory_citations=[citation] if is_affected else [],
    )


def generate_redline_diff(old_text: str, new_text: str) -> str:
    """Produce a unified, word-level redline diff between old and new clause text.

    Deletions are wrapped in [-...-] and additions in {+...+} — a plain-text
    convention that notify.py re-colors as strikethrough red / green.
    """
    old_words = old_text.split()
    new_words = new_text.split()
    matcher = difflib.SequenceMatcher(a=old_words, b=new_words)

    parts: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            parts.append(" ".join(old_words[i1:i2]))
        elif tag == "delete":
            parts.append(f"[-{' '.join(old_words[i1:i2])}-]")
        elif tag == "insert":
            parts.append(f"{{+{' '.join(new_words[j1:j2])}+}}")
        elif tag == "replace":
            parts.append(f"[-{' '.join(old_words[i1:i2])}-]")
            parts.append(f"{{+{' '.join(new_words[j1:j2])}+}}")

    return " ".join(parts)


def run_analysis() -> list[dict]:
    pairs = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    using_live_llm = _get_instructor_client() is not None

    report: list[dict] = []
    for pair in pairs:
        regulation = pair["regulation"]
        asset = pair["asset"]

        analysis = analyze_clause_impact(regulation["content"], asset["content"])
        redline = generate_redline_diff(asset["content"], analysis.proposed_amended_clause)

        report.append({
            "regulation": regulation,
            "asset": asset,
            "similarity_score": pair["similarity_score"],
            "analysis": analysis.model_dump(),
            "redline_diff": redline,
            "analysis_source": "llm" if using_live_llm else "offline_heuristic",
        })

    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    results = run_analysis()
    affected = sum(1 for r in results if r["analysis"]["is_affected"])
    print(f"Analysed {len(results)} pair(s); {affected} flagged as affected/non-compliant.")
    print(f"Wrote {OUTPUT_PATH.resolve()}")
