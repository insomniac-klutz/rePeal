# PRD — `repeal`: Appeals Intelligence over Public External-Review Data

| | |
|---|---|
| **Status** | v0.1 starter — approved for Phase 0 kickoff |
| **Owner** | [Your name] (product + engineering decisions) |
| **Builder** | Claude Code (executes phases; escalates deviations as OQ.md entries for the owner to rule; ruled work lands via ROLLER.md) |
| **Decision process** | `OQ.md` (every call and who made it) + `ROLLER.md` (the work rulings produce), repo root, since 2026-09-09. The four ADRs of 2026-08-16 are folded into OQ.md Phase 0 as OQ-0.1–0.4. |
| **Repo name** | `repeal` (repo dir: rePeal) — renamed from working title `overturn`, 2026-08-16 |
| **License** | Code: Apache-2.0. Data: not redistributed — see §4 |

> **How to use this document:** Claude Code executes phases **sequentially** (§9). Each phase ends at its Definition of Done (DoD). Stop there, commit artifacts (code + tests + docs + ledger updates), and wait for owner review. Any deviation from a default in this PRD requires an OQ.md entry ruled by the owner; the change lands with the ROLLER.md item that ruling produced. Never silently change scope, targets, or stack.

---

## 1. Problem & opportunity

US insurers deny a large share of claims and prior-authorization requests, yet almost nobody appeals — and appeals that are filed succeed at remarkable rates. Per KFF's analyses of federal transparency data: HealthCare.gov insurers denied ~19% of in-network claims in 2024, fewer than 1% of denials were appealed, and across Medicare Advantage / Medicaid MCO / ACA markets, roughly 43–67% of appealed prior-auth denials were overturned (Medicare Advantage standard requests: ~67% overturned; some insurers 90%+).

The market failure is a **labor bottleneck**: deciding *which* denials are worth fighting and *drafting* the appeal is expensive human work. This project builds a system that automates both — using the only large public corpus of real appeal decisions with outcomes.

**Portfolio goals (equal priority to product goals):** demonstrate clinical NLP, LLM information extraction, hybrid retrieval, calibrated ML, grounded generation, text2SQL, eval-first engineering, and a fully logged decision trail (OQ.md rulings + ROLLER.md backlog).

## 2. Users & jobs-to-be-done

- **Primary persona:** provider-side revenue-cycle / denials analyst.
  Jobs: (a) triage which already-denied, internally-appealed cases are worth escalating to external review (estimates reflect external-review-stage likelihood only), (b) find winning precedent, (c) draft a grounded appeal letter in minutes instead of hours.
- **Secondary (stretch, v1.1):** payer utilization-management QA — "would this denial survive external review?"
- **Demo audience:** a recruiter/interviewer must grasp the system end-to-end in a 5-minute demo.

## 3. Success criteria

Initial targets — revise only via an OQ.md ruling, never silently:

| Layer | Metric | Initial target |
|---|---|---|
| Extraction | per-field F1 vs gold set | macro ≥ 0.80 |
| Leakage scrub | residual verdict-language rate (audited) | < 2% |
| Retrieval | Recall@10 on judged queries | ≥ 0.70 |
| Prediction | ECE on temporal holdout **and** AUC | ECE ≤ 0.05 **and** AUC ≥ floor set after the logreg baseline (via OQ ruling) |
| Generation | citation-faithfulness (claims traceable to a source) | ≥ 95% |
| Analytics agent | execution accuracy on 40-question eval | ≥ 85% |
| Engineering | one-command reproduce; CI green; every phase's calls are in OQ.md and its work in TODO.md / ROLLER.md | binary |

## 4. Data

**Primary corpus:** California DMHC Independent Medical Review (IMR) Determinations — all external-review decisions since 2001-01-01. Tens of thousands of cases; upstream is periodically republished as a whole file, so v1 builds against one pinned, sha256-identified snapshot and refresh is an explicit, deliberate act (OQ-1.3).

