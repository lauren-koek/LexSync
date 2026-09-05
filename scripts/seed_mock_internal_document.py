"""Seed a mock internal document (no PDF) and link it to relevant regulatory changes.

Creates an InternalDocument + chunks directly (bypassing the PDF upload/OCR path),
embeds each clause, then runs the internal-document reanalysis so DocumentSuggestions
are generated against any regulation the policy cites (here: MAS Notice 643). The
document then appears on the Internal Documents page and, because it cites Notice 643,
on the regulatory change's impact view.

Run:  python -m scripts.seed_mock_internal_document
"""

from __future__ import annotations

import hashlib
from uuid import uuid4

from backend.analysis import analyse
from backend.analysis.ingest import chunk_legal_document
from backend.analysis.suggestions import _notice_references, reanalyze_internal_document
from backend.db.models import Document, DocumentSuggestion, InternalDocument, InternalDocumentChunk
from backend.db.session import get_session
from internal_index import EMBEDDING_DIM, embed_text

TITLE = "Related Party Transaction (RPT) Approval Policy"
FILENAME = "RC-POL-014_RPT_Approval_Policy_v2.1.md"

# Plain-text policy body. Numbered clauses give the chunker clean clause
# references, and the "MAS Notice 643" citations are what tie this document to
# the "Notice 643 Transactions with Related Parties" regulatory record.
DOCUMENT_TEXT = """\
Related Party Transaction (RPT) Approval Policy
Document ref: RC-POL-014. Version: v2.1. Redline from: v2.0 (14 Mar 2018).

1. Purpose and Scope
This policy sets out the framework for identifying, assessing, approving, monitoring
and reporting related party transactions entered into by the Company and its
subsidiaries. It applies to every transaction between the Company and a related party
and is to be read together with MAS Notice 643 (Transactions with Related Parties).

2. Board Approval Threshold
A related party transaction exceeding the materiality threshold set under this policy,
or any write-off of exposure to a related party, requires the approval of a special
majority of three-fourths of the Board, determined based on the total number of
directors on the Board, excluding any director required to abstain due to an interest
in the transaction. Basis: MAS Notice 643, paragraph 26.

3. Definitions and Materiality Threshold
Related party has the meaning given in MAS Notice 643. The materiality threshold means
a transaction, or series of related transactions within any rolling 12-month period,
whose aggregate value equals or exceeds the lower of SGD 1,000,000 or 5% of the
Company's latest audited net tangible assets.

4. Identification and Assessment
Any employee who becomes aware of a proposed or existing related party transaction must
notify Compliance before the transaction is committed. An interested director must
declare the nature and extent of their interest and must not participate in the
deliberation or vote on that transaction.

5. Reporting of Exceptions
Every related party transaction that is an exception to, or does not comply with, this
policy must be reported to the Board on a quarterly basis. Basis: MAS Notice 643,
paragraph 18.

6. Record Keeping
Compliance retains full records of each related party transaction, including the
approval trail and declarations of interest, for a minimum of seven years and makes
them available to the auditors and to MAS on request.
"""


def seed() -> None:
    content = DOCUMENT_TEXT.encode("utf-8")
    digest = hashlib.sha256(content).hexdigest()
    document_id = uuid4()

    raw_chunks = chunk_legal_document(DOCUMENT_TEXT, "INTERNAL_ASSET", str(document_id))
    prepared = []
    for raw in raw_chunks:
        vector = [float(value) for value in embed_text(raw["content"])]
        assert len(vector) == EMBEDDING_DIM, "embedding width mismatch"
        prepared.append((raw, vector))

    with get_session() as session:
        existing = session.query(InternalDocument).filter_by(sha256=digest).first()
        if existing is not None:
            print(f"Already seeded: {existing.id} ({existing.title!r})")
            return

        document = InternalDocument(
            id=document_id,
            title=TITLE,
            filename=FILENAME,
            # No PDF is stored; this key is a placeholder so the row is valid.
            object_key=f"internal-documents/{document_id}/{FILENAME}",
            content_type="text/markdown",
            size_bytes=len(content),
            sha256=digest,
            status="indexed",
            chunk_count=len(prepared),
        )
        document.chunks = [
            InternalDocumentChunk(
                title=f"{TITLE} — {raw['clause_reference']}",
                clause_reference=raw["clause_reference"],
                content=raw["content"],
                embedding=vector,
            )
            for raw, vector in prepared
        ]
        session.add(document)
        session.flush()

        result = reanalyze_internal_document(document_id, session)

        # The reanalysis only flags clauses when an LLM (or the offline heuristic)
        # judges them affected. To guarantee the document shows up on the relevant
        # regulatory change for a demo, attach deterministic suggestions taken
        # verbatim from the redline: the exact old -> new clause wording.
        linked = _attach_notice_643_suggestions(document_id, session)

        print(f"Seeded internal document {document_id}")
        print(f"  clauses: {len(prepared)}")
        print(f"  reanalysis: {result}")
        print(f"  linked to regulatory change: {linked}")


