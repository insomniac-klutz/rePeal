"""The 14-column contract for the raw DMHC IMR CSV.

Header check, casts, enum domains, snake_case renames, and the derived `overturned`
label + `row_id` surrogate key that every downstream module (`normalize`, `quality`,
`profile`) trusts. Values are pinned from the 2026-06-01 snapshot (OQ-1.0); anything
outside them is a hard failure, not a silent coercion.
"""

from __future__ import annotations

from pathlib import Path

import pandera.polars as pa
import polars as pl

SCHEMA_VERSION = "1"

# Verbatim header order of the real CSV (OQ-1.0 Schema table).
SOURCE_COLUMNS: tuple[str, ...] = (
    "ReferenceID",
    "ReportYear",
    "DiagnosisCategory",
    "DiagnosisSubCategory",
    "TreatmentCategory",
    "TreatmentSubCategory",
    "Determination",
    "Type",
    "AgeRange",
    "PatientGender",
    "IMRType",
    "DaysToReview",
    "DaysToAdopt",
    "Findings",
)

RENAMES: dict[str, str] = {
    "ReferenceID": "reference_id",
    "ReportYear": "report_year",
    "DiagnosisCategory": "diagnosis_category",
    "DiagnosisSubCategory": "diagnosis_subcategory",
    "TreatmentCategory": "treatment_category",
    "TreatmentSubCategory": "treatment_subcategory",
    "Determination": "determination_raw",
    "Type": "case_type",
    "AgeRange": "age_range",
    "PatientGender": "patient_gender",
    "IMRType": "imr_type",
    "DaysToReview": "days_to_review",
    "DaysToAdopt": "days_to_adopt",
    "Findings": "findings",
}

# Seven buckets, top-coded `65+`, pinned from the real 2026-06-01 snapshot (691 nulls).
AGE_RANGES: tuple[str, ...] = (
    "0 to 10",
    "11 to 20",
    "21 to 30",
    "31 to 40",
    "41 to 50",
    "51 to 64",
    "65+",
)

# Hard-fail domains — an unrecognized value here is a contract violation, never a
# pass-through. (`diagnosis_category`/`treatment_category`/subcategories are NOT enum
# columns: the 2026 taxonomy migration means new labels are expected and handled by
# `normalize.py`'s crosswalk, counted rather than rejected — OQ-1.0 Hazards #1, OQ-1.2.)
ENUMS: dict[str, tuple[str, ...]] = {
    "determination_raw": (
        "Overturned Decision of Health Plan",
        "Upheld Decision of Health Plan",
    ),
    "case_type": ("Medical Necessity", "Experimental/Investigational", "Urgent Care"),
    "imr_type": ("Standard", "Expedited"),
    "patient_gender": ("Female", "Male", "Other"),
    "age_range": AGE_RANGES,
}

# Enum columns where an empty source string is a legitimate null, not a violation.
NULLABLE_ENUMS: tuple[str, ...] = ("patient_gender", "age_range")

# Non-enum string columns where an empty source string is a legitimate null.
NULLABLE_STRINGS: tuple[str, ...] = ("diagnosis_subcategory", "treatment_subcategory")

# Columns that must never be null after validation.
REQUIRED: tuple[str, ...] = ("reference_id", "findings")

DETERMINATION_TO_OVERTURNED: dict[str, bool] = {
    "Overturned Decision of Health Plan": True,
    "Upheld Decision of Health Plan": False,
}

# OQ-1.4 (leakage protocol, OQ-0.1): `days_to_review`/`days_to_adopt` measure the
# external review itself — they do not exist at denial time. Never a predictor input,
# kept for descriptive analytics only. Phase 5's "no post-decision features" test
# enforces this against this exact tuple.
POST_DECISION: tuple[str, ...] = ("days_to_review", "days_to_adopt")

# OQ-1.4: known at IMR filing time — legitimate predictor inputs.
PREDICTION_ELIGIBLE: tuple[str, ...] = (
    "report_year",
    "diagnosis_category",
    "diagnosis_subcategory",
    "treatment_category",
    "treatment_subcategory",
    "case_type",
    "age_range",
    "patient_gender",
    "imr_type",
)

LABEL = "overturned"
# Post-decision narrative (OQ-0.1): surfaces only, never a predictor input.
NARRATIVE = "findings"

# Final column order: identifiers/features first, label parts + narrative last.
COLUMN_ORDER: tuple[str, ...] = (
    "row_id",
    "reference_id",
    "report_year",
    "diagnosis_category",
    "diagnosis_subcategory",
    "treatment_category",
    "treatment_subcategory",
    "case_type",
    "age_range",
    "patient_gender",
    "imr_type",
    "days_to_review",
    "days_to_adopt",
    "determination_raw",
    "overturned",
    "findings",
)


class SchemaContractError(ValueError):
    """The raw CSV violates the ingest contract: header, cast, or enum domain."""


