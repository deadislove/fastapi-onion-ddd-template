# Security Policy

## Supported Versions

This is a template repository — there are no numbered releases to track. Security fixes
are applied to the `main` branch only. If you've forked this template into a real
project, define your own supported-versions policy here.

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report vulnerabilities privately via one of:

- GitHub's [private vulnerability reporting](../../security/advisories/new) for this repository, or
- Email: **daweilin7689@gmail.com**

Please include:

- A description of the vulnerability and its potential impact
- Steps to reproduce (a minimal example is ideal)
- Any relevant logs, stack traces, or affected versions/commits

We aim to acknowledge reports within **3 business days**
and to keep you updated on remediation progress.

## Scope Notes for This Template

A few things worth knowing if you're auditing a fork of this template:

- JWT access/refresh tokens are strictly typed and revocable (Redis-backed blacklist,
  see `app/infrastructure/security/token_revocation.py`); refresh tokens rotate on use.
- Dependencies are pinned and hash-locked (`requirements.txt`); `pip-audit` and a Trivy
  image scan run in CI (`.github/workflows/ci.yml`).
- `JWT_SECRET_KEY` in `.env.example` is a placeholder — **always** set a strong, unique
  secret (`python -c "import secrets; print(secrets.token_hex(32))"`) outside of local dev.
- `ALLOWED_ORIGINS` defaults away from `"*"`; if you do set it to `"*"`, credentialed
  requests (cookies/Authorization headers) are automatically disabled — see `app/main.py`.
