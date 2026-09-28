"""Process entry point with graceful SIGTERM handling.

Kubernetes stops a pod by sending SIGTERM, waiting terminationGracePeriodSeconds,
then SIGKILL. On SIGTERM we:

  1. mark the pod not-ready (/ready -> 503), so no new traffic is routed here;
  2. let uvicorn stop accepting connections and finish in-flight requests,
     bounded by SHUTDOWN_GRACE_SECONDS;
  3. run the FastAPI lifespan shutdown, which closes the DB pool and Redis;
  4. exit 0.

The preStop `sleep` in the Deployment runs *before* SIGTERM arrives, giving
the endpoints controller time to take the pod out of the Service first.
"""

from __future__ import annotations

import logging
import signal
from types import FrameType

import uvicorn
from fastapi import FastAPI

from app.core.config import get_settings
from app.main import create_app

log = logging.getLogger("civicpulse.server")


class GracefulServer(uvicorn.Server):
    def __init__(self, config: uvicorn.Config, app: FastAPI) -> None:
        super().__init__(config)
        self._app = app

    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        container = getattr(self._app.state, "container", None)
        if container is not None and not container.draining.is_set():
            container.draining.set()
            log.info("received %s: draining in-flight requests", signal.Signals(sig).name)
        super().handle_exit(sig, frame)


def main() -> None:
    settings = get_settings()
    app = create_app(settings)
    config = uvicorn.Config(
        app,
        host="0.0.0.0",  # noqa: S104 — inside a container, listening on all interfaces is the point
        port=8000,
        proxy_headers=True,
        forwarded_allow_ips="*",  # only reachable via nginx / the Ingress, never directly
        timeout_graceful_shutdown=settings.shutdown_grace_seconds,
        access_log=False,
        log_config=None,
    )
    GracefulServer(config, app).run()


if __name__ == "__main__":
    main()
