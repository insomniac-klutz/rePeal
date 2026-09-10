"""Tests for repeal.ingest.quality -- the eight row-level quality flags (OQ-1.11).

TDD note: written before src/repeal/ingest/quality.py exists. First run is
expected to fail on import (red); quality.py lands next to turn it green.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from repeal.ingest.quality import FLAG_COLUMNS, QualityReport, Thresholds, flag

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "imr_synthetic.csv"

# A "clean" row that trips none of the eight flags. Every test below starts
# from this and overrides only the field(s) relevant to the flag under test,
# so a failing assertion points at exactly one behavior.
_CLEAN_FINDINGS = "Clean findings text that is long enough and ends properly. " + "x" * 150 + "."


def _row(row_id: int, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "row_id": row_id,
        "reference_id": f"MN26-{10000 + row_id}",
        "report_year": 2026,
        "diagnosis_category": "Musculoskeletal",
        "diagnosis_subcategory": "Back",
        "treatment_category": "Surgery",
        "treatment_subcategory": "Spinal",
        "determination_raw": "Upheld Decision of Health Plan",
        "case_type": "Medical Necessity",
        "age_range": "41-50",
        "patient_gender": "Female",
        "imr_type": "Standard",
        "days_to_review": 30,
        "days_to_adopt": 5,
        "overturned": False,
        "findings": _CLEAN_FINDINGS,
    }
    base.update(overrides)
    return base


def _frame(rows: list[dict[str, object]]) -> pl.DataFrame:
    return pl.DataFrame(rows)


def test_flag_findings_short_fires_under_threshold_not_over() -> None:
    df = _frame([_row(0, findings="short"), _row(1)])
    result, report = flag(df)
    assert result["flag_findings_short"].to_list() == [True, False]
    assert report.counts["flag_findings_short"] == 1


def test_flag_findings_truncated_fires_without_terminal_punctuation() -> None:
    df = _frame(
        [
            _row(0, findings="A" * 250),  # long, no terminal punctuation
            _row(1),  # clean row ends with "."
            _row(2, findings="B" * 199 + "."),  # exactly at the floor, punctuated
        ]
    )
    result, report = flag(df)
    assert result["flag_findings_truncated"].to_list() == [True, False, False]
    assert report.counts["flag_findings_truncated"] == 1


def test_flag_encoding_artifact_fires_on_mojibake() -> None:
    df = _frame(
        [
            _row(0, findings="Patient didnâ€™t improve. " + "x" * 100),
            _row(1),
        ]
    )
    result, report = flag(df)
    assert result["flag_encoding_artifact"].to_list() == [True, False]
    assert report.counts["flag_encoding_artifact"] == 1


def test_flag_duplicate_reference_id_fires_on_shared_id() -> None:
    df = _frame(
        [
            _row(0, reference_id="MN26-99999"),
            _row(1, reference_id="MN26-99999"),
            _row(2),
        ]
    )
    result, report = flag(df)
    assert result["flag_duplicate_reference_id"].to_list() == [True, True, False]
    assert report.counts["flag_duplicate_reference_id"] == 2


def test_flag_duplicate_findings_fires_on_exact_text_match() -> None:
    dupe_text = "Identical findings text repeated verbatim. " + "y" * 150 + "."
    df = _frame(
        [
            _row(0, findings=dupe_text),
            _row(1, findings=dupe_text),
            _row(2),
        ]
    )
    result, report = flag(df)
    assert result["flag_duplicate_findings"].to_list() == [True, True, False]
    assert report.counts["flag_duplicate_findings"] == 2


def test_flag_legacy_cohort_requires_age_and_gender_null_only() -> None:
    # Real-corpus finding (lead, integrated run): the 691 rows missing age_range +
    # patient_gender are ReportYear 2001-2003, and every one of them HAS a
    # days_to_review value. The 691 rows missing days_to_review are a completely
    # different set, 2007 onward. Same count, disjoint rows -- a coincidence the
    # original recon (and this flag's first cut) mistook for one cohort, which is
    # why a three-condition AND fired zero times on the real 42,749-row corpus.
    # days_to_review is deliberately NOT part of this flag.
    df = _frame(
        [
            # real 2001-03 shape: both demo fields null, review populated
            _row(0, age_range=None, patient_gender=None, days_to_review=30),
            _row(1, age_range=None, patient_gender=None, days_to_review=None),  # null either way
            _row(2, age_range=None, patient_gender="Female", days_to_review=None),  # one field only
            _row(3, days_to_review=None),  # real 2007+ shape -- disjoint, must NOT flag
            _row(4),  # clean
        ]
    )
    result, report = flag(df)
    assert result["flag_legacy_cohort"].to_list() == [True, True, False, False, False]
    assert report.counts["flag_legacy_cohort"] == 2


def test_flag_id_prefix_mismatch_covers_letter_year_and_malformed() -> None:
    df = _frame(
        [
            _row(0),  # MN26-10000 / Medical Necessity / 2026 -- matches
            _row(1, reference_id="EI26-10001"),  # letters wrong for case_type
            _row(2, reference_id="MN03-10002"),  # year digits wrong
            _row(3, reference_id="BAD-ID-1234"),  # doesn't match the pattern at all
            _row(4, reference_id="UR26-10004", case_type="Urgent Care"),  # valid UR -- no flag
            _row(5, reference_id="UC26-10005", case_type="Urgent Care"),  # UC isn't real (it's UR)
        ]
    )
    result, report = flag(df)
    assert result["flag_id_prefix_mismatch"].to_list() == [False, True, True, True, False, True]
    assert report.counts["flag_id_prefix_mismatch"] == 4


def test_has_section_markers_fires_on_any_marker() -> None:
    df = _frame(
        [
            _row(0, findings="Findings: patient had knee pain. " + "z" * 180 + "."),
            _row(1),
        ]
    )
    result, report = flag(df)
    assert result["has_section_markers"].to_list() == [True, False]
    assert report.counts["has_section_markers"] == 1


def test_flag_never_drops_or_reorders_rows() -> None:
    df = _frame([_row(i) for i in range(5)])
    result, report = flag(df)
    assert result.height == df.height == 5
    assert result["row_id"].to_list() == [0, 1, 2, 3, 4]
    assert set(df.columns) <= set(result.columns)
    assert report.rows == 5


def test_thresholds_are_honored_short_floor() -> None:
    df = _frame([_row(0, findings="x" * 50)])
    default_result, _ = flag(df)
    assert default_result["flag_findings_short"].to_list() == [True]  # 50 < 100

    lenient_result, _ = flag(df, Thresholds(short_findings_chars=5))
    assert lenient_result["flag_findings_short"].to_list() == [False]  # 50 >= 5


def test_all_flag_columns_present_and_boolean() -> None:
    df = _frame([_row(0)])
    result, report = flag(df)
    for col in FLAG_COLUMNS:
        assert col in result.columns
        assert result[col].dtype == pl.Boolean
    assert isinstance(report, QualityReport)
    assert report.thresholds == Thresholds()


def _load_fixture_frame() -> pl.DataFrame | None:
    if not FIXTURE_PATH.exists():
        return None
    try:
        from repeal.ingest.schema import validate
    except ImportError:
        return None
    try:
        return validate(pl.scan_csv(FIXTURE_PATH, infer_schema_length=0).collect())
    except Exception:
        return None


@pytest.mark.skipif(
    _load_fixture_frame() is None,
    reason="synthetic fixture and/or schema.validate() not committed yet",
)
def test_flag_on_synthetic_fixture() -> None:
    """Exact counts, not `>= 1` -- generate_synthetic.py (seed=42) is deterministic,
    so these are facts about the committed fixture, not estimates: a wrong regex
    (like the UC/UR bug this replaced -- 15 innocent Urgent Care rows misflagged)
    now fails the suite instead of passing quietly under a `>= 1` floor.
    `flag_duplicate_findings`'s 2 is a deliberate plant (two different
    ReferenceIDs sharing one Findings text, modeling an upstream copy-paste
    artifact -- see generate_synthetic.py's dedicated block), distinct from the
    dupe-ID pair above it, which has deliberately divergent Findings and so
    doesn't contribute to this count.
    """
    df = _load_fixture_frame()
    assert df is not None
    result, report = flag(df)
    assert result.height == df.height
    for col in FLAG_COLUMNS:
        assert col in result.columns
    assert report.counts == {
        "flag_findings_short": 1,  # the planted 1-char Findings row
        "flag_findings_truncated": 0,  # every fixture Findings ends in terminal punctuation
        "flag_encoding_artifact": 1,  # the planted mojibake row
        "flag_duplicate_reference_id": 2,  # the planted dupe-ID pair
        "flag_duplicate_findings": 2,  # deliberate plant, see docstring
        "flag_legacy_cohort": 1,  # the planted 2001 legacy-cohort row
        "flag_id_prefix_mismatch": 1,  # the planted MN-prefix-on-Urgent-Care row
        "has_section_markers": 2,  # the two planted modern rows with section markers
    }
