# ADR 0003: Local web app (React and Blueprint)
- Status: Accepted
- Date: 2026-10-31

## Context
The project has no user interface of its own; Yamcs's web UI is third-party and unverified with this configuration. A dashboard is needed. Blueprint (Palantir's open-source React toolkit, Apache-2.0, checked on its repository page) targets dense desktop-style web interfaces, which suits a mission-control screen.

## Options considered
1. A desktop application (Tkinter, Qt, Electron or Tauri).
2. A single dependency-free HTML page served by Python.
3. A React and TypeScript app using Blueprint, served locally and talking to a Python API.

## Decision
Option 3. The Python backend exposes objects, links and actions through an API; the dashboard is a client of it. It runs on localhost (`127.0.0.1`). A desktop wrapper can be added later if wanted.

## Consequences
- The repository now has two languages and needs Node.js for the dashboard, with a build step.
- Multiple clients (an operator and a supervisor) can use it at once.
- Charts and the ground-track map need libraries beyond Blueprint.
- The backend cannot trust the browser; every action is authorised in the runner.
- No claim is made that Palantir's own products use Blueprint; only that Palantir publishes it.
