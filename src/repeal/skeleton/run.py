"""Walking-skeleton entry point (OQ-1.5): cards.jsonl -> DuckDB slice -> temporal
split -> logreg -> one query case -> static demo page, behind one command.

    uv run python -m repeal.skeleton.run [--case <reference_id> | --row-id <int>] [--k 5]

Orchestration only -- `warehouse` owns the DB, `baseline` owns the model, `page`
owns the HTML. Every module here is expected to be superseded phase by phase; the
point right now is finding what breaks at the seams (OQ.md, Phase 1.5).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import polars as pl

from repeal.config import get_settings
from repeal.ingest.run import PARQUET_FILENAME
from repeal.skeleton import cards, page, warehouse
from repeal.skeleton.baseline import Baseline, Split, evaluate, temporal_split

CARDS_FILENAME = "cards.jsonl"
DEMO_FILENAME = "demo.html"
_INGEST_REPORT_FILENAME = "ingest_report.json"


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m repeal.skeleton.run")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--case", default=None, help="reference_id of the case to demo")
    group.add_argument("--row-id", type=int, default=None, help="row_id of the case to demo")
    parser.add_argument("--k", type=int, default=5, help="drivers and precedents to show")
    return parser


def _extraction_instructions() -> str:
    return (
        "no case cards yet -- run the extraction first:\n"
        "  1. make skeleton-sample\n"
        "  2. extract per src/repeal/skeleton/prompts/case_card_v0.md into cards_part_*.jsonl\n"
        "  3. uv run python -m repeal.skeleton.cards --merge\n"
    )


def _default_sha(interim_dir: Path) -> str | None:
    """`snapshot.sha256` from `ingest_report.json`, when the ingest ran normally
    (mirrors `repeal.ingest.profile._default_sha`)."""
    report_path = interim_dir / _INGEST_REPORT_FILENAME
    if not report_path.is_file():
        return None
    report = json.loads(report_path.read_text())
    return report.get("snapshot", {}).get("sha256")


def _resolve_row_id(
    slice_df: pl.DataFrame, split: Split, args: argparse.Namespace
) -> int | None:
    """Resolve `--case` / `--row-id` / the default to a `row_id` present in
    `slice_df`. Default is the first row (by `row_id`) of the test split.

    Prints a message and returns `None` (the caller exits 2) on no match, or on an
    ambiguous `--case` -- a duplicate `reference_id` prints every matching `row_id`
    rather than guessing which one was meant.
    """
    if args.case is not None:
        matches = slice_df.filter(pl.col("reference_id") == args.case)
        if matches.height == 0:
            print(f"no case with reference_id={args.case!r} in the slice", file=sys.stderr)
            return None
        if matches.height > 1:
            row_ids = sorted(matches.get_column("row_id").to_list())
            print(
                f"reference_id={args.case!r} is ambiguous: row_id={row_ids} "
                "-- pass --row-id to disambiguate",
                file=sys.stderr,
            )
            return None
        return int(matches.get_column("row_id")[0])
    if args.row_id is not None:
        matches = slice_df.filter(pl.col("row_id") == args.row_id)
        if matches.height == 0:
            print(f"no case with row_id={args.row_id} in the slice", file=sys.stderr)
            return None
        return int(args.row_id)
    return int(split.test.sort("row_id").get_column("row_id")[0])


def _print_summary(
    case_row: dict,
    proba: float,
    drivers: list[tuple[str, float]],
    precedents: pl.DataFrame,
    metrics: dict,
    demo_path: Path,
) -> None:
    print(f"case: {case_row.get('reference_id')} (row_id={case_row.get('row_id')})")
    print(f"external-review overturn likelihood: {proba * 100:.1f}%")
    print("top drivers:")
    for name, weight in drivers:
        print(f"  {name}: {weight:+.3f}")
    print("precedents:")
    for row in precedents.iter_rows(named=True):
        print(f"  {row['reference_id']} ({row['report_year']})")
    print(metrics["banner"])
    auc = metrics["auc"]
    print(f"AUC: {auc:.3f}" if auc is not None else "AUC: n/a (one-class test split)")
    print(page.FOOTER)
    print(f"wrote {demo_path}")


def main(argv: list[str] | None = None) -> int:
    """Run the walking-skeleton demo once. Returns 0 on success; 2 if `cards.jsonl`
    is missing, the query case isn't in the slice, or `--case` is ambiguous."""
    args = _build_arg_parser().parse_args(argv)
    settings = get_settings()
    skeleton_dir = settings.interim_dir / "skeleton"
    cards_path = skeleton_dir / CARDS_FILENAME
    demo_path = skeleton_dir / DEMO_FILENAME

    if not cards_path.is_file():
        print(_extraction_instructions(), file=sys.stderr)
        return 2

    loaded_cards = cards.load_cards(cards_path)
    prompt_hash = loaded_cards[0].prompt_hash if loaded_cards else None

    skeleton_dir.mkdir(parents=True, exist_ok=True)
    db_path = skeleton_dir / warehouse.DB_FILENAME
    parquet_path = settings.interim_dir / PARQUET_FILENAME

    con = warehouse.build(db_path, parquet_path, cards_path)
    try:
        slice_df = warehouse.slice_frame(con)
        split = temporal_split(slice_df)
        model = Baseline().fit(split.train)
        metrics = evaluate(model, split.test)

        row_id = _resolve_row_id(slice_df, split, args)
        if row_id is None:
            return 2

        query_df = slice_df.filter(pl.col("row_id") == row_id)
        case_row = query_df.row(0, named=True)
        proba = float(model.predict_proba(query_df)[0])
        drivers = model.drivers(k=args.k)
        precedents = warehouse.precedents(con, row_id, k=args.k)
    finally:
        warehouse.close(con)

    meta = {
        "sha": _default_sha(settings.interim_dir),
        "prompt_hash": prompt_hash,
        "n_train": metrics["n_train"],
        "n_test": metrics["n_test"],
        "auc": metrics["auc"],
    }
    html = page.render(case_row, proba, drivers, precedents, meta)
    page.write(demo_path, html)
    _print_summary(case_row, proba, drivers, precedents, metrics, demo_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
