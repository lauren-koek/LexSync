from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON, Date, String, Text


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    doc_type: Mapped[str | None] = mapped_column(String(100))
    date: Mapped[date | None] = mapped_column(Date, nullable=True)
    title: Mapped[str | None] = mapped_column(Text)
    topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[Any] = mapped_column(JSON)
    applies_to: Mapped[Any] = mapped_column(JSON)
    related_items: Mapped[Any] = mapped_column(JSON)
    pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_local_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_categories: Mapped[Any] = mapped_column(JSON, nullable=True)
    llm_impact_check: Mapped[str | None] = mapped_column(Text, nullable=True)
    scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
