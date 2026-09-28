"""ORM mapping of the complaints table.

The schema itself is owned by Alembic (alembic/versions/). This mapping must
match it; tests/test_migrations.py fails if they drift.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain import TRIAGED_BY_VALUES, Category, Priority, Status


class Base(DeclarativeBase):
    pass


def _pg_enum(enum_cls: type, name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        values_callable=lambda e: [m.value for m in e],
        create_type=False,  # created by the migration, not by the app
    )


class ComplaintRow(Base):
    __tablename__ = "complaints"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    reporter_contact: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category: Mapped[Category] = mapped_column(_pg_enum(Category, "complaint_category"), nullable=False)
    priority: Mapped[Priority] = mapped_column(_pg_enum(Priority, "complaint_priority"), nullable=False)
    status: Mapped[Status] = mapped_column(
        _pg_enum(Status, "complaint_status"), nullable=False, server_default=Status.open.value
    )
    ai_summary: Mapped[str | None] = mapped_column(String(140), nullable=True)
    triaged_by: Mapped[str] = mapped_column(String(32), nullable=False)
    triage_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("char_length(text) BETWEEN 10 AND 2000", name="ck_complaints_text_length"),
        CheckConstraint("char_length(location) BETWEEN 3 AND 200", name="ck_complaints_location_length"),
        CheckConstraint("triage_latency_ms >= 0", name="ck_complaints_latency_nonnegative"),
        CheckConstraint(
            "triaged_by IN (" + ", ".join(f"'{v}'" for v in TRIAGED_BY_VALUES) + ")",
            name="ck_complaints_triaged_by",
        ),
        Index("ix_complaints_status_priority", "status", "priority"),
        Index("ix_complaints_created_at", "created_at"),
    )
