# repeal: what, why, and how

**Journey 1. Written 2026-09-10, against branch `rep-01`.** Phase 0 and Phase 1 are
complete and committed; Phase 1.5 (the walking skeleton) is open and in progress as this
is written — the task board shows three teammates mid-build on the extraction, warehouse,
and baseline/demo modules described in §6.3, and none of that code has landed in the tree
yet. Every number below is checked against `OQ.md`, `ROLLER.md`, `TODO.md`, `PRD.md`,
`docs/data-card.md`, `docs/evals/eda.md`, and the actual source files under
`src/repeal/ingest/` as they stand today — file paths and ledger IDs are cited inline so
you can verify anything here yourself. The next journey document should pick up from
wherever Phase 1.5 lands.

This is written for two readers sharing one page: someone deciding whether to hire the
person who built this, and an engineer who wants to know exactly how it works. Each
section opens in plain language — what it is and why it matters — and gets more
technical as it goes. Skim the first paragraph of a section for the pitch; read the rest
for the mechanism.

---

## 1. Why this exists

Health insurance denials in the US are a numbers game that patients lose by default. Per
Kaiser Family Foundation's (KFF) analysis of federal transparency data, HealthCare.gov
insurers denied roughly 19% of in-network claims in 2024. Fewer than 1% of those denials
were ever appealed. Of the ones that were appealed, the outcomes are almost embarrassing:
across Medicare Advantage, Medicaid managed-care, and ACA marketplace plans, somewhere
between 43% and 67% of appealed prior-authorization denials got overturned — Medicare
Advantage standard appeals ran about 67% overturned, and some individual insurers cleared
90%+. Read those two facts together and the story isn't "insurers are usually right and
patients occasionally win." It's "appeals usually win, and almost nobody files one."

That gap is not a persuasion problem, it's a labor problem. Deciding *which* denials are
worth the fight, and then *drafting* the appeal, is expensive human work — a revenue-cycle
or denials analyst has to read a denial letter, guess whether external review is winnable,
find something like it that won before, and write a letter grounded in real precedent and
real evidence. Most organizations don't have the staff-hours to do that at scale, so the
overwhelming majority of winnable appeals never get filed. `repeal` ("re: your denial")
is a bet that this specific bottleneck — triage plus drafting — is exactly the kind of
thing language models and retrieval systems are good at, provided you don't cheat.

