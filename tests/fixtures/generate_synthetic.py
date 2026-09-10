"""Generator for `tests/fixtures/imr_synthetic.csv` — a ~60-row, fully-synthetic stand-in
for the real DMHC IMR corpus (OQ-1.8: no real corpus rows are ever committed).

Deterministic under `random.Random(seed)` only. Column names and enum values are derived
from `repeal.ingest.schema` so the fixture and the contract can never drift apart. Every
enum value, both category vocabularies, and every quality-flag pathology the pipeline must
detect appear at least once — see `tests/test_fixture.py` for the assertions that pin this.

Run directly to regenerate the committed CSV: `uv run python -m tests.fixtures.generate_synthetic`
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

from repeal.ingest.schema import ENUMS, SOURCE_COLUMNS

SEED = 42
FIXTURE_PATH = Path(__file__).resolve().parent / "imr_synthetic.csv"

# ReferenceID prefix per `Type`, pinned from the real 2026-06-01 snapshot: every one of
# the 42,749 real rows agrees with this map and with its own ReportYear suffix — zero
# natural exceptions, so `flag_id_prefix_mismatch` has to be exercised by a planted row.
PREFIX_FOR_CASE_TYPE: dict[str, str] = {
    "Medical Necessity": "MN",
    "Experimental/Investigational": "EI",
    "Urgent Care": "UR",
}

# Legacy (pre-2026) <-> new (2026-only) vocabulary pairs the fixture must exercise so
# `normalize.py`'s alias table has known real targets (OQ-1.0 Hazards #1, OQ-1.2). All
# six pairs are verified real labels from the 2026-06-01 snapshot, not invented.
DIAGNOSIS_CROSSWALK_PAIRS: tuple[tuple[str, str], ...] = (
    ("Orth/Musculoskeletal", "Musculoskeletal"),
    ("Endocrine/Metabolic", "Endo/Metabolic"),
    ("Mental Disorder", "Mental Behav Neur"),
    ("Cancer", "Neoplasms (Tumor)"),
)
TREATMENT_CROSSWALK_PAIRS: tuple[tuple[str, str], ...] = (
    ("Diag/ MD Eval", "Eval and Mgmt"),
    ("Transportation", "Ambulance Transport"),
)

# Whitespace/punctuation near-duplicate — exercises mechanical canonicalization
# (trim/collapse/case), not the explicit alias table.
NEAR_DUPLICATE_DIAGNOSIS_PAIR: tuple[str, str] = ("Pregnancy Childbirth", "Pregnancy/Childbirth")

# A label in neither vocabulary — must pass through normalize.py counted, never errored.
UNKNOWN_VOCAB_LABEL = "Zzz Unknown Category"

# Filler category pools (real labels from the 2026-06-01 snapshot) so ordinary rows
# aren't all identical — split legacy/new the same way the real corpus is split.
_LEGACY_DIAGNOSIS_POOL: tuple[str, ...] = (
    "Digestive System/ GI",
    "Infectious Disease",
    "Respiratory System",
    "Not Applicable",
    "Vision",
    "Foot Disorder",
    "Dental Problems",
)
_NEW_DIAGNOSIS_POOL: tuple[str, ...] = (
    "Circulatory System",
    "Nervous System",
    "Skin Subcutaneous",
    "Genitourinary Sys",
    "Resp System",
    "Digest System",
)
_LEGACY_TREATMENT_POOL: tuple[str, ...] = (
    "Chiropractic Care",
    "Home Health Care",
    "Emergency/Urg Care",
    "Ophthalmology Proc",
    "Special Proc",
)
_NEW_TREATMENT_POOL: tuple[str, ...] = (
    "Surgery",
    "Radio Proc",
    "Med Surg Supplies",
    "Path Lab Proc",
    "Durable Med Equip",
)
_SUBCATEGORY_POOL: tuple[str, ...] = ("Unspecified", "General", "Follow-up Care", "")

_FINDINGS_OPENERS = (
    "The physician reviewer found that the patient requested authorization for",
    "The reviewer evaluated the record regarding the request for",
    "Independent medical review was requested concerning",
)
_FINDINGS_SUBJECTS = (
    "a course of physical therapy following a documented injury",
    "an elective surgical procedure for a chronic condition",
    "a specialty medication not previously trialed",
    "durable medical equipment for home use",
    "an out-of-network specialist consultation",
)
_FINDINGS_VERDICTS = (
    "the record supports medical necessity and the denial should be overturned.",
    "the record does not establish medical necessity and the denial is upheld.",
    "the evidence is equivocal, but guideline criteria are not met.",
)


def _findings(rng: random.Random) -> str:
    """Invented reviewer-narrative prose — never real corpus text (OQ-1.8).

    The numeric case note isn't cosmetic: with only the three phrase pools
    (3x5x3 = 45 combinations) two of ~60 rows would collide by pure pigeonhole
    and silently blow up `flag_duplicate_findings` with accidental noise. The
    4-digit tag pushes the combination space past 400k, so the only rows that
    ever share Findings text are the ones planted to do exactly that below.
    """
    opener = rng.choice(_FINDINGS_OPENERS)
    subject = rng.choice(_FINDINGS_SUBJECTS)
    verdict = rng.choice(_FINDINGS_VERDICTS)
    case_note = rng.randint(1000, 9999)
    return f"{opener} {subject} (internal case note {case_note}). On review, {verdict}"


def _reference_id(
    rng: random.Random, case_type: str, report_year: int, used: set[str]
) -> str:
    prefix = PREFIX_FOR_CASE_TYPE[case_type]
    yy = report_year % 100
    while True:
        candidate = f"{prefix}{yy:02d}-{rng.randint(1000, 99999)}"
        if candidate not in used:
            used.add(candidate)
            return candidate


def _base_row(
    rng: random.Random, used_ids: set[str], *, report_year: int, case_type: str
) -> dict[str, str]:
    """A fully-populated, schema-shaped row with plausible random values."""
    is_new_vocab = report_year == 2026
    diag_pool = _NEW_DIAGNOSIS_POOL if is_new_vocab else _LEGACY_DIAGNOSIS_POOL
    treat_pool = _NEW_TREATMENT_POOL if is_new_vocab else _LEGACY_TREATMENT_POOL
    return {
        "ReferenceID": _reference_id(rng, case_type, report_year, used_ids),
        "ReportYear": str(report_year),
        "DiagnosisCategory": rng.choice(diag_pool),
        "DiagnosisSubCategory": rng.choice(_SUBCATEGORY_POOL),
        "TreatmentCategory": rng.choice(treat_pool),
        "TreatmentSubCategory": rng.choice(_SUBCATEGORY_POOL),
        "Determination": rng.choice(ENUMS["determination_raw"]),
        "Type": case_type,
        "AgeRange": rng.choice(ENUMS["age_range"]),
        "PatientGender": rng.choice(ENUMS["patient_gender"]),
        "IMRType": rng.choice(ENUMS["imr_type"]),
        "DaysToReview": str(rng.randint(1, 30)),
        "DaysToAdopt": str(rng.randint(1, 45)),
        "Findings": _findings(rng),
    }


def _coverage_rows(
    rows: list[dict[str, str]], rng: random.Random, used_ids: set[str]
) -> list[dict[str, str]]:
    """Additive rows patching in any enum value the rows built so far missed.

    Never mutates an existing row — several of `rows` are deliberately-planted
    pathologies (a prefix mismatch, a duplicate ID) and patching them in place could
    silently erase the thing the row exists to test.
    """
    column_to_field = {
        "determination_raw": "Determination",
        "case_type": "Type",
        "imr_type": "IMRType",
        "patient_gender": "PatientGender",
        "age_range": "AgeRange",
    }
    present = {field: {row[field] for row in rows} for field in column_to_field.values()}
    extra: list[dict[str, str]] = []
    for enum_column, field in column_to_field.items():
        for value in ENUMS[enum_column]:
            if value in present[field]:
                continue
            case_type = value if field == "Type" else rng.choice(ENUMS["case_type"])
            report_year = rng.randint(2002, 2025)
            row = _base_row(rng, used_ids, report_year=report_year, case_type=case_type)
            row[field] = value
            extra.append(row)
            present[field].add(value)
    return extra


def build_rows(seed: int = SEED) -> list[dict[str, str]]:
    """Build the fixture's rows deterministically. Same `seed` -> same rows, always."""
    rng = random.Random(seed)
    used_ids: set[str] = set()
    rows: list[dict[str, str]] = []

    # Four legacy/new diagnosis-category pairs (OQ-1.0 Hazards #1); the first two also
    # carry the two treatment-category pairs, so a single row never needs more than one
    # job title.
    treatment_overlay: dict[int, tuple[str, str]] = {
        0: TREATMENT_CROSSWALK_PAIRS[0],
        1: TREATMENT_CROSSWALK_PAIRS[1],
    }
    for i, (legacy_diag, new_diag) in enumerate(DIAGNOSIS_CROSSWALK_PAIRS):
        legacy_year = 2015 + i * 3
        legacy_row = _base_row(
            rng, used_ids, report_year=legacy_year, case_type="Medical Necessity"
        )
        legacy_row["DiagnosisCategory"] = legacy_diag
        new_row = _base_row(rng, used_ids, report_year=2026, case_type="Medical Necessity")
        new_row["DiagnosisCategory"] = new_diag
        if i in treatment_overlay:
            legacy_treat, new_treat = treatment_overlay[i]
            legacy_row["TreatmentCategory"] = legacy_treat
            new_row["TreatmentCategory"] = new_treat
        rows.append(legacy_row)
        rows.append(new_row)

    # Near-duplicate spelling (mechanical canonicalization target, not the alias table).
    near_a, near_b = NEAR_DUPLICATE_DIAGNOSIS_PAIR
    row = _base_row(rng, used_ids, report_year=2012, case_type="Medical Necessity")
    row["DiagnosisCategory"] = near_a
    rows.append(row)
    row = _base_row(rng, used_ids, report_year=2013, case_type="Medical Necessity")
    row["DiagnosisCategory"] = near_b
    rows.append(row)

    # A label in neither vocabulary — pass-through, counted not errored.
    row = _base_row(rng, used_ids, report_year=2020, case_type="Experimental/Investigational")
    row["DiagnosisCategory"] = UNKNOWN_VOCAB_LABEL
    rows.append(row)

    # Duplicate ReferenceID, divergent Findings — a chronic corpus hazard (39 real
    # pairs, 2002-2026), not a fresh-load artifact.
    dup_id = "MN08-77777"
    used_ids.add(dup_id)
    row = _base_row(rng, used_ids, report_year=2008, case_type="Medical Necessity")
    row["ReferenceID"] = dup_id
    row["Findings"] = (
        "Initial independent review found the requested spinal fusion not medically "
        "necessary based on the submitted records."
    )
    rows.append(row)
    row = _base_row(rng, used_ids, report_year=2008, case_type="Medical Necessity")
    row["ReferenceID"] = dup_id
    row["Findings"] = (
        "A later independent review filed under the same reference number reached the "
        "opposite conclusion, finding the fusion medically necessary given updated imaging."
    )
    rows.append(row)

    # Duplicate Findings text across two *different* ReferenceIDs — a plausible
    # copy-paste artifact upstream, and flag_duplicate_findings's dedicated,
    # deliberate trigger (distinct from the dup-ID pair above, whose Findings differ).
    shared_findings = (
        "The physician reviewer found that the requested treatment meets the plan's "
        "medical necessity criteria based on the submitted clinical documentation."
    )
    row = _base_row(rng, used_ids, report_year=2010, case_type="Medical Necessity")
    row["Findings"] = shared_findings
    rows.append(row)
    row = _base_row(rng, used_ids, report_year=2022, case_type="Medical Necessity")
    row["Findings"] = shared_findings
    rows.append(row)

    # A 1-character Findings (real min length is 1 char).
    row = _base_row(rng, used_ids, report_year=2016, case_type="Urgent Care")
    row["Findings"] = "."
    rows.append(row)

    # 2001 legacy cohort: AgeRange and PatientGender empty (the real 691-row 2001-2003
    # cohort; flag_legacy_cohort keys on those two). DaysToReview is left empty here too,
    # but in the real corpus its 691 nulls are a separate 2007+ population (OQ-1.14).
    row = _base_row(rng, used_ids, report_year=2001, case_type="Medical Necessity")
    row["AgeRange"] = ""
    row["PatientGender"] = ""
    row["DaysToReview"] = ""
    rows.append(row)

    # Mojibake: a right single quote mis-decoded as UTF-8-read-as-Latin-1.
    row = _base_row(rng, used_ids, report_year=2019, case_type="Medical Necessity")
    row["Findings"] = (
        "The patientâ€™s physician requested authorization for continued care; the "
        "reviewer found the memberâ€™s condition met medical necessity criteria."
    )
    rows.append(row)

    # ReferenceID prefix disagrees with Type — MN prefix on an Urgent Care row (real
    # data has zero such mismatches; this one is entirely planted).
    row = _base_row(rng, used_ids, report_year=2015, case_type="Urgent Care")
    row["ReferenceID"] = "MN15-00042"
    rows.append(row)

    # Modern rows with the real section markers; the first also carries embedded
    # quotes, a comma, and an internal newline to exercise CSV quoting end to end.
    row = _base_row(rng, used_ids, report_year=2026, case_type="Medical Necessity")
    row["Findings"] = (
        'Findings: The physician reviewer found that the patient, a "high-risk" '
        "candidate, requested authorization for an inpatient admission.\n"
        "Final Result: The reviewer determined the service is medically necessary; "
        "the Health Plan's denial should be overturned.\n"
        "Credentials/Qualifications: The reviewer is board-certified and actively "
        "practicing."
    )
    rows.append(row)
    row = _base_row(rng, used_ids, report_year=2025, case_type="Experimental/Investigational")
    row["Findings"] = (
        "Findings: The physician reviewer evaluated the request for an investigational "
        "therapy. Final Result: The reviewer determined the denial should be upheld. "
        "Credentials/Qualifications: The reviewer is board-certified in the relevant "
        "specialty."
    )
    rows.append(row)

    # Year-span filler: one row per year 2001-2025 (2026 already well represented above).
    case_types = ENUMS["case_type"]
    for report_year in range(2001, 2026):
        case_type = case_types[report_year % len(case_types)]
        rows.append(_base_row(rng, used_ids, report_year=report_year, case_type=case_type))

    # Pad to ~60 rows.
    while len(rows) < 58:
        report_year = rng.randint(2001, 2026)
        case_type = rng.choice(case_types)
        rows.append(_base_row(rng, used_ids, report_year=report_year, case_type=case_type))

    rows.extend(_coverage_rows(rows, rng, used_ids))
    return rows


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    """Write `rows` as a CSV with the exact real-file header order (RFC4180 quoting)."""
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(SOURCE_COLUMNS)
        for row in rows:
            writer.writerow([row[column] for column in SOURCE_COLUMNS])


def main() -> None:
    write_csv(build_rows(), FIXTURE_PATH)
    print(f"wrote {FIXTURE_PATH}")


if __name__ == "__main__":
    main()
