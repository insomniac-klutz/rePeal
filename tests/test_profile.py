"""Tests for `repeal.ingest.profile`: pure stats functions + markdown renderer.

Every table function gets a small inline frame with hand-computed expected
numbers. `cutoff_candidates` gets a frame spanning 2001-2026 sized so exactly
one candidate in the default range meets every OQ-1.5 criterion.
"""

from __future__ import annotations

import json

import polars as pl
import pytest

from repeal.ingest.profile import (
    ProfileStats,
    category_top_n,
    compute,
    cutoff_candidates,
    duplicate_pair_comparison,
    findings_length_percentiles_by_year,
    flag_counts,
    label_rate_by_year_and_type,
    main,
    null_cohorts,
    render,
    rows_and_label_rate_by_year,
    section_marker_prevalence_by_year,
    to_markdown,
    vocabulary_by_era,
)


def _row(df: pl.DataFrame, **filters: object) -> dict:
    """Return the single row of `df` matching every `col=value` filter."""
    cond = None
    for key, value in filters.items():
        clause = pl.col(key) == value
        cond = clause if cond is None else cond & clause
    matches = df.filter(cond).to_dicts()
    assert len(matches) == 1, f"expected exactly one row for {filters}, got {len(matches)}"
    return matches[0]


# --------------------------------------------------------------------------
# rows_and_label_rate_by_year / label_rate_by_year_and_type
# --------------------------------------------------------------------------


def test_rows_and_label_rate_by_year():
    df = pl.DataFrame(
        {
            "report_year": [2020, 2020, 2020, 2020, 2021, 2021],
            "overturned": [True, False, True, False, True, True],
        }
    )
    result = rows_and_label_rate_by_year(df)
    assert result.columns == ["report_year", "rows", "overturned", "overturn_rate"]

    row_2020 = _row(result, report_year=2020)
    assert row_2020["rows"] == 4
    assert row_2020["overturned"] == 2
    assert row_2020["overturn_rate"] == pytest.approx(0.5)

    row_2021 = _row(result, report_year=2021)
    assert row_2021["rows"] == 2
    assert row_2021["overturned"] == 2
    assert row_2021["overturn_rate"] == pytest.approx(1.0)


def test_label_rate_by_year_and_type():
    df = pl.DataFrame(
        {
            "report_year": [2020, 2020, 2020, 2021],
            "case_type": ["Medical Necessity", "Medical Necessity", "Urgent Care", "Urgent Care"],
            "overturned": [True, False, True, True],
        }
    )
    result = label_rate_by_year_and_type(df)
    assert result.columns == ["report_year", "case_type", "rows", "overturned", "overturn_rate"]

    mn_2020 = _row(result, report_year=2020, case_type="Medical Necessity")
    assert mn_2020["rows"] == 2
    assert mn_2020["overturn_rate"] == pytest.approx(0.5)

    uc_2020 = _row(result, report_year=2020, case_type="Urgent Care")
    assert uc_2020["rows"] == 1
    assert uc_2020["overturn_rate"] == pytest.approx(1.0)

    uc_2021 = _row(result, report_year=2021, case_type="Urgent Care")
    assert uc_2021["rows"] == 1
    assert uc_2021["overturn_rate"] == pytest.approx(1.0)


# --------------------------------------------------------------------------
# vocabulary_by_era
# --------------------------------------------------------------------------


def test_vocabulary_by_era_flags_new_labels_relative_to_all_prior_years():
    df = pl.DataFrame(
        {
            "report_year": [2019, 2019, 2020, 2020, 2021, 2021, 2021],
            "diagnosis_category": ["A", "B", "A", "C", "A", "C", "D"],
        }
    )
    result = vocabulary_by_era(df, col="diagnosis_category")
    assert result.columns == ["report_year", "n_distinct", "new_labels"]

    r2019 = _row(result, report_year=2019)
    assert r2019["n_distinct"] == 2
    assert sorted(r2019["new_labels"]) == ["A", "B"]

    r2020 = _row(result, report_year=2020)
    assert r2020["n_distinct"] == 2
    assert r2020["new_labels"] == ["C"]

    r2021 = _row(result, report_year=2021)
    assert r2021["n_distinct"] == 3
    assert r2021["new_labels"] == ["D"]