- Dataset page: https://data.chhs.ca.gov/dataset/independent-medical-review-imr-determinations-trend
- Mirror: https://catalog.data.gov/dataset/independent-medical-review-imr-determinations-trend
- Expected fields (verify against actual download; enforce with a schema contract test): `ReferenceID`, `ReportYear`, `DiagnosisCategory`, `DiagnosisSubCategory`, `TreatmentCategory`, `TreatmentSubCategory`, `Determination` (Upheld / Overturned — the label), `Type` (Medical Necessity / Experimental-Investigational / Urgent Care), `AgeRange`, `PatientGender`, `Findings` (free-text reviewer narrative, typically a few hundred words).

**Data handling rules (non-negotiable):**
1. Store raw downloads immutably in `data/raw/` (gitignored) with checksums. **Do not redistribute raw or modified data** — publish only code, derived aggregate artifacts, and small annotated excerpts needed for the gold sets (with source attribution). Terms permit noncommercial use without approval but prohibit altering the provided data; linking to the source is the distribution mechanism.
2. Data is de-identified and public. No re-identification attempts, ever. No PHI enters this repo.
3. Use ICD-10-CM / HCPCS Level II freely if needed (public domain). **Never add CPT descriptors** (AMA-licensed).

**Secondary corpus (v1.1, out of scope for v1):** NY DFS external appeals database (adds insurer names). **Enrichment (v1.1):** Medicare NCD/LCD text, FDA labels, ClinicalTrials.gov, USPSTF. No NCCN (licensed).

## 5. Leakage protocol (core design constraint)

The `Findings` text is written **after** the decision by the reviewer and frequently states the verdict ("the reviewer determined the requested service was medically necessary"). Therefore:

