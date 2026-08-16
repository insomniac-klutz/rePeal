# Build log — YYYY-WW

| | |
|---|---|
| **Week** | ISO week (`date +%G-%V`) |
| **Phase(s)** | e.g. Phase 1 — Ingest + EDA |
| **Status** | in progress \| phase gate met \| blocked on owner |

## Decisions

What was decided this week and by whom. Link every decision that deviates from a PRD default
to its ADR file (`docs/adr/ADR-NNN-*.md`) — a decision without an ADR is a decision that did
not happen. Note anything in the PRD found ambiguous.

- **D-N:** … → `docs/adr/ADR-NNN-…md`

## Progress

What shipped, phase by phase. Prefer artifacts over adjectives: file paths, test counts, eval
numbers, DoD items met. Note which phase gates passed (`uv run pytest` green + DoD met).

-

## Dead ends

**Explicitly welcomed — dead ends are content, not embarrassment** (PRD §10). What was tried
and abandoned, and *why* it failed. Approaches that looked right and weren't are the most
valuable thing in this log; a week with no dead ends usually means a week with no risk taken.

-

## Costs

**$0 API cost — all LLM stages run as Claude Code agent/skill workflows under the owner's Max
subscription (ADR-002).** There is no per-call cost telemetry to report. Log **agent and
workflow effort** instead:

| Workflow / phase | Agents | Passes | Wall-clock | Artifact(s) + prompt hash |
|---|---|---|---|---|
| | | | | |

## Next

What the next week targets, and what is blocked on the owner (reviews, the design zip,
adjudication tiers, open decisions from PRD §13).

-
