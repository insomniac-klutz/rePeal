# Data card — CA DMHC Independent Medical Review (IMR) Determinations

> **Populated, Phase 1 (2026-09-09).** PRD §9 makes this file a DoD item: written against
> the *actual* download (verified field list, row counts, class balance, quality flags), not
> expectations. Source: the pinned 2026-06-01 snapshot, `make ingest` → `data/interim/
> imr_cases.parquet` + `ingest_report.json` (integrated run, byte-identical on re-run). Every
> number below either comes straight from `ingest_report.json` or is reproducible from
> `docs/evals/eda.md`, which this file points at rather than duplicates.

| | |
|---|---|
| **Status** | populated — Phase 1 |
| **Last updated** | 2026-09-10 |
| **Corpus** | California DMHC Independent Medical Review Determinations |
| **Coverage** | all external-review decisions since 2001-01-01; periodic full-file republish upstream, v1 pinned to the 2026-06-01 snapshot (OQ-1.3) |
| **Scale** | 42,749 cases, verified · report_year 2001–2026 (2026 partial: 546 rows, publish cutoff 2026-06-01) |

## Source

- **Dataset page:** https://data.chhs.ca.gov/dataset/independent-medical-review-imr-determinations-trend
- **Mirror:** https://catalog.data.gov/dataset/independent-medical-review-imr-determinations-trend
- **Publisher:** California Department of Managed Health Care (DMHC), via the California
  Health & Human Services Open Data Portal.
- **Attribution:** required on every derived artifact and in the model cards.
- **Pinned snapshot:** `imr_2026-06-01.csv`, 85,409,358 bytes, sha256
  `f68951823f6ffc09566cc190d97b2808e0269a069843efe809a3f5f90d4c893b`, upstream
  `last_modified` 2026-06-01 (a periodic full-file republish, no per-row dates, no append
  feed — `Frequency: "Other"`), retrieved 2026-09-09T19:31:56Z. CKAN's advertised
  size/hash are stale (wrong by 14 MB) and the S3 `ETag` is multipart, not an md5 — this
  self-computed sha256 is the only trustworthy integrity anchor (OQ-1.0, OQ-1.3). All of v1
  builds against this one dated file; a refresh is a deliberate, separate act.
- **2020 data-dictionary PDF:** verified **unusable as a schema contract** — it documents 11
  fields (the real header has 14), and describes a `PaientAge` *[sic]* number that is
  actually `AgeRange` text buckets. `schema.py`'s 14-column contract was authored from the
  real CSV header, not the PDF, and is re-verified against the live file on every
  `make ingest` run.

## Verified fields

The 16 parquet columns after `schema.validate()` (14 source fields + the derived
`overturned` label + the synthesized `row_id`), their dtypes and nullability from
`schema.CONTRACT`, and their OQ-0.1 leakage class from `schema.PREDICTION_ELIGIBLE` /
`POST_DECISION` / `LABEL` / `NARRATIVE` — the machine-readable source of truth Phase 5's
"no post-decision features" test runs against, not a hand-kept list.