The reason there's a "provided you don't cheat" clause is the data source. `repeal` is
built entirely on the California Department of Managed Health Care (DMHC) Independent
Medical Review (IMR) determinations dataset — every external-review decision the state
has made public since 2001, 42,749 of them as of the pinned 2026-06-01 snapshot (source
and provenance in §6.2). An IMR is what happens when a patient exhausts their health
plan's internal appeal process and asks the state to send the case to an independent
physician reviewer instead. It is, as far as this project's owner could determine, the
only large public corpus of real appeal decisions that comes with both a reviewer's
narrative *and* a labeled outcome (upheld or overturned) attached to real denial
categories. That is also exactly why its numbers can't be read as "how often does
appealing work" — every case in this corpus already survived internal appeal before it
got anywhere near external review. That's a selection-biased sample by construction, and
every prediction this system will ever produce is framed as *external-review overturn
likelihood*, never "should you appeal at all" (this framing is PRD §5 item 4, enforced as
a caveat on every model output, and it's the same caveat printed in `README.md`).

There's a second reason this project exists, stated with equal priority in the PRD: it's
a portfolio piece. The owner is using `repeal` to demonstrate a specific, unusually broad
slate of skills in one coherent system — clinical natural-language processing (NLP, the
subfield of ML concerned with understanding text), LLM-based information extraction,
hybrid retrieval, calibrated machine learning, grounded text generation, natural-language-
to-SQL translation, eval-first engineering practice, and a fully logged decision trail
(the `OQ.md`/`ROLLER.md` ledger pair described in §4). The demo audience named explicitly
in the PRD is a recruiter or interviewer who has five minutes to grasp the whole system
(PRD §2). Everything about how this project is scoped, phased, and documented — including
this document — is shaped by that constraint as much as by the product goal.

## 2. What we are building

Three things, all built on top of one shared corpus and one shared leakage discipline
(§3). First, **precedent retrieval**: given a denial, find comparable cases that actually
went to external review, so an analyst can see what similar fights looked like and how
they ended. Second, a **calibrated overturn-likelihood estimate**: not just a yes/no
guess but a number that means what it says — if the model says 70%, roughly 70% of cases
it says that about should actually overturn, checked against a held-out time window
rather than tuned to look good on training data. Third, **grounded appeal-letter
drafting**: an LLM writes the actual appeal letter, but every factual claim in it has to
trace back to a cited source (a precedent case, a guideline snippet), and the generator is
checked — not just prompted — to reject uncited claims and fabricated citations.

The primary persona is a provider-side revenue-cycle or denials analyst — someone on the
side of a hospital or medical group, not the insurer. Their three jobs, in order: decide
which already-denied, already-internally-appealed cases are worth escalating to external
review; find winning precedent fast; draft a grounded letter in minutes instead of hours.
A secondary, explicitly stretch-goal persona (v1.1, not v1) flips the lens to the payer
side — utilization-management QA asking "would this denial survive external review if
challenged?" (PRD §2).

Technically, the system is a pipeline with four consumer-facing surfaces sitting on one
warehouse: a CSV ingest that becomes a validated Parquet table; an LLM extraction and
scrub stage that turns each case's free-text reviewer narrative into a structured,
verdict-scrubbed "case card"; a DuckDB warehouse joining raw cases, case cards, and
evidence; and, fed by that warehouse, hybrid retrieval (lexical + embedding), a
calibrated classifier, a citation-checked letter generator, and — if it survives to v1,
see §7 — a text-to-SQL analytics agent over the same warehouse. All four consumer surfaces
sit behind one FastAPI service and one React/Vite frontend (PRD §6 has the full diagram;
the frontend is currently blocked on a design-asset delivery, §7). The five-minute-demo
constraint drove real architecture decisions, not just polish: it's the stated reason the
project moved off Streamlit and onto a real React/Vite frontend once a design system
became available cheaply enough to justify the switch (`OQ-0.3`, detailed in §6.1).

## 3. The one idea that makes this hard

Here's the trap a naive version of this project falls into on day one: the corpus's
`Findings` column — the reviewer's narrative explaining the decision — is written *after*
the decision and routinely just states the verdict in plain English (a sentence to the
effect of "the reviewer determined the requested service was medically necessary" is a
completely ordinary thing for this text to contain). Train a classifier on that text and
you will get a model that scores close to perfect. You will also have built nothing,
because you've trained a model to read the answer already written on the page. This is
the single design constraint everything else in `repeal` bends around, and it's the
project's answer to the obvious follow-up question a reviewer should ask: "your model
predicts denial outcomes — did you accidentally let it read the outcome?"

The fix, ruled as `OQ-0.1` (`PRD.md` §5, landed `28b17eb`, 2026-08-16) and called the
**leakage protocol**, has five parts. First, an inference-time contract: every prediction
runs on a *pre-decision case card* — the information a provider actually has at denial
time (patient context, diagnosis, treatment requested, the payer's stated denial
rationale, evidence available) — and raw `Findings` text is never a prediction input,
full stop. Second, a pipeline: LLM extraction reconstructs that case card from `Findings`
while explicitly scrubbing every verdict/outcome word out of it. Third, a validation
suite that runs in CI: a verdict-language detector (a regex battery plus an LLM audit
pass, target residual rate under 2%); an **adversarial sentinel** — a TF-IDF (term
frequency–inverse document frequency, a classic way to turn text into numeric features
weighted by how distinctive a word is) plus logistic-regression model trained once on raw
`Findings` and once on scrubbed case cards, with both numbers published in every eval
report going forward, so a near-perfect raw score next to a much lower scrubbed score is
the receipt that the scrub actually worked; and a human spot-check of 50 cases with a
logged checklist. Fourth, a framing rule: every model output is labeled *"external-review
overturn likelihood,"* not "appeal success likelihood," carrying the selection-bias
caveat from §1 into the UI itself. Fifth, an explicit carve-out: raw `Findings` text *is*
allowed in retrieval display and letter-generation grounding, with citation, because
those are human-in-the-loop surfaces where a person reads the source before acting on it
— not blind prediction inputs.

That carve-out is also where the leakage protocol gets a second, less obvious problem,
and the project's response to it is a good example of the kind of thinking this system
tries to demonstrate. Phase 5's baseline ladder (§7) ends with an LLM few-shot predictor
that retrieves precedent cases and puts them in the prompt. If those retrieved precedents
are the same "display record" objects that carry raw `Findings`, the leakage protocol's
carve-out for human-in-the-loop display just became a backdoor for feeding raw outcome
language straight into a *prediction* surface — clause five permits raw text for display
and generation, not for this. `OQ-0.1`'s amendment closes that gap with three rules
enforced in code and covered by tests, not left to prompt discipline: precedents fed to a
predictor are represented as **(scrubbed case card + `Determination` label) only** — raw
text never enters that prompt, not as context, not as a citation, not truncated; the
precedent pool for any test-set prediction is restricted to cases decided strictly before
the query case's `ReportYear`, mirroring the temporal split so future decisions can never
inform past-facing predictions; and the query case (plus any exact-duplicate
`ReferenceID`) is always excluded from its own precedent pool. The acknowledged cost,
stated plainly in the ruling: this few-shot predictor "will look worse than a leaky
version would — that is the point, the gap is reported, not fixed." A model that's honest
about being handicapped is worth more here than a model that quietly isn't.

One more wrinkle, resolved as `OQ-1.4` once the real CSV header turned up three fields the
PRD hadn't anticipated: `IMRType`, `DaysToReview`, `DaysToAdopt`. The two `Days*` fields
measure how long the review itself took — they don't exist until after the review
finishes, so they're tagged post-decision and permanently excluded from every predictor's
feature set (enforced by a machine-readable tag in `schema.py`, not a comment someone has
to remember). `IMRType` (Standard vs. Expedited) is different: it's set at the moment the
case is *filed*, before any review happens, so it's legitimately pre-decision information
and is prediction-eligible — with the nuance that "known at filing" isn't quite the same
as "known at denial time," which the eventual model card will say outright rather than
paper over.

## 4. How we decide

This project made the decision log load-bearing: nothing commits
until it's current. `OQ.md` is a ledger — one entry per call, whether it's an architecture
choice or a one-line data question — with a fixed shape: **Context** (what's actually
true, with numbers), **Options** (including the ones rejected, and why), **Assumed** (the
call the builder made to keep moving without waiting on an answer), a **Recommendation**,
and then `Ruled <date>:` with the owner's actual decision and `Landed <hash>` once the
change is in the tree. `ROLLER.md` is the other half: any ruling that requires an actual
code or doc change gets exactly one `ROLLER.md` tick-box, cross-referenced both directions
with the OQ entry, so there's no ruling that silently never became work and no work item
floating around with no ruling behind it.

The mechanical rule that makes this more than documentation theater: a question never
blocks *work* — the builder writes down an **Assumed** call and keeps going, because
waiting on every open question would stall the whole project on the owner's inbox. What a
question blocks is *commits*. Before anything lands, whoever's building greps both
ledgers for their own session's tag and it has to come back empty:
`grep -nE '^\s*- \[ \] \[s:<tag>\]' OQ.md ROLLER.md`. One open box with your tag on it and
you're not committing yet, no matter how done the code looks. This is the same
non-negotiable posture as the pytest pre-commit hook, aimed one layer up — the hook
guards against broken tests, this guards against unreviewed decisions.

Three real examples, because the abstract description undersells how concrete this gets.
`OQ-1.1` asked whether a click-through terms modal on the dataset's portal page — which
names an unrelated state office (the Office of the Patient Advocate, OPA) and restricts
altering the data — actually binds a DMHC dataset it doesn't obviously belong to. The
owner ruled a "portfolio posture" (noncommercial use, every derived artifact flagged
modified/non-official, no raw or altered data ever redistributed) with one condition: go
check whether that modal is dataset-specific or portal-wide boilerplate. The follow-up
(`R-02`) fetched the raw HTML of DMHC's page and three unrelated organizations' dataset
pages plus OPA's own, byte-for-byte, and found the identical `id="popup"` fragment on all
of them — confirming it's boilerplate injected across the whole CalHHS portal, not a
DMHC- or OPA-specific restriction. That finding is now sitting in `docs/data-card.md`
under Terms & release determination, not just in someone's head.

`OQ-1.5` is the temporal-cutoff decision Phase 5's train/test split depends on. Rather
than pick a year by feel, the ruling fixed *criteria* first — test share between 15% and
25%, at least two full calendar years in the test window, a test era that's past the
label-drift plateau so calibration is judged against realistic base rates, 2026 excluded
because it's a partial year straddling a vocabulary migration, 2001 excluded as
negligible (28 rows) — and then had `profile.py` emit a candidate table for cutoff years
2019 through 2024 (reproduced in §6.2) before ruling on the actual year. 2021 won (22.4%
test share, four full modern years); 2022 also technically qualified (18.2%, three years)
but wasn't chosen. The point isn't that 2021 is obviously correct — it's that the
criteria, not the year, is the thing that got argued about, and the year is now frozen
and, per the PRD, never re-tuned.

`OQ-1.12` is the messiest one, and the most honest about it. The category-taxonomy
crosswalk (§6.2) had 16 legacy-to-2026 category mappings that were only best guesses, not
clean renames, and the ruling had three options on the table: apply none, apply all 16, or
apply exactly the subset that's a genuine ICD-10-chapter-consistent broadening rather than
a lossy merge. The owner picked the third option and asked for a design-trace note
explaining the reasoning — which is now sitting as a comment block at the top of
`src/repeal/ingest/resources/category_crosswalk_v1.yaml`, not just in the ledger. Nine of
the sixteen guesses got applied; seven stayed canonical as their legacy selves, covering
13,582 rows (31.8% of the whole corpus) that are still waiting on a real 2026 answer.
That's not a loose end anyone's hiding — it's flagged in `docs/data-card.md`'s Surprises
section and revisited the next time a full single-vocabulary year of data exists.

## 5. How we build

The mechanism, in one line: a lead plans and coordinates, named teammates write all the
code, and nothing ships until the lead has actually read the diff. `CLAUDE.md` — the
project's own operating manual, checked into the repo — makes this the *only* path: if
the lead's fingers produce anything ending in `.py`, that's treated as a bug in judgment,
not a shortcut. The lead explores with 2–3 scouts, clarifies open questions with the owner
(feeding straight into `OQ.md`, §4), plans in Claude Code's plan mode with a named roster
of 3–5 teammates on strictly disjoint files, executes by spawning those teammates with
full context baked into the spawn prompt (a teammate starts every task with zero memory
of anything said before it was spawned — if the lead doesn't say it, the teammate
invents it), and only then reviews. Review means reading `git diff` against what was
handed out, not the teammate's self-report of what it did — the project's own history has
at least one case where those two disagreed. Small fixes (a comment, a guard clause, a
stale docstring) get fixed inline; anything that's a real design call or a scope change
gets kicked back to the owner instead of quietly landing.

Every feature in this codebase is built test-first: write the failing test, run it, watch
it fail (the "red" is proof the test tests something real, not a tautology), write the
minimum code that turns it green, then refactor with the safety net already in place. For
a new module `src/xxx/foo.py`, the test file `tests/test_foo.py` gets written *before*
`foo.py` exists, so the first run fails on an import error — that's expected, not a bug. A
git pre-commit hook runs the full `uv run pytest` suite before every commit with no bypass
available; if it's red, the commit didn't happen. The teammate that owns an implementation
file owns its test file too — no "I'll write the code and someone else adds tests"
division of labor.

The LLM-execution model deserves its own paragraph because it's a genuinely unusual
choice, ruled as `OQ-0.2` (landed `28b17eb`). The original PRD specified an Anthropic API
client module with retries, JSONL cost logging, and a hard budget cap — the standard
shape for a metered LLM integration. But the owner runs this project through Claude Code
under a Max subscription, where the same extraction, annotation, and generation work
executes as agent/skill workflows at zero marginal API cost. Building a budget-cap system
to guard against a cost that doesn't exist would have been exactly the kind of
accidental complexity `CLAUDE.md`'s own sanity-check rules warn against, so the client
module, the cost meter, and the budget cap were all cut before a line of code existed for
them. Model assignment is by judgment level, not a fixed default: `claude-opus-5` for
judgment-heavy surfaces (gold-set annotation, scrub auditing, letter generation, LLM-as-
judge scoring), `claude-haiku-4-5` for bulk full-corpus extraction passes, and every
teammate spawned for ordinary build work runs on `claude-sonnet-5` per `CLAUDE.md`'s team
rules. What replaces a cost ledger as the reproducibility contract is the **artifact**:
every LLM stage writes a versioned JSONL or Parquet file carrying its prompt hash, prompt
version, model id, and workflow name, and everything downstream consumes that artifact,
never a live model call. The tradeoff is named directly in the ruling: no per-call cost
telemetry (there isn't a dollar figure to report, only wall-clock and agent effort — see
the Phase 1 gate line in §6.2 for what that looks like in practice), and an LLM-stage
re-run isn't guaranteed to reproduce byte-for-byte the way the pure-code ingest pipeline
is (§6.2) — the committed artifact, not the replayed call, is the unit of truth.

## 6. What has been built so far

### 6.1 Phase 0 — scaffold (2026-08-16)

Four teammates on disjoint files: `phantom-amender` on the PRD itself, `cipher-scribe` on
the (now-folded, see below) decision records and data-card stub, `vortex-toolsmith` on the
toolchain/Makefile/pre-commit/CI, `blitz-skeleton` on the package skeleton and its smoke
tests. Before any of that shipped, a multi-agent review of the draft PRD surfaced 43
verified findings — naming drift across three different working titles (`overturn`,
`mimir`, `repeal`), a missing `.gitignore` entry for `data/`, a contradiction between when
Phase 2's retrieval judgments were supposed to be authored and when Phase 4's retrievers
would actually exist to judge against, an undefined temporal cutoff year, success-
criteria in PRD §3 that weren't actually measurable as originally written, and a direct
conflict between the PRD's "sequential phases" language and `CLAUDE.md`'s team-based
execution model. All of it got fixed before Phase 0 was called done. Total marginal API
spend: $0, by design (`OQ-0.2`, §5). The gate landed at 8 tests passing, with one item
still open today — GitHub Actions CI going green on the `maestro` branch — because branch
`rep-01` (this branch) hasn't been pushed and merged yet; that's tracked as `OQ-0.7`,
still `Ruled: pending`.

Four foundational rulings came out of Phase 0 and shape everything downstream: the
leakage protocol (`OQ-0.1`, §3); the no-API-client execution model (`OQ-0.2`, §5); the UI
stack — React/Vite frontend plus FastAPI backend, replacing an earlier Streamlit-first
plan once a recruiter-facing five-minute demo made Streamlit's ceiling the wrong tradeoff,
with Phase 8 now blocked on the owner delivering a design-asset "zip" (`OQ-0.3`, still
open as `OQ-0.8`, see §7); and the 250-case gold-set annotation methodology, including the
explicit disclosure that the same model family that annotates the gold set is later
evaluated against it (`OQ-0.4`, §7). The project's name itself was a Phase 0 ruling too —
`repeal`, replacing the working titles `overturn` and a stray `mimir` reference left over
from an unrelated template repo (`OQ-0.5`).

Originally, this project ran on four ADR (architecture decision record) documents plus
weekly build logs under `docs/`. On 2026-09-09, `CLAUDE.md` was rewritten to require the
`OQ.md`/`ROLLER.md` model described in §4, and its commit gate started grepping for files
that didn't exist yet — the Phase 1 design and its eleven open questions were sitting
untracked under `docs/ascension/` and `docs/oqs/` at the time. The owner ruled
(`OQ-P.1`/`OQ-P.2`/`OQ-P.3`, `R-01`) to fold everything into the two root-level ledgers,
keeping the originals' content in git history rather than deleting it — which is why every
Phase 0 entry in `OQ.md` today is labeled "ex-ADR-001" and so on. The four ADRs became
`OQ-0.1` through `OQ-0.4` verbatim in substance; only the filing system changed.

### 6.2 Phase 1 — ingest and EDA (design ruled 2026-09-09; built 2026-09-09/10)

The first real download turned up several things the PRD's authors couldn't have known
without fetching the file. The actual CSV is 85,409,358 bytes; CKAN (the open-data portal
software behind data.chhs.ca.gov) advertises a size and hash that are stale by about 14
MB, and the S3 `ETag` on the file is a multipart hash, not an md5 — so a self-computed
SHA-256 (recorded as `f68951823f6ffc09566cc190d97b2808e0269a069843efe809a3f5f90d4c893b` in
`data/raw/manifest.json`) is the only integrity anchor anyone can actually trust. The row
count came in at exactly 42,749 — matching the PRD's rough estimate of "~42.7k" almost
exactly. Upstream republishes the whole file periodically with no per-row dates and no
append feed, which is why the project pins one dated snapshot (`OQ-1.3`) rather than
tracking a moving target; a refresh is `uv run python -m repeal.ingest.run --refresh`, a
deliberate act, never automatic.

The real header has 14 columns, not the 11 the PRD assumed and not the 11 documented in
DMHC's own 2020 data-dictionary PDF — which also describes a field called `PaientAge`
*(sic)* as a number, when the actual field (`AgeRange`) is a 7-bucket text enum, top-coded
at `65+`. That PDF was formally ruled unusable as a schema source; `schema.py`'s 14-column
contract is authored from the live header and re-verified against reality on every
`make ingest` run, so schema drift fails loudly instead of silently mis-parsing.

The taxonomy turned out to be the hardest problem in the phase. Twenty-five years of raw
`DiagnosisCategory`/`TreatmentCategory` values don't form one vocabulary — read straight
off the CSV, 48 distinct diagnosis labels and 58 distinct treatment labels appear across
the corpus's history, and 2026 introduces a second, ICD-10-style (International
Classification of Diseases, 10th revision — the WHO's public-domain diagnosis coding
standard) spelling of the diagnosis axis that runs alongside the legacy one rather than
replacing it: the original portal recon, done before any crosswalk existed, counted 33
distinct raw diagnosis values in 2026 against a steady 24 in 2023–2025 (`OQ-1.0`). The
response, ruled across `OQ-1.2`, `OQ-1.12`, and `OQ-1.13`: canonicalize to the new
vocabulary at the category level only, preserve every raw label in a `*_raw` sibling
column, and apply only mappings that are actual renames or genuine broadenings. Fifteen
diagnosis and two treatment labels were clean renames, applied outright. Of sixteen
further best-guess mappings, nine survived a second look as ICD-10-chapter-consistent
broadenings and were applied (covering 4,815 diagnosis rows and 2,744 treatment rows);
the other seven — covering 13,582 rows, 31.8% of the entire corpus — stayed canonical as
their legacy selves rather than force a mapping that would have quietly merged two
different things. Once `normalize.py` collapses the raw spellings onto that one canonical
column, the diagnosis axis calms down considerably: `docs/evals/eda.md`'s vocabulary-by-
era table (computed on the canonical, post-crosswalk column, not the raw one) shows 21
canonical diagnosis labels in every year from 2020 through 2026, with exactly one label —
`Ear and Mastoid` — that's genuinely new in 2026 with no legacy-era counterpart at all.
The treatment axis didn't get the same relief: of 31 legacy treatment labels, only 2 have
a confident match in the new vocabulary (`OQ-1.2`), because 2026's treatment labels read
like CPT (Current Procedural Terminology, the AMA-licensed procedure code set this
project is contractually barred from using directly)/HCPCS (Healthcare Common Procedure
Coding System, the public-domain sibling standard) section names, not a renamed version
of the old scheme — and it shows in the same canonical table: treatment categories hold
at 28–29 distinct labels every year from 2019 through 2025, then jump to 35 in 2026, 21
of them brand new. `Pharmacy`, the single largest treatment category in the corpus at
11,948 rows (28% of every treatment-category row), has no 2026 counterpart at all — the
new vocabulary carries drug-specific HCPCS buckets instead — and neither do ten specialty
procedure labels (about 6,568 rows, which the 2026 scheme folds into one generic
`Surgery` bucket) nor a possible `DME` split (only 24 rows of evidence so far). All three
are left alone deliberately, revisited at the first refresh that brings a full,
single-vocabulary 2026 year. The full design trace lives as a comment block at the top of
`src/repeal/ingest/resources/category_crosswalk_v1.yaml`.

