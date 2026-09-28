"""All SQL for complaints lives here, and nowhere else."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain import Category, Priority, Status
from app.repositories.models import ComplaintRow


@dataclass(frozen=True)
class ComplaintFilter:
    category: Category | None = None
    priority: Priority | None = None
    status: Status | None = None


class ComplaintRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, **fields: Any) -> ComplaintRow:
        row = ComplaintRow(**fields)
        self._s.add(row)
        self._s.flush()
        self._s.refresh(row)  # pick up server defaults: status, created_at
        return row

    def get(self, complaint_id: uuid.UUID) -> ComplaintRow | None:
        return self._s.get(ComplaintRow, complaint_id)

    def search(self, flt: ComplaintFilter, *, page: int, page_size: int) -> tuple[list[ComplaintRow], int]:
        conditions = []
        if flt.category is not None:
            conditions.append(ComplaintRow.category == flt.category)
        if flt.priority is not None:
            conditions.append(ComplaintRow.priority == flt.priority)
        if flt.status is not None:
            conditions.append(ComplaintRow.status == flt.status)

        total = self._s.scalar(select(func.count()).select_from(ComplaintRow).where(*conditions)) or 0
        # ORDER BY created_at DESC LIMIT n is served by ix_complaints_created_at;
        # the status/priority filters by ix_complaints_status_priority.
        rows = self._s.scalars(
            select(ComplaintRow)
            .where(*conditions)
            .order_by(ComplaintRow.created_at.desc(), ComplaintRow.id)
            .limit(page_size)
            .offset((page - 1) * page_size)
        ).all()
        return list(rows), int(total)

    def transition_status(self, complaint_id: uuid.UUID, *, expected: Status, new: Status) -> ComplaintRow | None:
        """Compare-and-set. Returns None if the row's status changed underneath us,
        so two operators clicking at once cannot both 'win' an invalid path."""
        result = self._s.execute(
            update(ComplaintRow)
            .where(ComplaintRow.id == complaint_id, ComplaintRow.status == expected)
            .values(status=new, updated_at=func.now())
            .returning(ComplaintRow.id)
        ).first()
        if result is None:
            return None
        self._s.expire_all()
        return self.get(complaint_id)

    def counts_by(self, column: str) -> dict[str, int]:
        col = getattr(ComplaintRow, column)
        rows = self._s.execute(select(col, func.count()).group_by(col)).all()
        return {str(key.value if hasattr(key, "value") else key): int(n) for key, n in rows}

    def total(self) -> int:
        return int(self._s.scalar(select(func.count()).select_from(ComplaintRow)) or 0)

    def insert_if_absent(self, rows: list[dict[str, Any]]) -> int:
        """Idempotent bulk insert keyed on id. Returns how many rows were new."""
        if not rows:
            return 0
        stmt = (
            insert(ComplaintRow).values(rows).on_conflict_do_nothing(index_elements=["id"]).returning(ComplaintRow.id)
        )
        return len(self._s.execute(stmt).all())