| Parquet column | Source field | dtype | Nullable (real count) | OQ-0.1 class |
|---|---|---|---|---|
| `row_id` | *(synthesized)* | Int64 | no | identifier — source row order within the pinned snapshot, not a source field |
| `reference_id` | `ReferenceID` | String | no | pre-decision (39 duplicate values — see Surprises) |
| `report_year` | `ReportYear` | Int32 | no | pre-decision — temporal axis / split key |
| `diagnosis_category` | `DiagnosisCategory` | String | no | pre-decision (`_raw` sibling preserved) |
| `diagnosis_subcategory` | `DiagnosisSubCategory` | String | yes (2) | pre-decision (`_raw` sibling preserved) |
| `treatment_category` | `TreatmentCategory` | String | no | pre-decision (`_raw` sibling preserved) |
| `treatment_subcategory` | `TreatmentSubCategory` | String | yes (1) | pre-decision (`_raw` sibling preserved) |
| `case_type` | `Type` | String enum | no | pre-decision — Medical Necessity / Experimental-Investigational / Urgent Care |
| `age_range` | `AgeRange` | String enum | yes (691) | pre-decision — 7 buckets, top-coded `65+` |
| `patient_gender` | `PatientGender` | String enum | yes (691) | pre-decision — Female / Male / Other |
| `imr_type` | `IMRType` | String enum | no | pre-decision — Standard / Expedited (undocumented field; OQ-1.4 ruled prediction-eligible) |
| `days_to_review` | `DaysToReview` | Int32 | yes (691) | **post-decision** — never a predictor (`schema.POST_DECISION`) |
| `days_to_adopt` | `DaysToAdopt` | Int32 | yes (0) | **post-decision** — never a predictor (`schema.POST_DECISION`) |
| `determination_raw` | `Determination` | String enum | no | **label** (source string) |
| `overturned` | *(derived from `Determination`)* | Boolean | no | **label** (`schema.LABEL`) |
| `findings` | `Findings` | String | no | **post-decision narrative** (`schema.NARRATIVE`) — surfaces only, never a predictor (OQ-0.1) |

After `normalize.apply` (crosswalk v1), `diagnosis_category`/`treatment_category`/
`diagnosis_subcategory`/`treatment_subcategory` each gain a `*_raw` sibling holding the
untouched source string. After `quality.flag`, eight `flag_*`/`has_section_markers` Bool
columns are appended — see Quality flags below.

## Terms & release determination

**Ruled posture (OQ-1.1, 2026-09-09): noncommercial research/portfolio use under the CalHHS portal ToU's modify-with-flagging clause. Attribution wording and the final terms text are confirmed before Phase 2 ships.**

Current working position, per PRD §4 and OQ-0.4:

- The terms permit **noncommercial use without approval** but **prohibit redistributing or
  altering the provided data**. Linking to the source is the distribution mechanism.
- Raw downloads live immutably in `data/raw/` (gitignored) with checksums. **No raw or
  modified data is committed or published.**
- **Released gold files contain `ReferenceID`s + annotations + a join script only — never
  `Findings` text.** A consumer reproduces the gold set by downloading the source themselves
  and running the join script (OQ-0.4).
- The formal terms determination — exact license text, permitted derived-artifact scope, and
  attribution wording — **must be finalized before Phase 2 ships**, since Phase 2 is what
  produces the releasable gold files.
- Every derived artifact (parquet, indexes, gold sets, eval reports) is flagged **modified,
  non-official** and carries the preferred citation: `DMHC IMR Data, 2001 - Current`, the
  dataset URL, and the publication date of the pinned snapshot — **2026-06-01** for every
  v1 artifact (sha256 `f68951823f6ffc09566cc190d97b2808e0269a069843efe809a3f5f90d4c893b`;
  see Source above).
- Commercial use is treated as **blocked pending approval** (the OPA click-through's
  commercial clause); this is a portfolio project.
- Control-page check (2026-09-09): portal-wide boilerplate — the identical `id="popup"` OPA
  click-through (verified byte-for-byte via raw HTTP fetch, not just rendered inspection)
  appears on the DMHC IMR page, on dataset pages from three unrelated organizations
  (Department of Health Care Services, California Department of Public Health, CHHS itself),
  and on OPA's own dataset page; it is boilerplate injected into every CHHS portal dataset
  page regardless of the page's actual publishing organization, not a DMHC- or OPA-specific
  clause.

## Privacy & licensing constraints

- Data is **de-identified and public**. **No re-identification attempts, ever. No PHI enters
  this repo.** (PRD §4, non-negotiable.)
- ICD-10-CM / HCPCS Level II may be used freely (public domain). **Never add CPT
  descriptors** — AMA-licensed.
- No NCCN content (licensed).

## Known caveats

- **Selection bias:** these cases already survived internal appeal. All outputs are framed as
  *"external-review overturn likelihood"*, not "appeal success likelihood" (PRD §5 item 4).
- **Post-hoc narrative:** `Findings` frequently states the verdict. It is never a prediction
  input; see PRD §5 and OQ.md OQ-0.1.
