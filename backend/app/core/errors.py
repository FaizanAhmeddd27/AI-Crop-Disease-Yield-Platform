"""Standard error contract (SRS Appendix B, ARCH §7.2).

Every failure returns the same JSON envelope:

    {"error": {"code": "...", "message": "...", "details": {...}, "request_id": "..."}}

so the frontend can map codes to user-facing messages without parsing prose
(FR-UI-005).
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import REQUEST_ID_HEADER, get_request_id

logger = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    UNSUPPORTED_CROP = "UNSUPPORTED_CROP"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    NOT_A_LEAF = "NOT_A_LEAF"
    RATE_LIMITED = "RATE_LIMITED"
    WEATHER_UNAVAILABLE = "WEATHER_UNAVAILABLE"
    MODEL_NOT_READY = "MODEL_NOT_READY"
    EXPLANATION_UNAVAILABLE = "EXPLANATION_UNAVAILABLE"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# HTTP status per error code (ARCH §7.2).
_STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.INVALID_INPUT: 400,
    ErrorCode.UNSUPPORTED_CROP: 400,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.FILE_TOO_LARGE: 413,
    ErrorCode.UNSUPPORTED_MEDIA_TYPE: 415,
    ErrorCode.NOT_A_LEAF: 422,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.WEATHER_UNAVAILABLE: 502,
    ErrorCode.MODEL_NOT_READY: 503,
    ErrorCode.EXPLANATION_UNAVAILABLE: 503,
    ErrorCode.INTERNAL_ERROR: 500,
}


class AppError(Exception):
    """Base class for errors that are safe to surface to the client."""

    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    status_code: int = 500

    def __init__(
        self,
        message: str,
        *,
        code: ErrorCode | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
            self.status_code = _STATUS_BY_CODE[code]
        self.details = details or {}


class ModelNotReadyError(AppError):
    code = ErrorCode.MODEL_NOT_READY
    status_code = 503


class UnsupportedCropError(AppError):
    code = ErrorCode.UNSUPPORTED_CROP
    status_code = 400


class UnsupportedMediaTypeError(AppError):
    code = ErrorCode.UNSUPPORTED_MEDIA_TYPE
    status_code = 415


class WeatherUnavailableError(AppError):
    code = ErrorCode.WEATHER_UNAVAILABLE
    status_code = 502


def error_body(
    code: ErrorCode | str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": str(code),
            "message": message,
            "details": details or {},
            "request_id": request_id or get_request_id(),
        }
    }


def _request_id_for(request: Request | None) -> str:
    """Request id that also survives the ServerErrorMiddleware boundary."""
    if request is not None:
        value = getattr(request.state, "request_id", None)
        if value:
            return str(value)
    return get_request_id()


def _json_error(
    status_code: int,
    code: ErrorCode | str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_body(code, message, details=details, request_id=request_id),
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error(
                "application error",
                extra={"code": str(exc.code), "request_id": _request_id_for(request)},
            )
        return _json_error(
            exc.status_code,
            exc.code,
            exc.message,
            details=exc.details,
            request_id=_request_id_for(request),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Keep only the serialisable parts of pydantic's error objects.
        details = [
            {
                "loc": list(error.get("loc", ())),
                "msg": error.get("msg", ""),
                "type": error.get("type", ""),
            }
            for error in exc.errors()
        ]
        return _json_error(
            422,
            ErrorCode.INVALID_INPUT,
            "Request validation failed.",
            details={"errors": details},
            request_id=_request_id_for(request),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        fallback = ErrorCode.INTERNAL_ERROR if exc.status_code >= 500 else ErrorCode.INVALID_INPUT
        code = {
            404: ErrorCode.NOT_FOUND,
            429: ErrorCode.RATE_LIMITED,
            503: ErrorCode.MODEL_NOT_READY,
        }.get(exc.status_code, fallback)
        return _json_error(
            exc.status_code,
            code,
            str(exc.detail),
            request_id=_request_id_for(request),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Never leak internals to the client; the request id ties the response
        # to the (redacted) log entry. This handler runs outside the request
        # middleware, so it sets the header itself.
        request_id = _request_id_for(request)
        logger.error("unhandled exception", exc_info=exc, extra={"request_id": request_id})
        return JSONResponse(
            status_code=500,
            content=error_body(
                ErrorCode.INTERNAL_ERROR,
                "An unexpected error occurred. Please try again.",
                request_id=request_id,
            ),
            headers={REQUEST_ID_HEADER: request_id},
        )
