"""State machine, logging and shutdown unit tests."""

from __future__ import annotations

import json
import logging
import signal

import pytest

from app.core.logging import JsonFormatter, request_id_var
from app.domain import Status
from app.services.state_machine import TRANSITIONS, InvalidTransition, allowed_next, check_transition

VALID = {
    (Status.open, Status.in_progress),
    (Status.open, Status.rejected),
    (Status.in_progress, Status.resolved),
    (Status.in_progress, Status.rejected),
}


@pytest.mark.parametrize("current", list(Status))
@pytest.mark.parametrize("requested", list(Status))
def test_transition_table_matches_the_specification(current: Status, requested: Status) -> None:
    if (current, requested) in VALID:
        check_transition(current, requested)
    else:
        with pytest.raises(InvalidTransition) as info:
            check_transition(current, requested)
        assert f"'{current.value}' -> '{requested.value}'" in str(info.value)


def test_terminal_states_have_no_exits() -> None:
    assert allowed_next(Status.resolved) == [] and allowed_next(Status.rejected) == []
    assert "terminal" in str(InvalidTransition(Status.resolved, Status.open))


def test_table_covers_every_status() -> None:
    assert set(TRANSITIONS) == set(Status)


def test_json_log_line_carries_request_id_and_extras() -> None:
    token = request_id_var.set("req-123")
    try:
        record = logging.makeLogRecord({"msg": "triage fallback", "levelname": "WARNING", "provider": "llm:groq"})
        line = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert line["request_id"] == "req-123"
    assert line["provider"] == "llm:groq"
    assert line["msg"] == "triage fallback"


def test_sigterm_marks_the_pod_as_draining() -> None:
    import threading
    from types import SimpleNamespace

    import uvicorn
    from fastapi import FastAPI

    from app.server import GracefulServer

    app = FastAPI()
    app.state.container = SimpleNamespace(draining=threading.Event())
    server = GracefulServer(uvicorn.Config(app), app)
    server.handle_exit(signal.SIGTERM, None)
    assert app.state.container.draining.is_set()
    assert server.should_exit
