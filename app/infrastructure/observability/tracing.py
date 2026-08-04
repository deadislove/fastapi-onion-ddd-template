"""
OpenTelemetry tracing — auto-instruments FastAPI and SQLAlchemy, injects trace/span IDs
into log records (picked up by JSONFormatter), and exports spans via OTLP/HTTP.
Controlled entirely by settings.OTEL_ENABLED — a no-op when disabled, so tests and quick
local runs never need a collector reachable.
"""
from __future__ import annotations

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import settings
from app.infrastructure.database.session import engine


def configure_tracing(app: FastAPI) -> None:
    """Wire up OpenTelemetry. Must run after the FastAPI app and DB engine both exist."""
    if not settings.OTEL_ENABLED:
        return

    provider = TracerProvider(
        resource=Resource.create({SERVICE_NAME: settings.OTEL_SERVICE_NAME})
    )
    exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    # AsyncEngine wraps a sync Engine internally — instrumenting that is the documented
    # way to trace SQLAlchemy's async engines (the events it hooks are sync-side either way).
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    # Stamps otelTraceID/otelSpanID onto every LogRecord so JSONFormatter can include them.
    LoggingInstrumentor().instrument(set_logging_format=False)
