"""Tests for repeal.skeleton.warehouse -- the Phase 1.5 DuckDB layer (OQ-1.5.3).

TDD note: written before src/repeal/skeleton/warehouse.py exists. First run is
expected to fail on import (red); warehouse.py lands next to turn it green.

Inline frames only -- no real corpus rows in a committed file. `cases` mirrors just
the columns warehouse.py actually touches (row_id, reference_id, report_year,
diagnosis_category, treatment_category, case_type, overturned, findings); the real
ingest parquet carries ~18 more, and `build`/`slice_frame` don't care -- they select
`*`. `cards` mirrors `repeal.skeleton.cards.cards_frame`'s exact schema (row_id,
reference_id, denial_basis, n_evidence, evidence_kinds, scrub_flag_count,
patient_context, diagnosis_norm, treatment_requested, payer_rationale, evidence_json)
without importing that module -- warehouse.py's `cards: Path | pl.DataFrame` branch
keeps the two modules decoupled at test time (only integration/end-to-end coverage
exercises the real `cards.py` -> JSONL path branch).

Fixture layout -- four diagnosis-category "namespaces" so each behavior is isolated
and every assertion is an exact list, not a `>=`:
  - Musculoskeletal/Surgery/Medical Necessity (row_id 0-7): 6 earlier full matches
    (0-5) + query (6, 2016) + a same-year distractor (7, 2016) that must never
    appear -- k-honoring, newest-first ordering, self-exclusion, strictly-earlier.
  - Cardiovascular/Urgent Care (row_id 8-11): one earlier Stent (full) match (8),
    query (9, Stent, 2018), two earlier Bypass-only matches (10, 11) -- fallback to
    diagnosis+case_type, `match_level` mix in one result.
  - Neurological/Experimental-Investigational (row_id 12): alone in its category --
    nothing earlier anywhere matches, empty result with the right columns.
  - Renal/Medical Necessity (row_id 13-14): a duplicate `reference_id` pair on
    distinct row_ids -- join-by-row_id sanity -- and row 14 is the one 2026 row.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl
import pytest

from repeal.skeleton.warehouse import (
    DB_FILENAME,
    CardRowIdMismatchError,
    build,
    close,
    precedents,
    slice_frame,
)

_CARD_SCHEMA: dict[str, object] = {
    "row_id": pl.Int64,
    "reference_id": pl.String,
    "denial_basis": pl.String,
    "n_evidence": pl.Int64,
    "evidence_kinds": pl.List(pl.String),
    "scrub_flag_count": pl.Int64,
    "patient_context": pl.String,
    "diagnosis_norm": pl.String,
    "treatment_requested": pl.String,
    "payer_rationale": pl.String,
    "evidence_json": pl.String,
}

# row_ids that get a case card -- a strict subset of `_BASE_CASES`, mirroring the
# real ~100-cards-over-42,749-cases shape. 4 and 11 are deliberately card-less, to
# prove the cases<->case_cards join is INNER (they must be absent from `slice`).
_CARD_ROW_IDS: tuple[int, ...] = (0, 1, 2, 3, 5, 6, 8, 9, 10, 12, 13, 14)


def _case(row_id: int, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "row_id": row_id,
        "reference_id": f"REF-{row_id}",
        "report_year": 2015,
        "diagnosis_category": "Musculoskeletal",
        "treatment_category": "Surgery",
        "case_type": "Medical Necessity",
        "overturned": False,
        "findings": f"findings text for row {row_id}",
    }
    base.update(overrides)
    return base


def _card(row_id: int, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "row_id": row_id,
        "reference_id": f"REF-{row_id}",
        "denial_basis": "medical_necessity",
        "n_evidence": 1,
        "evidence_kinds": ["guideline"],
        "scrub_flag_count": 0,
        "patient_context": "adult patient",
        "diagnosis_norm": "musculoskeletal",
        "treatment_requested": "surgery",
        "payer_rationale": "not medically necessary",
        "evidence_json": '[{"kind": "guideline", "text": "..."}]',
    }
    base.update(overrides)
    return base


_BASE_CASES: list[dict[str, object]] = [
    # Musculoskeletal group -- k-honoring / ordering / earlier-year discipline.
    _case(0, report_year=2010),
    _case(1, report_year=2011),
    _case(2, report_year=2012),
    _case(3, report_year=2013),
    _case(4, report_year=2014),  # no card -- proves the join is INNER
    _case(5, report_year=2015),
    _case(6, report_year=2016),  # QUERY_A
    _case(7, report_year=2016),  # same year as QUERY_A, distinct row -- must be excluded
    # Cardiovascular group -- fallback to diagnosis+case_type.
    _case(
        8,
        report_year=2005,
        diagnosis_category="Cardiovascular",
        treatment_category="Stent",
        case_type="Urgent Care",
        overturned=True,
    ),
    _case(
        9,  # QUERY_B
        report_year=2018,
        diagnosis_category="Cardiovascular",
        treatment_category="Stent",
        case_type="Urgent Care",
    ),
    _case(
        10,
        report_year=2010,
        diagnosis_category="Cardiovascular",
        treatment_category="Bypass",
        case_type="Urgent Care",
    ),
    _case(
        11,  # no card -- also proves the join is INNER
        report_year=2012,
        diagnosis_category="Cardiovascular",
        treatment_category="Bypass",
        case_type="Urgent Care",
    ),
    # Neurological group -- alone, nothing earlier anywhere matches.
    _case(
        12,  # QUERY_C
        report_year=2003,
        diagnosis_category="Neurological",
        treatment_category="Anticonvulsant",
        case_type="Experimental/Investigational",
    ),
    # Renal group -- duplicate reference_id pair, distinct row_ids; 14 is the 2026 row.
    _case(
        13,
        reference_id="REF-DUP",
        report_year=2019,
        diagnosis_category="Renal",
        treatment_category="Dialysis",
        case_type="Medical Necessity",
    ),
    _case(
        14,
        reference_id="REF-DUP",
        report_year=2026,
        diagnosis_category="Renal",
        treatment_category="Dialysis",
        case_type="Medical Necessity",
    ),
]


def _cases_frame() -> pl.DataFrame:
    return pl.DataFrame(_BASE_CASES)


def _cards_frame(row_ids: tuple[int, ...] = _CARD_ROW_IDS) -> pl.DataFrame:
    rows = [_card(0, evidence_kinds=["guideline", "fda_status"], n_evidence=2)]
    rows += [_card(row_id) for row_id in row_ids if row_id != 0]
    return pl.DataFrame(rows, schema=_CARD_SCHEMA)


def _write_cases_parquet(tmp_path: Path) -> Path:
    parquet_path = tmp_path / "imr_cases.parquet"
    _cases_frame().write_parquet(parquet_path)
    return parquet_path


def _build_fixture(
    tmp_path: Path, *, cards: pl.DataFrame | None = None, db_name: str = DB_FILENAME
) -> duckdb.DuckDBPyConnection:
    db_path = tmp_path / db_name
    parquet_path = _write_cases_parquet(tmp_path)
    return build(db_path, parquet_path, cards if cards is not None else _cards_frame())


# ---------------------------------------------------------------------------
# build()
# ---------------------------------------------------------------------------


def test_build_creates_tables_and_view_with_correct_row_counts(tmp_path):
    con = _build_fixture(tmp_path)
    try:
        assert con.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == len(_BASE_CASES)
        assert con.execute("SELECT COUNT(*) FROM case_cards").fetchone()[0] == len(
            _CARD_ROW_IDS
        )
        assert con.execute("SELECT COUNT(*) FROM slice").fetchone()[0] == len(_CARD_ROW_IDS)
    finally:
        close(con)


def test_build_join_is_on_row_id_not_reference_id(tmp_path):
    # Both members of the REF-DUP pair (13, 14) have cards. A join keyed on
    # reference_id (with case_cards also carrying reference_id) would cross-join
    # into 4 rows for this reference_id; keyed on row_id it's exactly 2.
    con = _build_fixture(tmp_path)
    try:
        dup = slice_frame(con).filter(pl.col("reference_id") == "REF-DUP")
        assert dup.height == 2
        assert sorted(dup["row_id"].to_list()) == [13, 14]
    finally:
        close(con)


def test_build_raises_when_card_row_id_missing_from_cases(tmp_path):
    bad_cards = _cards_frame((0, 1)).vstack(
        pl.DataFrame([_card(999)], schema=_CARD_SCHEMA)
    )
    with pytest.raises(CardRowIdMismatchError):
        _build_fixture(tmp_path, cards=bad_cards)


def test_build_twice_rebuilds_from_scratch_not_a_merge(tmp_path):
    db_path = tmp_path / DB_FILENAME
    parquet_path = _write_cases_parquet(tmp_path)

    con1 = build(db_path, parquet_path, _cards_frame())
    first_height = slice_frame(con1).height
    close(con1)

    smaller_cards = _cards_frame((0, 1, 2))
    con2 = build(db_path, parquet_path, smaller_cards)
    second = slice_frame(con2)
    close(con2)

    assert first_height == len(_CARD_ROW_IDS)
    assert second.height == 3
    assert second["row_id"].to_list() == [0, 1, 2]


def test_db_created_at_the_requested_path(tmp_path):
    con = _build_fixture(tmp_path, db_name="custom_name.duckdb")
    close(con)
    assert (tmp_path / "custom_name.duckdb").is_file()


# ---------------------------------------------------------------------------
# slice_frame()
# ---------------------------------------------------------------------------


def test_slice_frame_sorted_by_row_id_with_card_columns_present(tmp_path):
    con = _build_fixture(tmp_path)
    try:
        result = slice_frame(con)
        assert result["row_id"].to_list() == sorted(_CARD_ROW_IDS)
        for col in (
            "row_id",
            "reference_id",
            "report_year",
            "diagnosis_category",
            "treatment_category",
            "case_type",
            "overturned",
            "findings",
            "denial_basis",
            "n_evidence",
            "evidence_kinds",
            "scrub_flag_count",
            "patient_context",
            "diagnosis_norm",
            "treatment_requested",
            "payer_rationale",
        ):
            assert col in result.columns
        # evidence_json is provenance, not a display field -- deliberately left off slice.
        assert "evidence_json" not in result.columns

        row0 = result.filter(pl.col("row_id") == 0)
        assert row0["evidence_kinds"].to_list() == [["guideline", "fda_status"]]
    finally:
        close(con)


# ---------------------------------------------------------------------------
# precedents()
# ---------------------------------------------------------------------------


def test_precedents_honors_k_orders_newest_first_and_excludes_self_and_same_year(tmp_path):
    con = _build_fixture(tmp_path)
    try:
        result = precedents(con, row_id=6, k=5)
        assert result["row_id"].to_list() == [5, 4, 3, 2, 1]
        assert result["match_level"].to_list() == ["full"] * 5
        assert 0 not in result["row_id"].to_list()  # truncated by k
        assert 6 not in result["row_id"].to_list()  # self-excluded
        assert 7 not in result["row_id"].to_list()  # same year, not strictly earlier
    finally:
        close(con)


def test_precedents_falls_back_to_diagnosis_match_level_when_full_matches_are_scarce(tmp_path):
    con = _build_fixture(tmp_path)
    try:
        result = precedents(con, row_id=9, k=5)
        assert result["row_id"].to_list() == [11, 10, 8]
        assert result["match_level"].to_list() == ["diagnosis", "diagnosis", "full"]
    finally:
        close(con)


def test_precedents_empty_when_nothing_matches_earlier(tmp_path):
    con = _build_fixture(tmp_path)
    try:
        result = precedents(con, row_id=12, k=5)
        assert result.height == 0
        assert set(result.columns) == {
            "row_id",
            "reference_id",
            "report_year",
            "case_type",
            "diagnosis_category",
            "treatment_category",
            "overturned",
            "findings",
            "match_level",
        }
    finally:
        close(con)


def test_precedents_queries_the_full_cases_table_not_the_card_slice(tmp_path):
    # row 11 has no card (excluded from `slice`/case_cards) but must still surface
    # as a precedent -- OQ-1.5.3: precedents run over the FULL corpus.
    con = _build_fixture(tmp_path)
    try:
        result = precedents(con, row_id=9, k=5)
        assert 11 in result["row_id"].to_list()
    finally:
        close(con)


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------


def test_close_closes_the_connection(tmp_path):
    con = _build_fixture(tmp_path)
    close(con)
    with pytest.raises(duckdb.Error):
        con.execute("SELECT 1")


# ---------------------------------------------------------------------------
# build(cards=Path) -- the real repeal.skeleton.cards wiring
# ---------------------------------------------------------------------------
# Every test above keeps `cards` a `pl.DataFrame` by design (this module's tests
# don't depend on repeal.skeleton.cards). This one instead proves the `Path`
# branch -- `_resolve_cards_frame`'s lazy `load_cards`/`cards_frame` call -- against
# cipher-cards' real fixture: 12 hand-written cards (row_ids 0, 3, 5, 6, 10, 15,
# 19, 20, 22, 23, 26, 28) matching tests/fixtures/imr_synthetic.csv, no provenance
# stamps, hence `check_hash=False`.

_SYNTHETIC_CSV = Path(__file__).parent / "fixtures" / "imr_synthetic.csv"
_SKELETON_CARDS_JSONL = Path(__file__).parent / "fixtures" / "skeleton_cards.jsonl"
_SKELETON_CARDS_ROW_IDS = [0, 3, 5, 6, 10, 15, 19, 20, 22, 23, 26, 28]


def _real_fixture_frame() -> pl.DataFrame | None:
    if not (_SYNTHETIC_CSV.exists() and _SKELETON_CARDS_JSONL.exists()):
        return None
    try:
        import repeal.skeleton.cards  # noqa: F401
        from repeal.ingest.schema import read_raw, validate
    except ImportError:
        return None
    try:
        return validate(read_raw(_SYNTHETIC_CSV))
    except Exception:
        return None


@pytest.mark.skipif(
    _real_fixture_frame() is None,
    reason="synthetic fixture, repeal.ingest.schema, and/or repeal.skeleton.cards not available",
)
def test_build_accepts_a_real_cards_jsonl_path_end_to_end(tmp_path):
    """The one test that exercises `cards: Path` for real, against a real
    `CaseCard` JSONL and the real ingest contract -- everything above proves
    `build()`'s own logic against the `cards_frame()` shape, decoupled from
    `repeal.skeleton.cards`; this proves the two modules actually fit together.
    """
    frame = _real_fixture_frame()
    assert frame is not None
    parquet_path = tmp_path / "imr_cases.parquet"
    frame.write_parquet(parquet_path)

    db_path = tmp_path / DB_FILENAME
    con = build(db_path, parquet_path, _SKELETON_CARDS_JSONL, check_hash=False)
    try:
        result = slice_frame(con)
        assert result["row_id"].to_list() == _SKELETON_CARDS_ROW_IDS
        assert "denial_basis" in result.columns
        assert "evidence_json" not in result.columns
    finally:
        close(con)
