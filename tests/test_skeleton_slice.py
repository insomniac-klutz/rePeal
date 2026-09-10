"""End-to-end test for the walking-skeleton run command (OQ-1.5): fixture ingest ->
fixture cards merged (provenance stamped) -> `run.main` -> DuckDB slice -> logreg ->
one static demo page, all behind one command. Also covers `run._resolve_row_id`'s
error contract directly (no DB needed for that part).
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

import polars as pl
import pytest

from repeal.ingest import download
from repeal.ingest import run as ingest_run
from repeal.skeleton import cards, run
from repeal.skeleton.baseline import Split

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "imr_synthetic.csv"
FIXTURE_CARDS = Path(__file__).parent / "fixtures" / "skeleton_cards.jsonl"
RAW_FILENAME = "imr_2026-06-01.csv"


def _fake_entry(filename: str, size_bytes: int) -> download.ManifestEntry:
    return download.ManifestEntry(
        filename=filename,
        url="https://example.invalid/imr.csv",
        resource_id="test-resource",
        upstream_last_modified="2026-06-01",
        retrieved_at="2026-06-01T00:00:00+00:00",
        sha256="0" * 64,
        size_bytes=size_bytes,
    )


def _adopt(source: Path):
    """A `download.fetch` replacement that copies `source` into `raw_dir` -- no network."""

    def _fake_fetch(
        raw_dir: Path, *, refresh: bool = False, session: object | None = None
    ) -> download.ManifestEntry:
        raw_dir.mkdir(parents=True, exist_ok=True)
        dest = raw_dir / RAW_FILENAME
        shutil.copyfile(source, dest)
        return _fake_entry(RAW_FILENAME, dest.stat().st_size)

    return _fake_fetch


@pytest.fixture
def slice_pipeline(tmp_path, monkeypatch):
    """REPEAL_DATA_DIR -> tmp_path; ingest the synthetic fixture, then merge the
    fixture cards on top of it (provenance stamped by `cards.merge_parts`)."""
    monkeypatch.setenv("REPEAL_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(download, "fetch", _adopt(FIXTURE_CSV))
    assert ingest_run.main([]) == 0

    skeleton_dir = tmp_path / "interim" / "skeleton"
    skeleton_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURE_CARDS, skeleton_dir / "cards_part_fixture.jsonl")
    cards.merge_parts(skeleton_dir, skeleton_dir / "cards.jsonl")
    return tmp_path


def test_main_returns_zero_on_the_fixture_slice(slice_pipeline):
    assert run.main([]) == 0


def test_demo_html_exists_with_footer_and_a_percentage(slice_pipeline):
    run.main([])
    demo_path = slice_pipeline / "interim" / "skeleton" / "demo.html"
    assert demo_path.is_file()
    html = demo_path.read_text(encoding="utf-8")
    assert "Drafts for professional review" in html
    assert "%" in html


def test_second_run_is_byte_identical(slice_pipeline):
    run.main([])
    demo_path = slice_pipeline / "interim" / "skeleton" / "demo.html"
    first_hash = hashlib.sha256(demo_path.read_bytes()).hexdigest()

    run.main([])
    second_hash = hashlib.sha256(demo_path.read_bytes()).hexdigest()
    assert first_hash == second_hash


def test_unknown_case_returns_two(slice_pipeline):
    assert run.main(["--case", "NOPE-00000"]) == 2


def test_missing_cards_jsonl_returns_two(tmp_path, monkeypatch):
    monkeypatch.setenv("REPEAL_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(download, "fetch", _adopt(FIXTURE_CSV))
    assert ingest_run.main([]) == 0  # parquet exists, but no cards.jsonl was ever written
    assert run.main([]) == 2


def _slice_df() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "row_id": [1, 2, 3, 4],
            "reference_id": ["MN20-001", "MN20-002", "MN22-003", "MN22-003"],
            "report_year": [2020, 2020, 2022, 2022],
        }
    )


def _split() -> Split:
    df = _slice_df()
    return Split(
        train=df.filter(pl.col("report_year") <= 2021),
        test=df.filter(pl.col("report_year") > 2021).sort("row_id"),
    )


def _args(case=None, row_id=None, k=5) -> argparse.Namespace:
    return argparse.Namespace(case=case, row_id=row_id, k=k)


class TestResolveRowId:
    """`run._resolve_row_id` in isolation -- pure function, no DB needed."""

    def test_default_is_first_row_of_test_split_by_row_id(self):
        assert run._resolve_row_id(_slice_df(), _split(), _args()) == 3

    def test_case_resolves_to_its_row_id(self):
        assert run._resolve_row_id(_slice_df(), _split(), _args(case="MN20-002")) == 2

    def test_row_id_resolves_directly(self):
        assert run._resolve_row_id(_slice_df(), _split(), _args(row_id=1)) == 1

    def test_unknown_case_returns_none(self, capsys):
        assert run._resolve_row_id(_slice_df(), _split(), _args(case="nope")) is None
        assert "nope" in capsys.readouterr().err

    def test_unknown_row_id_returns_none(self, capsys):
        assert run._resolve_row_id(_slice_df(), _split(), _args(row_id=999)) is None
        assert "999" in capsys.readouterr().err

    def test_ambiguous_case_prints_both_row_ids_and_returns_none(self, capsys):
        assert run._resolve_row_id(_slice_df(), _split(), _args(case="MN22-003")) is None
        err = capsys.readouterr().err
        assert "3" in err
        assert "4" in err