(One loose thread worth flagging rather than quietly resolving: `docs/data-card.md`'s own
Surprises section still describes the diagnosis axis as "24 steady, jumping to 33 in 2026
with 4 genuinely new labels" — the pre-crosswalk raw-label framing above, not updated to
the post-crosswalk canonical count this paragraph cites from `docs/evals/eda.md`. Both
numbers are real; they describe different columns, and the data card now says which.)

Two places the corpus corrected assumptions made before anyone had looked at real rows.
First: the original design brief guessed that Urgent Care cases carry a `UC` prefix on
their `ReferenceID`. Verifying all 42,749 real rows showed the actual, always-consistent
prefix set is `{MN, EI, UR}` — Urgent Care is `UR`, not `UC` — and the code comment in
`src/repeal/ingest/quality.py` (lines 29–36) says so plainly: "The OQ-1.0 spawn brief said
'UC' — that was wrong; it's 'UR'." Second, and more consequential: initial recon described
"one clean cohort" of 691 rows from 2001–2003 missing `AgeRange`, `PatientGender`, *and*
`DaysToReview` together. When the quality flag built on that three-way definition ran
against the real corpus, it matched zero rows. The actual situation, found by a
verification query and ruled as `OQ-1.14`: there are two *different*, same-sized, disjoint
691-row populations — one is `age_range` and `patient_gender` both null, all from
2001–2003 (27/646/18 rows by year); the other is `days_to_review` null, scattered across
seventeen separate years from 2007 through 2026 (65 rows alone in 2008). Same count,
unrelated rows, coincidence. `flag_legacy_cohort` was redefined to the two-column version
and the correction is recorded in `docs/data-card.md`'s Surprises section rather than
quietly patched away.

