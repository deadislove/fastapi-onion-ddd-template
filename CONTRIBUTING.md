# Contributing

Thanks for considering a contribution. This is a template repository, so contributions
here mainly improve the template itself (architecture, tooling, docs) — not a specific
product's features.

## Getting Started

1. Fork and clone the repo.
2. Start a local Redis instance (used as the JWT revocation store):
   `brew install redis && redis-server` or `docker run -p 6379:6379 redis:7-alpine`.
3. Install dependencies and pre-commit-equivalent tooling:
   ```bash
   pip install -r requirements-dev.txt
   cp .env.example .env
   ```
4. Run the app: `uvicorn app.main:app --reload` (applies pending Alembic migrations
   automatically — see the README's "Database Migrations" section).

## Before Opening a Pull Request

CI (`.github/workflows/ci.yml`) runs four required checks; run them locally first so
review cycles aren't spent on things a machine can catch:

```bash
ruff check . --fix     # lint
mypy                    # static types (config: mypy.ini)
pytest --cov=app        # tests — add tests for new behavior, don't just patch the bug
pip-audit -r requirements.txt   # dependency vulnerabilities
```

A fifth CI job builds the Docker image and scans it with Trivy — no local step needed
unless you changed the `Dockerfile`.

## Conventions

- **Architecture**: respect the onion boundaries — `domain/` has zero external
  dependencies (no FastAPI/SQLAlchemy/Pydantic imports); `application/` orchestrates but
  doesn't touch ORM/HTTP directly; `infrastructure/` and `presentation/` are the only
  layers allowed to import third-party frameworks. See the README's "Architecture
  Principles" section.
- **Errors**: business errors return `Result[T, DomainError]` (see
  `app/domain/common/result.py`) — don't raise exceptions for expected failure cases.
  Reserve real exceptions for programmer errors / genuinely unexpected states.
- **Value Objects**: if you add a field with a real invariant (format, range, non-empty),
  give it a Value Object in `app/domain/value_objects.py` rather than validating loosely
  scattered `str`/`float` fields — see `Email`, `Money`, `ProductName` for the pattern.
- **Domain Events**: if an aggregate mutation is meaningful to the rest of the system,
  queue an event (see `User.update_profile()` / `Product.update()`) rather than adding
  silent side effects — but only from entity methods called *after* the entity has a
  real ID (see `mark_created()`/`mark_registered()` and the comments in
  `app/application/services/user_service.py` for why).
- **Dependencies**: edit `requirements.in` / `requirements-dev.in`, then regenerate the
  locked, hashed `requirements*.txt` with `uv` — see the README's "Dependency Locking"
  section. Don't hand-edit the generated `.txt` files.
- **Migrations**: after changing a SQLAlchemy model, run
  `alembic revision --autogenerate -m "..."` and commit the generated file under
  `alembic/versions/`. Never rely on `Base.metadata.create_all()`.

## Commit Messages & PRs

- Keep commits scoped to one logical change; a short imperative subject line
  (`Fix refresh token rotation`, not `fixed stuff`) is enough — this isn't a project that
  enforces Conventional Commits or similar.
- Describe *why* in the PR description if it isn't obvious from the diff.
- Link the issue being fixed, if any.

## Reporting Bugs vs. Security Issues

Regular bugs: open a GitHub issue. Security vulnerabilities: **do not** open a public
issue — see [SECURITY.md](SECURITY.md) instead.
