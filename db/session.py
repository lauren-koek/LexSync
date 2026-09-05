import os
from collections.abc import Generator
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base

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
    Base.metadata.create_all(engine)