The phase also shipped eight quality flags — never row drops, only columns, because
exclusion is a downstream consumer's explicit and reported decision, not something ingest
decides unilaterally:

| Flag | Count | Share | What it catches |
|---|---|---|---|
| `flag_findings_short` | 3 | 0.01% | `findings` under 100 characters |
| `flag_findings_truncated` | 541 | 1.27% | ≥200 chars but doesn't end in terminal punctuation |
| `flag_encoding_artifact` | 0 | 0% | mojibake byte patterns |
| `flag_duplicate_reference_id` | 78 | 0.18% | `reference_id` shared with another row |
| `flag_duplicate_findings` | 202 | 0.47% | `findings` text shared with another row |
| `flag_legacy_cohort` | 691 | 1.62% | `age_range` and `patient_gender` both null |
| `flag_id_prefix_mismatch` | 0 | 0% | `reference_id` prefix disagrees with `case_type`/`report_year` |
| `has_section_markers` | 38,468 | 90.0% | contains a `Findings:`/`Final Result:`/`Credentials/Qualifications:` marker |

(Flags are independent, not mutually exclusive — a row can carry more than one. Full
table and threshold justification: `docs/data-card.md` § Quality flags.) The 78 rows
behind `flag_duplicate_reference_id` (39 ID pairs) turned out to be entirely benign — every
pair has identical `findings` text and an identical `overturned` label, reading as
re-submitted records rather than data corruption. The 202 rows behind
`flag_duplicate_findings` are a different story worth flagging forward to Phase 3: they
reduce to 93 distinct texts with a median length around 1,500–1,600 characters — these are
real narratives repeating, not a short boilerplate stub reused verbatim, which matters
because a naive "assume every `Findings` value is unique" assumption in the scrub pipeline
would be wrong for about half a percent of the corpus.

