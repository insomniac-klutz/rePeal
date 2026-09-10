# OQ — open questions and rulings

This file is the ledger of every call made on this project and who made it —
architecture and process decisions alike, kept next to `PRD.md` and `TODO.md`. Ruled
entries stay forever; deleting from it is deleting history. An entry is `- [ ]` while
open and `- [x]` once ruled. Every entry a session writes carries `[s:xxxxxxxx]` right
after the checkbox — the first 8 hex characters of that Claude Code session's id — a
stable `OQ-<section>.<n>` ID (never reused; other docs cite it), the question,
**Context**, **Options**, **Assumed** (the call the lead made to keep building without
waiting on an answer), a **Recommendation**, then `Ruled <date>:` with the caller's
decision and `Landed <hash>` once it's in the tree.

A session's lead commits nothing while an entry carrying that session's tag is open here
or in `ROLLER.md` — checked with `grep -nE '^\s*- \[ \] \[s:<tag>\]' OQ.md ROLLER.md`,
which must print nothing before `git add`. Entries dated before the 2026-09-09 cutover
carry no tag: ruled ones are closed history, open ones are owner-open carry-overs that
gate no session's commits.

A ruling that requires a code change gets exactly one `ROLLER.md` item, cross-referenced
both ways — `ROLLER: R-nn` here, `OQ: <section> — "<first words>"` there — and the same
`Landed` closes both. Questions surface the minute they exist — a scout's, a teammate's,
the lead's own — appended under the phase they belong to and tagged with the building
session's id, never held for a recap or parked in a plan file with a question mark
standing in for tracking. `PRD.md` and `TODO.md` track the phased work; this file tracks
the calls that shaped it.

---

## Process

- [x] [s:53ce5611] OQ-P.1 — Decision-tracking model: ADRs and build logs, or OQ.md and ROLLER.md — and where the ledgers live.
  **Context.** PRD v0.1 mandated an ADR in `docs/adr/` for every deviation plus weekly
  build logs in `docs/logs/`. `CLAUDE.md`, rewritten 2026-09-09, mandates `OQ.md` /
  `ROLLER.md` and its commit gate greps `OQ.md ROLLER.md`, which did not exist. The
  Phase 1 HLD and its 11 open questions were sitting untracked under `docs/ascension/`
  and `docs/oqs/`, in a shape that was not the house shape.
  **Options.** (a) keep the ADRs frozen under `docs/adr` with a banner and use OQ/ROLLER
  for new calls only; (b) fold everything under `docs/` into the two root files, git
  history keeping the originals; (c) stay on ADRs.
  **Recommendation at the time:** (a).
  **Ruled 2026-09-09:** owner — (b): "we have moved away from adr model to oq/roller
  model" and "essentially entire docs fold into my two root files"; the ledgers live at
  the repo root next to `PRD.md` and `TODO.md`.
  **Landed:** 1dd64c9 (`refactor : fold adrs oqs hld and logs into oq and roller ledgers`) · **ROLLER:** R-01.

- [x] [s:53ce5611] OQ-P.2 — Fold scope: what, if anything, stays under `docs/`.
  **Context.** After the fold, `docs/` would hold only `docs/data-card.md` (a PRD Phase
  1 DoD deliverable — a data card is a product artifact readers of the model card
  expect) and `docs/evals/` (Phase 3–7 DoD deliverables: `eda.md`, `extraction.md`,
  `retrieval.md`, the model card, `generation.md`, `analytics.md` — all named by path in
  PRD §9). The owner said "essentially entire docs", and "essentially" is doing work.
  **Options.** (a) fold the process docs (`docs/adr`, `docs/logs`, `docs/oqs`,
  `docs/ascension`, the ADR and log templates) and keep `docs/data-card.md` and
  `docs/evals/` as product artifacts; (b) fold literally everything — the data-card
  content becomes OQ-0.1 context and `docs/evals/` returns when Phase 3 needs it; (c)
  keep `docs/logs/` weekly logs too.
  **Assumed:** (a) — the DoDs name those two paths and a data card is not a call.
  **Recommendation:** (a).
  **Note.** Either way, PRD §10's "weekly log in `docs/logs/`" and §1's "(ADRs + weekly
  build logs)" get rewritten so the ledgers are the trail; cipher-sweeper is doing that
  now on the same assumption. OQ-0.2's Consequences still describe per-phase
  agent/workflow effort as recorded "in build-log entries" — that wording stands as
  ruled 2026-08-16 and isn't retroactively edited. Assumed: the record itself moves to
  `TODO.md`'s ✅ gate line, which carries the effort note (agents, passes, wall-clock)
  when each phase's gate flips.
  **Ruled 2026-09-09:** owner — (a): "ok do it" on the recommendation; `docs/data-card.md`
  and `docs/evals/` stay, everything else under `docs/` is folded. · **Landed:** 1dd64c9 (`refactor :
  fold adrs oqs hld and logs into oq and roller ledgers`) · **ROLLER:** —
  (the work is R-01).

- [x] [s:53ce5611] OQ-P.3 — CLAUDE.md carries other-repo residue: fix it in this pass, or owner-only edits.
  **Context.** `CLAUDE.md` is tracked by git (its own line 195 says it is gitignored; it
  is not) and carries four lines from the repo it was ported from: line 195 "(moved from
  the repo root on 2026-09-09: … gitignored …)"; line 229 "PACK_PLAN's old Phase H,
  moved out on 2026-09-04"; line 238 "PACK_PLAN and DOCPRO_PLAN track the phased work";
  and the TDD section's "Phases are A through G, defined in TODO.md" (this repo's
  phases are 0–8). The file is open in the owner's IDE with an uncommitted rewrite (317
  lines in, 86 out today), so any commit of it carries that rewrite.
  **Options.** (a) fix exactly those four lines in this pass, nothing else in the file;
  (b) the owner edits `CLAUDE.md`, nobody else touches it.
  **Assumed:** (a) — minimal, reversible, and the gate grep needs the paths to be true.
  **Recommendation:** (a).
  **Ruled 2026-09-09:** owner — (a): "ok do it" on the recommendation; the four lines stay
  fixed, nothing else in the file touched. · **Landed:** 1e25ae4 (`update : claude.md ledger paths and
  phase names`) · **ROLLER:** — (covered by R-01).

---

## Phase 0 — Scaffold

Phase 0 ran 2026-08-16 (ISO week 2026-33). A multi-agent PRD review produced 43 verified
findings — naming drift across `overturn` / `mimir` / `repeal`, the missing `data/`
gitignore, the Phase 2 / Phase 4 pooling contradiction, the undefined temporal cutoff,
unmeasurable §3 metric definitions, and the PRD-vs-`CLAUDE.md` sequential-vs-teams
conflict. The scaffold itself was built by four teammates on disjoint files:
`phantom-amender` (PRD), `cipher-scribe` (ADRs, build log, data card, TODO),
`vortex-toolsmith` (toolchain, Makefile, pre-commit, CI), `blitz-skeleton` (package
skeleton + smoke tests). $0 API cost, by design (OQ-0.2).

- [x] OQ-0.1 — Leakage protocol (ex-ADR-001).
  **Context.** `Findings` is written after the decision and routinely states the
  verdict; any model trained on it scores near-perfectly and means nothing. The PRD
  fixed the protocol as a design constraint and instructed that §5 be committed
  verbatim.
  **Decision.** Protocol text: PRD §5, five clauses — inference-time contract
  (predictions run on a pre-decision case card only, raw `Findings` never a prediction
  input), extraction+scrub pipeline, a three-part validation suite (verdict-language
  detector, adversarial TF-IDF/logreg sentinel on raw vs. scrubbed, human spot-check
  n=50), external-review framing (selection-bias caveat), and retrieval/generation may
  use raw `Findings` with citation since those are human-in-the-loop surfaces. Full
  text lives at PRD §5 — not duplicated here.

  **Amendment (precedent channel), verbatim from ADR-001:**
  The PRD §9 Phase 5 baseline ladder ends with an **LLM few-shot predictor using
  retrieved precedents**. That path can smuggle raw `Findings` back into the prediction
  surface through the retrieval channel, which clause 5 above permits *only* for
  human-in-the-loop display and generation grounding. This amendment closes that gap.

  When retrieved precedents feed the Phase 5 LLM few-shot predictor:

  1. **Precedent representation:** each precedent is represented as **(scrubbed case
     card + `Determination` label) ONLY**. Raw `Findings` text is never placed in the
     predictor's prompt — not as context, not as a citation, not in truncated form. The
     retrieval layer used for prediction returns case-card projections, not display
     records.
  2. **Temporal restriction:** the precedent pool for any test-set prediction is
     restricted to cases decided **strictly before the query case's `ReportYear`**. This
     mirrors the Phase 5 temporal split (train ≤ cutoff, test after) and prevents
     future decisions from informing past-facing predictions.
  3. **Self-exclusion:** the query case is always excluded from its own precedent pool,
     as are exact-duplicate `ReferenceID`s surfaced by the retrieval layer.

  These three constraints are enforced in code at the precedent-assembly boundary and
  covered by tests, not left to prompt discipline.

  **Consequences.** Positive: every published prediction number is defensible; the
  raw-vs-scrubbed sentinel gap becomes a headline artifact rather than a hidden caveat.
  Cost: the few-shot predictor is handicapped relative to a naive implementation and
  will look worse than a leaky version would — that is the point, the gap is reported,
  not fixed. Follow-ups: Phase 4 retrieval must expose two distinct retrieval surfaces
  (display records vs. case-card projections for prediction); Phase 5 must include a
  test that fails if raw `Findings` appears in any predictor prompt, and a test
  asserting the temporal + self-exclusion filters on the precedent pool.
  **Ruled 2026-08-16:** owner — commit PRD §5 verbatim as the leakage protocol, extended
  with the precedent-channel amendment enforced in code, not prompt discipline.
  **Landed:** 28b17eb · **ROLLER:** —

