"""End-to-end tests for the ingest pipeline entry point (`run.main`) over the
committed synthetic fixture. No network: `download.fetch` is monkeypatched to
adopt the fixture instead of hitting the real CHHS endpoint.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import polars as pl
import pytest

from repeal.ingest import download, run
from repeal.ingest.quality import FLAG_COLUMNS
from repeal.ingest.schema import SOURCE_COLUMNS, read_raw

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "imr_synthetic.csv"
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
def isolated_pipeline(tmp_path, monkeypatch):
    """REPEAL_DATA_DIR -> tmp_path; `download.fetch` adopts the fixture, no network."""
    monkeypatch.setenv("REPEAL_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(download, "fetch", _adopt(FIXTURE_PATH))
    return tmp_path


def test_main_returns_zero_on_the_fixture(isolated_pipeline):
    assert run.main([]) == 0


def test_main_writes_parquet_and_report(isolated_pipeline):
    run.main([])
    interim = isolated_pipeline / "interim"
    assert (interim / run.PARQUET_FILENAME).exists()
    assert (interim / run.REPORT_FILENAME).exists()


def test_parquet_row_count_matches_fixture(isolated_pipeline):
    run.main([])
    df = pl.read_parquet(isolated_pipeline / "interim" / run.PARQUET_FILENAME)
    assert df.height == read_raw(FIXTURE_PATH).height


def test_parquet_has_flag_and_raw_columns(isolated_pipeline):
    run.main([])
    df = pl.read_parquet(isolated_pipeline / "interim" / run.PARQUET_FILENAME)
    for column in FLAG_COLUMNS:
        assert column in df.columns
    assert any(c.endswith("_raw") for c in df.columns), "normalize.apply should add *_raw columns"


def test_report_row_count_matches_parquet(isolated_pipeline):
    run.main([])
    report = json.loads((isolated_pipeline / "interim" / run.REPORT_FILENAME).read_text())
    df = pl.read_parquet(isolated_pipeline / "interim" / run.PARQUET_FILENAME)
    assert report["rows"] == df.height


def test_report_carries_snapshot_and_versions(isolated_pipeline):
    run.main([])
    report = json.loads((isolated_pipeline / "interim" / run.REPORT_FILENAME).read_text())
    assert report["snapshot"]["filename"] == RAW_FILENAME
    assert report["schema_version"]
    assert report["crosswalk_version"]
    assert "flag_counts" in report
    assert "enum_counts" in report


def test_report_carries_normalize_block(isolated_pipeline):
    # The 16 crosswalk guesses (OQ-1.2 "uncertain") are a ruling the owner still has to
    # make -- their per-label row counts have to live in the artifact of record, not
    # just in unknown_labels.
    run.main([])
    report = json.loads((isolated_pipeline / "interim" / run.REPORT_FILENAME).read_text())
    assert "normalize" in report
    assert "mapped" in report["normalize"]
    assert "uncertain_seen" in report["normalize"]


def test_second_run_is_byte_identical(isolated_pipeline):
    run.main([])
    parquet_path = isolated_pipeline / "interim" / run.PARQUET_FILENAME
    first_hash = hashlib.sha256(parquet_path.read_bytes()).hexdigest()

    run.main([])
    second_hash = hashlib.sha256(parquet_path.read_bytes()).hexdigest()
    assert first_hash == second_hash


def test_broken_header_returns_one(tmp_path, monkeypatch):
    monkeypatch.setenv("REPEAL_DATA_DIR", str(tmp_path))
    columns = list(SOURCE_COLUMNS)
    columns[0], columns[1] = columns[1], columns[0]  # reordered -> contract violation
    broken = tmp_path / "broken_source.csv"
    broken.write_text(",".join(columns) + "\n", encoding="utf-8")

    monkeypatch.setattr(download, "fetch", _adopt(broken))
    assert run.main([]) == 1
