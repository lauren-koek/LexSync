"""Create durable internal-document parents and regulatory suggestions."""

from sqlalchemy import text

from backend.db.session import engine

STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS internal_documents (
        id UUID PRIMARY KEY,
        title TEXT NOT NULL,
        filename TEXT NOT NULL,
        object_key TEXT NOT NULL UNIQUE,
        content_type VARCHAR(100) NOT NULL,
        size_bytes INTEGER NOT NULL,
        sha256 VARCHAR(64) NOT NULL UNIQUE,
        status VARCHAR(20) NOT NULL DEFAULT 'indexed',
        error_message TEXT,
        chunk_count INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ
    )""",
    "ALTER TABLE internal_document_chunks DROP COLUMN IF EXISTS doc_id",
    "ALTER TABLE internal_document_chunks ADD COLUMN IF NOT EXISTS internal_document_id UUID",
    "DELETE FROM internal_document_chunks WHERE internal_document_id IS NULL",
    """DO $$ BEGIN
        ALTER TABLE internal_document_chunks
        ADD CONSTRAINT fk_internal_chunks_document
        FOREIGN KEY (internal_document_id) REFERENCES internal_documents(id) ON DELETE CASCADE;
    EXCEPTION WHEN duplicate_object THEN NULL; END $$""",
    "ALTER TABLE internal_document_chunks ALTER COLUMN internal_document_id SET NOT NULL",
    "CREATE INDEX IF NOT EXISTS ix_internal_document_chunks_internal_document_id ON internal_document_chunks (internal_document_id)",
    """CREATE TABLE IF NOT EXISTS document_suggestions (
        id UUID PRIMARY KEY,
        regulatory_document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        internal_document_id UUID NOT NULL REFERENCES internal_documents(id) ON DELETE CASCADE,
        internal_chunk_id UUID NOT NULL REFERENCES internal_document_chunks(id) ON DELETE CASCADE,
        regulation_clause_reference TEXT NOT NULL,
        regulation_content TEXT NOT NULL,
        similarity_score DOUBLE PRECISION NOT NULL,
        is_affected BOOLEAN NOT NULL,
        impact_score INTEGER NOT NULL,
        legal_reasoning TEXT NOT NULL,
        proposed_amended_clause TEXT NOT NULL,
        statutory_citations JSON NOT NULL DEFAULT '[]',
        redline_diff TEXT NOT NULL,
        analysis_source VARCHAR(30) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ,
        CONSTRAINT uq_document_suggestion_match UNIQUE (
            regulatory_document_id, regulation_clause_reference, internal_chunk_id
        )
    )""",
    "CREATE INDEX IF NOT EXISTS ix_document_suggestions_regulatory_document_id ON document_suggestions (regulatory_document_id)",
    "CREATE INDEX IF NOT EXISTS ix_document_suggestions_internal_document_id ON document_suggestions (internal_document_id)",
)


def upgrade() -> None:
    with engine.begin() as connection:
        for statement in STATEMENTS:
            connection.execute(text(statement))


if __name__ == "__main__":
    upgrade()
