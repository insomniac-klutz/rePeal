# Data card — CA DMHC Independent Medical Review (IMR) Determinations

> **Stub — populated in Phase 1.** PRD §9 Phase 1 makes this file a DoD item: it is written
> against the *actual* download (verified field list, row counts, class balance, quality
> flags), not against expectations. Everything below marked *(Phase 1)* is a placeholder.

| | |
|---|---|
| **Status** | stub — populated in Phase 1 |
| **Last updated** | 2026-08-16 |
| **Corpus** | California DMHC Independent Medical Review Determinations |
| **Coverage** | all external-review decisions since 2001-01-01; actively updated |
| **Scale** | ~42.7k cases *(verify at ingest — Phase 1)* |

## Source

- **Dataset page:** https://data.chhs.ca.gov/dataset/independent-medical-review-imr-determinations-trend
- **Mirror:** https://catalog.data.gov/dataset/independent-medical-review-imr-determinations-trend
- **Publisher:** California Department of Managed Health Care (DMHC), via the California
  Health & Human Services Open Data Portal.
- **Attribution:** required on every derived artifact and in the model cards.

## Expected fields

Verified against the actual download and enforced by a schema contract test in Phase 1.

| Field | Notes |
|---|---|
| `ReferenceID` | case identifier; the join key for released gold sets |
| `ReportYear` | used for the temporal split (Phase 5) and the precedent cutoff (ADR-001 amendment) |
| `DiagnosisCategory` / `DiagnosisSubCategory` | taxonomy drift across 20+ years — normalization map built in Phase 1 EDA, versioned |
| `TreatmentCategory` / `TreatmentSubCategory` | as above |
| `Determination` | **the label** — Upheld / Overturned |
| `Type` | Medical Necessity / Experimental-Investigational / Urgent Care |
| `AgeRange`, `PatientGender` | de-identified demographics |
| `Findings` | free-text reviewer narrative, typically a few hundred words — **written after the decision; see ADR-001** |

## Terms & release determination

**Placeholder — IDs + annotations only; determination to be finalized before Phase 2.**

Current working position, per PRD §4 and ADR-004:

- The terms permit **noncommercial use without approval** but **prohibit redistributing or
  altering the provided data**. Linking to the source is the distribution mechanism.
- Raw downloads live immutably in `data/raw/` (gitignored) with checksums. **No raw or
  modified data is committed or published.**
- **Released gold files contain `ReferenceID`s + annotations + a join script only — never
  `Findings` text.** A consumer reproduces the gold set by downloading the source themselves
  and running the join script (ADR-004).
- The formal terms determination — exact license text, permitted derived-artifact scope, and
  attribution wording — **must be finalized before Phase 2 ships**, since Phase 2 is what
  produces the releasable gold files.

## Privacy & licensing constraints

- Data is **de-identified and public**. **No re-identification attempts, ever. No PHI enters
  this repo.** (PRD §4, non-negotiable.)
- ICD-10-CM / HCPCS Level II may be used freely (public domain). **Never add CPT
  descriptors** — AMA-licensed.
- No NCCN content (licensed).

## Known caveats

- **Selection bias:** these cases already survived internal appeal. All outputs are framed as
  *"external-review overturn likelihood"*, not "appeal success likelihood" (ADR-001 §4).
- **Post-hoc narrative:** `Findings` frequently states the verdict. It is never a prediction
  input; see `docs/adr/ADR-001-leakage-protocol.md`.
- **Taxonomy drift** across 20+ years of category labels — normalization map is a Phase 1
  deliverable.

## To be populated in Phase 1

- [ ] Verified field list + dtypes vs. the actual download (schema contract test)
- [ ] Row count, date range, download checksum + retrieval date
- [ ] Class balance by year and by `Type`
- [ ] Category distributions + the versioned normalization map
- [ ] `Findings` length statistics; truncation / quality flags and the exclude-and-report policy
- [ ] Duplicates and nulls; any surprises found in EDA
- [ ] Final terms determination replacing the placeholder above
