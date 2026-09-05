"""Migration 0001: add issued_pursuant_to columns to documents.

The project creates tables with ``Base.metadata.create_all``, which does not
ALTER existing tables. This standalone, idempotent migration adds the two
``issued_pursuant_to`` columns to an already-populated ``documents`` table.

Usage:
    DATABASE_URL=postgresql://... python -m backend.db.migrations.0001_add_issued_pursuant_to

Safe to run more than once (uses ADD COLUMN IF NOT EXISTS).
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from backend.db.session import engine

logger = logging.getLogger(__name__)

_STATEMENTS = (
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS issued_pursuant_to_text TEXT",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS issued_pursuant_to JSON",
)


def upgrade() -> None:
    with engine.begin() as conn:
        for stmt in _STATEMENTS:
            logger.info("Running: %s", stmt)
            conn.execute(text(stmt))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    upgrade()
    print("Migration 0001 applied: issued_pursuant_to columns present on documents.")
