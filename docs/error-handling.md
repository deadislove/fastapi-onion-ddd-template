# Error Handling

Every error response — validation failures, business rule violations, unhandled crashes,
rate limiting — is formatted as [RFC 7807 Problem Details](https://www.rfc-editor.org/rfc/rfc7807),
correlated with the request that caused it. This document explains the two-stage translation
(`DomainError` → `HTTPException` → RFC 7807 JSON) and where each stage lives.

## The Shape

Every error response body looks like this:

```json
{
  "type": "https://httpstatuses.com/404",
  "title": "Not Found",
  "status": 404,
  "detail": "Product '99999' was not found.",
  "instance": "/api/v1/products/99999",
  "request_id": "b2fde987-5f62-412c-a86d-568b858753e3"
}
```

- `detail` is always the **specific** message, not a generic placeholder — see
  [Pitfall](#pitfall-generic-vs-specific-detail) below for why that's worth calling out.
- `request_id` matches the `X-Request-ID` response header and every structured log line for
  this request — see [observability.md](observability.md#request-id-correlation).

## Stage 1: Domain Errors

Business/validation failures never `raise` inside the domain or application layers — they
return `Result[T, DomainError]` (see [architecture.md](architecture.md#result-pattern)).
`DomainError` (`app/domain/exceptions.py`) pairs a `DomainErrorCode` (a `StrEnum`) with a
human-readable message and an optional `details` dict:

```python
DomainError.product_not_found(99999)
# DomainError(code=PRODUCT_NOT_FOUND, message="Product '99999' was not found.",
#             details={"identifier": "99999"})
```

## Stage 2: DomainError → HTTPException

Each router owns a `_domain_error_to_http()` function mapping `DomainErrorCode` to an HTTP
status code, then raises a plain `fastapi.HTTPException(status_code=..., detail=error.message)`.
This mapping is **per-router** (in `app/presentation/api/v1/routers/{users,products}.py`)
because the same generic code can mean different things depending on context — e.g.
`DomainErrorCode.NOT_FOUND` maps to 404 in both, but `products.py` additionally maps
`INSUFFICIENT_STOCK` to 400, which is meaningless in `users.py`.

| `DomainErrorCode` | HTTP status |
|---|---|
| `USER_NOT_FOUND`, `PRODUCT_NOT_FOUND`, `NOT_FOUND` | 404 |
| `USER_ALREADY_EXISTS`, `PRODUCT_ALREADY_EXISTS`, `ALREADY_EXISTS` | 409 |
| `INVALID_CREDENTIALS`, `INVALID_TOKEN`, `TOKEN_EXPIRED`, `TOKEN_REVOKED`, `UNAUTHORIZED` | 401 |
| `FORBIDDEN` | 403 |
| `VALIDATION_ERROR`, `INSUFFICIENT_STOCK` | 400 |
| *(unmapped codes)* | 400 (default) |

## Stage 3: HTTPException → RFC 7807 JSON

This is the part worth reading carefully if you're touching `app/infrastructure/error_handlers.py`.

A single handler, registered for `starlette.exceptions.HTTPException` (the base class
`fastapi.HTTPException` inherits from), catches **every** `HTTPException` raised anywhere in
the app — not just the ones the routers raise deliberately, but also the ones Starlette raises
internally for unmatched routes (404) and disallowed methods (405):

```python
# app/infrastructure/error_handlers.py
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_problem_detail(
            status=exc.status_code,
            title=_status_title(exc.status_code),   # http.HTTPStatus(code).phrase
            detail=str(exc.detail),
            instance=request.url.path,
        ),
        headers=exc.headers,
    )
```

Registering by **class** rather than by individual status code is the key design choice here
— see the pitfall below for what goes wrong with the more obvious-looking alternative.

Two more handlers cover cases that aren't `HTTPException`:

- `RateLimitExceeded` (raised by `slowapi` when a route's rate limit is hit) → `429`.
- Anything else — a genuinely unhandled exception, a bug — is caught by
  `GlobalExceptionHandlerMiddleware`, logged at `ERROR` with a full traceback
  (`exc_info=True`), and returned as a generic `500` **without the traceback**, so internal
  errors never leak implementation details to a client.

### Pitfall: Generic vs. Specific `detail`

An earlier version of this handler registered separate `@app.exception_handler(404)` and
`@app.exception_handler(405)` functions. Those intercept **every** `HTTPException` with that
exact status code — including ones application code raises on purpose, not just Starlette's
own routing errors. The bug: those handlers ignored `exc.detail` entirely and always returned
a generic message like `"The requested resource '{path}' was not found."`, silently discarding
the actually-useful message a `DomainError` had produced (e.g. `"Product '99999' was not
found."`). The current single-handler-by-class design fixes this by always using
`str(exc.detail)` — and as a side effect, also means 400/401/403/409 (which previously had no
registered handler at all and fell through to FastAPI's bare `{"detail": "..."}` default) now
get the same RFC 7807 treatment as 404/405 always accidentally had.

## What's *Not* Reformatted, On Purpose

`422 Unprocessable Entity` — Pydantic request validation errors (a malformed email, a
password under the minimum length) — is deliberately left in FastAPI's own format:

```json
{
  "detail": [
    {"type": "value_error", "loc": ["body", "email"], "msg": "value is not a valid email address...", ...}
  ]
}
```

This is a field-level, structured array — more useful to a client than collapsing it into a
single RFC 7807 `detail` string would be. If you want 422s reformatted too, that's a
deliberate scope decision to revisit, not an oversight.

## Extending the Error Catalog

Adding a new business error is a three-step, single-direction change:

1. Add a `DomainErrorCode` member and a `DomainError.your_error(...)` classmethod
   (`app/domain/exceptions.py`).
2. Return `Err(DomainError.your_error(...))` from wherever the business rule lives
   (an entity method, a service method).
3. Add the code → status mapping in the relevant router's `_domain_error_to_http()`.

No changes needed in `error_handlers.py` — the RFC 7807 formatting is automatic for any
`HTTPException`, regardless of what `DomainErrorCode` produced it.
