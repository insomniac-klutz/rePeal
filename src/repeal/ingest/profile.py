"""Pure EDA statistics over the ingested IMR frame, plus a markdown renderer.

Every function is `pl.DataFrame -> pl.DataFrame` (a table) unless its
docstring says otherwise. No plotting, no notebook (OQ-1.7): `compute()`
bundles every table into a `ProfileStats`, `render()` turns that into the
markdown written to `docs/evals/eda.md`. CLI:

    python -m repeal.ingest.profile --parquet <path> --out <path> [--sha <sha>]
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import polars as pl

# --------------------------------------------------------------------------
# Per-year / per-category tables
# --------------------------------------------------------------------------


def rows_and_label_rate_by_year(df: pl.DataFrame) -> pl.DataFrame:
    """Row count, overturned count, and overturn rate per `report_year`.

    `overturned` in the OUTPUT is the per-year count of `True` labels (not
    the source boolean column); `overturn_rate` is that count over `rows`,
    rounded to 3 dp.
    """
    return (
        df.group_by("report_year")
        .agg(
            pl.len().alias("rows"),
            pl.col("overturned").sum().alias("overturned"),
            pl.col("overturned").mean().round(3).alias("overturn_rate"),
        )
        .sort("report_year")
        .select(["report_year", "rows", "overturned", "overturn_rate"])
    )


def label_rate_by_year_and_type(df: pl.DataFrame) -> pl.DataFrame:
    """`rows_and_label_rate_by_year`, split additionally by `case_type`."""
    return (
        df.group_by(["report_year", "case_type"])
        .agg(
            pl.len().alias("rows"),
            pl.col("overturned").sum().alias("overturned"),
            pl.col("overturned").mean().round(3).alias("overturn_rate"),
        )
        .sort(["report_year", "case_type"])
        .select(["report_year", "case_type", "rows", "overturned", "overturn_rate"])
    )


def vocabulary_by_era(df: pl.DataFrame, col: str = "diagnosis_category") -> pl.DataFrame:
    """Per-year distinct-label count in `col`, and which labels are new.

    "New" means never seen in any strictly earlier `report_year` in `df`.
    This is the generic tool that surfaces vocabulary breaks like the 2026
    taxonomy migration (OQ-1.0 Hazard #1): a year whose `new_labels` is large
    relative to `n_distinct` introduced a largely-disjoint vocabulary rather
    than gradual drift. Null labels are ignored. Run it on a raw `*_raw`
    category column to see the break, and on the canonical column to confirm
    `normalize.py`'s crosswalk closed it.
    """
    per_year = (
        df.filter(pl.col(col).is_not_null())
        .group_by("report_year")
        .agg(pl.col(col).unique().alias("_labels"))
        .sort("report_year")
    )
    seen: set[str] = set()
    rows = []
    for year, labels in per_year.iter_rows():
        label_set = set(labels)
        new_labels = sorted(label_set - seen)
        rows.append({"report_year": year, "n_distinct": len(label_set), "new_labels": new_labels})
        seen |= label_set
    return pl.DataFrame(
        rows,
        schema={
            "report_year": per_year.schema["report_year"],
            "n_distinct": pl.Int64,
            "new_labels": pl.List(pl.Utf8),
        },
    )


def category_top_n(df: pl.DataFrame, col: str, n: int = 15) -> pl.DataFrame:
    """Top-`n` labels in `col` by row count, with share and overturn rate.

    Rows where `col` is null are excluded from both the ranking and the
    `share` denominator — `share` is "share of labeled rows", not of all
    rows. Ties in `rows` break alphabetically on the label for determinism.
    """
    labeled = df.filter(pl.col(col).is_not_null())
    denom = labeled.height or 1
    return (
        labeled.group_by(col)
        .agg(
            pl.len().alias("rows"),
            pl.col("overturned").mean().round(3).alias("overturn_rate"),
        )
        .with_columns((pl.col("rows") / denom).round(3).alias("share"))
        .sort(["rows", col], descending=[True, False])
        .head(n)
        .rename({col: "label"})
        .select(["label", "rows", "share", "overturn_rate"])
    )


def findings_length_percentiles_by_year(df: pl.DataFrame) -> pl.DataFrame:
    """Per-year percentiles of `findings` character length, plus a short-count.

    p1/p5/p25/p50/p75/p95/p99 use linear interpolation (rounded to 1 dp);
    `max` and `n_under_100` (count of findings under 100 chars) are exact.
    """
    percentiles = (1, 5, 25, 50, 75, 95, 99)
    quantile_exprs = [
        pl.col("_len").quantile(p / 100, interpolation="linear").round(1).alias(f"p{p}")
        for p in percentiles
    ]
    return (
        df.with_columns(pl.col("findings").str.len_chars().alias("_len"))
        .group_by("report_year")
        .agg(
            *quantile_exprs,
            pl.col("_len").max().alias("max"),
            (pl.col("_len") < 100).sum().alias("n_under_100"),
        )
        .sort("report_year")
    )


def duplicate_pair_comparison(df: pl.DataFrame) -> pl.DataFrame:
    """Summarize `reference_id` groups that have more than one row.

    One-row table: how many such groups exist, how many total rows they
    span, and — within those groups — how many have identical vs divergent
    `findings` text, and identical vs divergent `overturned` labels. A group
    is "identical" on a field when every row in it shares one value.
    """
    groups = (
        df.group_by("reference_id")
        .agg(
            pl.len().alias("n"),
            pl.col("findings").n_unique().alias("_findings_nunique"),
            pl.col("overturned").n_unique().alias("_overturned_nunique"),
        )
        .filter(pl.col("n") > 1)
    )
    row = {
        "reference_id_groups": groups.height,
        "rows_in_groups": int(groups["n"].sum()) if groups.height else 0,
        "findings_identical_groups": groups.filter(pl.col("_findings_nunique") == 1).height,
        "findings_divergent_groups": groups.filter(pl.col("_findings_nunique") > 1).height,
        "overturned_identical_groups": groups.filter(pl.col("_overturned_nunique") == 1).height,
        "overturned_divergent_groups": groups.filter(pl.col("_overturned_nunique") > 1).height,
    }
    return pl.DataFrame([row])


def null_cohorts(df: pl.DataFrame) -> pl.DataFrame:
    """Null counts per column, each with its own `report_year` span, plus two
    named demographic cohorts.

    One row per column in `df` (`null_count`, `null_share`, and — whenever
    `report_year` is present — the min/max `report_year` among that column's
    null rows, so "these nulls are all early years" vs. "these are a
    different, later cohort" is visible without hardcoding either claim).
    Then two synthetic rows: `_cohort_age_gender_all_null` (`age_range` AND
    `patient_gender` both null — the real 2001-2003 legacy-demographic
    cohort) and `_cohort_age_gender_days_all_null` (those two AND
    `days_to_review` all null together — OQ-1.0's ORIGINAL recon hypothesis
    for that cohort). Keep both: the gap between them — the three-way row
    near zero while the two-way row isn't — is the correction, in the table
    rather than just in prose (`days_to_review` nulls are a separate,
    non-overlapping cohort from 2007 on).
    """
    total = df.height
    has_years = "report_year" in df.columns
    rows = []
    for col in df.columns:
        null_count = df[col].null_count()
        year_min = year_max = None
        if has_years and null_count:
            null_rows = df.filter(pl.col(col).is_null())
            year_min = null_rows["report_year"].min()
            year_max = null_rows["report_year"].max()
        rows.append(
            {
                "column": col,
                "null_count": null_count,
                "null_share": round(null_count / total, 3) if total else None,
                "cohort_year_min": year_min,
                "cohort_year_max": year_max,
            }
        )

    def cohort_row(name: str, cols: tuple[str, ...]) -> dict:
        present = [c for c in cols if c in df.columns]
        if len(present) != len(cols):
            cohort = df.filter(pl.lit(False))
        else:
            cohort = df.filter(pl.all_horizontal([pl.col(c).is_null() for c in present]))
        size = cohort.height
        have_years = bool(size) and has_years
        return {
            "column": name,
            "null_count": size,
            "null_share": round(size / total, 3) if total else None,
            "cohort_year_min": cohort["report_year"].min() if have_years else None,
            "cohort_year_max": cohort["report_year"].max() if have_years else None,
        }

    rows.append(cohort_row("_cohort_age_gender_all_null", ("age_range", "patient_gender")))
    rows.append(
        cohort_row(
            "_cohort_age_gender_days_all_null",
            ("age_range", "patient_gender", "days_to_review"),
        )
    )
    return pl.DataFrame(rows)


def _slug_marker(marker: str) -> str:
    """`"Final Result:"` -> `"marker_final_result"` (prefixed to avoid colliding
    with a real column name, e.g. `findings` itself)."""
    cleaned = re.sub(r"[^0-9a-zA-Z]+", "_", marker).strip("_").lower()
    return f"marker_{cleaned}"


def section_marker_prevalence_by_year(
    df: pl.DataFrame,
    markers: tuple[str, ...] = ("Findings:", "Final Result:", "Credentials/Qualifications:"),
) -> pl.DataFrame:
    """Per-year share of rows whose `findings` contains each marker (literal substring)."""
    exprs = [
        pl.col("findings")
        .str.contains(marker, literal=True)
        .mean()
        .round(3)
        .alias(_slug_marker(marker))
        for marker in markers
    ]
    return df.group_by("report_year").agg(*exprs).sort("report_year")


def flag_counts(df: pl.DataFrame) -> pl.DataFrame:
    """Counts and shares of every `flag_*` / `has_section_markers` column present."""
    cols = [c for c in df.columns if c.startswith("flag_") or c == "has_section_markers"]
    total = df.height
    rows = [
        {
            "flag": col,
            "count": int(df[col].sum()),
            "share": round(int(df[col].sum()) / total, 3) if total else None,
        }
        for col in cols
    ]
    return pl.DataFrame(rows, schema={"flag": pl.Utf8, "count": pl.Int64, "share": pl.Float64})


def cutoff_candidates(
    df: pl.DataFrame,
    years: Iterable[int] = range(2019, 2025),
    exclude_years: tuple[int, ...] = (2001, 2026),
    modern_from: int = 2020,
    partial_years: tuple[int, ...] = (2026,),
    vocab_col: str = "diagnosis_category",
) -> pl.DataFrame:
    """Temporal-cutoff candidate table — the evidence for OQ-1.5's year ruling.

    For each candidate cutoff year `y` in `years`: train = rows with
    `report_year <= y`, test = `report_year > y`, both excluding
    `exclude_years` (default: 2001 near-empty, 2026 partial + mid-taxonomy-
    migration). `modern_from` is OQ-1.5's "all-modern test era" threshold —
    every distinct test year must be `>= modern_from`. `partial_years` marks
    calendar years known to be incomplete in the pinned snapshot (2026:
    publish cutoff 2026-06-01) and is excluded from `test_full_years`.
    `test_vocab_pure` checks whether any `vocab_col` label that appears ONLY
    in report_year 2026 (across the whole corpus, not just the candidate
    window) leaks into the test window — trivially True whenever 2026 is
    excluded from `exclude_years` (the default), and vacuously True if
    `vocab_col` isn't in `df`.

    `meets_criteria` is exactly OQ-1.5's three ruled conditions: 0.15 <=
    test_share <= 0.25, `test_full_years >= 2`, and every test year
    `>= modern_from`. `test_vocab_pure` is reported as evidence, not folded
    into the gate — the ruling only named three conditions.
    """
    excluded = set(exclude_years)
    usable = df.filter(~pl.col("report_year").is_in(list(excluded)))

    labels_2026_only: set[str] = set()
    if vocab_col in df.columns:
        labels_2026 = set(
            df.filter(pl.col("report_year") == 2026)[vocab_col].drop_nulls().unique().to_list()
        )
        labels_other = set(
            df.filter(pl.col("report_year") != 2026)[vocab_col].drop_nulls().unique().to_list()
        )
        labels_2026_only = labels_2026 - labels_other

    rows = []
    for y in years:
        train = usable.filter(pl.col("report_year") <= y)
        test = usable.filter(pl.col("report_year") > y)
        train_n, test_n = train.height, test.height
        total = train_n + test_n
        test_years = sorted(test["report_year"].unique().to_list())
        test_full_years = sum(1 for yr in test_years if yr not in partial_years)

        if labels_2026_only:
            vocab_pure = test.filter(pl.col(vocab_col).is_in(list(labels_2026_only))).height == 0
        else:
            vocab_pure = True

        meets_criteria = (
            total > 0
            and 0.15 <= (test_n / total) <= 0.25
            and test_full_years >= 2
            and all(yr >= modern_from for yr in test_years)
        )
        rows.append(
            {
                "cutoff_year": y,
                "train_rows": train_n,
                "test_rows": test_n,
                "test_share": round(test_n / total, 3) if total else None,
                "train_overturn_rate": round(train["overturned"].mean(), 3) if train_n else None,
                "test_overturn_rate": round(test["overturned"].mean(), 3) if test_n else None,
                "test_years": test_years,
                "test_full_years": test_full_years,
                "test_vocab_pure": vocab_pure,
                "meets_criteria": meets_criteria,
            }
        )
    return pl.DataFrame(rows)


# --------------------------------------------------------------------------
# Markdown rendering
# --------------------------------------------------------------------------


def to_markdown(df: pl.DataFrame, floats: int = 3) -> str:
    """Render a polars DataFrame as a GitHub-flavored markdown table.

    Floats round to `floats` decimals; lists comma-join; bools render as
    `true`/`false`; nulls render as an empty cell; a literal `|` in a
    stringified cell is escaped so it can't break the table.
    """
    header = "| " + " | ".join(df.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(df.columns)) + " |"
    lines = [header, sep]
    for record in df.iter_rows(named=True):
        cells = [_format_cell(record[col], floats) for col in df.columns]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _format_cell(value: object, floats: int) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{round(value, floats):.{floats}f}"
    if isinstance(value, list):
        return ", ".join(_format_cell(v, floats) for v in value)
    return str(value).replace("|", "\\|")


@dataclass
class ProfileStats:
    """Every computed EDA table, plus corpus-level meta (rows, year span, sha)."""

    tables: dict[str, pl.DataFrame]
    meta: dict[str, object]


def compute(df: pl.DataFrame, sha: str | None = None) -> ProfileStats:
    """Compute every EDA table from the post-ingest frame.

    Expects the full `data/interim/imr_cases.parquet` schema
    (`schema.validate` + `normalize.apply` + `quality.flag` output);
    category/flag/findings-specific tables are skipped when their columns
    aren't present, so narrower frames (e.g. in tests) still work.
    """
    tables: dict[str, pl.DataFrame] = {
        "Rows & overturn rate by year": rows_and_label_rate_by_year(df),
        "Overturn rate by year and case type": label_rate_by_year_and_type(df),
    }
    for label, col in (
        ("diagnosis category", "diagnosis_category"),
        ("treatment category", "treatment_category"),
    ):
        if col in df.columns:
            tables[f"{label.capitalize()} vocabulary by era"] = vocabulary_by_era(df, col=col)
    for label, col in (
        ("diagnosis category", "diagnosis_category"),
        ("diagnosis subcategory", "diagnosis_subcategory"),
        ("treatment category", "treatment_category"),
        ("treatment subcategory", "treatment_subcategory"),
    ):
        if col in df.columns:
            tables[f"Top {label} labels"] = category_top_n(df, col)
    if "findings" in df.columns:
        tables["Findings length percentiles by year"] = findings_length_percentiles_by_year(df)
        tables["Section-marker prevalence by year"] = section_marker_prevalence_by_year(df)
    if "reference_id" in df.columns:
        tables["Duplicate reference_id pairs"] = duplicate_pair_comparison(df)
    tables["Null cohorts"] = null_cohorts(df)
    flags = flag_counts(df)
    if flags.height:
        tables["Quality-flag counts"] = flags
    tables["Temporal-cutoff candidates"] = cutoff_candidates(df)

    meta: dict[str, object] = {
        "rows": df.height,
        "year_min": df["report_year"].min() if "report_year" in df.columns else None,
        "year_max": df["report_year"].max() if "report_year" in df.columns else None,
        "sha": sha,
    }
    return ProfileStats(tables=tables, meta=meta)


def render(stats: ProfileStats) -> str:
    """Render `ProfileStats` as markdown: title, meta line, one `##` section per table."""
    meta = stats.meta
    meta_parts = []
    if meta.get("rows") is not None:
        meta_parts.append(f"**Rows:** {meta['rows']:,}")
    if meta.get("year_min") is not None and meta.get("year_max") is not None:
        meta_parts.append(f"**Years:** {meta['year_min']}–{meta['year_max']}")
    if meta.get("sha"):
        meta_parts.append(f"**Snapshot sha256:** {meta['sha']}")

    lines = ["# EDA — CA DMHC Independent Medical Review (IMR) Determinations", ""]
    if meta_parts:
        lines.append("  ·  ".join(meta_parts))
        lines.append("")
    for title, table in stats.tables.items():
        lines.append(f"## {title}")
        lines.append("")
        lines.append(to_markdown(table))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _default_sha(parquet_path: Path) -> str | None:
    """`snapshot.sha256` from `ingest_report.json` beside `parquet_path`.

    None if there's no report there — `make eda` never passes `--sha`, so this
    is what lets its output carry the pinned snapshot's identity anyway.
    """
    report_path = parquet_path.parent / "ingest_report.json"
    if not report_path.is_file():
        return None
    report = json.loads(report_path.read_text())
    return report.get("snapshot", {}).get("sha256")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render the repeal EDA report from the ingested parquet."
    )
    parser.add_argument("--parquet", required=True, type=Path, help="path to imr_cases.parquet")
    parser.add_argument("--out", required=True, type=Path, help="path to write eda.md")
    parser.add_argument(
        "--sha",
        default=None,
        help="pinned snapshot sha256, for the meta line; defaults to "
        "ingest_report.json's snapshot.sha256 if that file sits beside --parquet",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    df = pl.read_parquet(args.parquet)
    sha = args.sha if args.sha is not None else _default_sha(args.parquet)
    stats = compute(df, sha=sha)
    text = render(stats)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text)


if __name__ == "__main__":
    main()