# --------------------------------------------------------------------------
# category_top_n
# --------------------------------------------------------------------------


def test_category_top_n_shares_rank_and_truncates():
    df = pl.DataFrame(
        {
            "diagnosis_category": ["A", "A", "A", "B", "B", "C", None],
            "overturned": [True, True, False, True, False, True, True],
        }
    )
    result = category_top_n(df, "diagnosis_category", n=15)
    assert result.columns == ["label", "rows", "share", "overturn_rate"]
    assert result.height == 3  # the null row is excluded from ranking

    a = _row(result, label="A")
    assert a["rows"] == 3
    assert a["share"] == pytest.approx(0.5)
    assert a["overturn_rate"] == pytest.approx(round(2 / 3, 3))

    c = _row(result, label="C")
    assert c["rows"] == 1
    assert c["share"] == pytest.approx(round(1 / 6, 3))

    top2 = category_top_n(df, "diagnosis_category", n=2)
    assert top2.height == 2
    assert set(top2["label"].to_list()) == {"A", "B"}


# --------------------------------------------------------------------------
# findings_length_percentiles_by_year
# --------------------------------------------------------------------------


def test_findings_length_percentiles_by_year_linear_interpolation():
    lengths = [10, 20, 30, 40, 50]
    df = pl.DataFrame(
        {
            "report_year": [2020] * len(lengths),
            "findings": ["x" * n for n in lengths],
        }
    )
    result = findings_length_percentiles_by_year(df)
    row = _row(result, report_year=2020)
    # linear interpolation (rank = q * (n - 1)) on [10, 20, 30, 40, 50]
    assert row["p1"] == pytest.approx(10.4, abs=0.05)
    assert row["p5"] == pytest.approx(12.0, abs=0.05)
    assert row["p25"] == pytest.approx(20.0, abs=0.05)
    assert row["p50"] == pytest.approx(30.0, abs=0.05)
    assert row["p75"] == pytest.approx(40.0, abs=0.05)
    assert row["p95"] == pytest.approx(48.0, abs=0.05)
    assert row["p99"] == pytest.approx(49.6, abs=0.05)
    assert row["max"] == 50
    assert row["n_under_100"] == 5


# --------------------------------------------------------------------------
# duplicate_pair_comparison
# --------------------------------------------------------------------------


def test_duplicate_pair_comparison_counts_identical_vs_divergent():
    df = pl.DataFrame(
        {
            "reference_id": ["A", "A", "B", "B", "C", "C", "D"],
            "findings": ["x", "x", "y", "z", "p", "p", "q"],
            "overturned": [True, True, True, False, False, False, True],
        }
    )
    result = duplicate_pair_comparison(df)
    assert result.height == 1
    row = result.to_dicts()[0]
    assert row["reference_id_groups"] == 3  # A, B, C (D is a singleton)
    assert row["rows_in_groups"] == 6
    assert row["findings_identical_groups"] == 2  # A, C
    assert row["findings_divergent_groups"] == 1  # B
    assert row["overturned_identical_groups"] == 2  # A, C
    assert row["overturned_divergent_groups"] == 1  # B


# --------------------------------------------------------------------------
# null_cohorts
# --------------------------------------------------------------------------


