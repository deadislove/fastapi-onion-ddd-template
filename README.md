# fastapi-onion-ddd-template

A production-ready **FastAPI** Web API template implementing **Onion Architecture** and **Domain-Driven Design (DDD)** principles.

## Features

- 🏗️ **Onion Architecture** — strict layer separation (Domain → Application → Infrastructure → Presentation)
- 🎯 **DDD** — Aggregate Roots built from real Value Objects (`Email`, `Money`, `ProductName`, `Password` — not primitives), Domain Events actually dispatched (not just declared), Repository Interfaces
- 💰 **Exact Money** — prices are `Decimal`/`Numeric` end-to-end (domain → DB), never `float` — no floating-point rounding drift in monetary values
- ✅ **Result Pattern** — explicit `Ok[T]` / `Err[E]` instead of exceptions for business errors
- 🔐 **JWT Authentication** — access/refresh token rotation with Bearer scheme; access and refresh tokens are strictly typed (one can't be used as the other)
- 🚪 **Logout / Token Revocation** — Redis-backed blacklist; `/logout` and refresh-token rotation immediately invalidate the old token's `jti`
- ⚡ **Rate Limiting** — per-route and global rate limiting via `slowapi`
- 🗄️ **SQLAlchemy v2 Async** — async ORM with factory pattern (SQLite/PostgreSQL/MySQL)
- 📖 **Swagger UI** — interactive OpenAPI docs at `/docs` with Bearer Auth support
- 🛡️ **Global Error Handler** — RFC 7807 Problem Details responses, no traceback leaks
- 🔄 **API Versioning** — all routes prefixed with `/api/v1/`
- 📊 **Observability** — structured JSON logging with request-ID correlation; opt-in OpenTelemetry tracing (FastAPI + SQLAlchemy auto-instrumented, OTLP export, Jaeger UI via docker-compose)
- 🐳 **Docker** — multi-stage build with non-root user
- 🧪 **Tests** — unit tests (domain) + integration tests (full API stack with in-memory SQLite)

## Project Structure

```
app/
├── domain/                    # Pure domain — zero external dependencies
│   ├── entities/              # User, Product aggregate roots
│   ├── repositories/          # Abstract repository interfaces (ABC)
│   ├── common/result.py       # Ok[T] / Err[E] Result pattern
│   ├── exceptions.py          # DomainError, DomainErrorCode
│   ├── value_objects.py       # Email, Money, ProductName
│   └── events.py              # Domain events
├── application/               # Business orchestration
│   ├── dtos/                  # Data Transfer Objects
│   ├── services/              # Domain services (UserService, ProductService, AuthService)
│   └── facades/               # Application facades (UserFacade, ProductFacade, UserProductFacade)
├── infrastructure/            # External concerns
│   ├── database/              # SQLAlchemy models, async session factory
│   ├── repositories/          # SQLAlchemy implementations of repository interfaces
│   ├── security/              # JWT handler, bcrypt hasher, rate limiter
│   ├── dependencies.py        # FastAPI dependency injection wiring
│   └── error_handlers.py      # Global exception handler middleware
├── presentation/api/v1/       # HTTP layer
│   ├── routers/               # users.py, products.py
│   ├── schemas/               # Pydantic request/response schemas
│   └── auth_middleware.py     # Bearer token extraction dependency
├── config.py                  # Pydantic Settings
└── main.py                    # FastAPI app factory
tests/
├── unit/                      # Pure domain unit tests (no DB)
└── integration/               # Full API integration tests (in-memory SQLite)
```

## Quick Start

### Local Development

Requires a running Redis instance (used as the JWT revocation store for logout / refresh
rotation) — e.g. `brew install redis && redis-server` or `docker run -p 6379:6379 redis:7-alpine`.

```bash
# 1. Clone and install dependencies
pip install -r requirements-dev.txt

# 2. Copy environment file
cp .env.example .env

# 3. Run the application
# Applies pending Alembic migrations on startup (creates the schema on a fresh
# DB, applies only the delta on an existing one) — see "Database Migrations" below.
uvicorn app.main:app --reload

# 4. Open Swagger UI
# http://localhost:8000/docs
```

### Docker

```bash
docker compose up -d --build
```

### Database Migrations

Alembic is the single source of truth for schema changes — the app never calls
`Base.metadata.create_all()` itself. `alembic/versions/*.py` files are committed to
version control like any other source file.

```bash
# After changing a model, generate a migration for the diff
alembic revision --autogenerate -m "describe the change"

# Apply migrations manually (the app also does this automatically on startup —
# see app/main.py's lifespan — so this is mainly for CI/CD or manual ops)
alembic upgrade head
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html
```

### Code Quality

```bash
ruff check . --fix

# Static type checking (config: mypy.ini) — not full --strict, but every function
# must be typed and the checks must be internally consistent.
mypy
```

### Dependency Locking

`requirements.txt` and `requirements-dev.txt` are fully pinned, hash-locked files generated
from `requirements.in` / `requirements-dev.in` via [`uv`](https://github.com/astral-sh/uv) —
this is what CI and the Docker build install from, so builds are reproducible. To change a
dependency, edit the `.in` file, then regenerate:

```bash
pip install uv
uv pip compile requirements.in -o requirements.txt --generate-hashes
uv pip compile requirements-dev.in -o requirements-dev.txt --generate-hashes
```

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/users/register` | — | Register new user |
| POST | `/api/v1/users/login` | — | Login, get JWT tokens |
| POST | `/api/v1/users/refresh` | — | Refresh access token (rotates and revokes the old refresh token) |
| POST | `/api/v1/users/logout` | ✅ | Revoke the current access token (and refresh token, if supplied) |
| GET | `/api/v1/users/me` | ✅ | Get current user profile |
| PATCH | `/api/v1/users/me` | ✅ | Update current user profile |
| GET | `/api/v1/users/` | 🔑 Superuser | List all users |
| GET | `/api/v1/users/{id}` | 🔑 Superuser | Get user by ID |
| DELETE | `/api/v1/users/{id}` | 🔑 Superuser | Delete user |
| GET | `/api/v1/products/` | — | List all products |
| GET | `/api/v1/products/{id}` | — | Get product by ID |
| GET | `/api/v1/products/owner/{id}` | — | Get products by owner |
| POST | `/api/v1/products/` | ✅ | Create product |
| PATCH | `/api/v1/products/{id}` | ✅ Owner | Update product |
| DELETE | `/api/v1/products/{id}` | ✅ Owner | Delete product |
| GET | `/health` | — | Health check |

## Architecture Principles

1. **Domain layer** has zero external dependencies — no FastAPI, SQLAlchemy, or Pydantic imports
2. **All imports** use absolute paths anchored at `app` (e.g., `from app.domain.entities import User`)
3. **Business errors** return `Result[T, DomainError]` — never raise exceptions
4. **Technical errors** (500) are caught by `GlobalExceptionHandlerMiddleware`
5. **Controllers** call Application Facades only — never raw repositories or domain services directly
6. **Async all the way** — no sync DB calls or blocking I/O in async handlers
7. **Value Objects at the aggregate boundary** — `User.email: Email`, `User.hashed_password: Password`, `Product.name: ProductName`, `Product.price: Money`; primitives only cross the wire at the presentation schema, converted at the DTO boundary
8. **Domain events are dispatched, not just declared** — entity mutators (`update_profile`, `Product.update`, etc.) queue events; `IEventDispatcher` (application layer) / `LoggingEventDispatcher` (infrastructure) publish them after the repository call, logged as structured JSON. Note: this happens before the request's DB transaction commits (no outbox pattern) — see `app/infrastructure/observability/event_dispatcher.py` for the tradeoff
9. **List endpoints are capped** — `skip`/`limit` query params are bounded (`limit` 1-100) via `app/presentation/api/v1/pagination.py`, not raw unbounded ints

## Environment Variables

See `.env.example` for all available configuration options.

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./dev.db` | Database connection URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL — used as the JWT revocation store |
| `JWT_SECRET_KEY` | *(change me!)* | JWT signing secret |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token TTL |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token TTL |
| `RATE_LIMIT_PER_MINUTE` | `60` | Global rate limit |
| `ALLOWED_ORIGINS` | `["http://localhost:3000"]` | CORS origins. `["*"]` disables `allow_credentials` automatically (browsers reject that combination) |
| `OTEL_ENABLED` | `false` | Turn on OpenTelemetry tracing (FastAPI + SQLAlchemy spans, exported via OTLP) |
| `OTEL_SERVICE_NAME` | `fastapi-onion-ddd-template` | Service name attached to exported spans |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4318/v1/traces` | OTLP/HTTP collector endpoint. In `docker compose`, points at the bundled `jaeger` service (`http://jaeger:4318/v1/traces`) — view traces at `http://localhost:16686` |
| `DEBUG` | `false` | Enable SQL echo logging |

Every response also carries an `X-Request-ID` header (generated, or echoed back if the caller
sends one), and every log line is a JSON object tagged with that same `request_id` — plus
`trace_id`/`span_id` when `OTEL_ENABLED=true` — so a single request can be traced end-to-end
across logs and traces.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for local setup, required checks, and conventions.

## Security

See [SECURITY.md](SECURITY.md) for how to report a vulnerability.

## License

[MIT](LICENSE) — fill in the copyright holder in the `LICENSE` file before publishing.
