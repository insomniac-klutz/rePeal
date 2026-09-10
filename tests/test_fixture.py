"""Tests for the synthetic fixture generator: byte-for-byte reproducibility, schema
validity, and that every pathology `normalize.py`/`quality.py` must detect is actually
present in the committed CSV (OQ-1.8 — synthetic-only, zero real corpus rows, ever)."""

from __future__ import annotations

import polars as pl

from repeal.ingest import schema
from tests.fixtures import generate_synthetic


def _validated_fixture() -> pl.DataFrame:
    raw = schema.read_raw(generate_synthetic.FIXTURE_PATH)
    return schema.validate(raw)


def test_regenerating_with_seed_42_is_byte_identical(tmp_path):
    out = tmp_path / "regenerated.csv"
    generate_synthetic.write_csv(generate_synthetic.build_rows(seed=42), out)
    assert out.read_bytes() == generate_synthetic.FIXTURE_PATH.read_bytes()


def test_fixture_has_the_exact_source_header():
    raw = schema.read_raw(generate_synthetic.FIXTURE_PATH)
    assert tuple(raw.columns) == schema.SOURCE_COLUMNS


def test_fixture_validates_against_schema_contract():
    df = _validated_fixture()
    assert df.height >= 58


def test_fixture_covers_every_enum_value():
    df = _validated_fixture()
    for column, allowed in schema.ENUMS.items():
        present = set(df[column].drop_nulls().unique().to_list())
        assert present == set(allowed), f"{column} missing {set(allowed) - present}"


def test_fixture_report_years_span_2001_to_2026():
    df = _validated_fixture()
    assert df["report_year"].min() == 2001
    assert df["report_year"].max() == 2026


def test_fixture_has_diagnosis_crosswalk_pairs():
    raw = schema.read_raw(generate_synthetic.FIXTURE_PATH)
    values = set(raw["DiagnosisCategory"].to_list())
    for legacy, new in generate_synthetic.DIAGNOSIS_CROSSWALK_PAIRS:
        assert legacy in values, f"missing legacy label {legacy!r}"
        assert new in values, f"missing new-vocab label {new!r}"


def test_fixture_has_treatment_crosswalk_pairs():
    raw = schema.read_raw(generate_synthetic.FIXTURE_PATH)
    values = set(raw["TreatmentCategory"].to_list())
    for legacy, new in generate_synthetic.TREATMENT_CROSSWALK_PAIRS:
        assert legacy in values, f"missing legacy label {legacy!r}"
        assert new in values, f"missing new-vocab label {new!r}"


def test_fixture_has_near_duplicate_spelling_pair():
    raw = schema.read_raw(generate_synthetic.FIXTURE_PATH)
    values = set(raw["DiagnosisCategory"].to_list())
    for label in generate_synthetic.NEAR_DUPLICATE_DIAGNOSIS_PAIR:
        assert label in values, f"missing near-duplicate label {label!r}"


def test_fixture_has_unknown_vocabulary_label():
    raw = schema.read_raw(generate_synthetic.FIXTURE_PATH)
    assert generate_synthetic.UNKNOWN_VOCAB_LABEL in raw["DiagnosisCategory"].to_list()


def test_fixture_has_duplicate_reference_id_with_divergent_findings():
    raw = schema.read_raw(generate_synthetic.FIXTURE_PATH)
    dupes = raw.group_by("ReferenceID").agg(
        pl.col("Findings").n_unique().alias("n_findings"), pl.len()
    )
    dupes = dupes.filter(pl.col("len") > 1)
    assert dupes.height >= 1, "fixture must contain a duplicate ReferenceID pair"
    assert (dupes["n_findings"] > 1).any(), "the duplicate pair's Findings must diverge"


def test_fixture_has_duplicate_findings_across_different_reference_ids():
    raw = schema.read_raw(generate_synthetic.FIXTURE_PATH)
    dupes = raw.group_by("Findings").agg(
        pl.col("ReferenceID").n_unique().alias("n_ids"), pl.len()
    )
    dupes = dupes.filter(pl.col("len") > 1)
    assert dupes.height >= 1
    assert (dupes["n_ids"] > 1).any(), "a duplicate-Findings group must span >1 ReferenceID"


def test_fixture_findings_are_otherwise_unique():
    # Guards against pigeonhole collisions in the filler-row phrase pools silently
    # drowning out the deliberate duplicate-Findings pair planted above.
    raw = schema.read_raw(generate_synthetic.FIXTURE_PATH)
    duplicated_rows = raw.height - raw["Findings"].n_unique()
    assert duplicated_rows <= 2, f"expected only one planted duplicate pair, got {duplicated_rows}"


def test_fixture_has_one_character_findings():
    raw = schema.read_raw(generate_synthetic.FIXTURE_PATH)
    assert (raw["Findings"].str.len_chars() == 1).any()


def test_fixture_has_legacy_cohort_row():
    # An empty CSV cell parses as null (not "") once read through polars.
    raw = schema.read_raw(generate_synthetic.FIXTURE_PATH)
    cohort = raw.filter(
        (pl.col("ReportYear") == "2001")
        & pl.col("AgeRange").is_null()
        & pl.col("PatientGender").is_null()
        & pl.col("DaysToReview").is_null()
    )
    assert cohort.height >= 1


def test_fixture_has_mojibake_row():
    raw = schema.read_raw(generate_synthetic.FIXTURE_PATH)
    assert raw.filter(pl.col("Findings").str.contains("â€™", literal=True)).height >= 1


def test_fixture_has_a_prefix_type_mismatch_row():
    raw = schema.read_raw(generate_synthetic.FIXTURE_PATH)
    mismatched = raw.filter(
        pl.col("ReferenceID").str.starts_with("MN") & (pl.col("Type") == "Urgent Care")
    )
    assert mismatched.height >= 1


def test_fixture_has_section_marker_rows():
    raw = schema.read_raw(generate_synthetic.FIXTURE_PATH)
    markers = raw.filter(
        pl.col("Findings").str.contains("Findings:", literal=True)
        & pl.col("Findings").str.contains("Final Result:", literal=True)
        & pl.col("Findings").str.contains("Credentials/Qualifications:", literal=True)
    )
    assert markers.height >= 2


def test_fixture_has_embedded_quotes_and_newline_in_findings():
    raw = schema.read_raw(generate_synthetic.FIXTURE_PATH)
    tricky = raw.filter(
        pl.col("Findings").str.contains("\n", literal=True)
        & pl.col("Findings").str.contains('"', literal=True)
    )
    assert tricky.height >= 1