def test_null_cohorts_per_column_and_legacy_cohort():
    # Mirrors the real corpus shape (OQ-1.0's recon claimed one 691-row
    # 2001-2003 cohort null on all three fields together; the real ingest
    # run showed that's wrong -- age_range+patient_gender null is one 691-row
    # 2001-2003 cohort, days_to_review null is a DIFFERENT, non-overlapping
    # set of rows from 2007 on). a/b/c carry the demographic-null cohort with
    # days_to_review present; d/e carry the days_to_review nulls alone.
    df = pl.DataFrame(
        {
            "reference_id": ["a", "b", "c", "d", "e", "f"],
            "report_year": [2001, 2002, 2003, 2007, 2008, 2020],
            "age_range": [None, None, None, "18-25", "18-25", "26-35"],
            "patient_gender": [None, None, None, "Female", "Male", "Male"],
            "days_to_review": [5, 6, 7, None, None, 12],
        }
    )
    result = null_cohorts(df)

    # Every column's null rows get their own report_year span, not just the
    # named cohorts -- this is what actually catches "these are different
    # rows in different years" without hardcoding that fact into the table.
    age_row = _row(result, column="age_range")
    assert age_row["null_count"] == 3
    assert age_row["cohort_year_min"] == 2001
    assert age_row["cohort_year_max"] == 2003

    days_row = _row(result, column="days_to_review")
    assert days_row["null_count"] == 2
    assert days_row["cohort_year_min"] == 2007
    assert days_row["cohort_year_max"] == 2008

    ref_row = _row(result, column="reference_id")
    assert ref_row["null_count"] == 0
    assert ref_row["cohort_year_min"] is None

    two_way = _row(result, column="_cohort_age_gender_all_null")
    assert two_way["null_count"] == 3
    assert two_way["cohort_year_min"] == 2001
    assert two_way["cohort_year_max"] == 2003

    three_way = _row(result, column="_cohort_age_gender_days_all_null")
    assert three_way["null_count"] == 0
    assert three_way["cohort_year_min"] is None
    assert three_way["cohort_year_max"] is None


# --------------------------------------------------------------------------
# section_marker_prevalence_by_year
# --------------------------------------------------------------------------


def test_section_marker_prevalence_by_year():
    df = pl.DataFrame(
        {
            "report_year": [2020, 2020, 2021, 2021],
            "findings": [
                "Findings: ok. Final Result: upheld.",
                "no markers here",
                "Findings: ok.",
                "Findings: ok. Final Result: overturned. Credentials/Qualifications: MD",
            ],
        }
    )
    result = section_marker_prevalence_by_year(df)
    assert result.columns == [
        "report_year",
        "marker_findings",
        "marker_final_result",
        "marker_credentials_qualifications",
    ]

    r2020 = _row(result, report_year=2020)
    assert r2020["marker_findings"] == pytest.approx(0.5)
    assert r2020["marker_final_result"] == pytest.approx(0.5)
    assert r2020["marker_credentials_qualifications"] == pytest.approx(0.0)

    r2021 = _row(result, report_year=2021)
    assert r2021["marker_findings"] == pytest.approx(1.0)
    assert r2021["marker_final_result"] == pytest.approx(0.5)
    assert r2021["marker_credentials_qualifications"] == pytest.approx(0.5)


# --------------------------------------------------------------------------
# flag_counts
# --------------------------------------------------------------------------


def test_flag_counts_only_flag_columns():
    df = pl.DataFrame(
        {
            "flag_findings_short": [True, False, False, True],
            "flag_duplicate_reference_id": [False, False, True, False],
            "has_section_markers": [True, True, True, False],
            "not_a_flag_col": [1, 2, 3, 4],
        }
    )
    result = flag_counts(df)
    assert set(result["flag"].to_list()) == {
        "flag_findings_short",
        "flag_duplicate_reference_id",
        "has_section_markers",
    }

    short = _row(result, flag="flag_findings_short")
    assert short["count"] == 2
    assert short["share"] == pytest.approx(0.5)

    dup = _row(result, flag="flag_duplicate_reference_id")
    assert dup["count"] == 1
    assert dup["share"] == pytest.approx(0.25)

    markers = _row(result, flag="has_section_markers")
    assert markers["count"] == 3
    assert markers["share"] == pytest.approx(0.75)


# --------------------------------------------------------------------------
# cutoff_candidates
# --------------------------------------------------------------------------