The label itself is far from stationary, which is the fact the temporal-cutoff decision
had to be built around. Pooled across all 25+ years, 52.5% of cases were overturned — but
no single year is close to that number: 25.0% in 2001, climbing through the 40s and 50s
across the 2010s, and sitting at 60–72% for essentially the entire 2020s (72.3% in 2025,
the highest full year in the corpus). A model trained on the full pooled distribution
would be calibrated to a base rate that no real year of deployment actually has. The
candidate table `profile.py` generated to settle this (full detail in
`docs/evals/eda.md` § Temporal-cutoff candidates):

| Cutoff year | Train rows | Test rows | Test share | Test years (full) | Meets all criteria |
|---|---|---|---|---|---|
| 2019 | 28,378 | 13,797 | 32.7% | 6 | no |
| 2020 | 30,575 | 11,600 | 27.5% | 5 | no |
| **2021** | **32,708** | **9,467** | **22.4%** | **4** | **yes — ruled** |
| 2022 | 34,484 | 7,691 | 18.2% | 3 | yes |
| 2023 | 36,730 | 5,445 | 12.9% | 2 | no |
| 2024 | 39,445 | 2,730 | 6.5% | 1 | no |

`OQ-1.5` ruled 2021 and froze it: train on everything through 2021, test on 2022–2025,
with 2001 (28 rows, negligible) and 2026 (546 rows, partial year, straddling the
vocabulary migration) excluded from both windows. Per the PRD, this year is not re-tuned
later regardless of what Phase 5 finds.

