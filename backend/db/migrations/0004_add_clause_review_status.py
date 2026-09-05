"""Persist the latest regulatory review verdict for every internal clause."""

from sqlalchemy import text

from backend.db.session import engine

STATEMENTS = (
    "ALTER TABLE internal_document_chunks ADD COLUMN IF NOT EXISTS review_status VARCHAR(20) NOT NULL DEFAULT 'not_checked'",
    "ALTER TABLE internal_document_chunks ADD COLUMN IF NOT EXISTS review_reason TEXT",
    "ALTER TABLE internal_document_chunks ADD COLUMN IF NOT EXISTS last_reviewed_at TIMESTAMPTZ",
)


def upgrade() -> None:
    with engine.begin() as connection:
        for statement in STATEMENTS:
            connection.execute(text(statement))


if __name__ == "__main__":
    upgrade()
