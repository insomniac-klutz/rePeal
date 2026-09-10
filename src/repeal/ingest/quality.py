"""Row-level quality flags for the IMR ingest pipeline (OQ-1.11).

`flag()` adds eight Bool columns to the frame and never drops or reorders
rows -- exclusion is a downstream consumer's explicit, reported decision
(OQ-1.0 invariants: "quality issues -> flags", never a silent drop).
Thresholds are parameters, not hardcoded constants: the EDA (phantom-profiler)
pins the real values from corpus percentiles and the data card records them.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

FLAG_COLUMNS: tuple[str, ...] = (
    "flag_findings_short",
    "flag_findings_truncated",
    "flag_encoding_artifact",
    "flag_duplicate_reference_id",
    "flag_duplicate_findings",
    "flag_legacy_cohort",
    "flag_id_prefix_mismatch",
    "has_section_markers",
)

_TERMINAL_PUNCTUATION: tuple[str, ...] = (".", "!", "?", '"', ")", "]")

# ReferenceID letter prefix -> case_type, per the real corpus (cipher-contract verified
# all 42,749 rows: prefixes are exactly {MN, EI, UR}, always consistent with Type and
# ReportYear). The OQ-1.0 spawn brief said "UC" -- that was wrong; it's "UR".
_PREFIX_TO_CASE_TYPE: dict[str, str] = {
    "MN": "Medical Necessity",
    "EI": "Experimental/Investigational",
    "UR": "Urgent Care",
}

_REFERENCE_ID_PATTERN = r"^(MN|EI|UR)(\d{2})-"


@dataclass(frozen=True)
class Thresholds:
    """Tunable knobs for the quality flags.

    Defaults are placeholders -- the EDA pins the real values from corpus
    percentiles and the data card records them (OQ-1.11).
    """

    short_findings_chars: int = 100
    truncation_min_chars: int = 200
    section_markers: tuple[str, ...] = (
        "Findings:",
        "Final Result:",
        "Credentials/Qualifications:",
    )
    mojibake_patterns: tuple[str, ...] = ("â€", "Ã", "�")

    def as_dict(self) -> dict[str, object]:
        """JSON-friendly form for `ingest_report.json`."""
        return {
            "short_findings_chars": self.short_findings_chars,
            "truncation_min_chars": self.truncation_min_chars,
            "section_markers": list(self.section_markers),
            "mojibake_patterns": list(self.mojibake_patterns),
        }


@dataclass
class QualityReport:
    """Per-flag row counts plus the thresholds/row count that produced them."""

    counts: dict[str, int]
    thresholds: Thresholds
    rows: int


def _any_contains(col: str, patterns: tuple[str, ...]) -> pl.Expr:
    """True where `col` contains any literal substring in `patterns`.

    `lit(False)` for an empty tuple -- there is no "contains nothing" row.
    """
    if not patterns:
        return pl.lit(False)
    return pl.any_horizontal(
        [pl.col(col).str.contains(pattern, literal=True) for pattern in patterns]
    )


def _expected_letters_expr() -> pl.Expr:
    """`case_type` mapped back to its expected ReferenceID letter prefix."""
    expr = pl.lit(None, dtype=pl.Utf8)
    for prefix, case_type in _PREFIX_TO_CASE_TYPE.items():
        expr = pl.when(pl.col("case_type") == case_type).then(pl.lit(prefix)).otherwise(expr)
    return expr


def flag(
    df: pl.DataFrame, thresholds: Thresholds | None = None
) -> tuple[pl.DataFrame, QualityReport]:
    """Add the eight quality-flag Bool columns.

    Pure `with_columns` expressions throughout -- row count and order are
    always preserved, and nothing here ever filters the frame.
    """
    thresholds = thresholds or Thresholds()

    findings_len = pl.col("findings").str.len_chars()
    findings_stripped = pl.col("findings").str.strip_chars()
    ends_terminal = pl.any_horizontal(
        [findings_stripped.str.ends_with(p) for p in _TERMINAL_PUNCTUATION]
    )

    ref_id_letters = pl.col("reference_id").str.extract(_REFERENCE_ID_PATTERN, 1)
    ref_id_year_digits = pl.col("reference_id").str.extract(_REFERENCE_ID_PATTERN, 2)
    ref_id_matches_pattern = pl.col("reference_id").str.contains(_REFERENCE_ID_PATTERN)

    year_mismatch = ref_id_year_digits.cast(pl.Int64, strict=False) != (
        pl.col("report_year").cast(pl.Int64) % 100
    )
    letters_mismatch = ref_id_letters != _expected_letters_expr()
    # Polars boolean `|` is Kleene logic, so `~matches | ...` is True whenever
    # the pattern failed to match, regardless of the then-null letter/year
    # comparisons. fill_null is belt-and-suspenders: this column is never null.
    prefix_mismatch = (~ref_id_matches_pattern | letters_mismatch | year_mismatch).fill_null(
        True
    )

    df = df.with_columns(
        (findings_len < thresholds.short_findings_chars).alias("flag_findings_short"),
        (
            (findings_len >= thresholds.truncation_min_chars) & ~ends_terminal
        ).alias("flag_findings_truncated"),
        _any_contains("findings", thresholds.mojibake_patterns).alias("flag_encoding_artifact"),
        (pl.len().over("reference_id") > 1).alias("flag_duplicate_reference_id"),
        (pl.len().over("findings") > 1).alias("flag_duplicate_findings"),
        # age_range + patient_gender only. The real 691-row null cohort (2001-2003)
        # and the 691 rows missing days_to_review (2007+) are DISJOINT sets that
        # happen to share a count -- OQ-1.0's recon read that coincidence as one
        # cohort, and a three-condition AND here fired zero times on the real
        # 42,749-row corpus as a result. days_to_review is deliberately excluded.
        (pl.col("age_range").is_null() & pl.col("patient_gender").is_null()).alias(
            "flag_legacy_cohort"
        ),
        prefix_mismatch.alias("flag_id_prefix_mismatch"),
        _any_contains("findings", thresholds.section_markers).alias("has_section_markers"),
    )

    counts = {col: int(df[col].sum()) for col in FLAG_COLUMNS}
    report = QualityReport(counts=counts, thresholds=thresholds, rows=df.height)
    return df, report
