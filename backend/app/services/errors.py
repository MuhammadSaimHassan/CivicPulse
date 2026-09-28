"""Errors the service layer raises; routes/errors.py maps them to HTTP."""

from __future__ import annotations

import uuid


class NotFound(Exception):
    def __init__(self, complaint_id: uuid.UUID) -> None:
        super().__init__(f"Complaint {complaint_id} not found")


class ConcurrentUpdate(Exception):
    def __init__(self, complaint_id: uuid.UUID) -> None:
        super().__init__(f"Complaint {complaint_id} was changed by someone else; reload and try again")
