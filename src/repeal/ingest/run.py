"""Ingest pipeline entry point: download -> validate -> normalize -> flag -> parquet.

Orchestrates the whole Phase 1 data flow (OQ-1.0) and is `make ingest`'s target.
Fails loudly and exits nonzero on a schema contract violation; everything else
(normalize, quality) never drops rows, so a clean run always parquets every
source row. Re-running against the same pinned snapshot is byte-identical:
`row_id` fixes source order, and the parquet is written with a fixed codec.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import polars as pl

from repeal.config import get_settings
from repeal.ingest import download, normalize, quality
from repeal.ingest.schema import ENUMS, SCHEMA_VERSION, SchemaContractError, read_raw, validate

PARQUET_FILENAME = "imr_cases.parquet"
REPORT_FILENAME = "ingest_report.json"
_NULL_KEY = "<null>"


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m repeal.ingest.run")
    parser.add_argument(
        "--refresh", action="store_true", help="force a fresh download to a new dated file"
    )
    return parser


def _enum_counts(df: pl.DataFrame) -> dict[str, dict[str, int]]:
    """Value counts for every hard-enforced enum column, null bucketed as `<null>`."""
    counts: dict[str, dict[str, int]] = {}
    for column in ENUMS:
        counts[column] = {
            (_NULL_KEY if row[column] is None else row[column]): row["count"]
            for row in df.get_column(column).value_counts().to_dicts()
        }
    return counts


def _build_report(
    df: pl.DataFrame,
    entry: download.ManifestEntry,
    norm_report: normalize.NormalizeReport,
    q_report: quality.QualityReport,
) -> dict[str, Any]:
    return {
        "snapshot": {
            "filename": entry.filename,
            "sha256": entry.sha256,
            "size_bytes": entry.size_bytes,
            "upstream_last_modified": entry.upstream_last_modified,
            "retrieved_at": entry.retrieved_at,
        },
        "schema_version": SCHEMA_VERSION,
        "crosswalk_version": normalize.CROSSWALK_VERSION,
        "rows": df.height,
        "enum_counts": _enum_counts(df),
        "unknown_labels": norm_report.unknown_labels,
        "normalize": {
            "mapped": norm_report.mapped,
            "uncertain_seen": norm_report.uncertain_seen,
        },
        "flag_counts": q_report.counts,
        "thresholds": q_report.thresholds.as_dict(),
    }


def _print_summary(df: pl.DataFrame, report: dict[str, Any], parquet_path: Path) -> None:
    overturned_rate = df.get_column("overturned").mean() or 0.0
    snapshot = report["snapshot"]
    year_min = df.get_column("report_year").min()
    year_max = df.get_column("report_year").max()
    print(f"ingest: {report['rows']} rows -> {parquet_path}")
    print(f"snapshot: {snapshot['filename']} sha256={snapshot['sha256'][:12]}…")
    print(
        f"schema_version={report['schema_version']} "
        f"crosswalk_version={report['crosswalk_version']}"
    )
    print(f"report_year: {year_min}-{year_max}")
    print(f"overturned rate: {overturned_rate:.1%}")
    unknown_total = sum(len(labels) for labels in report["unknown_labels"].values())
    print(f"unknown category labels: {unknown_total} distinct")
    for flag_name, count in report["flag_counts"].items():
        print(f"  {flag_name}: {count}")


def main(argv: list[str] | None = None) -> int:
    """Run the full ingest pipeline once; return 0 on success, 1 on a contract violation."""
    args = _build_arg_parser().parse_args(argv)
    settings = get_settings()

    entry = download.fetch(settings.raw_dir, refresh=args.refresh)
    raw = read_raw(settings.raw_dir / entry.filename)
    try:
        df = validate(raw)
    except SchemaContractError as exc:
        print(f"schema contract violated:\n{exc}", file=sys.stderr)
        return 1

    df, norm_report = normalize.apply(df)
    df, q_report = quality.flag(df)

    settings.interim_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = settings.interim_dir / PARQUET_FILENAME
    df.write_parquet(parquet_path, compression="zstd", compression_level=3)

    report = _build_report(df, entry, norm_report, q_report)
    report_path = settings.interim_dir / REPORT_FILENAME
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    _print_summary(df, report, parquet_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