def _cutoff_frame() -> pl.DataFrame:
    """87 rows across 2001-2026: 10/year for 2018-2025, 2 in 2001, 5 in 2026.

    Sized so that, over the default candidate years (2019-2024) with 2001 and
    2026 excluded, exactly cutoff_year=2023 lands in OQ-1.5's 15-25% test-share
    band with >=2 full test years -- the rest fail on share, full-years, or
    both. `diagnosis_category` carries a label ("NewTax") that appears only in
    2026, to exercise `test_vocab_pure`.
    """
    year_counts = {
        2001: 2,
        2018: 10,
        2019: 10,
        2020: 10,
        2021: 10,
        2022: 10,
        2023: 10,
        2024: 10,
        2025: 10,
        2026: 5,
    }
    overturn_true = {
        2001: 1,
        2018: 3,
        2019: 4,
        2020: 5,
        2021: 6,
        2022: 6,
        2023: 7,
        2024: 7,
        2025: 8,
        2026: 4,
    }
    years: list[int] = []
    overturned: list[bool] = []
    diagnosis: list[str] = []
    for year, n in year_counts.items():
        n_true = overturn_true[year]
        years += [year] * n
        overturned += [True] * n_true + [False] * (n - n_true)
        diagnosis += [("NewTax" if year == 2026 else "Standard")] * n
    return pl.DataFrame(
        {"report_year": years, "overturned": overturned, "diagnosis_category": diagnosis}
    )


def test_cutoff_candidates_shares_exclusions_and_meets_criteria():
    df = _cutoff_frame()
    result = cutoff_candidates(df, years=range(2019, 2025))
    assert result.height == 6

    for row in result.to_dicts():
        # 2001 (2 rows) and 2026 (5 rows) are excluded from every candidate.
        assert row["train_rows"] + row["test_rows"] == 80

    y2023 = _row(result, cutoff_year=2023)
    assert y2023["test_share"] == pytest.approx(0.25)
    assert y2023["test_full_years"] == 2
    assert y2023["test_years"] == [2024, 2025]
    assert y2023["meets_criteria"] is True
    assert y2023["train_overturn_rate"] == pytest.approx(round(31 / 60, 3))
    assert y2023["test_overturn_rate"] == pytest.approx(0.75)
    assert y2023["test_vocab_pure"] is True

    y2024 = _row(result, cutoff_year=2024)
    assert y2024["test_share"] == pytest.approx(0.125)
    assert y2024["test_full_years"] == 1
    assert y2024["meets_criteria"] is False

    y2019 = _row(result, cutoff_year=2019)
    assert y2019["test_share"] == pytest.approx(0.75)
    assert y2019["meets_criteria"] is False


def test_cutoff_candidates_vocab_purity_and_modern_from():
    df = _cutoff_frame()

    # 2026 excluded by default -> the 2026-only label can never reach test.
    default_result = _row(cutoff_candidates(df, years=[2025]), cutoff_year=2025)
    assert default_result["test_vocab_pure"] is True

    # Force 2026 into the test window: its exclusive label taints purity.
    leaky = _row(cutoff_candidates(df, years=[2025], exclude_years=()), cutoff_year=2025)
    assert leaky["test_years"] == [2026]
    assert leaky["test_vocab_pure"] is False

    # modern_from can flip an otherwise-passing candidate.
    lenient = _row(cutoff_candidates(df, years=[2023], modern_from=2020), cutoff_year=2023)
    assert lenient["meets_criteria"] is True
    strict = _row(cutoff_candidates(df, years=[2023], modern_from=2025), cutoff_year=2023)
    assert strict["meets_criteria"] is False


# --------------------------------------------------------------------------
# to_markdown
# --------------------------------------------------------------------------


def test_to_markdown_formats_floats_lists_bools_and_nulls():
    df = pl.DataFrame(
        {
            "label": ["A", "B"],
            "share": [0.123456, None],
            "tags": [["x", "y"], []],
            "flag": [True, False],
        }
    )
    text = to_markdown(df, floats=3)
    lines = text.strip("\n").split("\n")
    assert lines[0] == "| label | share | tags | flag |"
    assert lines[1] == "| --- | --- | --- | --- |"
    assert lines[2] == "| A | 0.123 | x, y | true |"
    assert lines[3] == "| B |  |  | false |"


# --------------------------------------------------------------------------
# render
# --------------------------------------------------------------------------