- **Taxonomy drift** across 20+ years of category labels — `normalize.py` +
  `category_crosswalk_v1.yaml` (v1) canonicalize to the 2026 vocabulary; scope and
  remaining gaps are in Category distributions below and OQ-1.12/OQ-1.13 (both ruled 2026-09-10).

## Quality flags

`quality.flag` (OQ-1.11) adds eight Bool columns, never drops rows — exclusion is a
downstream consumer's explicit, reported decision. Counts from the real corpus
(`ingest_report.json`):

| Flag | Count | Share | Threshold used |
|---|---|---|---|
| `flag_findings_short` | 3 | 0.01% | `findings` < 100 chars |
| `flag_findings_truncated` | 541 | 1.27% | ≥ 200 chars and doesn't end in terminal punctuation |
| `flag_encoding_artifact` | 0 | 0% | mojibake patterns (`â€`, `Ã`, `�`) |
| `flag_duplicate_reference_id` | 78 | 0.18% | `reference_id` shared with another row |
| `flag_duplicate_findings` | 202 | 0.47% | `findings` text shared with another row |
| `flag_legacy_cohort` | 691 | 1.62% | `age_range` AND `patient_gender` both null |
| `flag_id_prefix_mismatch` | 0 | 0% | `reference_id` prefix vs. `case_type`/`report_year` |
| `has_section_markers` | 38,468 | 90.0% | contains `Findings:`/`Final Result:`/`Credentials/Qualifications:` |

**Thresholds, pinned by EDA percentiles (OQ-1.11 procedure) — both CONFIRMED, not
changed from the code defaults:**
- `short_findings_chars = 100`: corpus-wide `findings` length has a hard cliff — only 2
  rows under 50 chars, 3 under 100, then *nothing* until 250+ (17 rows) — while the true
  distribution's 0.1st percentile is already 270 chars (p1 = 408, p50 = 1,654). 100 sits
  inside that empty cliff, isolating exactly the 3 degenerate rows without creeping into
  real-but-short narratives.
- `truncation_min_chars = 200`: this floor barely matters — the flagged count is 541 at
  both 100 and 200 chars, 539 at 300, 519 at 500; the discriminator is
  `~ends_terminal`, not the length gate. 200 is comfortably below the 1st percentile
  (408 chars) so it never excludes a genuine finding from the "should have ended
  properly" check — it exists only to avoid double-flagging the handful of rows
  `flag_findings_short` already caught.

Full by-year section-marker prevalence: `docs/evals/eda.md` § Section-marker prevalence
by year (near-universal, ≥98%, 2007–2014 and 2016–2017; a mid-corpus dip 2018–2021 down
to 18.8% in 2020, climbing back to 100% by 2026 — narrative structure isn't stable
enough for Phase 3's scrub to assume it's always there).

## To be populated in Phase 1

- [x] Verified field list + dtypes vs. the actual download (schema contract test) — see
      Verified fields above; `schema.CONTRACT`, 27 tests green (`tests/test_schema_contract.py`).
- [x] Row count, date range, download checksum + retrieval date — 42,749 rows, report_year
      2001–2026; sha256 `f68951823f6ffc09566cc190d97b2808e0269a069843efe809a3f5f90d4c893b`,
      retrieved 2026-09-09T19:31:56Z (see Source above).
- [x] Class balance by year and by `Type` — pooled 22,445/42,749 overturned (52.5%), but no
      single year is close to that: 25.0% in 2001 climbing to 72.3% in 2025 (69.6% in the
      partial 2026), crossing 50% around 2015–2016 and plateauing 60–72% from 2020 on. Full
      tables: `docs/evals/eda.md` § Rows & overturn rate by year, § Overturn rate by year
      and case type.
