# CI/CD & Supply Chain

Five independent jobs in `.github/workflows/ci.yml`, run on every push to `main` and every
PR. This document covers what each checks, how dependencies are locked, and — at some length,
because it's a real incident this repo lived through — why every third-party GitHub Action
here is pinned by commit SHA instead of a version tag.

## CI Jobs

| Job | What it runs | Fails the build on |
|---|---|---|
| `lint` | `ruff check .` | Any lint violation |
| `typecheck` | `mypy` (config: `mypy.ini`) | Any type error |
| `test` | `pytest --cov=app` | Any test failure |
| `dependency-audit` | `pip-audit -r requirements.txt` | Any known CVE in a *locked* dependency |
| `docker-build` | Build the runtime image, scan it with Trivy | Build failure only — Trivy is report-only (see below) |

`test` also uploads `coverage.xml` as a build artifact (14-day retention) — there's no
enforced coverage threshold gate yet; that's a reasonable next addition if you want one.

`dependency-audit` runs `pip-audit` against `requirements.txt` — the **locked, hash-pinned**
file, not `requirements.in`. This matters: it verifies the exact versions that actually ship,
not just what the loose `.in` constraints would technically allow.

`docker-build`'s Trivy scan uses `exit-code: "0"` (report-only) by default, uploading results
to the GitHub Security tab via SARIF rather than failing the build — so a fresh fork isn't red
on day one because of an upstream base-image CVE nobody's triaged yet. Flip it to `"1"` once
you're actually tracking findings.

## Dependency Locking

`requirements.txt` / `requirements-dev.txt` are fully pinned and hash-locked, generated from
`requirements.in` / `requirements-dev.in` via [`uv`](https://github.com/astral-sh/uv):

```bash
pip install uv
uv pip compile requirements.in -o requirements.txt --generate-hashes
uv pip compile requirements-dev.in -o requirements-dev.txt --generate-hashes
```

Edit the `.in` files; never hand-edit the generated `.txt` files. This is what both CI and the
Docker build install from, so a build today and a build in six months resolve to the exact
same bytes — `pip-tools` was tried first but is currently broken against modern `pip`
(internal API mismatch), so `uv` is what this template uses instead.

## Why Every Third-Party Action Is Pinned by SHA

On 2026-03-19, `aquasecurity/trivy-action` — the exact Trivy scanning action this workflow
uses — was compromised. An attacker with stolen maintainer credentials force-pushed 76 of 77
existing version tags (covering `0.0.1` through `0.34.2`) to malicious commits containing a
credential-stealing payload that read GitHub Actions runner memory and exfiltrated secrets to
an attacker-controlled domain. The exposure window was roughly 12 hours before it was caught.
See [GHSA-69fq-xp46-6x23](https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23)
for the full writeup.

This is precisely the failure mode that pinning-by-tag doesn't protect against — `@0.24.0` and
`@v3` both look stable, but a *tag* is just a mutable pointer someone with write access (or
stolen credentials) can force-push to point somewhere else entirely, silently. A commit SHA
can't be redefined; `owner/repo@<sha>` always means the same bytes.

**What this repo does about it**: every Action reference that has ever needed a version bump
in `docker-build` is pinned by full commit SHA, with the human-readable version kept as a
trailing comment:

```yaml
uses: aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25 # v0.36.0
```

Every SHA in this workflow was verified independently through the GitHub API before being
committed — not by trusting a single scraped release page. That distinction isn't
theoretical: while researching one of these bumps, a page-summarization tool fabricated a
plausible-looking but entirely wrong commit SHA; it was only caught because the real SHA was
independently cross-checked against the API directly, as described below.

```bash
# 1. Resolve the tag to an object
curl -s https://api.github.com/repos/<owner>/<repo>/git/refs/tags/<tag>
# 2. If it's an annotated tag (type: "tag"), dereference it to the underlying commit
curl -s https://api.github.com/repos/<owner>/<repo>/git/tags/<object-sha>
# 3. Confirm the commit itself is GPG-verified and authored by someone plausible
curl -s https://api.github.com/repos/<owner>/<repo>/commits/<commit-sha>
```

### The Verification Method

Concretely, for each Action bump in this repo's history:

1. Check whether the target repo has ever had a security incident (web search + the repo's
   own `SECURITY.md`/advisories page).
2. Read the actual release notes / changelog for breaking changes between the current and
   target version — not just "is it a major version bump," but whether the specific inputs
   *this workflow* uses are affected.
3. Resolve tag → commit via the GitHub API (never trust a single scraped/summarized page for
   a hex string — verify it independently, as above).
4. Confirm the commit is GPG-verified (`"verification": {"verified": true}`) and the author
   is a plausible maintainer, not an anonymous/fresh account.

This is also why `actions/checkout`, `actions/setup-python`, and `docker/build-push-action`
in this workflow are *not* SHA-pinned — they're first-party (`actions/`, `docker/`) with no
compromise history, and floating major-version tags for those are a defensible risk/ergonomics
tradeoff. If you want maximal consistency, pin those too; nothing about the setup requires it.

## Dependabot

`.github/dependabot.yml` covers three ecosystems, weekly:

- `pip` — opens PRs bumping the pinned `requirements*.txt` directly (the generated files, not
  just the loose `.in` constraints).
- `github-actions` — opens PRs bumping Action versions, including for the SHA-pinned ones
  above (Dependabot understands SHA pins and updates them correctly, keeping the version
  comment in sync).
- `docker` — bumps the base image in the `Dockerfile`.

**Every Dependabot PR that touches a GitHub Action should go through the verification method
above before merging** — Dependabot correctly identifies that a newer version exists, but it
doesn't (and can't) tell you whether that version's tag history is trustworthy.

## Adding a New CI Check

Add a job to `.github/workflows/ci.yml` following the existing pattern (`actions/checkout`,
`actions/setup-python`, `pip install -r requirements-dev.txt`, then the check itself). If it
needs a new dev dependency, add it to `requirements-dev.in` and regenerate the lockfile — see
[Dependency Locking](#dependency-locking) above.
