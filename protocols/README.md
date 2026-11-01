# Engineering protocols

Rules for building and running mini-mission-control, written for this project: the Python simulator, the generated XTCE database, the ontology layer, the action runner, the dashboard and the AI agent that sits on top.

## Status

**Every protocol here is `Proposed`, and only some parts are enforced.** A rule counts as `Enforced` when a test, a database permission or a CI gate fails if it is broken, and the file says which one. Today that is the generated-database freshness check, the existing test suite, and (since phase 1 of [../PLAN.md](../PLAN.md)) the database roles, privileges, constraints and append-only audit log. Everything marked `Not yet` is a written intention, not a fact about the repository.

Each file ends with an **Enforcement** section listing what would enforce it and its current state.

## Index

| File | Question it answers |
| --- | --- |
| [ai-assisted-development.md](ai-assisted-development.md) | How may an AI coding assistant (or a person) change this repo? |
| [agent-safety-and-autonomy.md](agent-safety-and-autonomy.md) | What may the in-app AI agent do, and how is it kept from doing more? |
| [command-safety-protocol.md](command-safety-protocol.md) | When is a telecommand allowed to leave the ground? |
| [action-runner-and-audit.md](action-runner-and-audit.md) | How is every write authorised, applied and recorded? |
| [testing-and-verification.md](testing-and-verification.md) | What counts as evidence that something works? |
| [agent-evaluation.md](agent-evaluation.md) | How do we test an AI agent whose output is not deterministic? |
| [security-and-threat-model.md](security-and-threat-model.md) | What can go wrong, and what stops it? |
| [ci-cd-and-release.md](ci-cd-and-release.md) | What must pass before a change is merged and shipped? |
| [observability-and-operations.md](observability-and-operations.md) | How do we see what the system is doing, and what do we do when it breaks? |
| [adr/](adr/README.md) | Why did we choose X over Y? (decision log) |

Related: [../ontology.md](../ontology.md) is the domain model these protocols protect.

## Basis, and what this is not

The protocols borrow ideas from published work: the OWASP Top 10 for LLM Applications (prompt injection, excessive agency), the NIST AI Risk Management Framework (govern, map, measure, manage), the ECSS space software standards (software engineering and product assurance, especially independent verification), the Model Context Protocol (typed tool interfaces) and Michael Nygard's architecture decision records.

They were written from general knowledge of those sources, **not** by auditing this project against them. Do not describe the project as compliant with any of them. "Informed by" is accurate; "compliant with" is not.

All numeric thresholds (timeouts, rate limits, windows) are **initial values** chosen to be reasonable for a simulator. They are meant to be tuned from measurements, and each should be revised when real data exists.

## Changing a protocol

Change a protocol in a pull request, like code. If the change reverses a decision, add an ADR.
