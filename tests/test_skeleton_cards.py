"""Tests for the Phase 1.5 case-card schema, sampler, prompt hash, and card I/O
(OQ-1.5.1, OQ-1.5.2, OQ-1.5.4). The sampler tests build a parquet-shaped frame inline
rather than running the real ingest pipeline; the merge/load tests build minimal
invented cards inline; the fixture test exercises the committed synthetic cards
against `tests/fixtures/imr_synthetic.csv` (OQ-1.8 — no real corpus rows anywhere)."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest
from pydantic import ValidationError

from repeal.ingest.schema import read_raw
from repeal.skeleton import cards
from tests.fixtures.generate_synthetic import FIXTURE_PATH

FIXTURE_CARDS_PATH = Path(__file__).resolve().parent / "fixtures" / "skeleton_cards.jsonl"

CASE_TYPES = ("Medical Necessity", "Experimental/Investigational", "Urgent Care")


def _raw_card(row_id: int, reference_id: str, **overrides: object) -> dict[str, object]:
    """A minimal, valid, provenance-free card dict — what an extractor part writes."""
    base: dict[str, object] = {
        "row_id": row_id,
        "reference_id": reference_id,
        "patient_context": "Adult patient with a chronic condition, no prior treatment.",
        "diagnosis_norm": "Chronic condition, unspecified.",
        "treatment_requested": "A requested course of treatment.",
        "denial_basis": "medical_necessity",
        "payer_rationale": "The plan found the request not medically necessary.",
        "evidence_cited": [{"kind": "guideline", "text": "Plan clinical guideline, section 4."}],
        "scrub_flags": [],
    }
    base.update(overrides)
    return base


def _stratified_frame() -> pl.DataFrame:
    """A parquet-shaped frame covering all 12 (case_type x overturned x era) strata,
    plus rows that must be excluded: edge report years and `flag_findings_short`.

    11 of the 12 strata get 11 rows each (eligible=121); one deliberately tiny stratum
    (Urgent Care / overturned / post-era) gets exactly 2, to exercise "small strata
    taken whole" against the floor of 2. 123 eligible + 9 excluded = 132 rows.
    """
    rows: list[dict[str, object]] = []
    row_id = 0

    def add(case_type: str, overturned: bool, report_year: int, *, short: bool = False) -> None:
        nonlocal row_id
        rows.append(
            {
                "row_id": row_id,
                "reference_id": f"XX{row_id:05d}",
                "report_year": report_year,
                "case_type": case_type,
                "overturned": overturned,
                "imr_type": "Standard",
                "age_range": "31 to 40",
                "patient_gender": "Female",
                "diagnosis_category": "Test Category",
                "treatment_category": "Test Treatment",
                "determination_raw": (
                    "Overturned Decision of Health Plan"
                    if overturned
                    else "Upheld Decision of Health Plan"
                ),
                "findings": (
                    "x" if short else "A sufficiently long findings narrative. " * 3
                ),
                "flag_findings_short": short,
            }
        )
        row_id += 1

    for case_type in CASE_TYPES:
        for overturned in (True, False):
            for era_year in (2018, 2024):  # pre (<=2021) / post (>=2022)
                tiny = case_type == "Urgent Care" and overturned and era_year == 2024
                n = 2 if tiny else 11
                for _ in range(n):
                    add(case_type, overturned, era_year)

    for _ in range(3):
        add("Medical Necessity", True, 2001)
    for _ in range(3):
        add("Medical Necessity", True, 2026)
    for _ in range(3):
        add("Medical Necessity", True, 2020, short=True)

    return pl.DataFrame(rows)


class TestDenialBasisEnum:
    def test_valid_members(self):
        assert cards.DenialBasis("medical_necessity") is cards.DenialBasis.medical_necessity
        assert (
            cards.DenialBasis("experimental_investigational")
            is cards.DenialBasis.experimental_investigational
        )
        assert cards.DenialBasis("urgent") is cards.DenialBasis.urgent

    def test_case_card_rejects_bad_denial_basis(self):
        with pytest.raises(ValidationError):
            cards.CaseCard(**_raw_card(1, "MN26-00001", denial_basis="not_a_real_basis"))

    def test_case_card_rejects_unknown_evidence_kind(self):
        with pytest.raises(ValidationError):
            cards.CaseCard(
                **_raw_card(
                    1, "MN26-00001", evidence_cited=[{"kind": "not_a_kind", "text": "x"}]
                )
            )

    def test_case_card_accepts_valid_card(self):
        card = cards.CaseCard(**_raw_card(1, "MN26-00001"))
        assert card.row_id == 1
        assert card.denial_basis is cards.DenialBasis.medical_necessity
        assert card.prompt_hash is None
        assert card.extractor is None


class TestNormalizeDenialBasis:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("medical necessity", cards.DenialBasis.medical_necessity),
            ("Medical Necessity", cards.DenialBasis.medical_necessity),
            ("medical_necessity", cards.DenialBasis.medical_necessity),
            ("Experimental/Investigational", cards.DenialBasis.experimental_investigational),
            ("experimental-investigational", cards.DenialBasis.experimental_investigational),
            ("E/I", cards.DenialBasis.experimental_investigational),
            ("e/i", cards.DenialBasis.experimental_investigational),
            ("urgent care", cards.DenialBasis.urgent),
            ("URGENT", cards.DenialBasis.urgent),
            ("  urgent  ", cards.DenialBasis.urgent),
        ],
    )
    def test_synonyms_normalize(self, value, expected):
        assert cards.normalize_denial_basis(value) == expected

    def test_garbage_raises_value_error(self):
        with pytest.raises(ValueError, match="banana"):
            cards.normalize_denial_basis("banana")


class TestPromptHash:
    def test_is_64_hex_chars(self):
        digest = cards.prompt_hash()
        assert len(digest) == 64
        int(digest, 16)  # raises ValueError if not hex

    def test_changes_when_file_changes(self, tmp_path):
        original = cards.PROMPT_PATH.read_bytes()
        copy_path = tmp_path / "case_card_v0.md"
        copy_path.write_bytes(original)
        assert cards.prompt_hash(copy_path) == cards.prompt_hash()

        copy_path.write_bytes(original + b"\nmutated")
        mutated_hash = cards.prompt_hash(copy_path)
        assert mutated_hash != cards.prompt_hash()
        assert len(mutated_hash) == 64


class TestSampleRowIds:
    def test_deterministic_across_two_calls(self):
        df = _stratified_frame()
        assert cards.sample_row_ids(df, n=100, seed=42) == cards.sample_row_ids(
            df, n=100, seed=42
        )

    def test_excludes_edge_years_and_short_findings(self):
        df = _stratified_frame()
        selected = set(cards.sample_row_ids(df, n=100, seed=42))
        excluded = set(
            df.filter(
                pl.col("report_year").is_in([2001, 2026]) | pl.col("flag_findings_short")
            )["row_id"].to_list()
        )
        assert selected.isdisjoint(excluded)

    def test_every_stratum_represented(self):
        df = _stratified_frame()
        selected = cards.sample_row_ids(df, n=100, seed=42)
        sampled = df.filter(pl.col("row_id").is_in(selected)).with_columns(
            pl.when(pl.col("report_year") <= 2021)
            .then(pl.lit("pre"))
            .otherwise(pl.lit("post"))
            .alias("_era")
        )
        assert sampled.select("case_type", "overturned", "_era").unique().height == 12

    def test_size_in_range(self):
        df = _stratified_frame()
        assert 95 <= len(cards.sample_row_ids(df, n=100, seed=42)) <= 105

    def test_returns_sorted_row_ids(self):
        df = _stratified_frame()
        selected = cards.sample_row_ids(df, n=100, seed=42)
        assert selected == sorted(selected)

    def test_small_stratum_taken_whole(self):
        df = _stratified_frame()
        selected = set(cards.sample_row_ids(df, n=100, seed=42))
        tiny = set(
            df.filter(
                (pl.col("case_type") == "Urgent Care")
                & pl.col("overturned")
                & (pl.col("report_year") == 2024)
            )["row_id"].to_list()
        )
        assert len(tiny) == 2
        assert tiny <= selected


class TestWriteSample:
    def test_columns_and_no_label(self, tmp_path):
        df = _stratified_frame()
        parquet_path = tmp_path / "imr_cases.parquet"
        df.write_parquet(parquet_path)
        out_path = tmp_path / "skeleton" / "sample.jsonl"

        count = cards.write_sample(parquet_path, out_path, n=100, seed=42)

        lines = out_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == count
        assert 95 <= count <= 105
        row_ids = []
        for line in lines:
            obj = json.loads(line)
            assert set(obj) == set(cards.SAMPLE_COLUMNS)
            assert "overturned" not in obj
            assert "determination_raw" not in obj
            row_ids.append(obj["row_id"])
        assert row_ids == sorted(row_ids)


class TestMergeParts:
    def test_stamps_provenance_and_sorts_by_row_id(self, tmp_path):
        parts_dir = tmp_path / "skeleton"
        parts_dir.mkdir()
        (parts_dir / "cards_part_b.jsonl").write_text(
            json.dumps(_raw_card(5, "MN26-00005")) + "\n", encoding="utf-8"
        )
        (parts_dir / "cards_part_a.jsonl").write_text(
            json.dumps(_raw_card(1, "MN26-00001")) + "\n", encoding="utf-8"
        )
        out = parts_dir / "cards.jsonl"

        count = cards.merge_parts(parts_dir, out)

        assert count == 2
        loaded = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
        assert [c["row_id"] for c in loaded] == [1, 5]
        by_row = {c["row_id"]: c for c in loaded}
        assert by_row[1]["extractor"] == "a"
        assert by_row[5]["extractor"] == "b"
        for card in loaded:
            assert card["prompt_hash"] == cards.prompt_hash()
            assert card["prompt_version"] == cards.PROMPT_VERSION
            assert card["model"] == cards.MODEL
            assert card["workflow"] == cards.WORKFLOW

    def test_rejects_duplicate_row_id_naming_it(self, tmp_path):
        parts_dir = tmp_path / "skeleton"
        parts_dir.mkdir()
        (parts_dir / "cards_part_a.jsonl").write_text(
            json.dumps(_raw_card(1, "MN26-00001")) + "\n", encoding="utf-8"
        )
        (parts_dir / "cards_part_b.jsonl").write_text(
            json.dumps(_raw_card(1, "MN26-99999")) + "\n", encoding="utf-8"
        )
        out = parts_dir / "cards.jsonl"

        with pytest.raises(ValueError, match="1"):
            cards.merge_parts(parts_dir, out)

    def test_rejects_invalid_card_naming_row_id_and_field(self, tmp_path):
        parts_dir = tmp_path / "skeleton"
        parts_dir.mkdir()
        bad = _raw_card(2, "MN26-00002", denial_basis="not_real")
        (parts_dir / "cards_part_a.jsonl").write_text(json.dumps(bad) + "\n", encoding="utf-8")
        out = parts_dir / "cards.jsonl"

        with pytest.raises(ValueError) as exc_info:
            cards.merge_parts(parts_dir, out)
        message = str(exc_info.value)
        assert "2" in message
        assert "denial_basis" in message

    def test_no_parts_raises(self, tmp_path):
        parts_dir = tmp_path / "empty"
        parts_dir.mkdir()
        with pytest.raises(ValueError, match="cards_part"):
            cards.merge_parts(parts_dir, parts_dir / "cards.jsonl")


class TestLoadCards:
    def test_round_trips_after_merge(self, tmp_path):
        parts_dir = tmp_path / "skeleton"
        parts_dir.mkdir()
        (parts_dir / "cards_part_a.jsonl").write_text(
            json.dumps(_raw_card(1, "MN26-00001")) + "\n", encoding="utf-8"
        )
        out = parts_dir / "cards.jsonl"
        cards.merge_parts(parts_dir, out)

        loaded = cards.load_cards(out)
        assert len(loaded) == 1
        assert loaded[0].row_id == 1
        assert loaded[0].prompt_hash == cards.prompt_hash()

    def test_rejects_wrong_hash_by_default(self, tmp_path):
        bad_line = _raw_card(1, "MN26-00001") | {
            "prompt_hash": "0" * 64,
            "prompt_version": cards.PROMPT_VERSION,
            "model": cards.MODEL,
            "workflow": cards.WORKFLOW,
            "extractor": "a",
        }
        path = tmp_path / "cards.jsonl"
        path.write_text(json.dumps(bad_line) + "\n", encoding="utf-8")

        with pytest.raises(ValueError, match="hash"):
            cards.load_cards(path)

    def test_check_hash_false_skips_check(self, tmp_path):
        bad_line = _raw_card(1, "MN26-00001") | {
            "prompt_hash": "0" * 64,
            "prompt_version": cards.PROMPT_VERSION,
            "model": cards.MODEL,
            "workflow": cards.WORKFLOW,
            "extractor": "a",
        }
        path = tmp_path / "cards.jsonl"
        path.write_text(json.dumps(bad_line) + "\n", encoding="utf-8")

        loaded = cards.load_cards(path, check_hash=False)
        assert len(loaded) == 1
        assert loaded[0].row_id == 1


class TestCardsFrame:
    def test_shape_and_derived_columns(self):
        raw_cards = [
            cards.CaseCard(**_raw_card(1, "MN26-00001")),
            cards.CaseCard(
                **_raw_card(
                    2,
                    "MN26-00002",
                    denial_basis="urgent",
                    evidence_cited=[
                        {"kind": "peer_reviewed_study", "text": "study 1"},
                        {"kind": "fda_status", "text": "fda note"},
                    ],
                    scrub_flags=["verdict_language_omitted"],
                )
            ),
        ]
        df = cards.cards_frame(raw_cards)
        assert df.height == 2
        expected_columns = {
            "row_id",
            "reference_id",
            "denial_basis",
            "n_evidence",
            "evidence_kinds",
            "scrub_flag_count",
            "patient_context",
            "diagnosis_norm",
            "treatment_requested",
            "payer_rationale",
            "evidence_json",
        }
        assert set(df.columns) == expected_columns

        row2 = df.filter(pl.col("row_id") == 2).to_dicts()[0]
        assert row2["denial_basis"] == "urgent"
        assert row2["n_evidence"] == 2
        assert row2["evidence_kinds"] == ["peer_reviewed_study", "fda_status"]
        assert row2["scrub_flag_count"] == 1

        row1 = df.filter(pl.col("row_id") == 1).to_dicts()[0]
        assert row1["n_evidence"] == 1
        assert row1["scrub_flag_count"] == 0

    def test_empty_list(self):
        df = cards.cards_frame([])
        assert df.height == 0


class TestFixtureCards:
    """The committed synthetic fixture cards (OQ-1.8): invented content keyed to real
    rows of `tests/fixtures/imr_synthetic.csv`, loadable by `load_cards(check_hash=False)`
    exactly as the warehouse/baseline teammates will load them."""

    def test_loads_at_least_twelve_cards(self):
        loaded = cards.load_cards(FIXTURE_CARDS_PATH, check_hash=False)
        assert len(loaded) >= 12

    def test_row_and_reference_ids_match_synthetic_csv(self):
        synthetic = read_raw(FIXTURE_PATH)
        ref_ids_by_row = dict(enumerate(synthetic["ReferenceID"].to_list()))
        loaded = cards.load_cards(FIXTURE_CARDS_PATH, check_hash=False)
        for card in loaded:
            assert card.row_id in ref_ids_by_row
            assert card.reference_id == ref_ids_by_row[card.row_id]

    def test_covers_all_denial_bases(self):
        loaded = cards.load_cards(FIXTURE_CARDS_PATH, check_hash=False)
        assert {c.denial_basis for c in loaded} == set(cards.DenialBasis)

    def test_covers_several_evidence_kinds(self):
        loaded = cards.load_cards(FIXTURE_CARDS_PATH, check_hash=False)
        kinds = {e.kind for c in loaded for e in c.evidence_cited}
        assert len(kinds) >= 3

    def test_has_a_verdict_scrubbed_card(self):
        loaded = cards.load_cards(FIXTURE_CARDS_PATH, check_hash=False)
        assert any(c.scrub_flags == ["verdict_language_omitted"] for c in loaded)

    def test_has_an_empty_evidence_card(self):
        loaded = cards.load_cards(FIXTURE_CARDS_PATH, check_hash=False)
        assert any(c.evidence_cited == [] for c in loaded)

    def test_cards_frame_on_fixture(self):
        loaded = cards.load_cards(FIXTURE_CARDS_PATH, check_hash=False)
        df = cards.cards_frame(loaded)
        assert df.height == len(loaded)
