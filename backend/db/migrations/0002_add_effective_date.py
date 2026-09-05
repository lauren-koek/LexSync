"""Migration 0002: add the source-extracted effective date to documents.

Usage:
    DATABASE_URL=postgresql://... python -m backend.db.migrations.0002_add_effective_date

Safe to run more than once (uses ADD COLUMN IF NOT EXISTS).
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from backend.db.session import engine

logger = logging.getLogger(__name__)


def upgrade() -> None:
    statement = "ALTER TABLE documents ADD COLUMN IF NOT EXISTS effective_date DATE"
    with engine.begin() as connection:
        logger.info("Running: %s", statement)
        connection.execute(text(statement))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    upgrade()
    print("Migration 0002 applied: effective_date column present on documents.")