Phase 1's gate closed at 150 tests passing, with the real `make ingest` run verified
idempotent (byte-identical parquet across repeated runs against the same pinned snapshot)
and `make check-upstream` clean. Effort, recorded on the `TODO.md` gate line rather than
in a separate build log per `OQ-P.2`: five teammates (`neon-fetcher` on the downloader,
`cipher-contract` on the schema contract, `vortex-mapper` on the crosswalk and quality
flags, `phantom-profiler` on the EDA and data card, and `blitz-crosswalk` for the follow-up
crosswalk ruling), roughly 1 hour 45 minutes of wall-clock on 2026-09-09 plus about 20
minutes more on 2026-09-10, one build pass each plus 2–4 review rounds, $0 API cost.

### 6.3 Phase 1.5 — walking skeleton (opened 2026-09-10, in progress)

This phase exists to find integration breakage while there are still only two or three
real components wired together, not the full six-layer system — a deliberately throwaway
slice: extract roughly 100 cases with the real prompt shape, load them into a minimal
DuckDB table, fit a logistic-regression baseline, and put a prediction plus a precedent
list on one page, all through a single command. The DoD is explicit that the numbers this
produces are not claims about model quality — they're a check that the seams between
extraction, storage, and serving don't break.

Five design questions had to be answered to even start building the skeleton, and all
five are currently sitting as **assumed, not yet ruled** entries in `OQ.md` under Phase
1.5 (`OQ-1.5.1` through `OQ-1.5.5`, all tagged to the session that opened this phase,
2026-09-10). Work is proceeding on the assumed calls per the project's own rule that a
question never stops building, only commits (§4):

1. **Where the extraction artifacts live** (`OQ-1.5.1`) — assumed: gitignored under
   `data/interim/skeleton/`, each row carrying its prompt hash, prompt version, model,
   workflow, and extractor identity; only the prompt, the schema, the sampler, and
   synthetic test cards get committed, because a case card is an LLM paraphrase of a
   `Findings` narrative and therefore modified data under the no-redistribution rule
   (`OQ-1.1`, `OQ-0.4`).
2. **Who extracts the ~100 cases** (`OQ-1.5.2`) — assumed: three `sonnet`-class teammates
   splitting the load roughly evenly, since 100 cases is neither a full-corpus bulk pass
   (which would default to haiku-class per `OQ-0.2`) nor a judgment-heavy annotation
   surface (which would default to opus-class) — it's just build work, so it defaults to
   `CLAUDE.md`'s standard sonnet assignment.