def test_render_includes_title_meta_and_sections():
    stats = ProfileStats(
        tables={"Foo table": pl.DataFrame({"a": [1, 2]})},
        meta={"rows": 5, "year_min": 2020, "year_max": 2021, "sha": "deadbeef"},
    )
    text = render(stats)
    assert text.startswith("# EDA")
    assert "5" in text
    assert "2020" in text and "2021" in text
    assert "deadbeef" in text
    assert "## Foo table" in text
    assert "| a |" in text


# --------------------------------------------------------------------------
# compute + render integration, and the CLI
# --------------------------------------------------------------------------


def _full_synthetic_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "reference_id": ["R1", "R2", "R3", "R3", "R4"],
            "report_year": [2020, 2020, 2021, 2021, 2021],
            "diagnosis_category": ["A", "B", "A", "A", None],
            "diagnosis_subcategory": ["a1", "b1", "a1", "a1", None],
            "treatment_category": ["T1", "T2", "T1", "T1", "T3"],
            "treatment_subcategory": ["t1", "t2", "t1", "t1", "t3"],
            "case_type": [
                "Medical Necessity",
                "Urgent Care",
                "Medical Necessity",
                "Medical Necessity",
                "Medical Necessity",
            ],
            "age_range": ["18-25", None, "26-35", "26-35", None],
            "patient_gender": ["Female", None, "Male", "Male", None],
            "days_to_review": [10, None, 12, 12, None],
            "overturned": [True, False, True, True, False],
            "findings": [
                "Findings: short.",
                "Final Result: upheld.",
                "Findings: ok. Final Result: overturned.",
                "Findings: ok. Final Result: overturned.",
                "x",
            ],
            "flag_findings_short": [False, False, False, False, True],
            "has_section_markers": [True, True, True, True, False],
        }
    )


def test_compute_and_render_cover_every_section():
    df = _full_synthetic_frame()
    stats = compute(df, sha="abc123")
    text = render(stats)

    expected_headings = [
        "Rows & overturn rate by year",
        "Overturn rate by year and case type",
        "Diagnosis category vocabulary by era",
        "Treatment category vocabulary by era",
        "Top diagnosis category labels",
        "Top diagnosis subcategory labels",
        "Top treatment category labels",
        "Top treatment subcategory labels",
        "Findings length percentiles by year",
        "Section-marker prevalence by year",
        "Duplicate reference_id pairs",
        "Null cohorts",
        "Quality-flag counts",
        "Temporal-cutoff candidates",
    ]
    for heading in expected_headings:
        assert f"## {heading}" in text, heading
    assert "abc123" in text


def test_cli_writes_report_to_out_path(tmp_path):
    df = _full_synthetic_frame()
    pq_path = tmp_path / "imr_cases.parquet"
    df.write_parquet(pq_path)
    out_path = tmp_path / "eda.md"

    main(["--parquet", str(pq_path), "--out", str(out_path), "--sha", "cafef00d"])

    assert out_path.exists()
    text = out_path.read_text()
    assert text.startswith("# EDA")
    assert "cafef00d" in text
    assert "## Temporal-cutoff candidates" in text


def test_cli_defaults_sha_from_ingest_report_next_to_the_parquet(tmp_path):
    # `make eda` never passes --sha; this is what makes its output carry the
    # snapshot sha anyway, by finding ingest_report.json next to the parquet.
    df = _full_synthetic_frame()
    pq_path = tmp_path / "imr_cases.parquet"
    df.write_parquet(pq_path)
    (tmp_path / "ingest_report.json").write_text(
        json.dumps({"snapshot": {"sha256": "beadfeed"}})
    )
    out_path = tmp_path / "eda.md"

    main(["--parquet", str(pq_path), "--out", str(out_path)])

    assert "beadfeed" in out_path.read_text()


def test_cli_has_no_sha_when_no_ingest_report_is_present(tmp_path):
    df = _full_synthetic_frame()
    pq_path = tmp_path / "imr_cases.parquet"
    df.write_parquet(pq_path)
    out_path = tmp_path / "eda.md"

    main(["--parquet", str(pq_path), "--out", str(out_path)])

    assert "Snapshot sha256" not in out_path.read_text()
