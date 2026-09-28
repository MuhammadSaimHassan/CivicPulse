"""Create the complaints table, its enums, constraints and indexes.

Revision ID: 0001
Revises:
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORY = ("water", "electricity", "sanitation", "roads", "streetlights", "other")
PRIORITY = ("high", "normal", "low")
STATUS = ("open", "in_progress", "resolved", "rejected")
TRIAGED_BY = ("llm:groq", "llm:gemini", "llm:openrouter", "llm:ollama", "rules", "rules:fallback", "simulated")


def upgrade() -> None:
    # gen_random_uuid() is built into PostgreSQL 13+; no extension needed on 16.
    category = postgresql.ENUM(*CATEGORY, name="complaint_category")
    priority = postgresql.ENUM(*PRIORITY, name="complaint_priority")
    status = postgresql.ENUM(*STATUS, name="complaint_status")
    for enum in (category, priority, status):
        enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "complaints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("reporter_contact", sa.String(200), nullable=True),
        sa.Column("category", postgresql.ENUM(name="complaint_category", create_type=False), nullable=False),
        sa.Column("priority", postgresql.ENUM(name="complaint_priority", create_type=False), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="complaint_status", create_type=False),
            nullable=False,
            server_default="open",
        ),
        sa.Column("ai_summary", sa.String(140), nullable=True),
        sa.Column("triaged_by", sa.String(32), nullable=False),
        sa.Column("triage_latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        # Enforced in the database as well as the app: a psql session or a
        # future second service cannot write a 3-character complaint either.
        sa.CheckConstraint("char_length(text) BETWEEN 10 AND 2000", name="ck_complaints_text_length"),
        sa.CheckConstraint("char_length(location) BETWEEN 3 AND 200", name="ck_complaints_location_length"),
        sa.CheckConstraint("triage_latency_ms >= 0", name="ck_complaints_latency_nonnegative"),
        sa.CheckConstraint(
            "triaged_by IN (" + ", ".join(f"'{v}'" for v in TRIAGED_BY) + ")",
            name="ck_complaints_triaged_by",
        ),
    )
    # Dashboard filter: WHERE status = ? [AND priority = ?]  (see ENGINEERING-NOTES)
    op.create_index("ix_complaints_status_priority", "complaints", ["status", "priority"])
    # Dashboard default sort: ORDER BY created_at DESC LIMIT/OFFSET
    op.create_index("ix_complaints_created_at", "complaints", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_complaints_created_at", table_name="complaints")
    op.drop_index("ix_complaints_status_priority", table_name="complaints")
    op.drop_table("complaints")
    for name in ("complaint_status", "complaint_priority", "complaint_category"):
        postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)