- [x] Category distributions + the versioned normalization map — `crosswalk_version = 1`
      (`category_crosswalk_v1.yaml`), 0 unknown labels on either axis (every real 2026-06-01
      category value is accounted for). `normalize.apply` rewrote 38,678/42,749 rows'
      `diagnosis_category` (90.5%) and 3,638 rows' `treatment_category` (8.5%) via 22
      diagnosis + 4 treatment crosswalk aliases (15 + 2 clear renames per OQ-1.2, plus the 7
      + 2 ICD-10-chapter-consistent broadenings OQ-1.12 ruled in on 2026-09-10) — the legacy
      vocabulary was the majority of the corpus' history, not a minor exception, once
      normalized forward to the 2026 scheme. Subcategories get mechanical cleanup only, no
      semantic crosswalk (OQ-1.2 depth ruling): 0 `diagnosis_subcategory` rows and 6
      `treatment_subcategory` rows needed even whitespace normalization. A further 7 labels
      (4 diagnosis, 3 treatment) are best-guess aliases **parked, not applied** — ruled
      OQ-1.12 2026-09-10: nine applied, seven kept as themselves. The seven cover 13,582
      rows (31.8% of the corpus) currently canonical as their legacy selves. See
      `ingest_report.json`'s `normalize.uncertain_seen` for the per-label counts (top three
      each: diagnosis — OB-GYN/ Pregnancy 1,080, Ears/Nose/Throat 702, Foot Disorder 397;
      treatment — Diag Imag & Screen 5,994, Mental Health 4,835, Alternative Tx 414).
      Separately, three treatment labels have **no candidate mapping at all**, not
      even a guess — a second, distinct open thread, OQ-1.13 — see Surprises. Full
      distributions: `docs/evals/eda.md` §§ Diagnosis/Treatment category vocabulary by era,
      Top diagnosis/treatment category/subcategory labels.
- [x] `Findings` length statistics; truncation / quality flags and the exclude-and-report
      policy — percentiles in `docs/evals/eda.md` § Findings length percentiles by year;
      flags + pinned thresholds in Quality flags above. Exclude-and-report policy (OQ-1.0
      invariant): flags are columns, never row drops — a consumer decides what to exclude
      and reports it; nothing here has silently dropped a row.
- [x] Duplicates and nulls; any surprises found in EDA — see Surprises below and
      `docs/evals/eda.md` §§ Duplicate reference_id pairs, Null cohorts.
- [x] Final terms determination replacing the placeholder above — posture ruled OQ-1.1
      (2026-09-09), recorded in Terms & release determination above; exact attribution
      wording and final legal text are explicitly deferred to before Phase 2 ships (that's
      the ruling, not a gap).

### Crosswalk design trace

Four steps, from the pinned 2026-06-01 snapshot (48 diagnosis / 58 treatment categories,
2026 rows carrying an ICD-10-chapter-style diagnosis vocabulary and a CPT/HCPCS-section-
style treatment vocabulary alongside the legacy labels). **1.** 15 diagnosis + 2 treatment
aliases applied as clear renames/standard abbreviations (4 diagnosis given as certain in
OQ-1.2). **2.** 16 more (11 diagnosis, 5 treatment) parked `uncertain` with a `why` each,
not applied, reported at 7,154 diagnosis / 13,987 treatment rows. **3.** OQ-1.12 (ruled
2026-09-10) applied the 9 of those 16 that are ICD-10-chapter-consistent broadenings
(4,815 + 2,744 rows), leaving the other 7 (13,582 rows) canonical as themselves. **4.**
Labels with no 2026 counterpart at all — `Pharmacy`, the ten specialty `* Proc` labels, the
`DME MACs`/`Durable Med Equip` split — left as themselves by OQ-1.13 (ruled 2026-09-10),
revisited at the first refresh that brings a full single-vocabulary 2026 year.

## Surprises

- **The legacy-cohort recon claim was wrong.** OQ-1.0's recon read "691 rows null on
  `age_range`, `patient_gender`, and `days_to_review`" as *one* clean 2001–2003 cohort. It
  isn't: `age_range` + `patient_gender` null together *is* one 691-row cohort (2001–2003,
  27/646/18 rows respectively) — but the 691 `days_to_review` nulls are a **different,
  disjoint** set of rows scattered across 17 years from 2007 through 2026 (65 alone in
  2008). Same count, unrelated rows; a three-way null filter fires **zero** times on the
  real corpus. `quality.flag_legacy_cohort` is defined on the two-column version;
  `profile.null_cohorts` reports both the two-way and three-way cohorts side by side so
  this is visible in the table, not just asserted in prose.
