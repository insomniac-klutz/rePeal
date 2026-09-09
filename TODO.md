# TODO — phase tracker

Phases follow PRD §9. Each phase stops at its Definition of Done for **owner review** — that
boundary is what "sequential phases" means; work *inside* a phase runs in parallel via agent
teams (OQ-0.2).

**Auto-update rule (`CLAUDE.md`):** flip `- [ ]` → `- [x]` for every completed item and its
children, and replace the `⛔` gate line with `✅ **Phase N complete — N tests passing**` the
moment tests confirm the gate passes. Don't wait to be asked.

**Ledgers:** [OQ.md](OQ.md) — every call and who made it · [ROLLER.md](ROLLER.md) — the work rulings produce. The 2026-08-16 decision records live in OQ.md Phase 0 as OQ-0.1–0.4.

---

## Phase 0 — Scaffold

- [x] `.gitignore` + naming cleanup — `data/` ignored per PRD §4; single project name `repeal` across PRD, `src/`, README
- [x] Dev toolchain + lockfile — `uv` env, Python 3.11+, `ruff`, `pytest`, committed `uv.lock`
- [x] Decision records — leakage protocol, execution model, UI stack, gold sets *(written as ADR-001…004 and a first build log; folded into OQ.md Phase 0 as OQ-0.1–0.4 on 2026-09-09)*; `docs/data-card.md` stub; `TODO.md`
- [x] Package skeleton per PRD §8 with smoke tests → `tests/test_smoke.py`
- [x] Pre-commit hooks (`ruff` + `uv run pytest`) + `scripts/install-hooks.sh`
- [x] `Makefile` targets stubbed: `setup ingest annotate extract index train eval serve demo`
- [ ] GitHub Actions CI (lint + tests) green on `maestro` *(pending first push to origin)*

✅ **Phase 0 complete — 8 tests passing** *(local gate: fresh clone → `make setup && make test` verified; CI item above confirms on first push)*

---

## Phase 1 — Ingest + EDA

Design: OQ-1.0 in OQ.md (HLD, proposed 2026-08-16). Nothing spawns until OQ-1.0–1.11 are ruled.

- [ ] Downloader with checksum verification → immutable `data/raw/`, idempotent `make ingest` → `src/repeal/ingest/download.py` → `tests/test_download.py`
- [ ] Schema contract test against the **real** field list; parquet output to `data/interim/` → `schema.py`, `run.py` → `tests/test_ingest.py`, `tests/test_schema_contract.py`
- [ ] Category normalization map for 20+ years of taxonomy drift — versioned → `normalize.py` + `resources/category_crosswalk_v1.yaml` → `tests/test_normalize.py`
- [ ] Quality flags for messy/truncated `Findings`; exclude-and-report policy → `quality.py` → `tests/test_quality.py`
- [ ] EDA — tested module + markdown renderer, not a notebook *(vehicle pending OQ-1.7)* → `profile.py` → `tests/test_profile.py`; renders `docs/evals/eda.md` — class balance by year/type, category distributions, `Findings` length stats, duplicates/nulls, surprises
- [ ] Populate `docs/data-card.md`; **define the temporal cutoff year** (fixed by the ruling on OQ-1.5) that Phase 5's split depends on

⛔ Phase 1 gate: `uv run pytest` green + DoD met — `make ingest` idempotently produces validated parquet; EDA report + data card committed

---

## Phase 1.5 — Walking skeleton *(inserted per owner decision D4)*

Thin end-to-end slice before any layer is built properly — find integration breakage while
there are two components, not six. Everything here is explicitly throwaway.

- [ ] ~100-case extraction slice (real prompt, real artifact shape, no full-corpus run)
- [ ] Minimal DuckDB load of that slice → `tests/test_skeleton_slice.py`
- [ ] Logistic-regression baseline on the slice — end-to-end wiring only, numbers are not claims
- [ ] Single-page demo joining the three *(hand-written; the design zip is not available yet — OQ-0.3)*
- [ ] Record what broke at the seams as OQ.md entries — that's the deliverable

⛔ Phase 1.5 gate: `uv run pytest` green + DoD met — one command runs slice → DuckDB → prediction → page

---

## Phase 2 — Annotation & gold sets

- [ ] **Case-card JSON Schema** (pydantic): `patient_context`, `diagnosis_norm`, `treatment_requested`, `denial_basis` (enum), `payer_rationale`, `evidence_cited[]` (typed), `guideline_refs[]`, `scrub_flags` → `tests/test_case_card_schema.py`
- [ ] Stratified sample of **250 cases** (type × determination × era) → `tests/test_sampling.py`
- [ ] Multi-agent annotation workflow: N independent annotators with differing prompts → disagreement-driven adjudicator pass (OQ-0.4) → `tests/test_annotation.py`
- [ ] CLI annotation/review tool *(Streamlit dropped — OQ-0.3)*; owner human spot-check tier **n ≥ 25**, over-sampled on disagreement
- [ ] Agreement stats reported: inter-agent agreement per field, escalation rate, adjudicator override rate, human correction rate + annotation guide **including the circularity limitation**
- [ ] **50 retrieval queries** (pooled judgments assembled in Phase 4 once retrievers exist) + **30-case generation rubric set**
- [ ] Release packaging: ReferenceIDs + annotations + **join script** against the source download, never `Findings` → `tests/test_join_script.py`; finalize the data-card terms determination

⛔ Phase 2 gate: `uv run pytest` green + DoD met — versioned gold files + annotation guide committed; agreement stats reported

---

## Phase 3 — Extraction + scrub pipeline

