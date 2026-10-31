# ADR 0004: The in-app agent proposes, people decide
- Status: Accepted
- Date: 2026-10-31

## Context
An AI agent over the ontology can read state, compute forecasts and suggest commands. Commands act on a machine that cannot be touched, can be irreversible, and an agent's output is non-deterministic and can be influenced by text in the data it reads (prompt injection). Control-room practice also warns about people over-trusting automation.

## Options considered
1. Read-only agent.
2. Agent proposes commands; a human approves and releases (autonomy level L2).
3. Agent releases non-vital commands itself within limits (L4 for part of the command set).

## Decision
Option 2. The agent can read, compute, propose commands and open anomaly records. It cannot approve, release or acknowledge alarms. Vital commands need a different human as approver. Raising the ceiling requires a new ADR, evidence from the agent evaluation suite and a supervisor's sign-off.

## Consequences
- Slower than autonomous operation, deliberately.
- Every agent proposal must carry evidence and a preflight result so the approver can judge it quickly.
- The system works without the agent; a model outage or kill switch removes a convenience, not a capability.
- Success is measured by useful, safe proposals, not by commands issued.
