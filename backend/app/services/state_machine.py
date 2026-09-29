"""Complaint status state machine — an explicit transition table.

This table is the single source of truth. The frontend never holds a copy: the
API returns `allowed_transitions` for each complaint, computed from here.
"""

from __future__ import annotations

from app.domain import Status

TRANSITIONS: dict[Status, frozenset[Status]] = {
    Status.open: frozenset({Status.in_progress, Status.rejected}),
    Status.in_progress: frozenset({Status.resolved, Status.rejected}),
    Status.resolved: frozenset(),  # terminal
    Status.rejected: frozenset(),  # terminal
}


class InvalidTransition(Exception):
    def __init__(self, current: Status, requested: Status) -> None:
        self.current = current
        self.requested = requested
        if not TRANSITIONS[current]:
            reason = f"'{current.value}' is a terminal status"
        else:
            allowed = ", ".join(sorted(s.value for s in TRANSITIONS[current]))
            reason = f"allowed from '{current.value}': {allowed}"
        super().__init__(f"Invalid status transition '{current.value}' -> '{requested.value}' ({reason})")


def allowed_next(current: Status) -> list[Status]:
    return sorted(TRANSITIONS[current], key=lambda s: list(Status).index(s))


def check_transition(current: Status, requested: Status) -> None:
    if requested not in TRANSITIONS[current]:
        raise InvalidTransition(current, requested)
