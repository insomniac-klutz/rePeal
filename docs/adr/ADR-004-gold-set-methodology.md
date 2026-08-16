# ADR-004 — Gold-set methodology: multi-agent annotation, human tier, IDs-only release

| | |
|---|---|
| **Status** | accepted |
| **Date** | 2026-08-16 |
| **Deciders** | owner |
| **Amends** | PRD §9 Phase 2 (annotation & gold sets), §13 (open decision: public gold-set release) |
| **Related** | ADR-002 (execution model), ADR-001 (leakage protocol) |

## Context

PRD §9 Phase 2 specifies a stratified **250-case** extraction gold set (by type ×
determination × era), built by *LLM-assisted pre-annotation → human adjudication*, with a
second-pass self-consistency check on 50 cases and reported agreement stats. The PRD assigns
adjudication to the owner and tooling to the builder.

Two pressures reshape the *how* without changing the *what*. First, ADR-002 moved all LLM
work to Claude Code agent workflows — which makes running **many independent annotators per
case** nearly free, an option a metered API budget would have priced out. Second, hand-
adjudicating 250 cases end-to-end is the single largest block of owner time in the project;
spending it on cases where independent annotators already agree is waste. Disagreement is the
signal worth paying attention to.

The honest cost of this design is circularity, addressed explicitly below.

## Decision

**We will keep the 250-case extraction gold set and produce it via a multi-agent Claude Code
annotation workflow with disagreement-driven escalation and a human spot-check tier.**

1. **Size:** **250 extraction gold cases**, stratified as the PRD specifies (type ×
   determination × era). Unchanged.
2. **Multi-agent annotation:** **N independent annotator agents per case**, each given a
   **different prompt and framing** (e.g. field-by-field extraction, narrative-summary-first,
   skeptical/minimal-extraction, evidence-typing-first). Agents do not see one another's
   output. Each emits a case card against the Phase 2 JSON Schema, tagged with its prompt
   hash per ADR-002.
3. **Disagreement-driven escalation:** per-field agreement is computed across the N
   annotations. Fields where annotators **agree** are accepted as-is. Fields where they
   **disagree** escalate to an **adjudicator pass** — a separate agent that sees all N
   candidate values plus the source and resolves, with its reasoning recorded in the
   artifact.
4. **Human tier:** the owner spot-checks **n ≥ 25 cases**, sampled to over-weight
   high-disagreement and adjudicated cases rather than sampled uniformly. The checklist and
   corrections are logged; owner corrections override the pipeline unconditionally and are
   marked as such in the gold file.
5. **Reported statistics:** inter-agent agreement per field, escalation rate per field,
   adjudicator override rate, and human-tier correction rate — all published in the
   annotation guide and `docs/evals/`.
6. **Retrieval and generation sets** (PRD Phase 2: 50 retrieval queries with pooled
   relevance judgments; 30-case generation rubric set) follow the same multi-agent-plus-human
   pattern, with pooled judgments assembled from the retrieval systems actually built in
   Phase 4.

### Known limitation — circularity (stated plainly)

**The same model family annotates the gold set and is later evaluated against it.** The
agreement statistics this workflow produces are therefore **inter-agent consistency, not
fully independent ground truth**. High agreement can reflect a shared prior rather than a
correct answer, and a systematic error shared by all N annotators will pass through the
adjudicator undetected. Extraction F1 measured against this gold set is an *upper-bounded,
optimistic* estimate.

We accept this limitation rather than hide it. It is mitigated three ways, none of which
eliminate it:

- **Prompt diversity** — differing framings decorrelate at least some shared failure modes,
  which is why the N annotators are not N copies of one prompt.
- **The human tier** — n ≥ 25 owner-adjudicated cases, over-sampled on disagreement, give an
  independent read on where the agent consensus is wrong.
- **Disclosure** — this limitation is restated verbatim in the **model card** and in the
  annotation guide, so no downstream reader of an F1 number encounters it as a surprise.

### Release policy

Published gold files contain **`ReferenceID`s + annotations + a join script against the source
download only — never `Findings` text.** The dataset terms permit noncommercial use without
approval but **prohibit redistributing or altering the provided data**; linking to the source
is the distribution mechanism (PRD §4). A consumer reproduces the full gold set by
downloading the CA DMHC IMR file themselves and running the join script. This resolves PRD
§13's open decision — *yes, release, with a methodology note* — within those terms.

**Rejected alternatives:** (a) single-annotator pre-annotation + full 250-case human
adjudication — the PRD default; correct but spends owner time uniformly instead of on
disagreement; (b) publishing excerpted `Findings` text alongside annotations — cleaner for
consumers, but redistributes provided data.

## Consequences

- **Positive:** owner effort concentrates where the signal is; agreement/escalation/override
  rates become publishable evidence about annotation quality; the workflow scales to the
  retrieval and generation sets at no additional cost.
- **Negative / cost:**
  - The circularity above is real and permanently caps how strong an extraction claim the
    project can make. Every F1 figure must carry the caveat.
  - N× annotation passes mean N× wall-clock and agent effort per case (no dollar cost, per
    ADR-002).
  - Consumers of the released gold set must obtain the source data themselves — a friction
    the join script minimizes but cannot remove. The join script needs its own test against
    a fixture.
- **Follow-ups:** choose and record N in Phase 2; write the annotation guide including the
  circularity paragraph; add the model-card disclosure item to Phase 5's checklist; build and
  test the join script as a Phase 2 deliverable; finalize the terms determination in the data
  card before Phase 2 ships.
