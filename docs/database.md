# Database

SQLAlchemy 2.0 async ORM, Alembic migrations, SQLite for local dev / PostgreSQL for
docker-compose and production. This document covers the schema, the migration workflow, and
why money is stored as `Numeric` rather than `Float`.

## Schema

Two tables, defined in `app/infrastructure/database/models.py`:

```
users                          products
──────────────────             ──────────────────
id            PK                id            PK
email         unique, indexed   name          indexed
hashed_password                 description
full_name                       price         Numeric(12, 2)
is_active                       stock
is_superuser                    is_active
created_at                      owner_id      FK -> users.id, ON DELETE CASCADE
updated_at                      created_at
                                 updated_at
```

`products.owner_id` cascades on delete — deleting a user deletes their products. The
`UserModel.products` relationship uses `lazy="selectin"`, so loading a user issues one extra
`SELECT ... WHERE owner_id IN (...)` to eager-load their products rather than N+1 lazy loads.

These are **ORM models**, distinct from the domain entities in `app/domain/entities/`. The
repository layer (`app/infrastructure/repositories/*.py`) is what converts between them — see
[architecture.md](architecture.md#repository-interfaces).

## Migrations Are the Only Way Schema Changes Happen

The app **never** calls `Base.metadata.create_all()`. Every schema change — including the
very first table creation on a brand-new database — goes through Alembic:

```python
# app/main.py, called from the lifespan on every startup
def _run_migrations() -> None:
    alembic_cfg = Config(str(_PROJECT_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(_PROJECT_ROOT / "alembic"))
    command.upgrade(alembic_cfg, "head")
```

`alembic upgrade head` is idempotent by construction: on an empty database it applies every
migration from scratch (equivalent to a fresh create); on a database that's already partway
there, it applies only the pending delta; on a database already at `head`, it's a no-op. This
is why the app can safely run it on *every* boot rather than needing separate "first deploy"
vs. "subsequent deploy" logic.

`docker-compose.yml` also runs a dedicated one-shot `migrate` service before `api` starts
(`depends_on: migrate: condition: service_completed_successfully`) — the app's own
startup-time migration call is a second, harmless, idempotent safety net on top of that (e.g.
for a bare `uvicorn app.main:app --reload` run without docker-compose).

`alembic/versions/*.py` files are committed to version control like any other source file —
they are not a build artifact and not gitignored.

### Adding a Migration

```bash
# 1. Change a model in app/infrastructure/database/models.py
# 2. Generate the migration
alembic revision --autogenerate -m "describe the change"
# 3. Read the generated file — autogenerate is a good first draft, not infallible
#    (it won't detect every kind of change, e.g. some check constraints)
# 4. Commit the migration file alongside the model change, same PR
```

`alembic/env.py` is already configured for SQLite-safe batch mode
(`render_as_batch=True`) — SQLite can't `ALTER COLUMN` directly, so Alembic rewrites the table
under the hood; this is transparent as long as autogenerate is used rather than hand-written
`op.alter_column()` calls for SQLite targets.

### Existing Migrations

| Revision | What it does |
|---|---|
| `abbd58b1d7c9` | Baseline: creates `users` and `products` |
| `decf20fd6710` | Changes `products.price` from `Float` to `Numeric(12, 2)` |

The second one is a real example worth reading if you're about to write your own
type-changing migration — it's a two-line `batch_alter_table` / `alter_column` diff,
auto-generated correctly by comparing the model to the live schema.

## Why `Decimal`, Not `Float`

`products.price` is `Numeric(12, 2)` in the database and `Decimal` in the domain
(`Money.amount` — see [architecture.md](architecture.md#value-objects)), end to end. This
wasn't the original design — an early version used `Float`/`float`, which has a real,
demonstrable bug:

```pycon
>>> 0.1 + 0.2
0.30000000000000004
```

That's binary floating-point being unable to represent most base-10 fractions exactly.
Accumulate enough of that drift across price updates and stock calculations and a monetary
value stops matching what was actually charged. `Decimal` is exact for base-10 values, which
is exactly what currency is.

`Money.create()` (`app/domain/value_objects.py`) is deliberate about *how* it converts to
`Decimal`, too:

```python
decimal_amount = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

Constructing `Decimal` directly from a `float` (`Decimal(99.99)`) would capture that float's
*own* binary imprecision — `Decimal(99.99)` is actually
`Decimal('99.9899999999999948419078...')`. Routing through `str(amount)` first captures
Python's shortest round-trip decimal representation instead, which is what a client's JSON
`99.99` actually meant.

The **wire format is unchanged** — `CreateProductRequest.price` and `ProductResponse.price`
are still plain `float` in the Pydantic schemas, converted at the DTO boundary
(`ProductDTO.from_entity`: `price=float(product.price.amount)`). This was a deliberate
compatibility choice: fix the internal representation (where the actual precision bug lived)
without changing the public API's JSON shape.

## Session Management

`get_db_session()` (`app/infrastructure/database/session.py`) is the FastAPI dependency every
repository ultimately gets its `AsyncSession` from: it commits on success, rolls back on any
exception, and always closes the session — a route handler never has to think about
transaction boundaries.

```python
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

One consequence worth knowing: the commit happens **after** the router returns its response
model, which is also after domain events for that request have already been published (see
[architecture.md](architecture.md#domain-events)'s note on the outbox-pattern tradeoff).

## Supported Databases

`_build_engine()` picks connection settings based on the `DATABASE_URL` scheme:

- `sqlite+aiosqlite://` — local dev default, `check_same_thread=False` for async use, no
  connection pool tuning (SQLite doesn't have one in the same sense).
- `postgresql+asyncpg://` / `mysql+aiomysql://` / others — `pool_pre_ping=True` (detects and
  replaces dead connections), `pool_size=10`, `max_overflow=20`.

`docker-compose.yml` runs PostgreSQL 15; switching to MySQL means changing `DATABASE_URL` and
the `pymysql`/`aiomysql` driver already being in `requirements.txt`.
