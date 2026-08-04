# Observability

Three pieces, designed to compose: structured JSON logs, a request ID that ties every log
line (and error response) back to one HTTP request, and opt-in distributed tracing that adds
`trace_id`/`span_id` on top of the same logs. All three live under
`app/infrastructure/observability/`.

## Structured Logging

`configure_logging()` (`app/infrastructure/observability/logging_config.py`) installs a
`JSONFormatter` on the root logger — every log line, from every logger in the process
(including `uvicorn.access`/`uvicorn.error`, redirected onto the same handler), becomes one
JSON object on stdout:

```json
{"timestamp": "2026-08-04T22:41:34+0800", "level": "INFO", "logger": "uvicorn.access", "message": "127.0.0.1:55375 - \"GET /health HTTP/1.1\" 200", "request_id": "..."}
```

Any `extra={...}` kwargs passed to a `logger.info(...)` call are included automatically —
`JSONFormatter.format()` walks `record.__dict__`, skips the reserved `LogRecord` attributes,
and includes everything else. `LoggingEventDispatcher` (below) relies on exactly this.

### Request ID Correlation

`RequestIDMiddleware` (`app/infrastructure/observability/request_id.py`) generates a UUID per
request (or reuses an inbound `X-Request-ID` header, so an upstream gateway's ID survives),
binds it to a `ContextVar`, and echoes it back as a response header. `JSONFormatter` reads
that same `ContextVar` for every log line emitted while handling the request — no need to
thread a request ID through every function call manually.

The same ID also appears in RFC 7807 error bodies (`request_id` field — see
[error-handling.md](error-handling.md)), so a client can hand a support team one ID that
correlates: the response they got, every log line from that request, and (if tracing is on)
the trace in Jaeger.

**Middleware order matters here.** `RequestIDMiddleware` is added *last* in
`main.py`'s `create_app()`, which makes it the *outermost* layer (Starlette wraps middleware
in reverse-registration order) — the request ID is bound before `GlobalExceptionHandlerMiddleware`
or anything else runs, so even a request that crashes with an unhandled exception gets a
correlated log line and error response.

### A Bug This Design Caught: Alembic Clobbering the Logger

Running Alembic migrations at app startup (see [database.md](database.md)) interacts badly
with `logging.config.fileConfig()`, which `alembic/env.py` calls to read `alembic.ini`'s
logging section. Two problems, both real, both fixed:

1. `fileConfig()`'s default `disable_existing_loggers=True` **disables every logger not
   listed in `alembic.ini`** — including `uvicorn.access`/`uvicorn.error`, silently killing
   all further log output from the app after the first migration run. Fixed by passing
   `disable_existing_loggers=False` in `alembic/env.py`.
2. Even with that fixed, `fileConfig()` still **replaces the root logger's handlers** with
   `alembic.ini`'s plain-text formatter, discarding the `JSONFormatter` `configure_logging()`
   installed at import time. Fixed by calling `configure_logging()` a second time, in
   `main.py`'s `lifespan()`, right after migrations run — reasserting the JSON setup for the
   rest of the process's life.

This was caught by actually booting the app and reading the logs, not by unit tests — a
useful reminder that "the pieces individually work" doesn't guarantee "the pieces work
together in the actual boot sequence."

## Domain Events as Logs

`LoggingEventDispatcher` (`app/infrastructure/observability/event_dispatcher.py`) is the
concrete `IEventDispatcher` — every domain event (see
[architecture.md](architecture.md#domain-events)) becomes one structured log line:

```json
{"logger": "domain.events", "message": "domain_event", "event_type": "ProductCreatedEvent", "event_data": {"event_id": "...", "product_id": 1, "owner_id": 1, "name": "Widget"}, "request_id": "..."}
```

Event fields are nested under `event_data` rather than spread as top-level `extra` kwargs —
`ProductCreatedEvent.name` collides with `LogRecord`'s own reserved `name` attribute (the
logger's name), which raises `KeyError: Attempt to overwrite 'name' in LogRecord` if spread
directly. `tests/unit/test_logging_event_dispatcher.py` exercises the *real* dispatcher
(not the in-memory fake used elsewhere) against every event type specifically to catch this
class of bug — it was found via a live smoke test, not a unit test, because the integration
tests all substitute a fake dispatcher that never touches Python's `logging` internals.

## OpenTelemetry Tracing (Opt-In)

Off by default (`OTEL_ENABLED=false`) so tests and quick local runs never need a collector
reachable. `configure_tracing()` (`app/infrastructure/observability/tracing.py`), called from
`main.py`'s `create_app()`, is a no-op when disabled and otherwise:

- Auto-instruments FastAPI (`FastAPIInstrumentor`) — one span per request.
- Auto-instruments SQLAlchemy (`SQLAlchemyInstrumentor`) — instruments
  `engine.sync_engine`, since `AsyncEngine` wraps a sync `Engine` internally and that's where
  the instrumentable events actually fire.
- Injects `otelTraceID`/`otelSpanID` onto every `LogRecord` (`LoggingInstrumentor`), which
  `JSONFormatter` picks up as `trace_id`/`span_id` — so a single request's logs and its trace
  are correlated the same way logs and `request_id` are.
- Exports spans via OTLP/HTTP (`OTLPSpanExporter`) to `OTEL_EXPORTER_OTLP_ENDPOINT`.

### Running It Locally

`docker compose up -d --build` starts a `jaeger` service
(`jaegertracing/all-in-one`, OTLP receiver built in since Jaeger 1.35) alongside the app, with
`OTEL_ENABLED=true` and `OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318/v1/traces` already
wired in `docker-compose.yml`. Open `http://localhost:16686` to browse traces.

Outside Docker, point `OTEL_EXPORTER_OTLP_ENDPOINT` at any OTLP/HTTP-compatible collector and
set `OTEL_ENABLED=true`.

## Environment Variables

| Variable | Default | Effect |
|---|---|---|
| `DEBUG` | `false` | `DEBUG=true` sets the root logger to `DEBUG` level and enables SQLAlchemy SQL echo |
| `OTEL_ENABLED` | `false` | Turns tracing on/off entirely |
| `OTEL_SERVICE_NAME` | `fastapi-onion-ddd-template` | `service.name` resource attribute on exported spans |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4318/v1/traces` | Where spans are POSTed |

## Extending This

- **New log destination** (e.g. shipping to a log aggregator instead of stdout): add a
  handler in `configure_logging()`. Everything that logs through the standard `logging`
  module — including third-party libraries — picks it up automatically.
- **New event sink** (Redis stream, Kafka, an outbox table): implement `IEventDispatcher`
  and rewire the one line in `app/infrastructure/dependencies.py` that constructs
  `LoggingEventDispatcher` — no changes to any entity or service.
