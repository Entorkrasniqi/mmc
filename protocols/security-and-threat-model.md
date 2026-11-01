# Security and threat model

**Status:** Proposed. This is a learning project with a fictional satellite, but it models a safety-relevant control system, so it is worth modelling threats properly. Not a security audit.

## Assets

1. The ability to command the spacecraft (even a simulated one).
2. Integrity of telemetry and of the operations record (alarms, command history, audit).
3. Operator identities and roles.
4. Secrets: database passwords, model API keys, tokens.

## Trust boundaries

```
 browser (operator) --HTTPS/HTTP--> API ----> action runner ----> PostgreSQL
                                     |             |
 AI agent (model provider) <-tools---+             +--outbox--> UDP link --> spacecraft / simulator
                                                                      ^
 telemetry (UDP) -------------------------------> ingestion ---------+ (data in, untrusted)
```

Everything crossing a boundary is untrusted until validated: browser input, model output, UDP datagrams, imported contact data, operator free text.

## Threats

| # | Threat | Where | Mitigation | State |
| --- | --- | --- | --- | --- |
| 1 | Anyone who can reach the TC UDP port can command the spacecraft | link | bind to `127.0.0.1`; in Compose, an internal network only; roadmap M5 (CRC) and M10 (message authentication) | Documented limit in README; not fixed |
| 2 | Forged or garbled telemetry accepted | ingestion | strict decode (length, APID, type checks, already in `codec.py`); count rejects; sequence-gap detection (M3) | Partly enforced |
| 3 | Unauthorised user runs an action | CLI, API | authenticate every request; role check in the runner; negative tests | Role check enforced (`tests/db/test_runner.py`, and over HTTP `tests/api/test_api_auth.py`: every route needs a token, the exact role matrix per action, one audit row per refusal). **Authentication over HTTP is a DEV-ONLY static token per operator** (no expiry, no revocation, localhost only: the API refuses another address). `minisat act` still trusts the operator name it is given, and so does anything else that calls the runner directly |
| 4 | Write path that bypasses the runner | database | separate DB roles; the reader and ingest roles cannot write operations tables; exact privilege matrix test | Enforced in the database (`tests/db/test_privileges.py`) |
| 5 | Audit trail altered | database | no UPDATE/DELETE grants, plus a trigger that also refuses the owner and superusers; optional hash chain later | Enforced (trigger and grants); hash chain not done |
| 6 | Prompt injection through notes, labels, imported data | agent | data/instruction separation; propose-only; evals ([agent-safety-and-autonomy.md](agent-safety-and-autonomy.md)) | Not yet |
| 7 | Agent exceeds its role (excessive agency) | agent | role has no approve/release; tools from registry only; kill switch | Not yet |
| 8 | Model output rendered unsafely (XSS) | dashboard | treat agent text as plain text; React escapes by default; never `dangerouslySetInnerHTML` with model or user text | The dashboard renders all text through React and has no `dangerouslySetInnerHTML` (checked by search, not by a test); the token is kept in `sessionStorage`, never in a URL or `localStorage` (a browser test checks the latter). No agent text exists yet |
| 9 | Sensitive data sent to a model provider | agent | send only the object fields a tool returns; no secrets in tool results; review provider data terms | Not yet |
| 10 | SQL injection | API, DB | parameterised queries through the ORM/driver only; no string-built SQL | API reads: every value is a query parameter, the only text put into SQL is fixed in code or an integer already clamped (`store.py`). No test injects hostile input yet |
| 11 | Vulnerable or malicious dependency | build | pin versions, lockfiles, `pip-audit` and `npm audit` in CI, Dependabot, licence check | Not yet |
| 12 | Secrets in git | repo | `.env` ignored (done), `.env.example` holds placeholders only, secret scanning in CI, rotate if ever committed | Partly |
| 13 | Container escape or over-privileged container | Docker | non-root user, read-only filesystem where possible, pinned base image digests; the dev database port is published on `127.0.0.1` only (never on the network) and the hardened configuration will not publish it at all | Partly (localhost-only port; the rest not yet) |
| 14 | Denial of service (flood of UDP or API calls) | link, API | rate limits, bounded queues, drop-and-count under load | API: page size capped at 500, series at 5000 points, 5 s statement timeout; **no rate limit**, one database connection per request. Not otherwise |
| 15 | Yamcs web UI has no login | Yamcs config | bound to `127.0.0.1`; do not expose (README) | Documented limit |
| 16 | Clock confusion causes wrong ordering or false "stale" | time | the three-clock rule in [action-runner-and-audit.md](action-runner-and-audit.md) | Not yet |

## Secrets

- Read from environment variables or a secrets store, never from code.
- `.env` files are git-ignored; commit `.env.example` with placeholders only.
- Different credentials per role (`app_runner`, `app_reader`, `ingest`, `migrator`).
- Logs never contain secrets or full prompts that include them.

## API

- Authenticate every route. For local development a fixed dev token is acceptable if clearly marked **dev only** and disabled by default outside development; real use needs proper login (OIDC) and short-lived tokens.
- Validate every input with the same schemas the runner uses.
- Set CORS to the dashboard origin only.
- Return specific errors for the user and log details server-side.

State since phase 4: the API authenticates every route except `/health/*` (a DEV-ONLY static token per operator; enforced by a test that walks the OpenAPI document), validates action parameters with the runner's own schemas (the routes pass the raw body to the runner so that a refused request is audited), allows CORS only for the dashboard origin (a test refuses `*` and other origins), answers database and unexpected errors without internals and with a correlation id, and sets `Cache-Control: no-store`. Real login (OIDC) and short-lived tokens are not built.

## Supply chain

- Lockfiles committed (`package-lock.json`; pinned Python requirements for deployment).
- Dependency licences checked for AGPL-3.0 compatibility before adding.
- Build images from pinned bases, and consider an SBOM when images are published.

## Honest scope

Out of scope here and stated plainly: link-layer security (frame authentication and encryption, as in real missions), formal verification, penetration testing, and anything a regulator would require for a real spacecraft. Do not claim them.

## Review

Re-read this table when a new boundary appears (a new adapter, a hosted deployment, a new agent tool). A new trust boundary without a row here is unreviewed.