1. **Inference-time contract:** prediction inputs are limited to a **pre-decision case card** — the information a provider actually holds at denial time: patient context, diagnosis, treatment requested, payer's denial rationale, evidence available. Raw `Findings` is **never** a prediction input.
2. **Pipeline:** LLM extraction reconstructs the case card from `Findings` while **scrubbing all outcome/verdict language**.
3. **Scrub validation suite (runs in CI on fixtures):**
   - a. Verdict-language detector (regex battery + LLM audit pass) — residual rate < 2% on an audit sample;
   - b. **Adversarial sentinel:** TF-IDF + logistic regression trained on *raw* Findings vs on *scrubbed* case cards. Raw is expected to score near-perfect (that's the leak); scrubbed must drop to a plausible range. Both numbers are reported in every eval report;
   - c. Human spot-check, n=50, checklist logged.
4. **Framing:** all model outputs are labeled *"external-review overturn likelihood"* — these cases already survived internal appeal (selection bias). This caveat appears in the model card and the UI.
5. Raw `Findings` may be used for retrieval display and generation grounding **with citation**, since those are human-in-the-loop surfaces, not prediction inputs.

Ruled as OQ-0.1 in OQ.md (2026-08-16), which also carries the precedent-channel amendment; this section is the protocol's source text. Application note (OQ-1.4): the corpus also carries `IMRType`, `DaysToReview` and `DaysToAdopt`; the two `Days*` fields measure the review itself and are never prediction inputs, `IMRType` is set at filing and is prediction-eligible, with the nuance documented in the model card.

## 6. System architecture

```
 CA IMR CSV ──► ingest ──► validate (schema contract) ──► data/interim (parquet)
                                                              │
                                   ┌──────────────────────────┤
                                   ▼                          ▼
                          LLM extraction ──► scrub ──► case_cards (validated JSON)
                                   │                          │
                                   ▼                          ▼
                        DuckDB warehouse (star-ish schema: dim_case, fact_determination,
                        case_cards, evidence)  ◄── loaders ───┘
                                   │
              ┌────────────────────┼─────────────────────┬───────────────────┐
              ▼                    ▼                     ▼                   ▼
      BM25 + dense index    overturn predictor    letter generator     NL analytics
      (+ optional rerank)   (LGBM, calibrated)    (LLM, grounded,      (text2SQL over
              │                    │               cited)              semantic layer)
              └────────────┬──────┴──────────┬──────────┴───────────┐
                           ▼                 ▼                      ▼
                      FastAPI service  ◄──────────────────►  React/Vite UI
                           ▲
                     evals harness (standalone, runs against every layer)
```

## 7. Tech stack (defaults — change only via OQ ruling)

> The **LLM** and **Service/UI** bullets below supersede this PRD's earlier defaults (Anthropic API client + budget cap; Streamlit) per **OQ-0.2** and **OQ-0.3**, ruled 2026-08-16.

- **Language/env:** Python 3.11+, `uv` for env + lockfile, `ruff` + `pytest` + `pre-commit`.
- **Warehouse:** DuckDB; Parquet artifacts; `polars` (or pandas where simpler).
- **LLM:** No Anthropic API client module and no budget cap. All LLM stages (extraction, scrub audit, annotation, generation, LLM-judge) are executed as **Claude Code agent/skill workflows** under the owner's Max subscription: Opus-class (`claude-opus-5`) for judgment-heavy surfaces (annotation, scrub audit, LLM-judge), Haiku-class (`claude-haiku-4-5`) for bulk full-corpus passes. Every stage writes **versioned JSONL/parquet artifacts with prompt hashes** for reproducibility — the artifact is the unit of provenance, not an API call log. Runtime inference for the v1.1 chatbot: local models behind a **LiteLLM-compatible interface**.
- **Embeddings:** local `sentence-transformers` (e.g., `BAAI/bge-small-en-v1.5`) for zero-cost reproducibility. OQ ruling required to switch to API embeddings.
- **Retrieval:** `rank_bm25` (or DuckDB FTS) + cosine over local embeddings (numpy/FAISS — corpus is small); optional cross-encoder rerank (`ms-marco-MiniLM`) in Phase 4 if judged-set results warrant.
- **Prediction:** scikit-learn baselines, LightGBM main model, sklearn calibration, SHAP for drivers.
- **Validation:** `pydantic` for case-card schema; `pandera` (or pydantic) for dataframe contracts.
- **Service/UI:** FastAPI backend + **React/Vite** frontend using the owner's design system (design assets delivered when the UI phase starts). Streamlit is dropped.
- **Experiment tracking:** lightweight — JSONL runs + `docs/evals/*.md` reports. (MLflow only if this becomes painful; rule it in OQ.md.)
- **Config:** YAML + `pydantic-settings`. Seeds pinned everywhere.

## 8. Repository layout

```
rePeal/
├── README.md            # rewritten in Phase 8; stub in Phase 0
├── PRD.md               # this file
├── OQ.md                # every decision: open questions, rulings, who made them, when they landed
├── ROLLER.md            # rolling backlog: the work rulings produce, one item per ruling
├── docs/
│   ├── evals/           # eval reports per layer, ablation tables
│   └── data-card.md
├── data/                # gitignored: raw/ interim/ processed/
├── src/repeal/
│   ├── ingest/  extract/  scrub/  warehouse/
│   ├── retrieval/  predict/  generate/  analytics/
│   └── evals/  api/
├── frontend/            # React/Vite (OQ-0.3)
├── notebooks/           # EDA only; anything load-bearing graduates to src/
├── tests/               # synthetic fixtures only, generated from the schema contract; no real rows (OQ-1.8)
├── Makefile             # setup ingest annotate extract index train eval serve demo
└── pyproject.toml
```

## 9. Execution plan — phases with Definitions of Done

### Phase 0 — Scaffold
Repo structure above; tooling; GitHub Actions CI (lint + tests); decision records — leakage protocol, execution model, UI stack, gold sets, folded into OQ.md Phase 0 as OQ-0.1–0.4; `Makefile` targets stubbed.
**DoD:** fresh clone → `make setup && make test` passes; CI green.

### Phase 1 — Ingest + EDA
Downloader with checksum verification; schema contract test against real fields; parquet output. EDA as a tested module (`profile.py`) that renders `docs/evals/eda.md` deterministically from the parquet, no notebook (OQ-1.7): class balance by year/type, category distributions, `Findings` length stats, duplicates/nulls, any surprises. Write `docs/data-card.md`.
**DoD:** `make ingest` idempotently produces validated parquet; EDA report + data card committed.

### Phase 1.5 — Walking skeleton
Thin vertical slice through the whole system before any of it is built properly: extraction over **~100 cases** → minimal DuckDB table → logreg baseline → single-page demo (CLI or minimal React page). Every layer is deliberately the cheapest thing that works; none of it is the Phase 3–8 implementation.
**DoD:** one command produces a prediction + precedent list for a sample case end-to-end.
**Purpose:** de-risk integration before full annotation — surface schema, join, and interface mismatches while they are still cheap to fix.

### Phase 2 — Annotation & gold sets
Define the **case-card JSON Schema**: `patient_context`, `diagnosis_norm`, `treatment_requested`, `denial_basis` (enum: medical_necessity | experimental_investigational | urgent), `payer_rationale`, `evidence_cited[]` (typed: guideline | peer_reviewed_study | fda_status | clinical_trial | expert_opinion), `guideline_refs[]`, `scrub_flags`. Stratified sample of **250 cases** (by type × determination × era), annotated by a **multi-agent Claude Code workflow** (OQ-0.4): independent annotator agents label each case blind to one another, disagreements escalate to a resolver pass, and the owner human spot-checks a stratified tier of **n ≥ 25** (weighted toward escalated/low-agreement cases). Agreement is reported at two levels: **inter-agent agreement** across the full 250, and **human–agent agreement** on the spot-check tier. Also author: **50 retrieval queries** (the queries only — their pooled relevance judgments are authored in Phase 4), and a **30-case generation rubric set**.
**Published gold files contain `ReferenceID`s + annotations + a join script only — never `Findings` text** (OQ-0.4; consistent with §4's no-redistribution rule).
**DoD:** versioned gold files + annotation guide committed; both agreement statistics reported; owner spot-check log committed.

### Phase 3 — Extraction + scrub pipeline
LLM extraction with structured JSON output, retries, caching; run over full corpus. Per-field precision/recall/F1 vs gold; error taxonomy in `docs/evals/extraction.md`. Implement scrub + **full OQ-0.1 (PRD §5) validation suite**; wire leakage sentinel into CI on fixtures.
**DoD:** eval report meets §3 targets or documents the gap with analysis; sentinel numbers (raw vs scrubbed AUC) published.

### Phase 4 — Warehouse + retrieval
DuckDB schema + loaders. Hybrid retrieval (BM25 + dense; rerank optional). **Author the pooled relevance judgments here** for the 50 queries written in Phase 2 — pooling requires candidate lists from the Phase 4 systems, so the judgments cannot exist before this phase. Evaluate Recall@k / nDCG on the judged set; ablation table (BM25-only vs dense-only vs hybrid vs +rerank).
**DoD:** hybrid ≥ each single method on the judged set; indexes rebuild reproducibly via `make index`; and Recall@10 ≥ 0.70 on the judged set or an OQ ruling + gap analysis.

### Phase 5 — Overturn predictor
Baselines in strict order: majority class → logreg(structured fields) → logreg(TF-IDF **scrubbed** text — doubles as leakage sentinel) → LightGBM(structured + extracted features) → LLM few-shot with retrieved precedents (small eval subset only, for cost). **Temporal split** (train ≤ cutoff year, test after) to mimic deployment; **the cutoff year is fixed during Phase 1 EDA via OQ ruling (OQ-1.5)** (working proposal: train ≤ 2021, test 2022+) and not re-tuned afterwards. Report AUC/PR, reliability plot, ECE, SHAP top drivers. Write model card with selection-bias caveats per OQ-0.1.
**DoD:** calibrated model card in `docs/evals/`; all baseline numbers in one table.

### Phase 6 — Grounded letter generation
Input: case card + top-k precedents (+ optional static guideline snippets). Output: appeal letter with inline citation markers mapping to source IDs. Hard rules in prompt + post-generation checker: **no uncited factual claims, no fabricated citations**; omit sections when evidence is absent. Evals: automated citation-faithfulness check + LLM-judge rubric (structure, specificity, tone) validated against owner's human scores on the 30-case set.
**DoD:** citation-faithfulness meets the §3 target on the rubric set or an OQ ruling + gap analysis; 5 sample letters (good + failure cases) committed.

### Phase 7 — NL analytics agent (text2SQL) *(cuttable to v1.1 — owner decision 2026-08-16)*
Semantic layer YAML (table/column descriptions; metric definitions, e.g., `overturn_rate`). NL → SQL over DuckDB: read-only connection, table allowlist, self-correction loop on execution errors. Author **40 question/gold-SQL pairs** (mix: trend, cohort, category, evidence-type questions); report execution accuracy.
**DoD:** ≥ 85% execution accuracy or documented gap; eval set committed.

### Phase 8 — Service, UI, ship
FastAPI: `/case` (intake), `/predict`, `/precedents`, `/draft_letter`, `/ask`. **React/Vite** flow built on the owner's design system (OQ-0.3): denial intake form → likelihood + drivers → precedent panel → letter editor → analytics tab. UI footer on every page: *"Drafts for professional review — not legal or medical advice. Estimates reflect external-review-stage likelihood only."* Final README (with demo GIF), architecture doc, cost report, model cards, and outlines for two blog posts (the leakage story; eval-first build).
**DoD:** `make demo` runs the full experience locally from a fresh clone.

## 10. Engineering standards (all phases)

- Every LLM stage emits a versioned artifact with its prompt hash and model (per §7 / OQ-0.2); artifacts and agent effort are summarized on the phase's ✅ gate line in `TODO.md` when the gate flips (OQ-P.2). No budget cap — LLM work runs under the owner's Max subscription.
- Unit tests for parsers/scrubber; golden-file tests for prompts; leakage sentinel in CI.
- Reproducibility: pinned lockfile, seeds, deterministic Make targets.
- Docs discipline: an OQ.md ruling for any PRD deviation, with the rejected options recorded in the entry — dead ends are content, not embarrassment; a ROLLER.md item for the work a ruling produces.
- Commit hygiene: commit format `action : description` per CLAUDE.md (all lowercase); one phase = one reviewable PR (or PR series).

## 11. Out of scope (v1)

Real PHI/EHR integration; payer submission APIs; NY DFS corpus; live guideline ingestion; model fine-tuning; multi-user auth; cloud deployment (local demo only; a hosted demo is a v1.1 decision).

## 12. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Residual verdict leakage inflates metrics | OQ-0.1 (PRD §5) suite in CI; publish raw-vs-scrubbed sentinel gap; human audit |
| LLM extraction throughput over full corpus | Haiku-class for bulk passes + Opus-class for gold/audit (§7); sample-first runs; artifacts cached and resumable so a re-run never repeats completed work |
| `Findings` text messy/truncated in places | quality flags at ingest; exclude-and-report policy |
| Targets in §3 prove unrealistic | revise via OQ ruling with evidence — never silently |
| Category taxonomy drift across 20+ years | versioned legacy→new crosswalk canonicalizing to the 2026 ICD-10-chapter vocabulary at category level, raw labels preserved, unknown labels passed through and counted (OQ-1.2) |
| Licensing missteps | no raw-data redistribution; no CPT descriptors; attribution in data card |

## 13. Open decisions (owner, not Claude Code)

**Resolved:**
- Final project name → **`repeal`** (2026-08-16).
- Gold-set public release → **yes: ReferenceIDs + annotations + join script only, never `Findings` text**, with a methodology note (2026-08-16; OQ-0.4).

**Still open**, tracked as OQ-0.9 (blog platform) and OQ-0.10 (v1.1 priority) in OQ.md.

## 14. Kickoff instruction

> Claude Code: read this PRD fully, then execute **Phase 0** only. Produce the scaffold, the leakage-protocol ruling (OQ-0.1), and CI. Stop at the DoD, record anything in this PRD you found ambiguous as OQ.md entries, and wait for owner review before Phase 1.