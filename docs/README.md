# Documentation

Deep-dive technical docs for this template. If you just want to run the thing, see the root
[README](../README.md)'s Quick Start; if you want to contribute, see
[CONTRIBUTING.md](../CONTRIBUTING.md). These docs are for understanding *why* the codebase is
shaped the way it is, in enough detail to extend it confidently.

- **[Architecture](architecture.md)** — the onion layers, the dependency rule that enforces
  them, and where each DDD tactical pattern (aggregates, value objects, domain events,
  repositories, the Result pattern) actually lives in the code.
- **[Authentication](authentication.md)** — JWT access/refresh token lifecycle, why tokens are
  strictly typed, Redis-backed revocation, refresh rotation, with a sequence diagram.
- **[Error Handling](error-handling.md)** — the `DomainError` → `HTTPException` → RFC 7807
  translation pipeline, and a real bug it fixed along the way.
- **[Observability](observability.md)** — structured JSON logging, request-ID correlation,
  domain events as logs, and opt-in OpenTelemetry tracing.
- **[Database](database.md)** — schema, the migration-only-no-`create_all` workflow, and why
  money is `Decimal`/`Numeric` rather than `float`.
- **[CI/CD & Supply Chain](ci-cd.md)** — what each CI job checks, dependency locking, and why
  every GitHub Action that's been bumped is pinned by commit SHA rather than a version tag
  (this repo lived through the `trivy-action` supply-chain compromise firsthand).

## Reading Order

If you're new to this codebase, `architecture.md` first — everything else assumes you know
the layer boundaries and where `Result`/Value Objects/Domain Events fit. After that, the rest
are independent; read whichever matches what you're touching.
