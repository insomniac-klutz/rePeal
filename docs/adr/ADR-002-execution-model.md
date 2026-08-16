# ADR-002 — Execution model: Claude Code workflows, not an API client

| | |
|---|---|
| **Status** | accepted |
| **Date** | 2026-08-16 |
| **Deciders** | owner |
| **Amends** | PRD §7 (Tech stack — LLM), §8 (`src/repeal/llm_client.py`), §10 (Engineering standards — cost logging), §12 (Risks — extraction cost) |

## Context

PRD §7 specifies the Anthropic API via the official Python SDK, with **one client module**
(`src/repeal/llm_client.py`) providing content-hash caching, retries, JSONL logging of
`{prompt hash, model, tokens, cost, latency}`, and a **hard budget cap via env var**; §12
lists "LLM extraction cost over full corpus" as a top risk, mitigated by caching, a cheaper
bulk model, and that budget cap. §10 requires per-phase cost summaries in the build logs.

That design assumes metered per-token spend. The owner holds a Claude Max subscription and
runs this project through Claude Code, where the same work — extraction, scrub audit,
annotation, generation, LLM-judge — can be executed as agent/skill workflows at **zero
marginal API cost**. Building an API client, a cost meter, and a budget cap to guard spend
that will never be incurred is accidental complexity: the entire risk row and half the
telemetry exist to manage a constraint that does not apply.

The competing concern is reproducibility. A metered API client gives you replayable calls
with recorded token counts; agent workflows do not. Reproducibility therefore has to be
carried by something else — the artifacts.

## Decision

**We will not build an Anthropic API client module, and we will not implement a budget cap.**
`src/repeal/llm_client.py` is removed from the repository layout.

1. **All LLM stages run as Claude Code agent/skill workflows** under the owner's Max
   subscription. This covers: full-corpus extraction, scrub audit, gold-set annotation,
   letter generation, and the LLM-judge.
2. **Model assignment by surface:**
   - `claude-opus-5` — judgment-heavy surfaces: gold-set pre-annotation, scrub audit, letter
     generation, LLM-judge.
   - `claude-haiku-4-5` — bulk full-corpus extraction.
   This supersedes the PRD's `claude-sonnet-4-6` default.
3. **Artifacts are the contract.** Every LLM stage emits versioned **JSONL/parquet**
   artifacts that carry the **prompt hash** (plus prompt version, model id, and workflow
   name) for each record. Artifacts are committed or checksummed; downstream phases consume
   artifacts, never live model calls.
4. **Runtime inference for the v1.1 chatbot** uses **local models behind a
   LiteLLM-compatible interface** — the same artifact/response contract, a swappable backend.
5. **Development process:** the project uses **agent teams *within* a phase**. The PRD's
   "execute phases **sequentially**" governs *phase order and the owner-review boundaries at
   each DoD* — it does **not** forbid intra-phase parallelism. A phase may be built by 3–5
   teammates working concurrently on disjoint files; the phase still stops at its DoD for
   owner review.
6. **Commit format** is `action : description`, all lowercase, per `CLAUDE.md`. This
   supersedes the PRD §10 "conventional commits" requirement.

**Rejected alternatives:** (a) build the API client anyway "for portability" — pays real
complexity now for a hypothetical backend later; (b) keep the budget cap as a no-op — dead
config that lies about how the system runs.

## Consequences

- **Positive:** zero API cost; no key management; no budget-cap failure mode mid-run; the
  bulk/judgment model split is preserved without a config layer to enforce it.
- **Negative / cost:**
  - **No per-call cost telemetry.** PRD §10's "costs summarized per phase" cannot be
    satisfied in dollars. It is **replaced by artifact + prompt-hash logging**: which
    workflow ran, against which prompt version, producing which artifact. Build logs record
    **agent/workflow effort** (agents spawned, passes, wall-clock) instead of dollars.
  - **Reproducibility depends on committed artifacts rather than replayable API calls.** An
    exact re-run of a workflow is not guaranteed to reproduce byte-identical output; the
    committed artifact is the reproducible unit. Any eval number must cite the artifact
    version it was computed from.
  - The "LLM extraction cost over full corpus" risk row in PRD §12 is void; the residual risk
    is *wall-clock and agent effort*, not spend.
- **Follow-ups:**
  - A future API backend **or** the v1.1 local-model backend can be added behind the **same
    artifact contract** — a component that writes the same JSONL/parquet with the same
    prompt-hash fields is a drop-in replacement. Nothing downstream needs to know which
    produced it.
  - Artifact schema (including `prompt_hash`, `prompt_version`, `model`, `workflow`) must be
    fixed in Phase 3 before full-corpus extraction runs.
