"""Tests for the 14-column ingest contract: header, casts, enum domains, renames, and the
derived `overturned` label / `row_id` surrogate key (OQ-1.0 Schema, OQ-1.4, OQ-1.6)."""

from __future__ import annotations

import polars as pl
import pytest

from repeal.ingest import download, schema


def _raw_frame(**overrides: list[str | None]) -> pl.DataFrame:
    """A minimal 2-row frame shaped exactly like `read_raw`'s output (all-string columns)."""
    base: dict[str, list[str | None]] = {
        "ReferenceID": ["MN26-00001", "EI25-00002"],
        "ReportYear": ["2026", "2025"],
        "DiagnosisCategory": ["Musculoskeletal", "Cancer"],
        "DiagnosisSubCategory": ["Back Pain", ""],
        "TreatmentCategory": ["Surgery", "Chemo Drugs"],
        "TreatmentSubCategory": ["Spine", ""],
        "Determination": ["Overturned Decision of Health Plan", "Upheld Decision of Health Plan"],
        "Type": ["Medical Necessity", "Experimental/Investigational"],
        "AgeRange": ["31 to 40", "65+"],
        "PatientGender": ["Female", "Male"],
        "IMRType": ["Standard", "Expedited"],
        "DaysToReview": ["10", ""],
        "DaysToAdopt": ["20", ""],
        "Findings": ["Short finding text.", "Another finding text."],
    }
    base.update(overrides)
    return pl.DataFrame(base, schema={c: pl.String for c in base})


class TestHeaderContract:
    def test_exact_header_passes(self):
        df = schema.validate(_raw_frame())
        assert df.height == 2

    def test_missing_column_raises_with_name(self):
        raw = _raw_frame().drop("PatientGender")
        with pytest.raises(schema.SchemaContractError, match="PatientGender"):
            schema.validate(raw)

    def test_extra_column_raises_with_name(self):
        raw = _raw_frame().with_columns(pl.lit("x").alias("BogusColumn"))
        with pytest.raises(schema.SchemaContractError, match="BogusColumn"):
            schema.validate(raw)

    def test_reordered_columns_raises(self):
        raw = _raw_frame()
        raw = raw.select(list(reversed(raw.columns)))
        with pytest.raises(schema.SchemaContractError, match="reorder"):
            schema.validate(raw)


class TestCasts:
    def test_report_year_cast_failure_names_value(self):
        raw = _raw_frame(ReportYear=["oops", "2025"])
        with pytest.raises(schema.SchemaContractError, match="oops"):
            schema.validate(raw)

    def test_days_to_review_cast_failure_names_value(self):
        raw = _raw_frame(DaysToReview=["ten", ""])
        with pytest.raises(schema.SchemaContractError, match="ten"):
            schema.validate(raw)

    def test_days_to_review_empty_string_becomes_null(self):
        df = schema.validate(_raw_frame(DaysToReview=["10", ""]))
        assert df["days_to_review"].to_list() == [10, None]

    def test_report_year_casts_to_int32(self):
        df = schema.validate(_raw_frame())
        assert df.schema["report_year"] == pl.Int32

    def test_report_year_missing_raises(self):
        # A cell that was empty on read parses as null (not "") once the CSV round-trips
        # through polars — `report_year` is non-nullable, so that still has to fail loudly.
        raw = _raw_frame().with_columns(pl.Series("ReportYear", ["2026", None]))
        with pytest.raises(schema.SchemaContractError, match="report_year"):
            schema.validate(raw)


