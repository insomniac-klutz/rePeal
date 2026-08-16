## Workflow — Agent Teams (mandatory for all work)

### Tool Chain

```
TeamCreate → TaskCreate (×N) → TaskUpdate (deps) → Agent w/ team_name (×N) → SendMessage → TaskUpdate (complete) → TeamDelete
```

### Tools

- `TeamCreate({ team_name, description })` — create team
- `TaskCreate({ subject, description, activeForm })` — add task to shared list
- `TaskUpdate({ taskId, owner, status, addBlockedBy })` — claim/complete/block tasks
- `TaskList` — check task statuses
- `Agent({ name, team_name, subagent_type: "general-purpose", prompt, run_in_background: true })` — **spawn teammate**
- `SendMessage({ type, recipient, content })` — teammate messaging / shutdown
- `TeamDelete` — cleanup after shutdown

### The One Rule That Matters
`Agent` WITHOUT `team_name` = subagent (isolated, no coordination). **NEVER use this.**
`Agent` WITH `team_name` + `name` = teammate (shared task list + mailbox). **ALWAYS use this.**

### Steps

1. **Explore**: `TeamCreate` → spawn 2–3 scout teammates → gather findings via `SendMessage`.
2. **Clarify**: ask user targeted questions based on findings.
3. **Plan**: enter plan mode. List each teammate (two-word cool and quircky codename , first word cool phrase , second word describing the task/responsibility ex phantom-parser, neon-extractor, vortex-mapper, cipher-scorer, blitz-linker), role, file ownership, dependency edges. Present for approval.
4. **Execute**: `TeamCreate` → `TaskCreate` (×N) → wire `addBlockedBy` → spawn teammates → lead delegates only, does NOT write code → wait for all `TaskUpdate(completed)`.
5. **Teardown**: `SendMessage(shutdown_request)` to each → `TeamDelete`.

### Rules

- ALL work goes through agent teams. Single-file / <20-line exceptions require explicit user permission.
- Each teammate owns distinct files — no shared-file edits.
- 3–5 teammates, 5–6 tasks each.
- Embed full context into spawn prompts — teammates have no conversation history.
- Lead coordinates only. If lead starts writing code, STOP and delegate.
- Use `planModeRequired: true` for risky teammates.
- Never pass `model` to `Agent`. Omitting inherits parent's pinned model. Passing enum like `"opus"` resolves to latest, not pinned version.


## Commit Workflow and Format

## Workflow

Whenever you are asked to commit .
- Group commits .
- Present groups first
- Then add them and commit one by one in a single command

### Format

```
action : description
```

- All lowercase
- Action is the verb: `add`, `update`, `fix`, `remove`, `refactor`, `rename`, etc.
- Then ` : ` (space-colon-space)
- Then a short description of what changed

### Examples:
```
add : project scaffold and meta files
update : hld with revised component boundaries
fix : missing pause gate in sync phase 2
remove : deprecated recon fallback logic
refactor : test-run tier resolution
rename : status template to match new schema
```

## TODO.md — Auto-update

After completing any phase or task:
- Flip `- [ ]` → `- [x]` for every completed item and its children
- Replace the `⛔` gate line with `✅ **Phase X complete — N tests passing**`
- Do this immediately when tests confirm the phase gate passes — don't wait to be asked

## TDD — Red-Green-Refactor

Every feature follows strict Red-Green-Refactor. No exceptions.

### The Cycle

1. **Red** — Write a failing test first. Run it. Confirm it fails. Never skip this.
2. **Green** — Write the minimum code to make the test pass. No more.
3. **Refactor** — Clean up with the green bar. Tests must stay green throughout.

### File Order Rule

For any new module `src/repeal/foo.py`:
1. Create `tests/test_foo.py` first
2. Write test functions that import from `src/repeal/foo.py` (the import will fail — that is red)
3. Create `src/repeal/foo.py` with minimum implementation
4. Run tests — they must go green
5. Only then proceed to the next test or refactor

### Phase Gates

Phases are defined in the PRD (`PRD.md`, phases 0–8) and tracked in TODO.md. Enforcement:

- All tests for Phase N must pass before any Phase N+1 code is written
- Run `uv run pytest` and confirm zero failures before starting the next phase
- Each phase's test files are listed in TODO.md alongside its tasks

### Agent Team TDD Rules

- The same teammate that owns an implementation file also owns its test file
- That teammate must follow R-G-R order: write test, see red, implement, see green
- Teammates must run `uv run pytest` after implementation and report pass/fail
- If tests fail, the owning teammate fixes — no cross-teammate test fixes

### Commands

```
uv run pytest                          # run all tests
uv run pytest tests/test_ingest.py     # run one file
uv run pytest -x                       # stop on first failure
uv run pytest --cov                    # with coverage report
uv run pytest --cov --cov-report=html  # coverage with HTML report
```

### Pre-commit Hook

A git pre-commit hook runs `uv run pytest` before every commit. If tests fail, the commit is rejected.

To install (required after fresh clone):
```
bash scripts/install-hooks.sh
```

## Sanity Check Before Building

Before implementing any non-trivial change, pause. Don't jump to code — think first, then propose.

### Simplicity

- **Default to the boring approach.** If the solution needs a paragraph to explain, it's probably wrong. The right answer is usually the one that makes someone say "obviously."
- **Watch for accidental complexity.** Every abstraction, config option, conditional branch, or indirection layer must earn its place. If you can delete it and nothing breaks, it shouldn't exist.
- **Catch the spiral early.** If we've iterated 3+ times on the same problem, the framing is probably wrong — not just the latest attempt. Step back and question the premise, not the implementation.
- **Don't port complexity.** When adapting something from another codebase, strip it to what the target actually needs. Source-repo patterns, naming, and structure are context-specific — carrying them over uncritically imports someone else's tech debt.

### Consequences

- **Think one level beyond the immediate task.** Who consumes this output? What systems does it touch? What process does it trigger? A CI change might be 5 lines of YAML but 20 hours of compliance review downstream.
- **Walk through the operational model.** Before proposing infrastructure, CI, release tooling, or architecture changes: what happens day-to-day when this is running? Who gets paged, what gets noisy, where does the friction land?
- **Project forward.** What happens when the current number (of packages, endpoints, consumers, environments) grows 5-10x? If the approach breaks at scale, say so now — even if we choose to accept it at current scale.
- **Distinguish real costs from theoretical ones.** "This adds 2 seconds to CI" is not the same as "this triggers 20 manual security reviews." Optimize for the expensive dimension, not the obvious one.

### Process

- **Present the tradeoff, not just the solution.** Show the tension (X gives you Y but costs Z), make a recommendation, and let the user decide. One turn, not a multi-round discovery process.
- **Name what you're trading away.** Every design choice closes a door. Say which door. "This pins exact versions, which means every release uploads all packages even if unchanged" is better than just "this pins exact versions."
- **Don't implement the first working approach — implement the right one.** A solution that works is table stakes. The goal is a solution that's simple, appropriate for the scale, and doesn't create problems the user has to discover later.