- **The 2026 vocabulary migration is real and large, on one axis.** On the raw
  `diagnosis_category_raw` labels, diagnosis categories hold steady at 24 distinct values
  for 2020–2025, then jump to 33 in 2026 (4 with no legacy spelling at all: Ear and Mastoid,
  Hlth Factor/Contact, Malfor/Deform/Abnor, Sym/Sign Ab Find). On the canonical
  post-crosswalk column the axis holds at 21 labels every year 2020–2026 with exactly one
  genuinely new 2026 label, Ear and Mastoid (`docs/evals/eda.md` § Diagnosis category
  vocabulary by era is computed on the canonical column).
  Treatment categories are worse: only 2 of 31 legacy labels have a confident 2026
  counterpart (OQ-1.2) — the new treatment vocabulary reads as CPT/HCPCS section names,
  not a renamed version of the old scheme, so treatment-category trends still fracture at
  2026 regardless of crosswalk effort (OQ-1.13, ruled 2026-09-10: left as they are for v1).
- **Label drift is large and monotonic-ish, not a rounding error.** Pooled overturn rate
  (52.5%) describes no actual year: 25.0% (2001) → ~45% (mid-2000s) → ~50% (mid-2010s) →
  60–72% (2020s). This is why OQ-1.5 makes the temporal-split criteria the decision, not
  the split ratio alone — see the cutoff-candidate table sent separately.
- **The 39 duplicate-`ReferenceID` rows are benign.** Every one of the 39 groups (78 rows)
  has identical `findings` text *and* identical `overturned` label between duplicates —
  0 divergent. Reads as re-submitted/re-published records, not data corruption or
  conflicting outcomes for the same case.
- **202 rows share `findings` text with at least one other row, but it's not boilerplate.**
  93 distinct texts account for those 202 rows — real narratives repeating (a median 1,576
  chars across the 202 rows; 1,495 chars across the 93 distinct texts), not a short
  templated stub reused verbatim. Worth a closer look before Phase 3's scrub treats
  every `Findings` value as unique.
- **Under a third of the corpus' categories remain on a provisional crosswalk mapping.**
  OQ-1.12 (ruled 2026-09-10) applied nine of the sixteen parked guesses; 13,582 rows
  (31.8%) still carry a `diagnosis_category`/`treatment_category` value in the seven
  labels that stayed `uncertain` — canonical-as-legacy-self, no confident 2026 label. Not
  a blocker for v1 (OQ-1.5 excludes 2026 from both modeling windows). These seven, plus
  the OQ-1.13 no-counterpart labels (`Pharmacy`, the ten `* Proc` labels, the `DME MACs`
  vs `Durable Med Equip` split), are revisited together at the first refresh that brings a
  full single-vocabulary 2026 year (OQ-1.13 ruled 2026-09-10: leave them for v1).
- **The corpus' single largest treatment category has no 2026 answer at all.**
  `Pharmacy` — 11,948 rows, 28% of every treatment-category row in the corpus — isn't in
  OQ-1.12's guesses either: the new vocabulary carries HCPCS-style drug buckets instead
  (`Chemo Drugs`, `Drug Ad Oth Oral`), not a renameable match. Same story for ten legacy
  procedure labels folding into a single new `Surgery` bucket (Orthopedic Proc 1,676,
  Gen Surg Proc 1,455, Reconstr/Plast Proc 1,310, … 6,568 rows combined) — a granularity
  loss, not a rename, so it's parked rather than guessed. `DME` (2,679 legacy rows) looks
  like it split into `Durable Med Equip` + `DME MACs`, 24 rows combined so far — too thin
  a signal to call yet. All three are OQ-1.13, ruled 2026-09-10: left as they are for v1, and independent of OQ-1.12's list —
  this is "no candidate exists," not "candidate unapplied."
