"""Structured (JSON) logging with per-request correlation IDs.

Log lines carry a `request_id` so a single prediction can be traced across the
API, services and external calls, as required by `docs/ARCH.md` §14 and
NFR-R-003. Image bytes, tokens and precise coordinates must never be logged
(NFR-S-010) — call sites are responsible for not putting them in the message.
"""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

from pythonjsonlogger.json import JsonFormatter
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"

_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return _request_id.get()


def set_request_id(request_id: str) -> None:
    _request_id.set(request_id)


class RequestIdFilter(logging.Filter):
    """Injects the current request id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Respect an explicit value (e.g. from a handler that runs after the
        # context var has been reset by the middleware's finally block).
        if not hasattr(record, "request_id"):
            record.request_id = get_request_id()
        return True


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging once, replacing uvicorn's default handlers."""
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Our own `app.access` logger emits richer structured access logs; keeping
    # uvicorn's on top would duplicate every request line.
    logging.getLogger("uvicorn.access").disabled = True
    for name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True


class RequestContextMiddleware:
    """Pure ASGI middleware: assigns a request id and logs one access line.

    Written as raw ASGI rather than `BaseHTTPMiddleware` to avoid an extra
    task/stream wrapper on every request (this API is latency sensitive:
    NFR-P-001).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._access_logger = logging.getLogger("app.access")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        incoming = headers.get(REQUEST_ID_HEADER.lower().encode())
        request_id = incoming.decode() if incoming else uuid.uuid4().hex
        token = _request_id.set(request_id)
        # Also publish on the ASGI scope: Starlette's ServerErrorMiddleware (which
        # owns the 500 handler) runs *outside* this middleware, so the context
        # var is already reset by the time it responds.
        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id

        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                raw_headers = list(message.get("headers", []))
                raw_headers.append((REQUEST_ID_HEADER.lower().encode(), request_id.encode()))
                message["headers"] = raw_headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            self._access_logger.info(
                "request completed",
                extra={
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "status_code": status_code,
                },
            )
            _request_id.reset(token)


def log_extra(**kwargs: Any) -> dict[str, Any]:
    """Build an `extra` dict for structured log calls."""
    return kwargs