def read_raw(path: Path) -> pl.DataFrame:
    """Read the raw DMHC CSV with every column as a string; casts happen in `validate`."""
    return pl.read_csv(path, infer_schema_length=0, encoding="utf8-lossy")


def validate(raw: pl.DataFrame) -> pl.DataFrame:
    """Enforce the 14-column contract; return the renamed, cast, labeled frame.

    Fails loudly (`SchemaContractError`) on a header mismatch, a cast failure, an
    unknown enum value, or a null in a required column — nothing is silently dropped
    or coerced (OQ-1.0 Invariants).
    """
    _check_header(raw)
    df = raw.rename(dict(RENAMES))
    df = _cast_int32(df, "report_year", nullable=False)
    df = _cast_int32(df, "days_to_review", nullable=True)
    df = _cast_int32(df, "days_to_adopt", nullable=True)
    df = _nullify_empty_strings(df, NULLABLE_ENUMS + NULLABLE_STRINGS)
    _check_enums(df)
    _check_required(df)
    df = df.with_columns(
        pl.col("determination_raw")
        .replace_strict(DETERMINATION_TO_OVERTURNED, return_dtype=pl.Boolean)
        .alias("overturned")
    )
    df = df.with_row_index("row_id").with_columns(pl.col("row_id").cast(pl.Int64))
    df = df.select(list(COLUMN_ORDER))
    return CONTRACT.validate(df)


def _check_header(raw: pl.DataFrame) -> None:
    got = tuple(raw.columns)
    if got == SOURCE_COLUMNS:
        return
    missing = [c for c in SOURCE_COLUMNS if c not in got]
    extra = [c for c in got if c not in SOURCE_COLUMNS]
    problems = []
    if missing:
        problems.append(f"missing={missing}")
    if extra:
        problems.append(f"extra={extra}")
    if not missing and not extra:
        problems.append(f"reordered: expected={list(SOURCE_COLUMNS)} got={list(got)}")
    raise SchemaContractError(f"header contract violated: {'; '.join(problems)}")


def _cast_int32(df: pl.DataFrame, column: str, *, nullable: bool) -> pl.DataFrame:
    source = df.get_column(column)
    working = source.replace("", None) if nullable else source
    cast = working.cast(pl.Int32, strict=False)
    # A value that fails to parse becomes null with `strict=False`; catch it by
    # comparing against the pre-cast column. For a non-nullable column a value that
    # was *already* null/empty on read (polars parses an empty CSV cell as null, not
    # "") is just as much a contract violation as unparseable text, so it counts too.
    failed = cast.is_null() & working.is_not_null()
    if not nullable:
        failed = failed | working.is_null()
    if failed.any():
        offending = working.filter(failed).unique().to_list()[:5]
        raise SchemaContractError(
            f"column {column!r}: cannot cast to Int32, offending values (first 5): {offending}"
        )
    return df.with_columns(cast.alias(column))


def _nullify_empty_strings(df: pl.DataFrame, columns: tuple[str, ...]) -> pl.DataFrame:
    return df.with_columns([pl.col(c).replace("", None) for c in columns])


def _check_enums(df: pl.DataFrame) -> None:
    for column, allowed in ENUMS.items():
        values = df.get_column(column).drop_nulls().unique().to_list()
        unknown = sorted(v for v in values if v not in allowed)
        if unknown:
            raise SchemaContractError(
                f"column {column!r}: unknown values {unknown}; allowed={list(allowed)}"
            )


def _check_required(df: pl.DataFrame) -> None:
    for column in REQUIRED:
        n = df.get_column(column).null_count()
        if n:
            raise SchemaContractError(f"column {column!r}: {n} null value(s) not allowed")


CONTRACT = pa.DataFrameSchema(
    {
        "row_id": pa.Column(pl.Int64, unique=True),
        "reference_id": pa.Column(pl.String),
        "report_year": pa.Column(pl.Int32),
        "diagnosis_category": pa.Column(pl.String),
        "diagnosis_subcategory": pa.Column(pl.String, nullable=True),
        "treatment_category": pa.Column(pl.String),
        "treatment_subcategory": pa.Column(pl.String, nullable=True),
        "case_type": pa.Column(pl.String, checks=pa.Check.isin(ENUMS["case_type"])),
        "age_range": pa.Column(
            pl.String, checks=pa.Check.isin(ENUMS["age_range"]), nullable=True
        ),
        "patient_gender": pa.Column(
            pl.String, checks=pa.Check.isin(ENUMS["patient_gender"]), nullable=True
        ),
        "imr_type": pa.Column(pl.String, checks=pa.Check.isin(ENUMS["imr_type"])),
        "days_to_review": pa.Column(pl.Int32, nullable=True),
        "days_to_adopt": pa.Column(pl.Int32, nullable=True),
        "determination_raw": pa.Column(
            pl.String, checks=pa.Check.isin(ENUMS["determination_raw"])
        ),
        "overturned": pa.Column(pl.Boolean),
        "findings": pa.Column(pl.String),
    },
    strict=True,
    ordered=True,
)
