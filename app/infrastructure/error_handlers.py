"""
Global Exception Handler Middleware — catches unhandled technical errors (500)
and returns RFC 7807 Problem Details style JSON responses.
Prevents traceback leaks to clients.
"""
from __future__ import annotations

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.infrastructure.observability.logging_config import request_id_ctx

logger = logging.getLogger(__name__)


def _problem_detail(
    status: int,
    title: str,
    detail: str,
    instance: str | None = None,
    **extra: object,
) -> dict:
    """Build an RFC 7807 Problem Details response body."""
    body: dict = {
        "type": f"https://httpstatuses.com/{status}",
        "title": title,
        "status": status,
        "detail": detail,
    }
    if instance:
        body["instance"] = instance
    request_id = request_id_ctx.get()
    if request_id:
        body["request_id"] = request_id
    body.update(extra)
    return body


def _status_title(status_code: int) -> str:
    """Human-readable title for a status code, e.g. 404 -> 'Not Found'."""
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Error"


class GlobalExceptionHandlerMiddleware(BaseHTTPMiddleware):
    """
    Catches any unhandled exception that propagates out of route handlers
    and returns a structured 500 JSON response without leaking tracebacks.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            logger.error(
                "Unhandled exception on %s %s: %s",
                request.method,
                request.url.path,
                exc,
                exc_info=True,
            )
            return JSONResponse(
                status_code=500,
                content=_problem_detail(
                    status=500,
                    title="Internal Server Error",
                    detail="An unexpected error occurred. Please try again later.",
                    instance=request.url.path,
                ),
            )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers on the FastAPI application."""

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content=_problem_detail(
                status=429,
                title="Too Many Requests",
                detail=f"Rate limit exceeded: {exc.detail}",
                instance=request.url.path,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """
        Formats *every* HTTPException as RFC 7807 — not just the 404/405 Starlette
        raises internally for unmatched routes/methods, but also every HTTPException
        raised by application code (e.g. _domain_error_to_http() in the routers, which
        covers 400/401/403/409/...). Registering a handler by status code in FastAPI
        only intercepts HTTPExceptions with that exact status code; registering one for
        the HTTPException class itself catches all of them through a single place.
        """
        return JSONResponse(
            status_code=exc.status_code,
            content=_problem_detail(
                status=exc.status_code,
                title=_status_title(exc.status_code),
                detail=str(exc.detail),
                instance=request.url.path,
            ),
            headers=exc.headers,
        )
