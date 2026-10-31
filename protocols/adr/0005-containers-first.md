# ADR 0005: Docker Compose now; Jenkins and Kubernetes later
- Status: Accepted
- Date: 2026-10-31

## Context
The stack will have PostgreSQL, a backend, an ingestion/automation worker, a simulator and a dashboard, optionally with Yamcs. The repository already has CI in GitHub Actions. Local `.jenkins` and `.minikube` folders suggest Jenkins and a local Kubernetes cluster are available to the maintainer.

## Options considered
1. No containers; install everything by hand.
2. Docker Compose for the whole stack, keep GitHub Actions for CI.
3. Add Jenkins and Kubernetes from the start.

## Decision
Option 2 now. Jenkins and Kubernetes remain optional later steps, added only after the Compose setup is stable and the pipeline is defined in commands both CI systems can call, so there is a single definition of "passing".

## Consequences
- A fresh machine needs Docker only.
- The deployment story is credible but small; Kubernetes would not change what the application does at this scale.
- Maintaining a second CI system carries a cost; do it only for a concrete goal (learning, or a target employer's stack).
- Details are in [../ci-cd-and-release.md](../ci-cd-and-release.md).