3. **How the precedent list is assembled** (`OQ-1.5.3`) — assumed: a SQL query over the
   *full* 42,749-row parquet (matching category and case type, strictly earlier
   `report_year`, self-excluded, newest first), even though the skeleton's logistic
   regression doesn't actually consume any precedents — the self-exclusion and temporal
   restriction get applied anyway, purely so nobody downstream picks up a leaky habit by
   watching the skeleton do it wrong.
4. **How the ~100 cases are sampled** (`OQ-1.5.4`) — assumed: a fixed seed (42, the
   project-wide pinned seed from `src/repeal/config.py`), stratified by case type,
   overturned/upheld, and era (pre-/post-2021 cutoff), excluding 2001, 2026, and any row
   already flagged `flag_findings_short`.
5. **What the "single-page demo" actually is before the design system exists**
   (`OQ-1.5.5`) — assumed: a static HTML file rendered by Python from the run's output
   (prediction, top drivers, precedent list, the mandatory disclaimer footer) plus the
   same content printed to the terminal — explicitly a hand-written throwaway, not an
   early draft of the real Phase 8 frontend, because the real frontend is blocked on a
   design-asset delivery that hasn't happened yet (`OQ-0.3`, `OQ-0.8`).

As of this writing, three teammates are actively building against those assumptions:
one on `cards.py` (the case-card schema, the extraction prompt, the sampler, a merge/load
step, a CLI, and fixture cards for testing), one on `warehouse.py` (the DuckDB load of
cases, case cards, a slice view, and the precedent query), and one on
`baseline.py`/`page.py` (feature engineering, the logistic regression, the temporal
split, driver explanations, and the static page itself). None of that code exists in the
tree as of this document — `pyproject.toml` and `uv.lock` already show uncommitted
additions of `duckdb`, `pydantic`, and `scikit-learn` to support it, but the modules
themselves are still in progress. This section describes the design and its open
questions, not finished work; the next journey document is the right place to report
what actually landed.

## 7. What comes next

Six more phases stand between here and a shippable v1, each ending at a Definition of
Done the owner reviews before the next one starts (`PRD.md` §9). **Phase 2** builds the
250-case stratified annotation gold set — multiple independent LLM annotator agents per
case, disagreements escalating to an adjudicator pass, an owner human spot-check tier of
at least 25 cases weighted toward the disagreements — plus 50 retrieval-query stems and a
30-case generation rubric, released as `ReferenceID`s plus annotations plus a join script,
never the underlying `Findings` text. **Phase 3** runs LLM extraction over the full
corpus, implements the scrub, and wires the full `OQ-0.1` validation suite — including the
adversarial sentinel — into CI, targeting macro F1 (the harmonic mean of precision and
recall, averaged evenly across fields) of at least 0.80 against the Phase 2 gold set, with
the circularity caveat attached to that number every time it's quoted. **Phase 4** builds
the DuckDB warehouse and hybrid retrieval: BM25 (a standard lexical ranking function that
scores documents by term overlap weighted by how rare and how concentrated each term is)
combined with dense embedding similarity, kept as two genuinely separate retrieval
surfaces — one for human-facing display that may include cited `Findings`, one for
prediction that only ever returns case-card projections — with pooled relevance judgments
authored here rather than in Phase 2, because pooling requires candidate lists from
retrieval systems that don't exist until this phase, targeting Recall@10 (the fraction of
known-relevant precedents that show up somewhere in the top 10 results) of at least 0.70
on the judged query set. **Phase 5** trains the overturn predictor through a fixed baseline
ladder (majority class, then structured-feature logistic regression, then TF-IDF-on-
scrubbed-text logistic regression doubling as an extra leakage check, then LightGBM, then
the handicapped LLM few-shot predictor from §3), evaluated on AUC (area under the ROC
curve — how well the model ranks overturned cases above upheld ones across every possible
threshold) and ECE (expected calibration error — how far predicted probabilities drift
from actual outcome frequencies; target ≤0.05), with SHAP (SHapley Additive exPlanations,
a standard way to attribute a prediction back to which input features drove it) values
explaining the top drivers. **Phase 6** generates the actual appeal letters, with a
post-generation checker rejecting uncited claims and fabricated citations, targeting 95%+
citation faithfulness. **Phase 7**, a natural-language-to-SQL analytics agent over the
warehouse targeting 85%+ execution accuracy against 40 hand-written question/gold-SQL
pairs, is explicitly cuttable to a later release — cut whole or not at all, never shipped
half-working (`OQ-0.6`). **Phase 8** wires FastAPI and the React/Vite frontend
together into one demo-able product with a disclaimer footer on every page.

Three things are blocked on the owner right now, tracked as open (`Ruled: pending`)
entries in `OQ.md`: the design-asset delivery that unblocks all Phase 8 frontend work
(`OQ-0.8`) — the Phase 1.5 page is deliberately hand-rolled specifically because this
hasn't landed yet; the first push of branch `rep-01` to `maestro` so GitHub Actions CI
actually runs for the first time (`OQ-0.7`); and two lower-urgency calls deferred on
purpose rather than forgotten — which platform hosts the two promised blog posts
(`OQ-0.9`) and which v1.1 stretch feature (a second state's appeals corpus, the payer-side
QA flip, or a hosted demo) gets priority (`OQ-0.10`).

