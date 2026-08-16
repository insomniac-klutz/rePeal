# ADR-001 — Leakage protocol (core design constraint)

| | |
|---|---|
| **Status** | accepted |
| **Date** | 2026-08-16 |
| **Deciders** | owner |
| **Source** | PRD §5, committed verbatim in Phase 0 as the PRD instructs |

## Context

The core scientific risk of this project is that the only free-text field in the corpus —
`Findings` — is written *after* the decision and routinely announces the verdict. Any model
trained on it would score near-perfectly and mean nothing. The PRD therefore fixes the
leakage protocol as a design constraint rather than an implementation detail, and instructs
that §5 be committed verbatim as this ADR. The verbatim text follows.

## Decision

> The `Findings` text is written **after** the decision by the reviewer and frequently states the verdict ("the reviewer determined the requested service was medically necessary"). Therefore:
>
> 1. **Inference-time contract:** prediction inputs are limited to a **pre-decision case card** — the information a provider actually holds at denial time: patient context, diagnosis, treatment requested, payer's denial rationale, evidence available. Raw `Findings` is **never** a prediction input.
> 2. **Pipeline:** LLM extraction reconstructs the case card from `Findings` while **scrubbing all outcome/verdict language**.
> 3. **Scrub validation suite (runs in CI on fixtures):**
>    - a. Verdict-language detector (regex battery + LLM audit pass) — residual rate < 2% on an audit sample;
>    - b. **Adversarial sentinel:** TF-IDF + logistic regression trained on *raw* Findings vs on *scrubbed* case cards. Raw is expected to score near-perfect (that's the leak); scrubbed must drop to a plausible range. Both numbers are reported in every eval report;
>    - c. Human spot-check, n=50, checklist logged.
> 4. **Framing:** all model outputs are labeled *"external-review overturn likelihood"* — these cases already survived internal appeal (selection bias). This caveat appears in the model card and the UI.
> 5. Raw `Findings` may be used for retrieval display and generation grounding **with citation**, since those are human-in-the-loop surfaces, not prediction inputs.
>
> Commit this section verbatim as `docs/adr/ADR-001-leakage-protocol.md` in Phase 0.

## Amendment (2026-08-16): precedents as prediction inputs

The PRD §9 Phase 5 baseline ladder ends with an **LLM few-shot predictor using retrieved
precedents**. That path can smuggle raw `Findings` back into the prediction surface through
the retrieval channel, which clause 5 above permits *only* for human-in-the-loop display and
generation grounding. This amendment closes that gap.

When retrieved precedents feed the Phase 5 LLM few-shot predictor:

1. **Precedent representation:** each precedent is represented as **(scrubbed case card +
   `Determination` label) ONLY**. Raw `Findings` text is never placed in the predictor's
   prompt — not as context, not as a citation, not in truncated form. The retrieval layer
   used for prediction returns case-card projections, not display records.
2. **Temporal restriction:** the precedent pool for any test-set prediction is restricted to
   cases decided **strictly before the query case's `ReportYear`**. This mirrors the Phase 5
   temporal split (train ≤ cutoff, test after) and prevents future decisions from informing
   past-facing predictions.
3. **Self-exclusion:** the query case is always excluded from its own precedent pool, as are
   exact-duplicate `ReferenceID`s surfaced by the retrieval layer.

These three constraints are enforced in code at the precedent-assembly boundary and covered
by tests, not left to prompt discipline.

## Consequences

- **Positive:** every published prediction number is defensible; the raw-vs-scrubbed sentinel
  gap becomes a headline artifact of the project rather than a hidden caveat.
- **Negative / cost:** the few-shot predictor is handicapped relative to a naive
  implementation, and its numbers will look worse than a leaky version would. That is the
  point; the gap is reported, not fixed.
- **Follow-ups:** Phase 4 retrieval must expose two distinct retrieval surfaces (display
  records vs. case-card projections for prediction). Phase 5 must include a test that fails
  if raw `Findings` appears in any predictor prompt, and a test asserting the temporal and
  self-exclusion filters on the precedent pool.
