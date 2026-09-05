from backend.db.models import (
    DocumentSuggestion,
    InternalDocument,
    InternalDocumentChunk,
)


def test_internal_chunk_belongs_to_parent_document():
    foreign_keys = InternalDocumentChunk.__table__.c.internal_document_id.foreign_keys

    assert foreign_keys
    assert next(iter(foreign_keys)).target_fullname == "internal_documents.id"
    assert "doc_id" not in InternalDocumentChunk.__table__.c


def test_document_digest_is_unique():
    assert InternalDocument.__table__.c.sha256.unique is True


def test_suggestion_match_is_unique():
    constraint_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in DocumentSuggestion.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }

    assert (
        "regulatory_document_id",
        "regulation_clause_reference",
        "internal_chunk_id",
    ) in constraint_columns