Every number this project publishes from here on carries at least one of three caveats,
and they're worth stating together because they compound rather than stack independently.
Selection bias (§1): these are cases that already survived internal appeal, so nothing
here ever claims to predict whether appealing is worth it in the first place, only
whether an already-filed external review is likely to succeed. Annotation circularity
(`OQ-0.4`, §3): the gold set that measures extraction quality is itself built by the same
model family later being evaluated, so every F1 figure this project ever reports (§6, §7)
is an optimistic upper bound on a real, independent-ground-truth number — mitigated
by prompt diversity across annotators and the human spot-check tier, but not eliminated,
and disclosed rather than hidden. And the 2026 vocabulary break (§6.2): because `OQ-1.5`'s
own criteria exclude 2026 from both the training and test windows, this doesn't touch the
v1 model at all — but it does mean any category trend chart drawn today quietly stops
updating at 2025 for the 31.8% of the corpus still sitting on a provisional crosswalk
mapping, until a full year of 2026-vocabulary data exists to remap against.

## 8. For the engineer

Repo layout, root to leaf, as of this writing:

```
rePeal/
├── README.md, PRD.md, OQ.md, ROLLER.md, TODO.md, CLAUDE.md   # the ledgers + spec
├── journeys/                  # this document and whatever follows it
├── docs/
│   ├── data-card.md           # populated, Phase 1
│   └── evals/eda.md           # populated, Phase 1 (more docs/evals/*.md arrive per phase)
├── data/                      # gitignored entirely
│   ├── raw/imr_2026-06-01.csv + manifest.json     # the pinned snapshot
│   └── interim/imr_cases.parquet + ingest_report.json
├── src/repeal/
│   ├── config.py              # Settings: paths + the pinned seed (42)
│   └── ingest/
│       ├── download.py        # fetch, checksum, manifest, upstream drift probe
│       ├── schema.py           # the 14-column contract + OQ-0.1 field classification
│       ├── normalize.py        # category_crosswalk_v1.yaml application
│       ├── quality.py          # the 8 quality flags
│       ├── profile.py          # EDA stats + docs/evals/eda.md renderer
│       ├── run.py              # make ingest's entry point
│       └── resources/category_crosswalk_v1.yaml
├── tests/                      # one test file per src module, plus tests/fixtures/
├── Makefile, pyproject.toml, uv.lock, scripts/install-hooks.sh
└── .github/workflows/ci.yml    # lint + pytest, on push to maestro and on PRs
```

Later phases add `src/repeal/{extract,scrub,warehouse,retrieval,predict,generate,
analytics,evals,api}/` and a top-level `frontend/` per `PRD.md` §8 — none of that exists
yet except as directories implied by the phase plan.

One-command entry points, from `Makefile` (targets not yet implemented print a "not
implemented until its phase" message and exit nonzero, by design — `annotate extract
index train eval serve demo` are all still stubs):

- `make setup` — `uv sync --group dev` then installs the pre-commit hook. Run this first
  on a fresh clone.
- `make test` — `uv run pytest`. 150 tests as of Phase 1's gate.
- `make lint` / `make fmt` — `ruff check` / `ruff check --fix`.
- `make ingest` — runs `python -m repeal.ingest.run`: download (skipped if the pinned
  snapshot's checksum already matches) → schema validation → category normalization →
  quality flagging → `data/interim/imr_cases.parquet` + `ingest_report.json`. Idempotent;
  re-running produces a byte-identical parquet. A forced refresh to a new dated snapshot
  is `uv run python -m repeal.ingest.run --refresh` directly (the `OQ-1.3` ruling's
  shorthand for this is "`make ingest REFRESH=1`"; today that flag lives on the underlying
  script, not yet wired as a `Makefile` variable — a small, harmless gap between the
  ledger's prose and the current `Makefile`).
- `make check-upstream` — a manual, network-only-on-demand probe against the CKAN
  datastore API for row-count and field-name drift versus the pinned snapshot. Deliberately
  excluded from CI and from pytest (`OQ-1.10`) — third-party APIs in a commit-blocking path
  are a false-red generator waiting to happen.
- `make eda` — regenerates `docs/evals/eda.md` from the current parquet via `profile.py`.

To reproduce from a fresh clone: `uv sync --group dev`, `bash scripts/install-hooks.sh`
(or just `make setup` for both), then `make ingest` to pull and validate the real 85 MB
CSV yourself (this is the one step that touches the network and takes a little while),
then `make eda` to regenerate the report, then `uv run pytest` to confirm all green. Every
number in this document traces back to one of: `docs/data-card.md`, `docs/evals/eda.md`,
`OQ.md`, `ROLLER.md`, `TODO.md`, `data/interim/ingest_report.json` (not committed — it
regenerates from `make ingest`), or a specific line in `src/repeal/ingest/*.py` cited
inline above. Of those, `docs/evals/eda.md` and `ingest_report.json` are mechanically
regenerated by `profile.py`/`run.py` straight from the pinned parquet (`OQ-1.7`) — treat
them as ground truth. `docs/data-card.md` is written by a person pointing at those two
rather than duplicating them, which is mostly true but not perfectly enforced today: see
the parenthetical in §6.2 for one place its prose and `eda.md`'s own table currently
disagree (raw vs. canonical diagnosis-label counts for 2026). This document is prose
written about a snapshot in time and inherits whichever of the two it happened to read.

---

*Facts in this document come from `PRD.md`, `OQ.md`, `ROLLER.md`, `TODO.md`,
`docs/data-card.md`, `docs/evals/eda.md`, and `src/repeal/ingest/` as they stood on
2026-09-10. No raw corpus rows, `Findings` narrative text, or real `ReferenceID` values
appear above, consistent with the no-redistribution posture ruled in `OQ-1.1`.*