- [x] OQ-0.2 — Execution model (ex-ADR-002).
  **Context.** PRD §7 specified the Anthropic API via the official SDK behind one
  client module (`src/repeal/llm_client.py`) with content-hash caching, retries, JSONL
  cost logging, and a hard budget cap via env var; PRD §12 listed "LLM extraction cost
  over full corpus" as a top risk. The owner runs this project on a Claude Max
  subscription through Claude Code, where the same work executes as agent/skill
  workflows at zero marginal API cost — the client, the cost meter, and the budget cap
  were guarding a constraint that doesn't apply. Reproducibility still needs a carrier
  once metered API calls are gone.
  **Decision.** No Anthropic API client module, no budget cap; `llm_client.py` removed
  from the layout. All LLM stages (full-corpus extraction, scrub audit, gold-set
  annotation, letter generation, LLM-judge) run as Claude Code agent/skill workflows
  under the owner's Max plan. Model assignment by surface: `claude-opus-5` for
  judgment-heavy work (annotation, scrub audit, generation, judge), `claude-haiku-4-5`
  for bulk full-corpus extraction — supersedes the PRD's `claude-sonnet-4-6` default.
  Artifacts are the contract: every LLM stage emits versioned JSONL/parquet carrying
  prompt hash + prompt version + model id + workflow name; downstream phases consume
  artifacts, never live model calls. Runtime inference for the v1.1 chatbot: local
  models behind a LiteLLM-compatible interface, same artifact/response contract,
  swappable backend. Development uses agent teams within a phase — the PRD's
  "sequential phases" governs phase order and the owner-review boundary at each DoD,
  not intra-phase parallelism. Commit format `action : description`, superseding the
  PRD's conventional-commits requirement.
  **Rejected.** (a) build the API client anyway "for portability" — real complexity now
  for a hypothetical backend later; (b) keep the budget cap as a no-op — dead config
  that lies about how the system runs; (c) the `llm_client.py` gateway itself — a
  genuinely good design for a metered project, but under a Max subscription it's an
  elaborate guard around a constraint that doesn't exist, and its cost telemetry would
  have logged zeros forever. Abandoned before a line was written; the tell was that PRD
  §12's cost risk and §7's budget cap both traced to one assumption nobody had
  rechecked.
  **Consequences.** Positive: zero API cost, no key management, no budget-cap failure
  mode mid-run, bulk/judgment model split preserved without a config layer. Cost: no
  per-call cost telemetry — PRD §10's "costs summarized per phase" can't be satisfied in
  dollars, replaced by artifact + prompt-hash logging and build-log entries recording
  agent/workflow effort instead; reproducibility depends on committed artifacts rather
  than replayable API calls — an exact re-run isn't guaranteed byte-identical, the
  committed artifact is the reproducible unit, and every eval number must cite the
  artifact version it was computed from; PRD §12's cost-risk row is void, residual risk
  is wall-clock and agent effort, not spend. Follow-ups: a future API backend or the
  v1.1 local-model backend can drop in behind the same artifact contract; artifact
  schema (`prompt_hash`, `prompt_version`, `model`, `workflow`) fixed in Phase 3 before
  full-corpus extraction.
  **Ruled 2026-08-16:** owner — no API client, no budget cap; agent/skill workflows
  under the Max plan, artifacts (not API logs) carry the reproducibility contract.
  **Landed:** 28b17eb · **ROLLER:** —

