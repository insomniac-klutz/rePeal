# ADR-003 — UI stack: React/Vite + FastAPI, Streamlit dropped

| | |
|---|---|
| **Status** | accepted |
| **Date** | 2026-08-16 |
| **Deciders** | owner |
| **Amends** | PRD §6 (architecture diagram), §7 (Service/UI), §8 (repo layout), §9 Phase 2 and Phase 8 |

## Context

PRD §7 chose **FastAPI + Streamlit**, explicitly trading polish for v1 speed — "React is a v2
decision". Streamlit also appears as the suggested surface for the Phase 2 annotation UI, and
Phase 8's DoD is a Streamlit flow: intake form → likelihood + drivers → precedent panel →
letter editor → analytics tab.

Two things changed the calculus. First, the demo audience is a recruiter or interviewer who
must grasp the system in five minutes (PRD §2) — the UI *is* the portfolio surface, and
Streamlit's ceiling is visibly low for a product story about drafting appeal letters.
Second, the owner already has a design system (a "claude design zip") that drops the cost of
a real frontend well below its usual price. The speed argument for Streamlit was the whole
argument, and it no longer holds.

## Decision

**We will build the v1 UI as a React/Vite frontend against the FastAPI backend. Streamlit is
dropped entirely — from Phase 8, from Phase 2's annotation tooling, and from the
architecture diagram.**

1. **Frontend:** React + Vite, in a top-level `frontend/` directory, styled with the owner's
   **design system supplied as a "claude design zip"** when the UI phase begins.
2. **Backend:** **FastAPI stays** as the API layer, unchanged in scope — `/case`, `/predict`,
   `/precedents`, `/draft_letter`, `/ask`. The frontend is a pure client of that contract.
3. **Phase 2 annotation tooling** falls back to the PRD's other option — a **CLI** — rather
   than waiting on the design zip or building throwaway UI.
4. The mandatory disclaimer footer from PRD §9 Phase 8 ("*Drafts for professional review —
   not legal or medical advice. Estimates reflect external-review-stage likelihood only.*")
   is a layout-level component present on every page.

**Rejected alternatives:** (a) keep Streamlit for v1 and rewrite in v2 — pays for the UI
twice and ships the weaker version to the demo audience; (b) hand-roll CSS instead of using
the design zip — slower and worse than the asset the owner already has.

## Consequences

- **Positive:** a demo-grade surface for the primary portfolio artifact; a real
  client/server boundary (the API contract gets exercised rather than bypassed by in-process
  Streamlit calls); design consistency for free from the supplied system.
- **Negative / cost:**
  - **UI work cannot start before the design zip is delivered.** This is a hard external
    dependency owned by the owner, not by the build. Phase 8 is blocked on it — if the zip
    slips, Phase 8 slips.
  - A JS toolchain, a second lockfile, and a build step enter the repo; `make demo` must now
    orchestrate two processes (Vite dev/build + uvicorn), and CI gains a frontend job.
  - The Phase 1.5 walking skeleton's "single-page demo" (ADR-004 / D4) must be a **minimal
    hand-written page**, since the design system is not yet available — it is explicitly
    throwaway and is not the Phase 8 frontend.
- **Follow-ups:** add `frontend/` to PRD §8's layout; replace "Streamlit UI" in the §6
  diagram with "React/Vite UI"; update Phase 2's DoD to name the CLI annotation tool; note
  the design-zip dependency on Phase 8 in `TODO.md`.
