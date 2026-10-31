# AI-assisted development protocol

**Status:** Proposed. **Applies to:** any AI coding assistant (Claude Code, Copilot, Cursor, ...) and any human working in this repo.

## Principle

A person owns every decision and every merge. An assistant may research, propose, implement and check, but its output is a draft until a person has reviewed the diff and seen the checks pass. Assistants make fluent, plausible mistakes; this repo's hardest bugs (an off-by-one in a length field, a flipped byte order) are exactly that kind.

## Workflow

1. **Understand.** Read the code and [../ontology.md](../ontology.md) before changing anything. Do not infer behaviour from file names.
2. **Plan, in writing, for anything non-trivial.** A non-trivial change touches the spec, the packet codec, the action runner, permissions, migrations or the agent tools. The plan names the files, the tests, and what could go wrong.
3. **Write the test first or alongside.** A bug fix starts with a test that fails for the right reason.
4. **Keep the diff small and single-purpose.** One concern per pull request. No drive-by reformatting.
5. **Run the checks.** Tests, lint, and `minisat gen-xtce --check` at minimum. See [testing-and-verification.md](testing-and-verification.md).
6. **Report with evidence.** State what was run and what happened. Failures are reported with their output.
7. **Human review** before merge.

## Hard rules

An assistant MUST NOT:

- Edit `yamcs/src/main/yamcs/mdb/minisat.xml` by hand. It is generated; change `spec/minisat.yaml` and run `minisat gen-xtce`.
- Change `spec/minisat.yaml` without regenerating the database and updating every test whose expected packet size changed (see exercise 1 in the README).
- Weaken, skip, delete or loosen a test or tolerance to make it pass. If a test looks wrong, say so and ask.
- Catch and silently ignore an exception on a code path that handles packets, commands or permissions.
- Write to operations tables except through the action runner ([action-runner-and-audit.md](action-runner-and-audit.md)).
- Add a dependency without stating why, its licence, and that it is compatible with AGPL-3.0.
- Put secrets, tokens or real credentials in code, tests, fixtures, prompts or logs.
- Run destructive operations (force-push, `reset --hard`, dropping a database, deleting files it has not looked at) without explicit confirmation.
- Commit or push unless asked.
- Say something works, passes, or is verified unless it ran that check in this session. "Should work" and "I believe" are the correct words for everything else.

An assistant SHOULD:

- Say when it is unsure, and which assumption it made instead of asking.
- Prefer extending the existing pattern over inventing a new one.
- Mark AI-written text that states facts about external systems (Yamcs behaviour, standards) as unverified until a source is cited.

## Review checklist for AI-generated changes

- [ ] Does every API, flag and class name actually exist? (Open the source; assistants invent plausible names.)
- [ ] Packet code: byte order, bit widths, "length = data bytes - 1", sequence-count wrap at 16384.
- [ ] Is each expected value in a test worked out independently, not copied from the implementation's output?
- [ ] Error handling: does a malformed input produce a specific error, and is it counted or logged?
- [ ] Permissions: is there a negative test (the wrong role is refused)?
- [ ] Migrations: reversible, reviewed, and tested on a database that already has data?
- [ ] Any new claim in docs is true, and unverified claims are labelled.
- [ ] Nothing unrelated changed.

## Provenance

- Commits that an assistant helped write carry the `Co-Authored-By:` trailer the tool provides.
- A pull request says which parts were AI-drafted when that affects how carefully to review (for example, "the migration SQL was AI-drafted").
- Prompts and conversations are not committed. Decisions that came out of them are written as ADRs ([adr/](adr/README.md)).

## Context for assistants

Keep the entry-point instructions (`CLAUDE.md` or similar) short and link to these files. Point assistants at: the README, [../ontology.md](../ontology.md), `spec/minisat.yaml`, and this folder. Do not paste long rules into prompts; a rule that lives only in a prompt is not a rule.

## Enforcement

| Rule | Mechanism | State |
| --- | --- | --- |
| Generated XTCE is current | `minisat gen-xtce --check` in CI and tests | Enforced (existing) |
| Tests and lint pass | CI | Enforced (existing) |
| No direct writes to operations tables | database grants; exact privilege matrix in `tests/db/test_privileges.py` | Enforced at the database (the runner module boundary is not built yet) |
| Licence check on dependencies | CI job | Not yet |
| Secrets not committed | `.env` is git-ignored (`.env.example` has placeholders); secret scanning in CI | Partly (ignore rule only) |
| Review before merge | branch protection | Not yet |