# ---------------------------------------------------------------------------
# Exact redline wording taken from the RC-POL-014 v2.0 -> v2.1 screenshot.
# ---------------------------------------------------------------------------

# Section 2 — Board Approval Threshold. Only the approval standard changes; the
# lead-in is identical in both versions, so the redline strikes/adds just the tail.
_BOARD_LEAD_IN = (
    "A related party transaction exceeding the materiality threshold set under this "
    "policy, or any write-off of exposure to a related party, requires the approval of "
)
BOARD_OLD_CLAUSE = _BOARD_LEAD_IN + (
    "a simple majority of the Board (i.e. more than half of directors present and voting)."
)
BOARD_NEW_CLAUSE = _BOARD_LEAD_IN + (
    "a special majority of three-fourths of the Board, determined based on the total "
    "number of directors on the Board, excluding any director required to abstain due "
    "to an interest in the transaction."
)

# Section 5 — Reporting of Exceptions. Marked [NEW] in the screenshot: no
# equivalent clause existed in v2.0, so the redline is a pure addition.
EXCEPTIONS_OLD_CLAUSE = ""
EXCEPTIONS_NEW_CLAUSE = (
    "Every related party transaction that is an exception to, or does not comply with, "
    "this policy must be reported to the Board on a quarterly basis."
)


def _attach_notice_643_suggestions(document_id, session) -> str | None:
    """Deterministically link the redlined clauses to MAS Notice 643.

    Returns the regulatory document title it linked to, or None if the Notice 643
    record could not be found.
    """
    regulation = next(
        (
            doc
            for doc in session.query(Document).all()
            if "notice643" in _notice_references(f"{doc.title or ''}\n{doc.ocr_text or ''}")
            and "notice643a" not in _notice_references(doc.title or "")
        ),
        None,
    )
    if regulation is None:
        return None

    document = session.get(InternalDocument, document_id)
    board_chunk = next(
        (c for c in document.chunks if "three-fourths" in c.content), document.chunks[1]
    )
    exceptions_chunk = next(
        (c for c in document.chunks if "quarterly basis" in c.content),
        document.chunks[-1],
    )

    _upsert_suggestion(
        session,
        regulation=regulation,
        document=document,
        chunk=board_chunk,
        reference="MAS Notice 643, paragraph 26",
        old_clause=BOARD_OLD_CLAUSE,
        new_clause=BOARD_NEW_CLAUSE,
        impact_score=8,
        legal_reasoning=(
            "Notice 643 paragraph 26 raises the Board approval bar for material related "
            "party transactions from a simple majority to a three-fourths special "
            "majority, determined on the total number of directors and excluding any "
            "interested director who must abstain. Amend the clause to require approval "
            "by a special majority of three-fourths of the Board."
        ),
    )
    _upsert_suggestion(
        session,
        regulation=regulation,
        document=document,
        chunk=exceptions_chunk,
        reference="MAS Notice 643, paragraph 18",
        old_clause=EXCEPTIONS_OLD_CLAUSE,
        new_clause=EXCEPTIONS_NEW_CLAUSE,
        impact_score=6,
        legal_reasoning=(
            "Notice 643 paragraph 18 requires exceptions to, or non-compliance with, the "
            "RPT policy to be reported to the Board. No equivalent clause existed in v2.0. "
            "Add a new clause requiring every non-compliant or exceptional related party "
            "transaction to be reported to the Board on a quarterly basis."
        ),
    )

    document.status = "outdated"
    session.flush()
    return regulation.title


def _upsert_suggestion(
    session,
    *,
    regulation,
    document,
    chunk,
    reference,
    old_clause,
    new_clause,
    impact_score,
    legal_reasoning,
) -> None:
    existing = (
        session.query(DocumentSuggestion)
        .filter_by(
            regulatory_document_id=regulation.id,
            regulation_clause_reference=reference,
            internal_chunk_id=chunk.id,
        )
        .first()
    )
    if existing is not None:
        return

    chunk.review_status = "outdated"
    chunk.review_reason = legal_reasoning
    session.add(
        DocumentSuggestion(
            regulatory_document_id=regulation.id,
            internal_document_id=document.id,
            internal_chunk_id=chunk.id,
            regulation_clause_reference=reference,
            regulation_content=new_clause,
            similarity_score=0.94,
            is_affected=True,
            impact_score=impact_score,
            legal_reasoning=legal_reasoning,
            # The concrete change the reviewer should apply — the exact new wording.
            proposed_amended_clause=new_clause,
            statutory_citations=[reference],
            redline_diff=analyse.generate_redline_diff(old_clause, new_clause),
            analysis_source="offline_heuristic",
            status="pending",
        )
    )


if __name__ == "__main__":
    seed()
