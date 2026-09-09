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
| `ReportYear` | used for the temporal split (Phase 5) and the precedent cutoff (OQ-0.1 amendment) |
| `DiagnosisCategory` / `DiagnosisSubCategory` | taxonomy drift across 20+ years — normalization map built in Phase 1 EDA, versioned |
| `TreatmentCategory` / `TreatmentSubCategory` | as above |
| `Determination` | **the label** — Upheld / Overturned |
| `Type` | Medical Necessity / Experimental-Investigational / Urgent Care |
| `AgeRange`, `PatientGender` | de-identified demographics |
| `Findings` | free-text reviewer narrative, typically a few hundred words — **written after the decision; see PRD §5 / OQ-0.1** |

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
  dataset URL, and the publication date of the pinned snapshot.
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
