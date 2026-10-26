"""Per-IP rate limiting on prediction endpoints (ARCH §9, DEV_PLAN Task 5.1).

One module-level Limiter: slowapi binds dashboards/routes to the Limiter
instance at decoration time, so every app built by `create_app` shares it;
storage is in-memory (limits.MemoryStorage). Tests can clear the bucket with
`reset_rate_limiter()`.
"""

from __future__ import annotations

import contextlib

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    headers_enabled=True,  # X-RateLimit-* headers on predict endpoints
    default_limits=[],
)

# slowapi evaluates a zero-argument limit provider per request, but gives it
# no access to the request/app — a process-level value read per request is
# the pragmatic hook (create_app sets it from the app's own settings, tests
# can override it by building an app with a different value).
_current_predict_limit = "20/minute"


def set_predict_limit(value: str) -> None:
    """Update the per-process predict rate (called by create_app/tests)."""
    global _current_predict_limit
    _current_predict_limit = value


def predict_limit() -> str:
    """Rate string read at request time (slowapi limit_value provider)."""
    return _current_predict_limit


def reset_rate_limiter() -> None:
    """Clear all rate-limit buckets (test fixture helper)."""
    storage = getattr(limiter, "_storage", None)
    reset = getattr(storage, "reset", None)
    if callable(reset):
        with contextlib.suppress(Exception):
            reset()
