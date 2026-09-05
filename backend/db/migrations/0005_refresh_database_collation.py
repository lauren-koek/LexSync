"""Repair indexes after an operating-system collation version change."""

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

from backend.db.session import engine

logger = logging.getLogger(__name__)

# A full-database REINDEX can outlast the platform healthcheck window, so this
# migration runs off the request-serving startup path (see migrations.runner).
BACKGROUND = True

VERSION_QUERY = """
SELECT datname, datcollversion, pg_database_collation_actual_version(oid)
FROM pg_database
WHERE datname = current_database()
"""


def upgrade(active_engine: Engine = engine) -> None:
    # REINDEX DATABASE is prohibited inside a transaction block. Keeping the
    # inspection and maintenance statements on one AUTOCOMMIT connection also
    # guarantees that current_database() is the database being rebuilt.
    with active_engine.connect().execution_options(
        isolation_level="AUTOCOMMIT"
    ) as connection:
        database_name, recorded_version, actual_version = connection.execute(
            text(VERSION_QUERY)
        ).one()
        if actual_version is None or recorded_version == actual_version:
            return

        quoted_name = active_engine.dialect.identifier_preparer.quote(database_name)
        logger.warning(
            "Repairing collation-dependent indexes for database %s (%s -> %s)",
            database_name,
            recorded_version,
            actual_version,
        )
        try:
            connection.execute(
                text(f"REINDEX DATABASE CONCURRENTLY {quoted_name}")
            )
        except Exception:
            logger.exception(
                "Unable to reindex database %s; collation repair will retry "
                "on the next application startup",
                database_name,
            )
            return
        connection.execute(
            text(f"ALTER DATABASE {quoted_name} REFRESH COLLATION VERSION")
        )


if __name__ == "__main__":
    upgrade()