class TestEnums:
    def test_unknown_case_type_raises_with_value(self):
        raw = _raw_frame(Type=["Not A Real Value", "Medical Necessity"])
        with pytest.raises(schema.SchemaContractError, match="Not A Real Value"):
            schema.validate(raw)

    def test_unknown_imr_type_raises_with_value(self):
        raw = _raw_frame(IMRType=["Not A Real Value", "Standard"])
        with pytest.raises(schema.SchemaContractError, match="Not A Real Value"):
            schema.validate(raw)

    def test_unknown_patient_gender_raises_with_value(self):
        raw = _raw_frame(PatientGender=["Not A Real Value", "Male"])
        with pytest.raises(schema.SchemaContractError, match="Not A Real Value"):
            schema.validate(raw)

    def test_unknown_age_range_raises_with_value(self):
        raw = _raw_frame(AgeRange=["Not A Real Value", "65+"])
        with pytest.raises(schema.SchemaContractError, match="Not A Real Value"):
            schema.validate(raw)

    def test_unknown_determination_raises_with_value(self):
        raw = _raw_frame(
            Determination=["Not A Real Value", "Upheld Decision of Health Plan"]
        )
        with pytest.raises(schema.SchemaContractError, match="Not A Real Value"):
            schema.validate(raw)


class TestNullability:
    def test_nullable_columns_allow_empty_string_as_null(self):
        raw = _raw_frame(
            AgeRange=["", "65+"],
            PatientGender=["", "Male"],
            DiagnosisSubCategory=["", "X"],
            TreatmentSubCategory=["", "Y"],
        )
        df = schema.validate(raw)
        assert df["age_range"][0] is None
        assert df["patient_gender"][0] is None
        assert df["diagnosis_subcategory"][0] is None
        assert df["treatment_subcategory"][0] is None

    def test_findings_null_rejected(self):
        raw = _raw_frame().with_columns(pl.Series("Findings", [None, "ok"]))
        with pytest.raises(schema.SchemaContractError, match="findings"):
            schema.validate(raw)

    def test_reference_id_null_rejected(self):
        raw = _raw_frame().with_columns(pl.Series("ReferenceID", [None, "EI25-00002"]))
        with pytest.raises(schema.SchemaContractError, match="reference_id"):
            schema.validate(raw)


class TestLabelDerivation:
    def test_overturned_mapping(self):
        df = schema.validate(_raw_frame())
        assert df["overturned"].to_list() == [True, False]
        assert df["determination_raw"].to_list() == [
            "Overturned Decision of Health Plan",
            "Upheld Decision of Health Plan",
        ]


class TestRowId:
    def test_row_id_is_source_order_zero_indexed(self):
        df = schema.validate(_raw_frame())
        assert df["row_id"].to_list() == [0, 1]
        assert df["reference_id"].to_list() == ["MN26-00001", "EI25-00002"]
        assert df.schema["row_id"] == pl.Int64


class TestFieldClassification:
    def test_post_decision_is_subset_of_output_columns(self):
        df = schema.validate(_raw_frame())
        assert set(schema.POST_DECISION) <= set(df.columns)

    def test_post_decision_disjoint_from_prediction_eligible(self):
        assert set(schema.POST_DECISION).isdisjoint(schema.PREDICTION_ELIGIBLE)

    def test_column_order_matches_contract(self):
        df = schema.validate(_raw_frame())
        assert df.columns == list(schema.COLUMN_ORDER)


class TestContract:
    def test_contract_validates_output_of_validate(self):
        df = schema.validate(_raw_frame())
        out = schema.CONTRACT.validate(df)
        assert out.equals(df)


class TestConstants:
    def test_source_columns_matches_downloads_expected_fields(self):
        # Two independently-owned constants describing the same 14 real columns --
        # pin them to each other so a drift can't happen silently on either side.
        assert schema.SOURCE_COLUMNS == download.EXPECTED_SOURCE_FIELDS

    def test_renames_cover_all_source_columns(self):
        assert set(schema.RENAMES) == set(schema.SOURCE_COLUMNS)

    def test_age_range_has_seven_buckets(self):
        assert len(schema.ENUMS["age_range"]) == 7

    def test_determination_map_matches_enum(self):
        assert set(schema.DETERMINATION_TO_OVERTURNED) == set(schema.ENUMS["determination_raw"])
