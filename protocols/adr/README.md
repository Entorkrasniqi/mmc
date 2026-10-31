# Architecture decision records

An ADR captures one significant decision: the context, the options, what was chosen and the consequences. We use the short format proposed by Michael Nygard. ADRs are numbered, never edited to change history; to reverse a decision, write a new ADR that supersedes the old one.

## When to write one

- A choice that is expensive to reverse (database, framework, wire format).
- A change to a safety rule or an autonomy ceiling ([../agent-safety-and-autonomy.md](../agent-safety-and-autonomy.md)).
- Anything a future reader would otherwise ask "why on earth did we do it this way?".

## Template

```markdown
# ADR NNNN: <title>
- Status: Proposed | Accepted | Superseded by NNNN
- Date: YYYY-MM-DD

## Context
What forces are at play?

## Options considered
1. ...
2. ...

## Decision
What we chose, in one or two sentences.

## Consequences
What gets easier, what gets harder, what we now have to watch.
```

## Index

| ADR | Title | Status |
| --- | --- | --- |
| [0001](0001-two-layer-ontology.md) | Two-layer ontology: generated definitions, database operations | Accepted |
| [0002](0002-postgresql.md) | PostgreSQL as the system store | Accepted |
| [0003](0003-local-web-app.md) | Local web app (React and Blueprint) | Accepted |
| [0004](0004-agent-propose-only.md) | The in-app agent proposes, people decide | Accepted |
| [0005](0005-containers-first.md) | Docker Compose now; Jenkins and Kubernetes later | Accepted |
