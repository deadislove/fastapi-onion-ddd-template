# Architecture

This template implements **Onion Architecture** (also called Ports & Adapters / Hexagonal
Architecture) with **Domain-Driven Design** tactical patterns. This document explains the
layers, the dependency rule that keeps them honest, and how each DDD pattern is actually
implemented in this codebase — not just named.

## The Onion

```
┌─────────────────────────────────────────────────────────────────┐
│  Presentation        FastAPI routers, Pydantic schemas, auth     │
│  (app/presentation)  middleware — HTTP-shaped things live here   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Infrastructure     SQLAlchemy models/repos, JWT, Redis,   │  │
│  │  (app/infrastructure) logging/tracing, DI wiring           │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │  Application      Services, Facades, DTOs — orches-  │  │  │
│  │  │  (app/application)  trates domain + infra ports       │  │  │
│  │  │  ┌───────────────────────────────────────────────┐  │  │  │
│  │  │  │  Domain         Entities, Value Objects,       │  │  │  │
│  │  │  │  (app/domain)     Events, Result, repository    │  │  │  │
│  │  │  │                   interfaces — zero deps        │  │  │  │
│  │  │  └───────────────────────────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## The Dependency Rule

**Dependencies point inward, always.** Domain knows nothing about Application; Application
knows nothing about Infrastructure or Presentation. Concretely:

- `app/domain/**` has **zero imports** from FastAPI, SQLAlchemy, Pydantic, or any other
  third-party framework. Run `grep -rE "^(from|import) (fastapi|sqlalchemy|pydantic)" app/domain`
  — it should return nothing, ever. If a PR adds one of those imports to `app/domain`, that's
  a layering violation, not a style nit.
- `app/application/**` orchestrates domain objects and defines the *interfaces* infrastructure
  must implement (`IPasswordHasher`, `ITokenService`, `ITokenRevocationStore`,
  `IEventDispatcher` — see `app/application/services/*.py`), but never imports SQLAlchemy,
  Redis clients, or FastAPI request/response types directly.
- `app/infrastructure/**` is the only layer allowed to know about SQLAlchemy, Redis, JWT
  libraries, and OpenTelemetry. It implements the interfaces application defines.
- `app/presentation/**` is the only layer allowed to know about FastAPI/Pydantic request and
  response shapes. Routers call **facades only** — never repositories or domain services
  directly (see `app/presentation/api/v1/routers/*.py`).

This is what makes the domain layer's unit tests (`tests/unit/`) run with no database, no
Redis, and no HTTP client — they import `app.domain.*` and nothing else.

## Request Flow

A typical mutating request (e.g. `POST /api/v1/products/`) flows through every layer exactly
once, in one direction:

```
Router (presentation)
  -> validates the body against a Pydantic schema (CreateProductRequest)
  -> builds an application DTO (CreateProductDTO) from it
  -> calls a Facade method
       Facade (application)
         -> calls a Service method
              Service (application)
                -> calls a Repository interface method (domain-defined, infra-implemented)
                     Repository (infrastructure)
                       -> maps the domain entity to/from a SQLAlchemy model
                       -> talks to Postgres/SQLite
                -> constructs/mutates a domain Entity (app/domain/entities/*.py),
                   which validates itself via Value Objects and returns Result[T, DomainError]
                -> publishes any queued Domain Events via IEventDispatcher
         -> maps the resulting Entity back to an outbound DTO (ProductDTO.from_entity)
  -> maps the DTO to a Pydantic response schema (ProductResponse) and returns it
```

Every fallible step returns `Result[T, DomainError]` instead of raising — the router is the
first (and only) place a `DomainError` gets translated into an HTTP status code
(`_domain_error_to_http()` in each router). See [error-handling.md](error-handling.md).

## DDD Tactical Patterns, and Where They Actually Live

A lot of "DDD" templates declare these patterns in name only. Here's what's real in this one,
verifiable by reading the linked file.

### Aggregate Roots

`User` (`app/domain/entities/user.py`) and `Product` (`app/domain/entities/product.py`) are
the two aggregate roots. Both are plain `@dataclass` — no ORM base class, no framework
decorators. They:

- Validate their own invariants at construction via `.create()` classmethods, which return
  `Result[Self, DomainError]` rather than raising.
- Mutate themselves through named methods (`update_profile()`, `Product.update()`,
  `reduce_stock()`) rather than exposing public setters — a caller can't put a `Product` into
  an invalid state (negative stock, empty name) because there's no way to set `stock`/`name`
  except through a method that validates first.
- Queue domain events on meaningful mutations (see below).

### Value Objects

`app/domain/value_objects.py` defines four: `Email`, `Password`, `ProductName`, `Money`.
These aren't decorative — the aggregates actually hold them as field types:

```python
# app/domain/entities/user.py
email: Email
hashed_password: Password

# app/domain/entities/product.py
name: ProductName
price: Money
```

This means an invalid `User`/`Product` **cannot exist in memory** — `Email.create()` validates
format, `Money.create()` rejects negative amounts and normalizes to a 2-decimal-place
`Decimal` (never `float` — see [database.md](database.md#why-decimal-not-float) for why that
matters for money specifically). Primitives only cross the boundary at the very edges:
Pydantic schemas in `app/presentation/api/v1/schemas/*.py` take/return `str`/`float`, and the
DTO layer (`app/application/dtos/*.py`) converts (`str(product.name)`, `float(product.price.amount)`)
when mapping an entity to an outbound DTO.

### Domain Events

`app/domain/events.py` declares six events (`UserRegisteredEvent`, `UserUpdatedEvent`,
`UserDeletedEvent`, `ProductCreatedEvent`, `ProductUpdatedEvent`, `ProductDeletedEvent`), and
they're genuinely dispatched, not just declared and left empty:

1. An entity mutator method appends an event to its own `_domain_events` list
   (e.g. `Product.update()` appends `ProductUpdatedEvent`).
2. For **creation** specifically, the event can't be queued inside `.create()` — the entity's
   `id` is `None` until the database assigns one. Instead, the repository calls
   `entity.mark_created()` / `entity.mark_registered()` immediately after the INSERT is
   flushed and the entity has a real ID (see `SQLAlchemyProductRepository.create()` in
   `app/infrastructure/repositories/product_repository.py`).
3. A service (`UserService`/`ProductService` in `app/application/services/*.py`) calls
   `entity.collect_events()` after a successful repository call and publishes them through
   `IEventDispatcher.publish_all()`.
4. `IEventDispatcher` (`app/application/services/event_dispatcher.py`) is the application-layer
   interface; `LoggingEventDispatcher` (`app/infrastructure/observability/event_dispatcher.py`)
   is the concrete implementation — it publishes each event as one structured JSON log line.
   Swapping this for a Redis stream / Kafka topic / outbox table later means writing a new
   class that implements `IEventDispatcher`, with **no changes to any entity or service**.

**Known limitation, documented rather than hidden**: events are published *before* the
request's database transaction commits (see `app/infrastructure/database/session.py`'s
`get_db_session`), because the current session-per-request design commits only after the
router returns. If the transaction later rolled back, the event would still have been
"published." A production system with stronger delivery guarantees would use a transactional
outbox instead. This is called out again in
`app/infrastructure/observability/event_dispatcher.py`'s module docstring.

### Repository Interfaces

`app/domain/repositories/{user_repository,product_repository}.py` define abstract `ABC`
classes (`IUserRepository`, `IProductRepository`) with no SQLAlchemy in sight — just
domain-typed method signatures. `app/infrastructure/repositories/*.py` implements them against
SQLAlchemy 2.0's async API, converting between ORM models and domain entities in `_to_entity`/
`_to_model` functions. Application services depend on the *interface*, and
`app/infrastructure/dependencies.py` wires the concrete implementation in via FastAPI's `Depends`.

### Result Pattern

`app/domain/common/result.py` implements `Ok[T]` / `Err[E]` as a `Result = Ok[T] | Err[E]`
union, used everywhere a domain or application operation can fail expectedly (not found,
validation error, already exists). `Ok.unwrap_err()` and `Err.unwrap()` are typed `NoReturn`
(they always raise) rather than `-> None` — this isn't cosmetic, it's what lets `mypy` narrow
`result.unwrap()` on the union type to just `T` instead of `T | None` at every call site; see
the comment at the top of `result.py` if you're wondering why that matters.

Business errors (user not found, insufficient stock, invalid credentials) flow through
`Result`, never through `raise`. Genuine exceptions (an entity's `assert self.id is not None`
in `mark_created()`) signal a programmer error — a repository calling a method it shouldn't —
not an expected business outcome.

## Facades vs. Services

Two layers of application-layer orchestration exist for a reason:

- **Services** (`UserService`, `ProductService`) hold single-aggregate business rules and talk
  to exactly one repository (plus the event dispatcher). `AuthService` holds authentication
  workflow logic (hashing, token issuance/validation, revocation).
- **Facades** (`UserFacade`, `ProductFacade`, `UserProductFacade`) are what routers actually
  call. They orchestrate one or more services, map DTOs, and handle cross-aggregate workflows
  that don't belong to a single entity's service — e.g. `UserProductFacade.create_product_for_user()`
  verifies the user exists (via `UserFacade`) before delegating to `ProductFacade`.

Routers never skip the facade to call a service or repository directly — see architecture
principle 5 in the root [README](../README.md#architecture-principles).
