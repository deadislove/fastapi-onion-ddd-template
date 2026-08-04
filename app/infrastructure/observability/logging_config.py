"""
Structured (JSON) logging — every log line is one JSON object on stdout, carrying the
current request's ID and (when OpenTelemetry tracing is enabled) its trace/span IDs.
"""
from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar

from app.config import settings

# Bound by RequestIDMiddleware for the lifetime of a single request; read here so every
# log record emitted while handling that request is automatically correlated with it.
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

_RESERVED_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message"}


class JSONFormatter(logging.Formatter):
    """Renders each LogRecord as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = request_id_ctx.get()
        if request_id:
            payload["request_id"] = request_id

        # Populated by OpenTelemetry's LoggingInstrumentor when tracing is enabled.
        trace_id = getattr(record, "otelTraceID", None)
        if trace_id and trace_id != "0":
            payload["trace_id"] = trace_id
            payload["span_id"] = getattr(record, "otelSpanID", None)

        # Any caller-supplied `extra={...}` fields, e.g. logger.info(..., extra={"user_id": 1}).
        for key, value in record.__dict__.items():
            if key not in _RESERVED_ATTRS and key not in payload:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """Install the JSON formatter on the root logger. Call once, at process startup."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # Route uvicorn's own loggers through the same JSON handler instead of their default
    # plain-text formatters, so the whole process emits one consistent log shape.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = [handler]
        uv_logger.propagate = False