- [x] OQ-0.3 — UI stack (ex-ADR-003).
  **Context.** PRD §7 chose FastAPI + Streamlit, trading polish for v1 speed ("React is
  a v2 decision"); Streamlit was also the suggested Phase 2 annotation surface and
  Phase 8's DoD was a Streamlit flow (intake → likelihood/drivers → precedent panel →
  letter editor → analytics tab). Two things changed the calculus: the demo audience is
  a recruiter who must grasp the system in five minutes, so the UI is the portfolio
  surface and Streamlit's ceiling is visibly low for a letter-drafting product story;
  and the owner already has a design system (a "claude design zip") that drops the cost
  of a real frontend well below its usual price. The speed argument for Streamlit was
  the whole argument, and it stopped holding.
  **Decision.** React + Vite in top-level `frontend/`, styled with the owner's design
  system supplied when the UI phase begins. FastAPI stays as the API layer, unchanged
  in scope — `/case /predict /precedents /draft_letter /ask` — the frontend is a pure
  client of that contract. Phase 2 annotation tooling falls back to a CLI rather than
  waiting on the zip or building throwaway UI. The mandatory disclaimer footer ("Drafts
  for professional review — not legal or medical advice. Estimates reflect
  external-review-stage likelihood only.") is a layout-level component on every page.
  **Rejected.** (a) keep Streamlit for v1 and rewrite in v2 — pays for the UI twice and
  ships the weaker version to the demo audience; (b) hand-roll CSS instead of the
  design zip — slower and worse than the asset the owner already has; (c) Streamlit
  itself, kept on the board through the whole PRD review on the "v1 speed over polish"
  argument — it fell once the zip made a real frontend cheap, since the speed advantage
  was the entire case for it and evaporated with it. Cost of the delay: Phase 2's
  annotation UI had to be re-specified as a CLI.
  **Consequences.** Positive: a demo-grade surface for the primary portfolio artifact; a
  real client/server boundary instead of in-process Streamlit calls; design consistency
  for free from the supplied system. Cost: UI work cannot start before the design zip is
  delivered — a hard external dependency owned by the owner, not the build, and Phase 8
  is blocked on it; a JS toolchain, a second lockfile, and a build step enter the repo,
  `make demo` must orchestrate Vite + uvicorn, CI gains a frontend job; the Phase 1.5
  walking skeleton's single-page demo must be a minimal hand-written page since the
  design system isn't available yet — explicitly throwaway, not the Phase 8 frontend.
  Follow-ups: `frontend/` added to PRD §8's layout; "Streamlit UI" replaced with
  "React/Vite UI" in the §6 diagram; Phase 2's DoD names the CLI annotation tool; the
  design-zip dependency on Phase 8 noted in `TODO.md`.
  **Ruled 2026-08-16:** owner — React/Vite frontend on the owner's design system +
  FastAPI backend; Streamlit dropped entirely, Phase 2 annotation falls back to a CLI.
  **Landed:** 28b17eb · **ROLLER:** —

- [x] OQ-0.4 — Gold-set methodology and public release (ex-ADR-004 + PRD §13).
  **Context.** PRD §9 Phase 2 specifies a stratified 250-case extraction gold set (type
  × determination × era), built by LLM-assisted pre-annotation → human adjudication,
  with a second-pass self-consistency check on 50 cases. OQ-0.2 made many independent
  annotators per case nearly free — an option a metered API budget would have priced
  out — and hand-adjudicating 250 cases end-to-end is the largest single block of owner
  time in the project; spending it on cases where independent annotators already agree
  is waste. Disagreement is the signal worth paying for.
  **Decision.** Keep the 250-case stratified extraction gold set. N independent
  annotator agents per case, each a different prompt/framing (field-by-field,
  narrative-summary-first, skeptical/minimal-extraction, evidence-typing-first), blind
  to each other, each emitting a case card against the Phase 2 JSON Schema tagged with
  its prompt hash. Per-field agreement computed across the N annotations; agreed fields
  accepted as-is, disagreements escalate to an adjudicator pass (a separate agent
  seeing all N candidates + source, reasoning recorded). Owner human tier: n ≥ 25 cases,
  over-sampled on disagreement and adjudicated cases rather than uniform; owner
  corrections override the pipeline unconditionally and are marked. Reported:
  inter-agent agreement per field, escalation rate per field, adjudicator override rate,
  human-tier correction rate — published in the annotation guide and `docs/evals/`.
  Retrieval (50 queries) and generation (30-case rubric) sets follow the same pattern,
  pooled judgments assembled in Phase 4 from the systems actually built there.
  **Circularity limitation, stated plainly.** The same model family annotates the gold
  set and is later evaluated against it — agreement is inter-agent consistency, not
  independent ground truth; a systematic error shared by all N annotators passes the
  adjudicator undetected; F1 against this set is an optimistic upper bound. Mitigated,
  not eliminated, by: prompt diversity (N annotators are not N copies of one prompt);
  the human tier (n ≥ 25, over-sampled on disagreement, an independent read on where
  consensus is wrong); disclosure (restated verbatim in the model card and annotation
  guide).
  **Release policy.** Published gold files contain `ReferenceID`s + annotations + a
  join script against the source download only — never `Findings` text. Terms permit
  noncommercial use without approval but prohibit redistributing or altering the
  provided data; linking to the source is the distribution mechanism. Resolves PRD §13:
  yes, release, with a methodology note.
  **Rejected.** (a) single-annotator pre-annotation + full 250-case human adjudication
  (the PRD default, and the build log's "uniform human adjudication" dead end) —
  correct but spends owner time uniformly instead of on disagreement, abandoned once
  multi-agent annotation became free; it bought a real liability (the circularity
  above) in exchange, now disclosed rather than solved; (b) publishing excerpted
  `Findings` alongside annotations — cleaner for consumers, redistributes provided
  data.
  **Consequences.** Positive: owner effort concentrates where the signal is;
  agreement/escalation/override rates become publishable evidence about annotation
  quality; the workflow scales to retrieval/generation sets at no additional cost.
  Cost: the circularity above permanently caps how strong an extraction claim the
  project can make, every F1 figure must carry the caveat; N annotation passes mean N×
  wall-clock/agent effort per case (no dollar cost, OQ-0.2); consumers must obtain the
  source data themselves, a friction the join script minimizes but can't remove.
  Follow-ups: choose and record N in Phase 2; write the annotation guide including the
  circularity paragraph; add the model-card disclosure item to Phase 5's checklist;
  build and test the join script against a fixture; finalize the terms determination in
  the data card before Phase 2 ships.
  **Ruled 2026-08-16:** owner — keep the 250-case gold set, annotate via multi-agent
  workflow with disagreement escalation and a human tier; release IDs + annotations +
  join script only, never `Findings`.
  **Landed:** 28b17eb · **ROLLER:** —

- [x] OQ-0.5 — Project name.
  **Context.** Working title `overturn`; `mimir` also live in the tree (`CLAUDE.md` was
  ported from a project of that name); three names across the PRD, package path, and
  README.
  **Decision.** `repeal` (repo dir `rePeal`, package `repeal`), tagline "re: your
  denial".
  **Ruled 2026-08-16:** owner — `repeal`.
  **Landed:** 99e066d · **ROLLER:** —

- [x] OQ-0.6 — Scope sequencing (owner decision D4).
  **Context.** Two scope calls made alongside the ADRs; neither is a stack deviation,
  so neither got its own ADR at the time.
  **Decision.** A Phase 1.5 walking skeleton is inserted after Phase 1 (~100-case
  extraction → minimal DuckDB → logreg → single throwaway page, one command end to end)
  to surface schema/join/interface mismatches while they're cheap. Phase 7 (text2SQL)
  is explicitly cuttable to v1.1 — cut whole, never shipped half. Tracked in `TODO.md`.
  **Ruled 2026-08-16:** owner — insert Phase 1.5 as a walking skeleton; Phase 7 stays
  cuttable to v1.1, whole or not at all.
  **Landed:** 28b17eb · **ROLLER:** —

- [ ] OQ-0.7 — Phase 0 gate: owner DoD review and first push to maestro.
  **Context.** `TODO.md` Phase 0's last unchecked box is "GitHub Actions CI green on
  maestro (pending first push)"; `uv run pytest` is green at 8 locally; branch `rep-01`
  is 8 commits ahead of `maestro`, which still sits at the initial commit; CI runs on
  push to `maestro` and on pull requests.
  **Options.** (a) merge/PR `rep-01` → `maestro` now; (b) after Phase 1.
  **Recommendation:** (a) — nothing downstream benefits from waiting, and the gate line
  in `TODO.md` can't flip until CI has actually run.
  **Ruled:** _pending_ · **Landed:** — · **ROLLER:** —

- [ ] OQ-0.8 — Design system delivery ("claude design zip").
  **Context.** OQ-0.3 made all Phase 8 UI work depend on it; the Phase 1.5 page is
  explicitly built without it.
  **Options.** (a) deliver before Phase 6 so the letter editor is designed against it;
  (b) deliver at Phase 8 kickoff.
  **Recommendation:** (a).
  **Ruled:** _pending_ · **Landed:** — · **ROLLER:** —

- [ ] OQ-0.9 — Blog platform (PRD §13).
  **Context.** Phase 8 owes outlines for two posts (the leakage story; the eval-first
  build).
  **Options.** whatever platform the owner already publishes on / a repo-hosted docs
  page / defer.
  **Recommendation:** defer the call until the Phase 8 outlines exist; default to
  wherever the owner already publishes.
  **Ruled:** _pending_ · **Landed:** — · **ROLLER:** —

- [ ] OQ-0.10 — v1.1 priority (PRD §13).
  **Context.** Candidates are the NY DFS external-appeals corpus (adds insurer names),
  the payer-side utilization-management QA flip, and a hosted demo (v1 is local-only).
  **Options.** those three.
  **Recommendation:** hosted demo first — the audience is recruiters and a local-only
  demo is a demo nobody sees — then the NY corpus.
  **Ruled:** _pending_ · **Landed:** — · **ROLLER:** —

---

## Phase 1 — Ingest + EDA

Facts in this section come from live-portal recon on 2026-08-16: CKAN `package_show`,
datastore SQL aggregates over all 42,749 rows, and a byte-range read of the real CSV header —
no full download yet. The design lives in OQ-1.0; the eleven calls it depends on are OQ-1.1
through OQ-1.11, and nothing in Phase 1 spawns until they're ruled. Questions the build
surfaces get appended below as OQ-1.12 onward, each carrying the building session's tag.

- [x] OQ-1.0 — Phase 1 design (HLD, proposed 2026-08-16, awaiting owner approval)
  **Context.** HLD proposed 2026-08-16 from the recon in the preamble above.

  **Objective & gate.** PRD §9: downloader with checksum verification, schema contract test
  against real fields, parquet output; EDA report to `docs/evals/eda.md` (class balance by
  year/type, category distributions, `Findings` length stats, duplicates/nulls, surprises);
  `docs/data-card.md`. Phase 1 additionally owes the temporal cutoff year Phase 5's split
  depends on, the versioned category-normalization map, and the `Findings` quality flags +
  exclude-and-report policy (TODO.md). Gate: `uv run pytest` green + `make ingest`
  idempotently produces validated parquet; EDA report + data card committed.

  **Dataset.** Main CSV, single file, all years, resource
  `3340c5d7-4054-4d03-90e0-5f44290ed095`. True size **85,409,358 bytes** — CKAN's advertised
  size/hash are stale, wrong by 14 MB, and the S3 `ETag` is multipart, not an md5, so a
  self-computed sha256 is the only trustworthy integrity anchor. Last publish **2026-06-01**,
  a periodic full-file republish with no append feed, no per-row date column, no committed
  cadence (`Frequency: "Other"`). Row count **42,749** exact, via datastore (PRD's ~42.7k was
  spot on). The 2020 data-dictionary PDF documents 11 fields, misses 3 real ones, and
  describes a `PaientAge` [sic] number that is actually `AgeRange` text buckets — unusable as
  a contract. The datastore SQL API is live (`datastore_active: true`): arbitrary aggregate
  SQL server-side, enabling a cheap schema-drift/row-count probe without downloading 81 MB.
  The portal URL 302s to a presigned S3 GET; HEAD returns 403, so probes must use ranged GET
  (206 works, `Accept-Ranges` honored).

  **Schema.** 14 fields, not the PRD's 11. Verbatim header order, with the ingest mapping
  this design proposes:

  | # | Source field | → parquet column | Cast | OQ-0.1 class |
  |---|---|---|---|---|
  | 1 | `ReferenceID` | `reference_id` | str | pre-decision (attribute, not unique — see Hazards) |
  | 2 | `ReportYear` | `report_year` | int | temporal axis (era feature; split key) |
  | 3 | `DiagnosisCategory` | `diagnosis_category` (+`_raw`) | str | pre-decision |
  | 4 | `DiagnosisSubCategory` | `diagnosis_subcategory` (+`_raw`) | str | pre-decision |
  | 5 | `TreatmentCategory` | `treatment_category` (+`_raw`) | str | pre-decision |
  | 6 | `TreatmentSubCategory` | `treatment_subcategory` (+`_raw`) | str | pre-decision |
  | 7 | `Determination` | `determination_raw` + **`overturned: bool`** | exact-string map | **label** |
  | 8 | `Type` | `case_type` | str (enum) | pre-decision |
  | 9 | `AgeRange` | `age_range` | str (7 buckets, nullable) | pre-decision |
  | 10 | `PatientGender` | `patient_gender` | str (nullable) | pre-decision |
  | 11 | `IMRType` | `imr_type` | str (Standard/Expedited) | pre-decision, pending OQ-1.4 |
  | 12 | `DaysToReview` | `days_to_review` | int (nullable) | post-decision — never a prediction input |
  | 13 | `DaysToAdopt` | `days_to_adopt` | int (nullable) | post-decision — never a prediction input |
  | 14 | `Findings` | `findings` | str | post-decision narrative — OQ-0.1 surfaces only |

  Plus a synthesized `row_id` surrogate key (source row order, valid within a pinned
  snapshot) because `ReferenceID` cannot be one. `Type`→`case_type` avoids shadowing the
  Python builtin. `DaysToReview`/`DaysToAdopt` measure the review process itself — they don't
  exist at denial time, so OQ-0.1's inference-time contract excludes them from every
  predictor feature set (still ingested: free descriptive signal, and `days_to_review`
  correlates with `imr_type`).

  **Value domains.**
  - `Determination` — `Overturned Decision of Health Plan` 22,445 (52.5%), `Upheld Decision
    of Health Plan` 20,304 (47.5%). The PRD-literal "Upheld"/"Overturned" match zero rows on
    equality; the contract pins the exact strings and hard-fails on anything else.
  - `Type` — `Medical Necessity` 31,504, `Experimental/Investigational` 10,476, `Urgent Care`
    769.
  - `IMRType` — `Standard` 30,208, `Expedited` 12,541 (undocumented field, enum enforced).
  - `AgeRange` — 7 buckets, top-coded `65+`, 691 nulls. `PatientGender` —
    `Female`/`Male`/`Other` (96), 691 nulls.
  - The 691 demographic nulls are one clean cohort: 2001–2003 rows missing `AgeRange` +
    `PatientGender` + `DaysToReview` together. Fenced off with a single `flag_legacy_cohort`.
  - `ReferenceID` prefix encodes type+year (`MN26-46990`, `EI03-1270`) — a free cross-check;
    prefix/`case_type`/`report_year` mismatches get flagged.

  **Hazards.** Five, measured:
  1. Taxonomy migration in 2026 — two vocabularies coexist. A new ICD-10-chapter-style label
     set (`Musculoskeletal`, `Endo/Metabolic`, `Mental Behav Neur`, `Neoplasms (Tumor)`, …)
     appears in ReportYear 2026 only (386 rows so far), while legacy labels
     (`Orth/Musculoskeletal`, `Endocrine/Metabolic`, `Mental Disorder`, `Cancer`, …) continue
     in parallel — 33 distinct `DiagnosisCategory` values in 2026 vs a steady 24 in
     2023–2025. Cardinality overall: 48 diagnosis / 58 treatment categories, 532 / 498
     subcategories. Without a crosswalk, category trends fracture at 2026 and any model
     trained on 2001–2025 labels won't recognize the new space — the "normalization map" TODO
     item is therefore a legacy↔new crosswalk, not just whitespace canonicalization
     (direction: OQ-1.2).
  2. Label drift: overturn rate climbs ~25–45% (2000s) → ~48–56% (mid-2010s) → **62–72%**
     (2020s). A pooled base rate of 52.5% describes no era — first-order evidence for the
     temporal-cutoff decision (OQ-1.5) and Phase 5's calibration story.
  3. `ReferenceID` duplicates: 39 rows share an ID with another row, spread 2002→2026 —
     chronic, not a fresh-load artifact. Design response: surrogate `row_id`,
     `flag_duplicate_reference_id`, nothing dropped; EDA reports whether pair contents are
     identical or divergent.
  4. `Findings` is never null but can be near-empty — min length 1 char, 3 rows under 100
     chars, mean ~1,812 chars (~300 words, as the PRD expected). Modern rows carry
     exploitable internal section markers (`Findings:`, `Final Result:`,
     `Credentials/Qualifications:`); prevalence by year is an EDA deliverable because Phase
     3's scrub can drop the `Final Result:` block wholesale if the structure holds.
  5. Terms are murkier than "open data": `license_id: null`; the CalHHS ToU requires
     attribution and flags modified data as non-official; the dataset page embeds an OPA
     click-through modal restricting alteration and gating commercial use, whose
     applicability to this (DMHC) dataset is unverified. Owner decision required — full
     quotes and analysis in OQ-1.1.

  **Data flow.**
  ```
  CHHS portal (single CSV, presigned-S3 redirect)
     │  download.py — streaming GET, sha256 while streaming, atomic rename
     ▼
  data/raw/imr_<snapshot-date>.csv + data/raw/manifest.json      (immutable, gitignored)
     │  schema.py — 14-column exact contract: names, order, casts, enum domains
     ▼  fail loudly with a readable diff; no partial passes
     │  normalize.py — category crosswalk (versioned YAML) → canonical + *_raw columns
     │  quality.py  — flag columns only; zero rows dropped
     ▼
  data/interim/imr_cases.parquet + data/interim/ingest_report.json   (lineage: snapshot sha,
     │                                                     schema/crosswalk versions, counts)
     │  profile.py — pure stats functions + markdown renderer
     ▼
  docs/evals/eda.md · docs/data-card.md (populated) · temporal-cutoff evidence table (→ OQ-1.5 ruling)
  ```
  `make ingest` runs download→validate→normalize→flag→parquet and prints the ingest report.
  Idempotency: matching checksum in the manifest skips the download; re-runs regenerate a
  byte-identical parquet from the same pinned snapshot (stable row order, fixed compression).

  **Modules.** `src/repeal/ingest/`:

  | Module | Responsibility | Tests |
  |---|---|---|
  | `download.py` | streaming fetch → temp file → sha256 → atomic rename; `manifest.json` entries `{url, retrieved_at, sha256, size_bytes, filename}`; skip-if-checksummed; ranged-GET probe helper (`Content-Range` size + `Last-Modified`) because HEAD 403s | `tests/test_download.py` (mocked HTTP; no network in tests, ever) |
  | `schema.py` | the contract: exact 14 source columns in order; casts (`report_year`, `days_to_*` → int); enum domains for `determination`/`case_type`/`imr_type`/`age_range` (hard-fail on unknowns); snake_case renames; `Determination`→`overturned` bool; `row_id` synthesis. Contract failure raises with a missing/extra/retyped diff | `tests/test_schema_contract.py` |
  | `normalize.py` | applies `resources/category_crosswalk_v1.yaml`: mechanical canonicalization (trim/collapse/case) + explicit alias→canonical table for the 2026 migration (category level; subcategory scope per OQ-1.2). Unknown categories pass through and are counted, not errored — new labels must never brick ingest; they surface in the report and the drift guard | `tests/test_normalize.py` |
  | `quality.py` | row flags: `flag_findings_short` (threshold pinned by EDA), `flag_findings_truncated`, `flag_encoding_artifact`, `flag_duplicate_reference_id`, `flag_duplicate_findings`, `flag_legacy_cohort` (the 691), `flag_id_prefix_mismatch`, `has_section_markers`. Flags never drop rows — exclude-and-report is the downstream consumer's move, made visible in the ingest report | `tests/test_quality.py` |
  | `profile.py` | pure functions frame→stats: rows/label-rate per year, per-era vocab tables (the 2026 break), category top-N, findings length percentiles by year, dupe-pair content comparison, null cohorts, section-marker prevalence by year, cutoff-candidate table (train/test share, era composition, label-rate stability per candidate year); markdown renderer → `docs/evals/eda.md`. Tables-first — no plotting dependency in Phase 1 | `tests/test_profile.py` |
  | `run.py` | orchestrates the flow; writes parquet + `ingest_report.json`; nonzero exit on contract failure; entry point for `make ingest` | `tests/test_ingest.py` (end-to-end over the fixture) |

  Shared infra: `tests/fixtures/imr_synthetic.csv` (~60 rows) + its committed generator —
  every enum value, both vocabularies, a duplicate-ID pair, a 1-char `Findings`, a
  legacy-cohort row, a mojibake row, a prefix-mismatch row. Every quality flag and normalize
  path is exercisable in CI with zero real rows committed (fixture policy: OQ-1.8).

  **Invariants.**
  - Pinned snapshot (OQ-1.3): all of v1 builds against one dated snapshot recorded in the
    manifest; refresh is an explicit, deliberate act producing a new dated raw file. Upstream
    is a full-file republish with no per-row dates — there is no incremental path, and every
    downstream artifact (gold sets, splits, indexes) keys on the row set.
  - Self-computed sha256 is the only integrity anchor (CKAN hash stale, S3 ETag multipart).
  - Nothing is silently dropped or coerced: unknown enum value → hard fail; unknown category
    label → pass-through + count; quality issues → flags.
  - Lineage on every artifact: parquet + report carry snapshot sha256, schema version,
    crosswalk version. Any eval number downstream cites them (OQ-0.2's artifact contract).
  - OQ-0.1 field classification is enforced from birth: `days_to_review`/`days_to_adopt` are
    tagged post-decision in `schema.py` metadata so Phase 5's "no post-decision features"
    test has a machine-readable source of truth.

  **Testing & CI.** CI (lint + pytest) never touches the network: all tests run on the
  synthetic fixture. The schema contract is authored from the recon-verified real header and
  verified against reality every `make ingest` run — exactly PRD §9's "schema contract test
  against real fields," continuously, not once. Optional `make check-upstream` (OQ-1.10) hits
  the datastore API for a one-request drift probe: 14 expected field names + row-count ≥
  pinned, catching the next taxonomy migration the day it lands, not in a model post-mortem.

  **Cutoff evidence.** `profile.py` produces a cutoff-candidate table for cutoffs 2019–2024:
  train/test row counts and shares, overturn rate on each side, era/vocabulary composition,
  2026-partial-year handling. Working proposal (PRD): train ≤2021 / test 2022+ → 23.4% test
  share. The label drift above makes the *criteria* the decision that matters (OQ-1.5); the
  ruling on OQ-1.5 fixes the year from this table, and it is not re-tuned afterwards.

  **Deliverables** (→ TODO):

  | TODO item | Files |
  |---|---|
  | Downloader + checksum, idempotent `make ingest` | `download.py`, `manifest.json` schema, Makefile · `tests/test_download.py` |
  | Schema contract vs real fields; parquet | `schema.py`, `run.py` · `tests/test_schema_contract.py`, `tests/test_ingest.py` |
  | Category normalization map, versioned | `normalize.py`, `resources/category_crosswalk_v1.yaml` · `tests/test_normalize.py` |
  | Quality flags + exclude-and-report policy | `quality.py`, ingest report · `tests/test_quality.py` |
  | EDA report | `profile.py` → `docs/evals/eda.md` · `tests/test_profile.py` |
  | Data card + temporal cutoff | `docs/data-card.md`, cutoff table → OQ-1.5 ruling |

  TODO.md's Phase 1 items carry this file mapping (added 2026-09-09). The data card's
  terms-determination section is owner-gated on OQ-1.1.

  **Roster** (spawned only after this design is approved and OQ-1.1–1.11 are ruled): four
  teammates, disjoint file ownership, strict R-G-R, lead coordinates only.

  | Teammate | Role | Owns | Blocked by |
  |---|---|---|---|
  | `neon-fetcher` | downloader | `download.py`, `tests/test_download.py`, `data/raw` manifest schema, Makefile `ingest`/`check-upstream` wiring, deps bootstrap (`pyproject.toml` + `uv.lock`, sole owner) | — |
  | `cipher-contract` | schema + orchestration | `schema.py`, `run.py`, `tests/test_schema_contract.py`, `tests/test_ingest.py`, synthetic fixture + generator | `neon-fetcher` (deps) |
  | `vortex-mapper` | taxonomy + quality | `normalize.py`, `quality.py`, `resources/category_crosswalk_v1.yaml`, `tests/test_normalize.py`, `tests/test_quality.py` | `cipher-contract` (column names, fixture) |
  | `phantom-profiler` | EDA + evidence | `profile.py`, `tests/test_profile.py`, `docs/evals/eda.md`, `docs/data-card.md` population, cutoff-candidate table + draft cutoff ruling | `cipher-contract` (fixture); full-corpus outputs additionally on integrated `make ingest` |

  ```
  neon-fetcher(deps) ──► cipher-contract(schema, fixture) ──► vortex-mapper ──► run.py integration
                                                └──────────► phantom-profiler ──► eda.md + data card
  ```

  Lead: task board, integration verification, real-corpus `make ingest` run, TODO
  flips, the ✅ gate line's effort note, owner comms. The one full download (81 MB)
  happens once, on the lead's machine, and the sha256 lands in the manifest as the
  pinned snapshot.

  **Cross-phase consequences.**
  - Phase 2's join script (gold-set release keys on `ReferenceID`) must handle the 39
    collisions — release keying becomes `reference_id` + a disambiguator from `row_id` order.
  - Phase 2's stratification "era" gets a principled definition from the EDA drift table
    instead of an arbitrary tercile.
  - Phase 3's scrub inherits the section-marker prevalence measurement — if `Final Result:`
    blocks are near-universal in modern rows, structural removal precedes regex scrubbing.
  - Phase 5 inherits the OQ-1.5 cutoff ruling, the non-stationary-base-rate calibration
    story, and a machine-readable post-decision field list to test against.
  - All phases inherit the drift guard: an upstream republish or vocabulary change is caught
    by `make check-upstream`, not discovered mid-eval.

  **Risks.**

  | Risk | Mitigation |
  |---|---|
  | OPA terms modal is held to bind (no-alteration / commercial approval) | OQ-1.1 owner decision before anything user-facing; meanwhile: noncommercial posture, no data redistribution (already policy), every derived artifact flagged modified/non-official + attributed |
  | Presigned-URL mechanics change or portal moves the resource | manifest records URL + resource id; data.gov mirror as fallback; probe helper isolates the mechanics in one place |
  | Upstream republishes mid-phase | pinned snapshot — new data changes nothing until deliberately refreshed; `check-upstream` makes it visible |
  | 2026 vocabulary keeps mutating (transition ongoing) | unknown categories pass through + counted; crosswalk is versioned and additive |
  | Fixture drifts from real schema | fixture generator derives from `schema.py` constants — one source of truth |
  | CI can't see real-data regressions | accepted split: logic in CI on fixtures, reality checked every local `make ingest` + drift probe (OQ-1.10) |

  **Out of scope.** No LLM extraction, no scrubbing, no DuckDB warehouse, no modeling, no
  retrieval — Phase 1.5+ owns those. No plotting deps. No incremental-update machinery
  (upstream can't support it). No subcategory semantic crosswalk unless OQ-1.2 says
  otherwise.

  Rulings on OQ-1.1, 1.2, 1.3, 1.4, 1.5 and 1.7 change PRD defaults; each gets its ROLLER.md
  item when ruled.

  **Options.** (a) approve the design as proposed. (b) approve with amendments, listed in the
  ruling. (c) redesign.
  **Assumed:** (a) — every Phase 1 file plan below is derived from it.
  **Recommendation:** (a).
  **Ruled 2026-09-09:** owner — (a) approved as proposed. All eleven dependent calls
  (OQ-1.1–1.11) were ruled the same day exactly as this design assumed; the only open slot
  is the cutoff year, which OQ-1.5 closes from the candidate table. Phase 1 may spawn.
  · **Landed:** 7fad9b8, 1b7a0e7, 3fabd9e, 6cdcdc4, c89aeb8 (the five Phase 1 build commits) — the Phase 1 build (TODO.md) lands it. · **ROLLER:** — (phase work)

- [x] OQ-1.1 — Terms posture: does the OPA click-through modal bind this project? (owner call)
  **Context.** The dataset carries no license (`license_id: null`, "No License Provided").
  Two documents govern. The CalHHS portal ToU (https://data.chhs.ca.gov/pages/terms, last
  modified 2023-01-27) grants a "non-exclusive, non-transferable, revocable license to use
  and distribute the Content," requires attribution ("attribution of credit to the CalHHS
  department or office … and a citation to the webpage and date of publication"), and permits
  modification with flagging:

  > "If you modify the Content for your own purposes in any way, you may not claim the data
  > is 'official government data' and must clearly indicate that the data and/or data table
  > has been modified."

  It also says the Content Source Organization's terms override the portal ToU on conflict.
  The OPA click-through modal embedded in this dataset page's HTML ("Accept OPA Terms of
  Use") reads:

  > "Users of this data file provided by the Office of the Patient Advocate (OPA) shall not
  > have the right to alter, enhance, or otherwise modify the data. Anyone desiring to use or
  > reproduce the data without modification for a noncommercial purpose may do so without
  > obtaining approval. All commercial uses must be approved and may be subject to a
  > license."

  PRD §4's "noncommercial use without approval … prohibit altering" line evidently paraphrases
  this modal — the constraint was known; what recon adds: (i) the modal names OPA while the
  source organization is DMHC (possibly misapplied boilerplate — recon could not verify
  whether the modal is portal-wide, control pages 404'd); (ii) it's referenced nowhere in the
  CKAN metadata or `Limitations` field; (iii) its no-alteration clause conflicts with the
  portal ToU's modify-with-flagging clause, and normalization/feature-derivation is
  modification; (iv) the commercial-approval clause matters the moment this stops being a
  portfolio project.

  **Options.**
  (a) Strict-OPA reading: treat the modal as binding — no derived/normalized artifacts at
  all, display-only use. Kills the project as designed.
  (b) Portfolio posture (recommended): noncommercial research/portfolio use; rely on the
  portal ToU's modify-with-flagging clause; every derived artifact carries a "modified,
  non-official" notice + the preferred citation (`DMHC IMR Data, 2001 - Current` + URL +
  publication date); no raw/modified data redistribution (already policy, OQ-0.4); commercial
  use treated as blocked pending approval. Follow-up: one control-page check to establish
  whether the modal is boilerplate; optionally an email to DMHC for a written read.
  (c) Ask first: email DMHC/portal before ingesting anything. Safest, slowest; blocks Phase 1
  on a government inbox.

  **Assumed:** (b) — the HLD (OQ-1.0) is built on the portfolio posture, including its risk
  mitigation and the data card's "modified, non-official" notice.
  **Recommendation:** (b), with the follow-up verification. It matches what the PRD already
  assumed, every mitigation is already project policy, and it keeps the one genuinely
  irreversible step (commercial positioning) explicitly gated.
  **Ruled 2026-09-09:** owner — (b) portfolio posture, with the follow-up verification.
  Noncommercial research use under the portal ToU's modify-with-flagging clause; every
  derived artifact flagged modified/non-official and cited; no data redistribution;
  commercial use blocked pending approval. · **Landed:** R-02 done 2026-09-09 — the OPA
  click-through is portal-wide boilerplate (identical `id="popup"` fragment on the DMHC IMR
  page, three unrelated organizations' pages and OPA's own; raw-HTTP byte-for-byte match);
  posture and finding recorded in `docs/data-card.md` (691241c, `update : data card terms posture
  from oq-1.1`). · **ROLLER:** R-02

- [x] OQ-1.2 — Category crosswalk: which vocabulary is canonical, and how deep?
  **Context.** The migration and its counts are covered in OQ-1.0 (Hazards, #1). Additional
  trap: near-duplicate labels exist within a vocabulary (`Pregnancy Childbirth` vs
  `Pregnancy/Childbirth`), not just across the legacy/new split.
  **Options.**
  (a) Canonicalize to the NEW vocabulary (recommended): legacy→new map. Future rows arrive
  already-canonical; aligned with ICD-10 chapters (public domain, PRD-permitted); history is
  rewritten once, under a versioned map. Cost: the new vocab is only ~6 months old — mappings
  for rare legacy labels lean on judgment.
  (b) Canonicalize to legacy: new→legacy map. History stays untouched, but every future
  ingest maps fresh data backwards into a dead scheme, forever.
  (c) Dual columns + `category_scheme` marker, no crosswalk: honest, defers the problem to
  every downstream consumer — exactly the accidental complexity CLAUDE.md warns about.
  **Depth.** Category level only in Phase 1 (48+58 labels — tractable, reviewable).
  Subcategories (532/498) get mechanical canonicalization (trim/case/whitespace) + raw
  preserved, semantic subcategory mapping deferred until something downstream demonstrably
  needs it.
  **Assumed:** (a) + category-level depth — the HLD (OQ-1.0)'s `normalize.py`/crosswalk
  design is built on it.
  **Recommendation:** (a) + category-level depth, raw labels always preserved in `*_raw`
  columns, map versioned as `category_crosswalk_v1.yaml`, unknown labels pass-through +
  counted.
  **Ruled 2026-09-09:** owner — (a) canonicalize to the new (ICD-10-chapter-style)
  vocabulary, category level only in Phase 1; subcategories mechanical cleanup + raw
  preserved; `*_raw` columns always kept; `category_crosswalk_v1.yaml` versioned; unknown
  labels pass through and are counted, never errored. · **Landed:** 3fabd9e — crosswalk +
  `normalize.py` are Phase 1 work (TODO); the PRD §12 row refinement is R-03. · **ROLLER:** R-03

- [x] OQ-1.3 — Snapshot policy: pin one dated snapshot for all of v1?
  **Context.** Upstream is a periodic full-file republish (whole CSV replaced; last publish
  2026-06-01; `Frequency: "Other"`, no committed cadence; no per-row dates → no incremental
  path — OQ-1.0). Every downstream artifact — gold-set ReferenceIDs (Phase 2), temporal split
  (Phase 5), indexes (Phase 4) — keys on the exact row set. Only a self-computed sha256
  identifies a snapshot (OQ-1.0).
  **Options.**
  (a) Pin (recommended): first `make ingest` records the snapshot (dated filename + sha256 in
  `manifest.json`); every re-run verifies and reuses it. Refresh is explicit (`make ingest
  REFRESH=1`) → new dated raw file, new manifest entry, deliberate downstream re-runs.
  (b) Always-latest: fresh data, and silent invalidation of every artifact built before the
  republish.
  **Assumed:** (a) — the HLD (OQ-1.0)'s pinned-snapshot invariant is built on it.
  **Recommendation:** (a). Reproducibility is a PRD §3 success criterion; freshness buys
  nothing until Phase 8.
  **Ruled 2026-09-09:** owner — (a) pin. First `make ingest` records the dated snapshot and
  its self-computed sha256 in `manifest.json`; re-runs verify and reuse it; refresh is
  explicit (`make ingest REFRESH=1`) and produces a new dated raw file, a new manifest
  entry, and deliberate downstream re-runs. · **Landed:** 7fad9b8 — `download.py` + manifest
  are Phase 1 work (TODO); the PRD §4 wording is R-04. · **ROLLER:** R-04

- [x] OQ-1.4 — Leakage-protocol classification of the three undocumented fields (OQ-0.1)
  **Context.** The real CSV carries `IMRType`, `DaysToReview`, `DaysToAdopt` — none in the
  PRD. OQ-0.1's inference-time contract: prediction inputs = information a provider holds at
  denial time. `DaysToReview`/`DaysToAdopt` measure the external review itself — they do not
  exist until the review completes. `IMRType` (`Standard` 30,208 / `Expedited` 12,541) is set
  at IMR intake: expedited status is requested/granted when the case is filed, so at the
  external-review stage it is knowable before the decision — but it is not, strictly, held at
  denial time.
  **Options.**
  (a) (recommended) Ingest all three. `days_to_*`: tagged post-decision, excluded from every
  predictor feature set (machine-readable tag in `schema.py`; Phase 5 test enforces), kept
  for descriptive analytics. `imr_type`: pre-decision, prediction-eligible — it's known at
  filing, and expedited-vs-standard plausibly carries real signal; the model card documents
  the nuance.
  (b) `imr_type` excluded too (strictest denial-time reading). Cleaner story, discards a
  legitimate filing-time feature.
  (c) Everything eligible. Violates OQ-0.1 for `days_to_*` — not actually on the table.
  **Assumed:** (a) — the HLD (OQ-1.0)'s schema table (`imr_type` pre-decision pending this
  entry, `days_to_*` post-decision) is built on it.
  **Recommendation:** (a); the ruling here is the record, noted against OQ-0.1.
  **Ruled 2026-09-09:** owner — (a) ingest all three. `days_to_review`/`days_to_adopt`
  tagged post-decision in `schema.py` metadata, excluded from every predictor feature set
  (Phase 5 test enforces), kept for descriptive analytics; `imr_type` pre-decision and
  prediction-eligible, nuance documented in the model card. · **Landed:** 1b7a0e7 —
  `schema.py` classification is Phase 1 work (TODO); the PRD §5 application note is R-05.
  · **ROLLER:** R-05

- [x] OQ-1.5 — Temporal cutoff: decision criteria, and what to do with 2026
  **Context.** PRD's working proposal: train ≤2021 / test 2022+ (→ 10,013 test rows, 23.4%).
  Alternative ≤2022 / 2023+ → 8,237 (19.3%). Complications recon measured: overturn rate is
  non-stationary (25% → 72% across the corpus, 62–72% in the 2020s — OQ-1.0), 2026 is partial
  (publish cutoff June, 546 rows) and straddles the vocabulary migration, and 2001 is
  near-empty (28 rows).
  **Proposed criteria** (the ruling argues from these, not from a hunch): test share 15–25%;
  ≥2 full calendar years of test data; test era is all-modern (post-drift-plateau) so
  calibration is judged against deployment-like base rates; 2026 excluded from train and test
  windows (kept in the corpus, flagged) until a full-year, single-vocabulary slice exists;
  2001 excluded as negligible.
  **Assumed:** train ≤2021 / test 2022+ (the PRD's working proposal, pending the candidate
  table) — Phase 5's split in the HLD (OQ-1.0) is built on it.
  **Recommendation:** `profile.py` emits the candidate table (2019–2024: shares, label-rate
  stability, composition); the ruling on this entry fixes the year, argued from the candidate
  table — working proposal stands unless the table contradicts it. The year is then frozen
  (PRD §9 Phase 5: never re-tuned).
  **Ruled 2026-09-09 (criteria):** owner — (a): the five criteria above are approved and
  train ≤2021 / test 2022+ is the working default; `profile.py`'s candidate table
  (2019–2024) decides the year in a second ruling on this entry, after which it is frozen
  and never re-tuned. 2026 stays out of both windows, flagged, until a full-year
  single-vocabulary slice exists; 2001 excluded.
  **Ruled 2026-09-10 (year):** owner — (a) 2021, frozen: train ≤2021 / test 2022–2025
  (32,708 / 9,467 rows, 22.4% test share, 4 full modern years; 2001 and 2026 excluded), from
  the candidate table in `docs/evals/eda.md` (2022 also met the criteria at 18.2% / 3 years).
  Never re-tuned (PRD §9 Phase 5). · **Landed:** `update : prd phase 5 cutoff year from oq-1.5`
  (cf7b887) · **ROLLER:** R-08

- [x] OQ-1.6 — Dataframe contract: pandera, or hand-rolled checks?
  **Context.** The contract is small — 14 columns, 4 enum domains, 3 casts, nullability
  rules (OQ-1.0, Schema) — but it is the single most load-bearing validation in the project:
  everything downstream trusts the parquet. PRD §7 default: "`pandera` (or pydantic) for
  dataframe contracts." Stack is polars (OQ-1.9).
  **Options.**
  (a) pandera with its polars integration (recommended): declarative schema doubles as
  documentation the data card can cite; readable failure reports; stays inside the PRD
  default. Cost: a dependency with its own API surface.
  (b) Hand-rolled polars asserts: ~60 lines, zero deps, fully controlled diff output. Cost:
  bespoke validation-report code; deviates from the PRD's wording, and the ruling here is the
  record if chosen.
  **Assumed:** (a) — the HLD (OQ-1.0)'s `schema.py` design is built on it.
  **Recommendation:** (a) — the boring choice here is the PRD default. Flip to (b) only if
  pandera's polars support fights us in practice (that experience would be the evidence for
  the ruling).
  **Ruled 2026-09-09:** owner — (a) pandera with its polars integration; inside the PRD
  default. Re-rule to (b) only on evidence that pandera's polars support fights us in
  practice. · **Landed:** 1b7a0e7 — `schema.py` is Phase 1 work (TODO); no PRD change.
  · **ROLLER:** —

- [x] OQ-1.7 — EDA vehicle: notebook (PRD-literal) or tested module + renderer?
  **Context.** PRD §9 says "EDA notebook exported to `docs/evals/eda.md`." CLAUDE.md mandates
  strict TDD for every feature; notebooks resist R-G-R and nbconvert drags in the jupyter
  dependency chain for a one-way export. The intent of the PRD line is the report, and the
  repo rule "anything load-bearing graduates to `src/`" already points this way — the EDA
  stats are load-bearing (the temporal-cutoff ruling and data card cite them).
  **Options.**
  (a) (recommended) `profile.py` (pure, tested stat functions) + a renderer writing
  `docs/evals/eda.md` directly; no notebook, no jupyter deps; report regenerates
  deterministically from the parquet. Deviates from the PRD's wording; the ruling here is the
  record.
  (b) Thin notebook that imports `profile.py` and exports via nbconvert. PRD-literal; adds
  the jupyter chain + a non-TDD artifact for zero analytical gain.
  **Assumed:** (a) — the HLD (OQ-1.0)'s module roster (`profile.py`, no notebook) is built on
  it.
  **Recommendation:** (a), tables-first (no plotting dependency in Phase 1; revisit if
  `eda.md` proves unreadable as tables).
  **Ruled 2026-09-09:** owner — (a) `profile.py` (pure, tested stat functions) + a
  renderer writing `docs/evals/eda.md`; no notebook, no jupyter, tables-first, no plotting
  dependency in Phase 1. · **Landed:** c89aeb8 — `profile.py` is Phase 1 work (TODO); the
  PRD §9 Phase 1 wording is R-06. · **ROLLER:** R-06

- [x] OQ-1.8 — Fixtures: synthetic-only, or a tiny real excerpt?
  **Context.** PRD §8 mentions "fixtures with small synthetic/excerpt samples," but the terms
  (OQ-1.1) prohibit redistributing the data, and a committed excerpt is redistribution. CI has
  no network, so whatever CI verifies must be committed.
  **Options.**
  (a) Synthetic-only (recommended): ~60 generated rows, real column names + realistic shapes,
  every enum value, both vocabularies, every pathology the flags detect (dupe pair, 1-char
  findings, legacy-cohort row, mojibake, prefix mismatch). Zero terms exposure. Generator
  committed; fixture derives from `schema.py` constants — one source of truth.
  (b) Tiny real excerpt (~5 rows): marginally more realistic, legally gray under OQ-1.1's
  cloud, and it would rot against republishes anyway.
  **Assumed:** (a) — the HLD (OQ-1.0)'s shared-fixture design (`tests/fixtures/imr_synthetic.csv`)
  is built on it.
  **Recommendation:** (a). Realism against the actual corpus is covered by `make ingest`
  validating the real download on every local run.
  **Ruled 2026-09-09:** owner — (a) synthetic-only: ~60 generated rows, real column names,
  every enum value, both vocabularies, every flagged pathology; generator committed and
  derived from `schema.py` constants; no real rows ever committed. · **Landed:** 1b7a0e7 —
  fixture + generator are Phase 1 work (TODO); the PRD §8 wording is R-07. · **ROLLER:** R-07

- [x] OQ-1.9 — First runtime dependencies
  **Context.** `pyproject.toml` has zero runtime deps today. Needed: dataframe + parquet,
  HTTP download, YAML crosswalk, contract library per OQ-1.6. PRD §7 prefers polars.
  **Proposed set.** `polars` (native parquet read/write — no pyarrow needed), `requests`
  (redirect-following streaming downloads; stdlib `urllib` is the zero-dep alternative but
  rebuilding retry/redirect handling is not worth it), `pyyaml` (crosswalk), `pandera` (per
  OQ-1.6 (a)). Explicitly not: pandas, pyarrow, jupyter (OQ-1.7), plotting libs. Dep additions
  owned by one teammate (`neon-fetcher`) to keep `pyproject.toml`/`uv.lock` single-writer.
  **Assumed:** the proposed set — the HLD (OQ-1.0)'s roster and module list are built on it.
  **Recommendation:** as proposed.
  **Ruled 2026-09-09:** owner — approved as proposed: `polars`, `requests`, `pyyaml`,
  `pandera`; no pandas, pyarrow, jupyter or plotting libs; deps single-writer (the
  downloader teammate). · **Landed:** 7fad9b8 — deps bootstrap is Phase 1 work (TODO); no
  PRD change. · **ROLLER:** —

- [x] OQ-1.10 — Upstream drift guard: where does the datastore probe live?
  **Context.** The live CKAN datastore allows a one-request schema/row-count check without
  downloading 81 MB (OQ-1.0). The 2026 vocabulary migration is exactly the class of silent
  upstream change that should be caught the day it lands. But CI network calls flake, and a
  third-party API in the commit-blocking path is a false-red generator.
  **Options.**
  (a) (recommended) `make check-upstream` target (probe: 14 expected field names, row-count ≥
  pinned snapshot, `last_modified` vs manifest) — run manually / before each phase; never in
  pytest or the commit-blocking CI job.
  (b) Also a scheduled non-blocking CI job (weekly cron, allowed to fail visibly).
  Nice-to-have; needs the repo pushed to origin first.
  (c) In the test suite. Rejected: network in unit tests.
  **Assumed:** (a) — the HLD (OQ-1.0)'s testing/CI split is built on it.
  **Recommendation:** (a) now, (b) once CI on `maestro` is live.
  **Ruled 2026-09-09:** owner — (a) `make check-upstream` only: manual / before each phase,
  never in pytest or the commit-blocking CI job. (b), a scheduled non-blocking CI probe, is
  not ruled in; it can be raised as a new entry once CI on `maestro` is live (OQ-0.7).
  · **Landed:** 7fad9b8 — Makefile target + probe helper are Phase 1 work (TODO); no PRD
  change. · **ROLLER:** —

- [x] OQ-1.11 — Quality-flag set and threshold procedure — sign-off
  **Context.** Measured reality: `Findings` has 0 nulls but a 1-char minimum (3 rows <100
  chars — OQ-1.0); 39 duplicate-`ReferenceID` rows (OQ-1.0); a clean 691-row 2001–2003 cohort
  missing all demographics (OQ-1.0); typographic-apostrophe UTF-8 text (mojibake possible in
  older rows); modern rows carry `Findings:`/`Final Result:`/`Credentials/Qualifications:`
  section markers (Phase 3's scrub wants the prevalence measured).
  **Proposed flags** (columns, never row drops — exclusion is the downstream consumer's
  explicit, reported decision): `flag_findings_short`, `flag_findings_truncated`,
  `flag_encoding_artifact`, `flag_duplicate_reference_id`, `flag_duplicate_findings`,
  `flag_legacy_cohort`, `flag_id_prefix_mismatch`, `has_section_markers`.
  **Threshold procedure.** Thresholds (short-findings char floor, truncation heuristics) are
  parameters with values pinned by EDA percentiles and recorded in the data card — not
  guessed in code review.
  **Assumed:** the proposed flag set and procedure — the HLD (OQ-1.0)'s `quality.py` design
  is built on it.
  **Recommendation:** approve set + procedure; flags are cheap to add later, expensive to
  retrofit into published artifacts.
  **Ruled 2026-09-09:** owner — approved as proposed: the eight flag columns, never row
  drops; thresholds pinned by EDA percentiles and recorded in the data card. · **Landed:** 3fabd9e — `quality.py` is Phase 1 work (TODO); no PRD change. · **ROLLER:** —

- [x] [s:53ce5611] OQ-1.12 — Crosswalk: apply the 16 parked legacy→2026 best-guess mappings, or keep those labels canonical-as-themselves?
  **Context.** `category_crosswalk_v1.yaml` was authored from the real 2026-06-01 corpus (48
  diagnosis / 58 treatment categories). Fifteen diagnosis aliases and two treatment aliases
  are clear renames and are applied. Sixteen more (11 diagnosis, 5 treatment) are
  best-guesses parked under `uncertain`, NOT applied: the legacy label stays canonical as
  itself and `normalize.apply` reports how often each occurs (`uncertain_seen` in
  `ingest_report.json`, filled by the integrated run). Diagnosis: Autism Spectrum→Mental
  Behav Neur; Chron Pain Synd→Sym/Sign Ab Find; Dental Problems→Digest System; Ears/Nose/
  Throat→Ear and Mastoid; Foot Disorder→Musculoskeletal; Genetic Diseases→Malfor/Deform/
  Abnor; Immuno Disorders→Diseases of Blood; Morbid Obesity→Endo/Metabolic; OB-GYN/
  Pregnancy→Pregnancy Childbirth; Post Surgical Comp→Injury Poison Oth; Prevention/Good
  Hlth→Hlth Factor/Contact. Treatment: Alternative Tx→Other Thera Proc; DME→Durable Med
  Equip; Diag Imag & Screen→Radio Proc; Mental Health→Medicine Serv Proc;
  Transportation→Ambulance Transport. Finding on the treatment axis: only 2 of 31 legacy
  treatment labels have a confident 2026 counterpart — the 2026 treatment vocabulary reads
  as CPT/HCPCS section names, not a rename of the old scheme — so treatment-category
  trends still fracture at 2026 for most labels whatever is ruled here.
  **Options.** (a) apply none; legacy labels stay canonical as themselves, their trends
  end at 2026 and the 2026 rows start fresh under the new labels; (b) apply all 16;
  (c) apply the ICD-10-chapter-consistent subset — the seven diagnosis guesses that are
  chapter-correct broadenings (Autism Spectrum, Chron Pain Synd, Genetic Diseases, Immuno
  Disorders, Morbid Obesity, Post Surgical Comp, Prevention/Good Hlth) plus DME and
  Transportation on the treatment side — and keep the rest (Dental, ENT, Foot, OB-GYN,
  Alternative Tx, Diag Imag & Screen, Mental Health) as themselves because each either
  splits across two new labels or broadens badly.
  **Row counts (real corpus, vortex-mapper's enumeration, 2026-09-09).** Diagnosis, 7,154 rows
  on unapplied guesses: Autism Spectrum 1,390 (2002–2025); OB-GYN/ Pregnancy 1,080
  (2001–2019); Immuno Disorders 960 (2002–2026); Morbid Obesity 948 (2001–2019);
  Prevention/Good Hlth 819 (2001–2025); Ears/Nose/Throat 702 (2001–2026); Foot Disorder
  397 (2002–2025); Genetic Diseases 350 (2002–2026); Chron Pain Synd 193 (2002–2018);
  Dental Problems 160 (2002–2025); Post Surgical Comp 155 (2003–2026). Treatment, 13,987
  rows: Diag Imag & Screen 5,994 (2001–2026); Mental Health 4,835 (2002–2026); DME 2,679
  (2001–2026; `DME MACs` has 6 rows so far); Alternative Tx 414 (2002–2025);
  Transportation 65 (2017–2025). Not in `uncertain` because no single target exists (see
  OQ-1.13): the ten specialty `* Proc` labels ≈ 6,568 rows and `Pharmacy` 11,948 rows.
  **Assumed:** (a) — that is what the code does today; nothing is mapped on a guess.
  **Recommendation:** (c): apply Autism Spectrum, Chron Pain Synd, Genetic Diseases, Immuno
  Disorders, Morbid Obesity, Post Surgical Comp, Prevention/Good Hlth (4,815 diagnosis rows,
  each an ICD-10-chapter-correct broadening) plus DME and Transportation (2,744 treatment
  rows); keep OB-GYN/ Pregnancy, Ears/Nose/Throat, Foot Disorder, Dental Problems,
  Diag Imag & Screen, Mental Health and Alternative Tx as themselves (13,582 rows) because
  each either splits across two new labels or folds a large distinct bucket into a
  looser one. If ruled, the nine move from `uncertain` to `aliases` in
  `category_crosswalk_v1.yaml` (version stays 1 until the first commit that ships it;
  bump to v2 after) and the mapped counts in `ingest_report.json` change accordingly.
  **Ruled 2026-09-10:** owner — (c) with a trace: "yes map to icd chapters … with a trace
  note that says what we did during crosswalk design". Lead's reading: apply the nine
  ICD-10-chapter-consistent mappings (Autism Spectrum, Chron Pain Synd, Genetic Diseases,
  Immuno Disorders, Morbid Obesity, Post Surgical Comp, Prevention/Good Hlth; DME,
  Transportation), keep the other seven as themselves, and record a design-trace note in
  the YAML header and the data card. · **Landed:** rides with
  `add : category crosswalk and quality flags` (3fabd9e) · **ROLLER:** R-09

- [x] [s:53ce5611] OQ-1.13 — Treatment-axis continuity across the 2026 migration: fold the ten legacy procedure labels into `Surgery`, and what about `Pharmacy` and `DME`?
  **Context.** Beyond the parked guesses in OQ-1.12, vortex-mapper's enumeration of the real
  corpus found three treatment-category breaks with no crosswalk answer at all. (1) Ten
  legacy procedure labels — Cardio-Vasc Proc, Ear-Nose-Thro Proc, Gen Surg Proc,
  Neurosurgery Proc, Ob-Gyn Proc, Ophthalmology Proc, Orthopedic Proc, Reconstr/Plast Proc,
  Special Proc, Urology Proc — have no 2026 equivalent; the new vocabulary's only procedure
  bucket is a single generic `Surgery`. Folding them in is a granularity decision (does an
  appeals model care that orthopedic ≠ neurosurgery?), not a rename. (2) `Pharmacy`, 11,948
  rows and the largest treatment category in the corpus, has no 2026 counterpart; the new
  vocabulary carries HCPCS-style drug buckets (`Chemo Drugs`, `Drug Ad Oth Oral`) instead.
  (3) `DME` (2,679 legacy rows) may have split into `Durable Med Equip` and `DME MACs` (24
  rows combined so far). Today all of these stay canonical as themselves. Two facts bound
  the stakes: the 2026 slice is 546 rows, 1.3% of the corpus, and OQ-1.5's ruled criteria
  exclude 2026 from both modeling windows, so v1's predictor never trains or tests on
  new-vocabulary treatment labels; the break affects trend reporting and future ingests,
  not the v1 model. The 2026 vocabulary is also still mutating (OQ-1.0 Risks).
  **Options.** (a) leave all three as they are; treatment trends end at 2025 for those
  labels, the 2026 rows start fresh, and the crosswalk is revisited at the first refresh
  that brings a full single-vocabulary 2026 year; (b) fold the ten procedure labels into
  `Surgery` now and map `DME`→`Durable Med Equip`, accepting the granularity loss on 25
  years of history for continuity on 546 rows; (c) add a coarse derived `treatment_group`
  column alongside the canonical label so both granularities survive — more machinery
  than Phase 1 needs.
  **Assumed:** (a) — nothing folded; it is what the code and the YAML do today.
  **Recommendation:** (a) for v1, with the revisit written into the data card's caveats;
  the decision gets cheaper, not harder, once a full 2026 year shows what the new
  treatment labels actually contain.
  **Ruled 2026-09-10:** owner — (a) "leave them". · **Landed:** nothing to change in code;
  the revisit-at-first-full-2026-year note goes into the data card with R-09. · **ROLLER:** —

- [x] [s:53ce5611] OQ-1.14 — Legacy-cohort flag: are the 691 demographic-null rows and the 691 `DaysToReview`-null rows the same rows?
  **Context.** OQ-1.0's value-domain notes (from the 2026-08-16 recon) describe "one clean
  cohort: 2001–2003 rows missing `AgeRange` + `PatientGender` + `DaysToReview` together",
  and OQ-1.11's `flag_legacy_cohort` was defined as all three null. The integrated run on
  the real corpus returned 0 rows for that flag.
  **Options.** (a) the three-way definition is right and the flag is buggy; (b) the recon
  conflated two populations with the same count and the flag must be the two demographic
  nulls only.
  **Ruled 2026-09-09 (by the code):** (b). On `data/interim/imr_cases.parquet` (snapshot
  sha f68951823f…): rows with `age_range` AND `patient_gender` null = 691, all ReportYear
  2001–2003 (27 / 646 / 18), and `days_to_review` is populated on every one of them; the
  691 `days_to_review` nulls are different rows, ReportYear 2007 onward (2007: 3, 2008: 65,
  2009: 9, 2010: 31, 2011: 20, …). Found by the lead's verification query after
  `make ingest`. `flag_legacy_cohort` is redefined as `age_range` null AND
  `patient_gender` null (expected 691); the data card records the correction.
  · **Landed:** `add : category crosswalk and quality flags` (3fabd9e) ·
  **ROLLER:** — (rides with the Phase 1 quality module)

---

## Phase 1.5 — Walking skeleton [s:53ce5611]

Opened 2026-09-10 for the thin end-to-end slice PRD §9 inserts between Phase 1 and Phase 2
(OQ-0.6): ~100-case extraction → minimal DuckDB → logreg → one throwaway page, one command,
numbers are not claims. Everything here is explicitly throwaway; the calls below are about
keeping the throwaway honest, not about the Phase 3–8 designs.

- [x] [s:53ce5611] OQ-1.5.1 — Where does the 100-card extraction artifact live?
  **Context.** OQ-0.2 makes versioned JSONL artifacts with prompt hashes the unit of
  provenance ("committed or checksummed"). OQ-1.1 (b) and OQ-0.4 forbid redistributing raw
  or modified data, and a case card is an LLM paraphrase of a `Findings` narrative, i.e.
  modified data. `data/` is gitignored wholesale.
  **Options.** (a) the cards stay under `data/interim/skeleton/` (gitignored), regenerable
  by the extraction workflow, each row carrying `prompt_hash`, `prompt_version`, `model`,
  `workflow`, `extractor`; the committed artifacts are the prompt, the schema, the sampler
  and synthetic test cards; (b) commit the 100 cards; (c) commit only a manifest with the
  JSONL's sha256.
  **Assumed:** (a) — consistent with every ruled policy; Phase 3 fixes the real artifact
  contract before any full-corpus run.
  **Recommendation:** (a).
  **Ruled 2026-09-10:** owner — (a): the cards stay gitignored and regenerable; prompt, schema,
  sampler and synthetic fixture cards are the committed artifacts. · **Landed:** `add : skeleton
  case card schema prompt and sampler` (926a0e5) · **ROLLER:** — (nothing beyond
  the phase's own commit)

- [x] [s:53ce5611] OQ-1.5.2 — Who executes the 100-case extraction?
  **Context.** OQ-0.2: LLM stages run as Claude Code agent workflows, `claude-opus-5` for
  judgment-heavy surfaces and `claude-haiku-4-5` for bulk full-corpus passes; CLAUDE.md
  pins every teammate to `sonnet` unless the owner says otherwise. 100 cases is neither a
  full-corpus pass nor a judgment surface.
  **Options.** (a) three sonnet teammates, ~34 cases each, reading the sampled narratives
  from a local gitignored file and writing JSONL cards against the versioned prompt;
  (b) one teammate for all 100 (slower, one long generation); (c) haiku-class per the
  OQ-0.2 bulk rule (needs the owner to say so per CLAUDE.md).
  **Assumed:** (a).
  **Recommendation:** (a).
  **Observed 2026-09-10:** three sonnet extractors finished 36/35/35 cards in 14–25 minutes each;
  one went idle after reading and needed a nudge (a replacement was spawned in parallel and
  discarded when the original finished first). All 106 cards validate, carry one prompt
  hash, and show zero verdict leakage in any field; 103 carry `verdict_language_omitted`.
  Evidence typing drifts by extractor (a: 25 studies / 10 guidelines; b: 15 / 18; c: 17 /
  10) — the annotation-guide problem OQ-1.5.10 names.
  **Ruled 2026-09-10:** owner — (a): sonnet teammates as the extraction stage for the skeleton;
  the bulk model for the full-corpus run is Phase 3's call (OQ-0.2 names haiku-class for
  bulk). · **Landed:** nothing to change (the 106 cards are the artifact, gitignored per
  OQ-1.5.1) · **ROLLER:** —

- [x] [s:53ce5611] OQ-1.5.3 — Precedent list for the skeleton: SQL over the full parquet, or a slice-only lookup?
  **Context.** The DoD wants "a prediction + precedent list for a sample case". Phase 4 owns
  real retrieval (BM25 + dense). DuckDB reads the 42,749-row parquet directly, so a
  category-match + recency query over the whole corpus costs nothing. OQ-0.1's amendment
  applies to precedents that feed a predictor; the skeleton's logreg uses none, so the
  list is display-only (raw `Findings` allowed with citation, PRD §5 item 5) — but
  self-exclusion and the strictly-earlier-year pool are applied anyway so nobody inherits
  a leaky habit.
  **Options.** (a) SQL over the full parquet: same `diagnosis_category` + `treatment_category`
  + `case_type`, `report_year` < the query case's, self-excluded, newest first, top 5;
  (b) the same over the 100-card slice only (mostly empty lists).
  **Assumed:** (a).
  **Recommendation:** (a).
  **Observed 2026-09-10:** works — five precedents for the default case, all from the year
  before the query, query excluded, `match_level` reported. Cost: `build` copies the whole
  parquet into the DuckDB file (112 MB) on every run; still ~1 s, but Phase 4 should read
  the parquet as a view rather than materialize it.
  **Ruled 2026-09-10:** owner — (a): SQL over the full parquet, display-only, self-excluded,
  strictly earlier years; the materialize-vs-view cost is carried into Phase 4's warehouse
  design. · **Landed:** `add : skeleton duckdb warehouse and precedents` (76915c9)
  · **ROLLER:** —

- [x] [s:53ce5611] OQ-1.5.4 — How are the ~100 cases sampled?
  **Context.** Phase 2 owns the real 250-case stratification (type × determination × era).
  The skeleton needs ~100 rows that exercise every seam, deterministically.
  **Options.** (a) seed 42, stratified by `case_type` × `overturned` × era (≤2021 vs
  2022–2025 per OQ-1.5), 2001 and 2026 excluded, rows with `flag_findings_short` excluded,
  quota-filled to ~100 with Urgent Care's small strata taken whole; (b) uniform random 100.
  **Assumed:** (a).
  **Recommendation:** (a).
  **Observed 2026-09-10:** the real corpus lands at 106 rows, not 95–105 — the floor of 2 per
  stratum across twelve strata pushes the total over `n`; Urgent Care's four small strata are
  taken whole (4+4 rows). Harmless; recorded so the band isn't mistaken for a contract.
  **Ruled 2026-09-10:** owner — (a): seeded stratified sample as built; 106 rows is the
  outcome, not a defect. · **Landed:** `add : skeleton case card schema prompt and sampler`
  (926a0e5) · **ROLLER:** —

- [x] [s:53ce5611] OQ-1.5.5 — What is the "single-page demo" before the design zip exists?
  **Context.** OQ-0.3: the Phase 1.5 page is a minimal hand-written throwaway, not the
  Phase 8 React frontend; PRD §9 allows "CLI or minimal React page".
  **Options.** (a) one static HTML file rendered by Python from the run's results
  (prediction, top drivers, precedent list, the mandatory disclaimer footer), written next
  to the artifacts (gitignored), plus the same content printed to the terminal;
  (b) a React/Vite page (a JS toolchain for a throwaway); (c) CLI only.
  **Assumed:** (a).
  **Recommendation:** (a).
  **Observed 2026-09-10:** works — `demo.html` is 5.5 KB, self-contained, escaped, footer and
  banner present, byte-identical across two runs (no timestamps).
  **Ruled 2026-09-10:** owner — (a): the static, escaped, timestamp-free HTML page plus the
  terminal summary. · **Landed:** `add : skeleton logreg baseline page and run command`
  (2faed5d) · **ROLLER:** —

- [x] [s:53ce5611] OQ-1.5.6 — Seam: DuckDB ↔ polars interop needs pyarrow, which OQ-1.9 kept out of the stack
  **Context.** Found by vortex-warehouse before writing `skeleton/warehouse.py`: every
  DuckDB↔polars bridge (`con.register(df)`, `.pl()`, `.df()`, `.arrow()`) goes through
  polars' `to_arrow()`, which raises `ModuleNotFoundError` without pyarrow. OQ-1.9 ruled
  pyarrow out ("polars has native parquet, no pyarrow needed"), which is true for Phase 1
  and false the moment DuckDB and polars have to exchange frames in memory. Phase 4's
  warehouse (PRD §6: DuckDB star schema, polars loaders) sits right on this wall.
  **Options.** (a) skeleton keeps the contained workaround — polars writes a scratch
  parquet, DuckDB `read_parquet`s it; results come back via DB-API `fetchall()` +
  `cursor.description` hand-assembled into polars; `evidence_kinds` round-trips as a
  native `LIST(VARCHAR)` — and Phase 4 decides whether to add pyarrow when it designs the
  real warehouse; (b) add pyarrow now (revisits OQ-1.9); (c) drop polars on the DuckDB
  side and use DuckDB's own relational API end to end in Phase 4.
  **Assumed:** (a) — two dozen lines, no new dependency, throwaway phase.
  **Recommendation:** (a) now; (b) is the likely Phase 4 answer and should be ruled there
  with the warehouse design, not smuggled in here.
  **Ruled 2026-09-10:** owner — (a): keep the contained workaround; pyarrow is ruled with
  Phase 4's warehouse design (TODO.md Phase 4 carries the pointer). · **Landed:** `add :
  skeleton duckdb warehouse and precedents` (76915c9) · **ROLLER:** —

- [x] [s:53ce5611] OQ-1.5.7 — Seam: the evidence-kind feature vocabulary is observed, not declared
  **Context.** Found by neon-baseline: `evidence_cited` kinds are free-form per card, so at
  100 rows there is no guarantee the train split sees every kind the test split does.
  Without pinning the vocabulary at fit time, a test-only kind silently misaligns the
  one-hot columns against the fitted coefficients — same matrix shape, wrong meaning, no
  crash. The skeleton's `Baseline.fit` learns the kind vocabulary from train and
  `predict_proba` reuses it (`features(df, known_kinds=…)`, an additive kwarg on the
  fixed interface); an unseen kind at predict time is dropped, not misaligned.
  **Options.** (a) skeleton: observed-from-train, as built; (b) Phase 5's real feature
  pipeline reserves one column per `EvidenceKind` enum value regardless of what is
  observed, so the design matrix is a function of the schema, not of the sample;
  (c) observed-only forever.
  **Assumed:** (a) for the skeleton.
  **Recommendation:** (b) in Phase 5 — a feature space defined by the schema is the only
  one that survives a refresh; rule it with the Phase 5 feature design.
  **Ruled 2026-09-10:** owner — (a) for the skeleton; (b), a schema-declared evidence-kind
  feature space, is recorded as the Phase 5 design (TODO.md Phase 5 carries the pointer).
  · **Landed:** `add : skeleton logreg baseline page and run command` (2faed5d)
  · **ROLLER:** —

- [x] [s:53ce5611] OQ-1.5.8 — Seam: the joined slice hands the query case its own answer key
  **Context.** Found by neon-baseline: `warehouse.slice_frame` returns every parquet column
  joined to the card — `findings`, `overturned`, `determination_raw`, `days_to_*` — for the
  query case as well as for training rows. The model never sees them (`baseline.features`
  selects only the six structured columns plus the card fields and asserts nothing
  forbidden leaks into the names), and `page.render` allowlists which case fields it ever
  prints instead of iterating `case.items()`, so the demo does not print the outcome next
  to the "prediction". But the leak-shaped object exists one dictionary away from the UI,
  and Phase 8's `/case` and `/predict` endpoints will be built on something like it.
  **Options.** (a) skeleton: allowlist in the page, as built; (b) Phase 8's API serves a
  case-card projection (card fields + `PREDICTION_ELIGIBLE` structured fields) and never
  the parquet row; the display record with cited `findings` is a separate precedent
  surface (OQ-0.1 §5, Phase 4's two retrieval surfaces); (c) strip the post-decision
  columns from `slice_frame` itself.
  **Assumed:** (a).
  **Recommendation:** (b), ruled with the Phase 8 API contract; (c) would also break the
  skeleton's training path, which needs `overturned`.
  **Ruled 2026-09-10:** owner — (a) for the skeleton; (b), the API serves a case-card
  projection and never the parquet row, is recorded as the Phase 8 contract (TODO.md Phase 8
  carries the pointer). · **Landed:** `add : skeleton logreg baseline page and run command`
  (2faed5d) · **ROLLER:** —

- [x] [s:53ce5611] OQ-1.5.9 — Seam: `row_id` is source order, not time
  **Context.** neon-baseline's first real-scale smoke test sampled "the first N rows" of
  the parquet and `temporal_split` refused it: the source CSV is not chronological —
  `row_id` 0–28 are all ReportYear 2026 — so a low `row_id` is not an old case, and any
  "head of the file" sample is 2026-heavy.
  **Ruled 2026-09-10 (by the code):** `row_id` is the pinned snapshot's row order and
  nothing else (schema.py docstring, OQ-1.0 Schema table); `sample_row_ids` stratifies by
  `report_year` and never by position, `precedents` orders by `report_year`, and the
  fail-loud split is what caught the bad sample. Evidence: neon-baseline's scratch run,
  2026-09-10; `data/interim/imr_cases.parquet` rows 0–28. Nothing to change; the fact is
  recorded so nobody downstream treats `row_id` as a recency proxy.
  · **Landed:** nothing to change · **ROLLER:** —

- [x] [s:53ce5611] OQ-1.5.10 — Seam: the narrative never marks where cited evidence ends and the reviewer's reasoning begins
  **Context.** Reported by extractors a and b over 71 real cards. A sentence dressed as a
  citation is often the reviewer's unattributed opinion with no named study or guideline
  to hang a tag on; under the scrub rule it is excluded, so cards come out thinner than the
  source (16 of 71 cards have empty `evidence_cited`; the median card cites one item).
  Standardized scoring frameworks (ASAM, CALOCUS-CASII) are the sharpest case: a
  legitimate guideline citation fused with the reviewer's per-dimension scores, which are
  the verdict wearing a rubric — extractors kept the framework as `guideline` evidence and
  dropped every score.
  **Options.** (a) accept thin cards as the honest reading (what the skeleton did);
  (b) Phase 2's annotation guide adds an explicit evidence-attribution rule (evidence
  counts only when the narrative attributes it to a party before the review; a framework
  name is evidence, its scores are not) and Phase 2's schema records `attribution` per
  evidence item; (c) let extractors include reviewer-cited literature as evidence
  (leak-shaped: the reviewer chose it after deciding).
  **Assumed:** (a) for the skeleton.
  **Recommendation:** (b), ruled with the Phase 2 case-card schema, using the line extractor c
  drew and held across 35 cards: attributable external content stated as a general clinical
  position (a named guideline's recommendation, a study's finding) is evidence; the
  reviewer's own scoring or synthesis of this patient against a framework is not, however
  specific it looks. Across all 106 cards, 28 (26%) cite nothing under that line.
  **Observed 2026-09-10, an accidental inter-rater measurement:** the same 35 narratives were
  extracted independently by two extractors (c, and the replacement d spawned during c's
  silence): 12 vs 16 empty-evidence cards, 42 vs 46 evidence items, identical denial-basis
  calls (0 deviations each), every card scrubbed in both. Where the two disagree is
  exactly the attribution line above — the variance OQ-0.4's N-annotator design exists to
  measure and escalate; Phase 2's guide should fix the line before, not after, annotation.
  **Ruled 2026-09-10:** owner — (a) for the skeleton; (b), the explicit attribution line and a
  per-item `attribution` field, is recorded for Phase 2's annotation guide and card schema
  (TODO.md Phase 2 carries the pointer). · **Landed:** nothing to change in the skeleton
  · **ROLLER:** —

- [x] [s:53ce5611] OQ-1.5.11 — Seam: `payer_rationale` is stated in some narratives and has to be reconstructed in others
  **Context.** Reported by both extractors: some narratives quote the plan's denial letter
  ("the plan denied X indicating Y"); many — especially those that end in an overturn —
  never separate the plan's original reasoning from the reviewer's own walkthrough and
  simply argue the clinical case for the treatment. There the field is a paraphrase from
  context, or a generic "denied as not medically necessary, no further detail" line. Two
  extractors handled this the same way by instinct, not by rule, so consistency across the
  merged set is luck. For Experimental/Investigational cases the statutory test ("likely to
  be more beneficial than any available standard therapy") is at once the generic denial
  rationale and the case-specific verdict, a sharper leak trap than upheld/overturned.
  **Options.** (a) skeleton: as extracted; (b) Phase 2's schema adds
  `payer_rationale_source: stated | inferred | absent` and the annotation guide fixes the
  E/I phrasing rule (rationale stays generic; the beneficial-vs-standard formula is never
  restated); (c) drop `payer_rationale` from the card when not stated.
  **Assumed:** (a).
  **Recommendation:** (b).
  **Ruled 2026-09-10:** owner — (a) for the skeleton; (b), a `payer_rationale_source` field and
  the E/I phrasing rule, is recorded for Phase 2's schema and annotation guide (TODO.md
  Phase 2 carries the pointer). · **Landed:** nothing to change in the skeleton · **ROLLER:** —

- [x] [s:53ce5611] OQ-1.5.12 — Seam: Phase 3's scrub cannot rely on section markers or on a fixed verdict vocabulary
  **Context.** Verdict language is present in 68 of 71 cards' sources (the three exceptions
  are narratives that stop before a conclusion). Pre-2013–2016 narratives (extractors put the boundary between those years; roughly a
  third of each slice) skip the
  "Nature of Statutory Criteria → Final Result → Credentials" template and end on a bare
  concluding sentence that states the determination just as plainly, so a scrub keyed on
  the `Final Result:` string misses them — consistent with the EDA's marker-prevalence
  dip to 18.8% in 2020 and the pre-2007 gaps. Multi-item requests carry per-item verdicts
  (one case rules on eight concurrent medications separately), and partial overturns make
  the reviewer's approved quantity or session count itself outcome content, so a scrub
  that removes the last paragraph still leaks.
  **Options.** (a) Phase 3's scrub is structural-first (drop `Final Result:` blocks where
  present) then sentence-level (verdict-language detector over every sentence), with
  per-item and quantity-aware rules and the adversarial sentinel as the judge — the
  design OQ-0.1 already implies; (b) marker-only scrub (fails on the older third of the
  corpus); (c) LLM-only scrub with no detector (unauditable).
  **Assumed:** (a) is the Phase 3 design; nothing changes in the skeleton.
  **Recommendation:** (a); the skeleton's extractor findings are the first test cases for
  Phase 3's detector fixture.
  **Ruled 2026-09-10:** owner — (a): structural-then-sentence-level scrub with per-item and
  quantity-aware rules and the sentinel as judge is the Phase 3 design (TODO.md Phase 3
  carries the pointer); the skeleton's source patterns seed the detector fixture.
  · **Landed:** nothing to change in the skeleton · **ROLLER:** —

- [x] [s:53ce5611] OQ-1.5.13 — Seam: structured fields disagree with the narrative in a small share of rows
  **Context.** In 71 cards: two rows whose `age_range`/`patient_gender` contradict the
  narrative's stated age and sex (one is Male / 21–30 in the row and a 27-year-old woman in
  the text; one has null demographics in the row and a stated age and sex in the text);
  one row whose `diagnosis_category` is an infectious-disease label while the narrative is
  entirely about chronic pain; one `Urgent Care` case adjudicated on medical-necessity
  criteria with no emergency-services test (`denial_basis_differs_from_case_type`); one
  request sentence grammatically missing the treatment name; one garbled dangling clause.
  Extractors followed the spec ("drawn from findings") and used the narrative. None of this
  is visible to Phase 1's flags, which never read the narrative's content.
  **Options.** (a) note it; (b) Phase 3's extraction emits `field_conflicts[]` (which
  structured field the narrative contradicts) so a quality flag can be derived from the
  cards, joining Phase 1's eight; (c) treat the structured field as truth and ignore the
  narrative.
  **Assumed:** (a).
  **Recommendation:** (b) — cheap at extraction time, impossible later.
  **Ruled 2026-09-10:** owner — (a) now; (b), `field_conflicts[]` emitted at extraction and a
  derived ninth quality flag, is recorded for Phase 3 (TODO.md Phase 3 carries the pointer).
  · **Landed:** nothing to change in the skeleton · **ROLLER:** —
