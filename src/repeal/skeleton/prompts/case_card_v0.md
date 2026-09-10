# Case Card Extraction — v0

You are extracting **case cards** from California DMHC Independent Medical Review (IMR)
records for the `repeal` project's Phase 1.5 walking skeleton. Each input row is one
IMR case; your job is to describe the situation *at the moment of denial* — never the
outcome of the review that followed.

## Input

A JSONL file, one object per line, with exactly these fields:

- `row_id` — integer surrogate key
- `reference_id` — the case's public reference ID
- `report_year` — the year DMHC reported the case
- `case_type` — `Medical Necessity`, `Experimental/Investigational`, or `Urgent Care`
- `imr_type` — `Standard` or `Expedited`
- `age_range`, `patient_gender` — demographic buckets, may be null
- `diagnosis_category`, `treatment_category` — DMHC's own category labels
- `findings` — the reviewer's full narrative, written *after* the decision

## Output

For every input row, emit exactly one JSON object with exactly these fields — no
extra fields, no provenance, no metadata:

- `row_id` — copied from the input
- `reference_id` — copied from the input
- `patient_context` — 1–2 sentences: age, gender, and clinically relevant history
  drawn from `findings`. No names, no case-note numbers, no reference IDs.
- `diagnosis_norm` — the condition in plain clinical terms (not the raw DMHC category)
- `treatment_requested` — what treatment, service, or item was denied
- `denial_basis` — exactly one of: `medical_necessity`, `experimental_investigational`,
  `urgent`. Default to the input's `case_type` mapped to the enum (Medical Necessity →
  `medical_necessity`, Experimental/Investigational → `experimental_investigational`,
  Urgent Care → `urgent`). Deviate only when the plan's stated rationale in the narrative
  is clearly a different basis, and then add `"denial_basis_differs_from_case_type"` to
  `scrub_flags` so the disagreement is visible.
- `payer_rationale` — the plan's stated reason for denying, paraphrased in your own
  words, not quoted
- `evidence_cited` — a list of `{"kind": ..., "text": ...}` objects for every piece of
  evidence either side raised before the review. `kind` is one of:
  - `guideline` — a clinical practice guideline or plan medical policy
  - `peer_reviewed_study` — a published study or journal article
  - `fda_status` — FDA approval, clearance, or off-label status
  - `clinical_trial` — an active or completed clinical trial
  - `expert_opinion` — a treating or consulting physician's opinion
  - `other` — anything that doesn't fit the above
  Empty list (`[]`) if the narrative cites no evidence. **The reviewer's own reasoning,
  findings, or opinion is NEVER evidence — it is written after the decision.** Only
  evidence the patient, the treating physician, or the plan raised before the review
  counts; `expert_opinion` means the treating or consulting physician's opinion, not
  the reviewer's.
- `scrub_flags` — a list of strings flagging anything you had to omit. Empty (`[]`)
  if nothing was omitted.

## **THE SCRUB RULE**

**Never state, paraphrase, or hint at the reviewer's determination or the outcome of
the review** — not "upheld", not "overturned", not "approved", not "denied *by the
reviewer*", not "medically necessary" or "not medically necessary" used as the
reviewer's *conclusion*, not "the plan must cover this" or any equivalent. The card
describes the case as it stood at denial time, before any review outcome existed.

If `findings` contains verdict language, **omit it from every field** and add the
string `"verdict_language_omitted"` to `scrub_flags`. When in doubt, leave it out and
flag it — a card that's missing color is fine; a card that leaks the label is not.

## Output format

One JSON object per line (JSONL). No prose before, after, or between objects. No
code fences. No provenance fields (`prompt_hash`, `model`, `workflow`, `extractor`,
etc.) — those are stamped later by the merge step, not by you.

## Worked example

Input line (invented — not a real case):

```json
{"row_id": 41, "reference_id": "MN20-00041", "report_year": 2020, "case_type": "Medical Necessity", "imr_type": "Standard", "age_range": "31 to 40", "patient_gender": "Female", "diagnosis_category": "Musculoskeletal", "treatment_category": "Surgery", "findings": "The patient is a 34-year-old woman with chronic lumbar radiculopathy who has completed six months of physical therapy and epidural injections without relief. Her surgeon requested authorization for a lumbar microdiscectomy, citing MRI findings of a herniated disc at L4-L5. The plan denied the request, stating the submitted records did not demonstrate that conservative treatment had failed per its own spine surgery guideline, and that a repeat MRI was needed first. On review, the reviewer found the record does support medical necessity and the denial should be overturned."}
```

Output line:

```json
{"row_id": 41, "reference_id": "MN20-00041", "patient_context": "A woman in her mid-30s with chronic lumbar radiculopathy, unresolved after six months of physical therapy and epidural injections.", "diagnosis_norm": "Lumbar radiculopathy with L4-L5 disc herniation", "treatment_requested": "Lumbar microdiscectomy", "denial_basis": "medical_necessity", "payer_rationale": "The plan held that conservative treatment had not been shown to fail per its spine surgery guideline, and wanted a repeat MRI before authorizing surgery.", "evidence_cited": [{"kind": "guideline", "text": "Plan's own spine surgery guideline on conservative-treatment failure"}, {"kind": "other", "text": "MRI showing L4-L5 disc herniation"}], "scrub_flags": ["verdict_language_omitted"]}
```

Note what happened: the input's final sentence ("the record does support medical
necessity and the denial should be overturned") is the reviewer's verdict. It does
not appear anywhere in the output, and `verdict_language_omitted` is flagged instead.
