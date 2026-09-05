import os
from collections.abc import Generator
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from backend.db.models import Base

load_dotenv()

_database_url = os.environ.get("DATABASE_URL")
if not _database_url:
    raise OSError("DATABASE_URL environment variable is not set")

engine = create_engine(_database_url)
SessionLocal = sessionmaker(bind=engine)


@contextmanager
def get_session() -> Generator[Session]:
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_tables() -> None:
    # The InternalDocumentChunk table uses pgvector's `vector` column type and
    # an HNSW index, both of which require the extension to already exist. It
    # must be created before create_all() builds the table — migrations run too
    # late (after create_tables) to cover this.
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