- [ ] LLM extraction with structured JSON output + retries, run over the full corpus as a Claude Code workflow (`claude-haiku-4-5`, OQ-0.2); artifacts carry `prompt_hash` / `prompt_version` / `model` → `tests/test_extract.py`
- [ ] Scrub implementation — strip all outcome/verdict language → `tests/test_scrub.py`
- [ ] **Full OQ-0.1 (PRD §5) validation suite:** verdict-language regex battery + LLM audit (residual < 2%), human spot-check n=50 with logged checklist
- [ ] **Adversarial leakage sentinel** — TF-IDF + logreg on raw `Findings` vs scrubbed case cards; wired into CI on fixtures → `tests/test_leakage_sentinel.py`
- [ ] Per-field precision/recall/F1 vs the gold set + error taxonomy → `docs/evals/extraction.md`, carrying the OQ-0.4 circularity caveat

⛔ Phase 3 gate: `uv run pytest` green + DoD met — eval report meets §3 targets or documents the gap with analysis; raw-vs-scrubbed sentinel numbers published

---

## Phase 4 — Warehouse + retrieval

- [ ] DuckDB star-ish schema + loaders: `dim_case`, `fact_determination`, `case_cards`, `evidence` → `tests/test_warehouse.py`
- [ ] BM25 + dense (local `sentence-transformers`) hybrid retrieval; optional cross-encoder rerank if the judged set warrants → `tests/test_retrieval.py`
- [ ] **Two distinct retrieval surfaces** (OQ-0.1 amendment): display records (may include cited `Findings`) vs case-card projections for prediction (never `Findings`) → `tests/test_retrieval_surfaces.py`
- [ ] Assemble pooled relevance judgments for the Phase 2 query set from the systems now built
- [ ] Recall@k / nDCG on the judged set + ablation table (BM25-only vs dense-only vs hybrid vs +rerank) → `docs/evals/retrieval.md`
- [ ] `make index` rebuilds indexes reproducibly (pinned seeds)

⛔ Phase 4 gate: `uv run pytest` green + DoD met — hybrid ≥ each single method on the judged set; indexes rebuild reproducibly

---

## Phase 5 — Overturn predictor

- [ ] Baselines in strict order: majority class → logreg(structured) → logreg(TF-IDF **scrubbed** text, doubles as sentinel) → LightGBM(structured + extracted) → `tests/test_predict.py`
- [ ] LLM few-shot with retrieved precedents on a small eval subset — precedents as **(scrubbed case card + `Determination`) only**, pre-query-year pool, self-excluded → `tests/test_precedent_pool.py`
- [ ] **Temporal split** (train ≤ cutoff year from Phase 1, test after) → `tests/test_temporal_split.py`
- [ ] Calibration + metrics: AUC/PR, reliability plot, **ECE**, SHAP top drivers; set the AUC floor via OQ ruling once the logreg baseline lands
- [ ] Model card in `docs/evals/` with selection-bias caveat (OQ-0.1 §4) **and** the OQ-0.4 circularity disclosure; all baseline numbers in one table

⛔ Phase 5 gate: `uv run pytest` green + DoD met — calibrated model card committed; all baseline numbers in one table

---

## Phase 6 — Grounded letter generation

- [ ] Generator: case card + top-k precedents (+ optional static guideline snippets) → appeal letter with inline citation markers mapping to source IDs → `tests/test_generate.py`
- [ ] Hard rules in prompt **and** post-generation checker: no uncited factual claims, no fabricated citations, omit sections when evidence is absent → `tests/test_citation_checker.py`
- [ ] Automated citation-faithfulness eval (define the denominator — per claim, not per letter)
- [ ] LLM-judge rubric (structure, specificity, tone) validated against owner human scores on the 30-case set → `tests/test_judge.py`
- [ ] 5 sample letters committed — **good and failure cases** → `docs/evals/generation.md`

⛔ Phase 6 gate: `uv run pytest` green + DoD met — faithfulness ≥ 95% on the rubric set; 5 sample letters committed

---

## Phase 7 — NL analytics agent (text2SQL) — **cuttable to v1.1** *(owner decision D4)*

Explicitly droppable if schedule pressure hits. Cut it as a whole; don't ship a half-version.

- [ ] Semantic layer YAML — table/column descriptions, metric definitions (e.g. `overturn_rate`) → `tests/test_semantic_layer.py`
- [ ] NL → SQL over DuckDB: **read-only connection**, table allowlist, self-correction loop on execution errors → `tests/test_text2sql.py`
- [ ] **40 question/gold-SQL pairs** (trend, cohort, category, evidence-type) committed
- [ ] Execution-accuracy report → `docs/evals/analytics.md`

⛔ Phase 7 gate: `uv run pytest` green + DoD met — ≥ 85% execution accuracy or documented gap; eval set committed

---

## Phase 8 — Service, UI, ship

> **Blocked on the owner's "claude design zip"** — UI work cannot start before it is delivered (OQ-0.3).

- [ ] FastAPI: `/case`, `/predict`, `/precedents`, `/draft_letter`, `/ask` → `tests/test_api.py`
- [ ] React/Vite frontend on the owner's design system (OQ-0.3): denial intake → likelihood + drivers → precedent panel → letter editor → analytics tab
- [ ] Disclaimer footer on **every** page: *"Drafts for professional review — not legal or medical advice. Estimates reflect external-review-stage likelihood only."*
- [ ] `make demo` runs the full experience locally from a fresh clone (Vite + uvicorn) → `tests/test_demo_smoke.py`
- [ ] Final README with demo GIF, architecture doc, model cards, and the **effort report** *(no dollar costs — OQ-0.2)*
- [ ] Outlines for two blog posts: the leakage story; eval-first build

⛔ Phase 8 gate: `uv run pytest` green + DoD met — `make demo` runs the full experience from a fresh clone
