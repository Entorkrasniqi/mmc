# CI/CD and release protocol

**Status:** Proposed; the first stage already exists in `.github/workflows/ci.yml`.

## Principle

The default branch is always releasable. A change merges only when automated checks, which are the same ones anyone can run locally, pass and a person has reviewed it.

## Pipeline stages

| Stage | Checks | State |
| --- | --- | --- |
| 1. Static | lint (`flake8`, 125 cols), type check (add `mypy` or `pyright` for the ontology package), `ruff`/`eslint` and `tsc` for the dashboard | lint exists |
| 2. Generated files fresh | `minisat gen-xtce --check`; any other generated file | exists |
| 3. Unit and component tests | `pytest` on Python 3.10-3.13; dashboard unit tests | Python exists |
| 4. Database tests | PostgreSQL service container; migrations applied from empty and from the previous release | not yet |
| 5. Schema validation | XTCE 1.2 XSD check | exists (needs network or a local XSD) |
| 6. Security | `pip-audit`, `npm audit`, secret scan, licence check | not yet |
| 7. Build | Docker images for backend and dashboard; `docker compose config` validates | not yet |
| 8. Integration | `docker compose up` in CI, run a short scripted scenario, check for the expected alarm and command lifecycle | not yet |
| 9. Agent evals | hard-gate subset of [agent-evaluation.md](agent-evaluation.md) | not yet |
| 10. Nightly | mutation check, full agent eval, long soak run | not yet |

Stages 1-8 gate merges. Stage 9 gates merges that touch the agent, its prompts or tools. Stage 10 reports.

## Branches and reviews

- Work on short-lived branches; merge by pull request.
- Branch protection on `main`: required checks, at least one human review, no direct pushes, no force-push.
- A pull request states what changed, why, how it was verified (with the evidence level from [testing-and-verification.md](testing-and-verification.md)) and which parts were AI-drafted when relevant.
- Commit messages: imperative, one logical change each.

## Database changes

- Migrations are versioned files (for example Alembic), applied by the `migrator` role only.
- Forward-only in production; each migration has a tested path from the previous release.
- Destructive changes (drop, rename) need an explicit data plan in the pull request.

## Containers

- One image per service: backend (API and runner), worker (ingestion and automations), simulator, dashboard.
- Multi-stage builds, non-root user, pinned base image, no secrets in layers, health check defined.
- `docker compose up` brings up the full stack on a clean machine. Compose files separate `dev` from a hardened default.

## Versioning and releases

- Semantic versioning. Pre-1.0 while the Yamcs path is unverified.
- A `CHANGELOG.md` in the "Keep a Changelog" style, updated in the pull request.
- A release is a tag plus built images; the notes list known limits (carry over the README's "honest limits").
- Rollback: redeploy the previous image; database rollback only by a prepared down-migration or restore, never improvised.

## Optional extras

These are separate, deliberate additions, not prerequisites:

- **Jenkins:** a `Jenkinsfile` that runs the same stages, so the pipeline is defined once in terms of commands (`make ci` or equivalent) and both GitHub Actions and Jenkins call it. Do not maintain two different definitions of "passing".
- **Kubernetes:** manifests or a Helm chart for a local cluster (kind or minikube): Deployments for stateless services, a StatefulSet (or an operator) for PostgreSQL, ConfigMaps and Secrets, readiness and liveness probes tied to the health endpoints in [observability-and-operations.md](observability-and-operations.md), NetworkPolicies so only the backend reaches the database and the TC port. Add only after the Compose setup is stable.

## Enforcement

Branch protection and required checks are repository settings and are not visible in the code; record in the pull request template or `CONTRIBUTING.md` when they are turned on.
