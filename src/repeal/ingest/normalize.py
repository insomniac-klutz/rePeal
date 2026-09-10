"""Category crosswalk: legacy DMHC vocabulary -> the 2026 vocabulary (OQ-1.2).

Ruled 2026-09-09: canonicalize to the NEW (ICD-10-chapter-style) vocabulary,
category level only. Subcategories get mechanical cleanup only (trim/collapse
whitespace, case untouched) -- no semantic crosswalk until something downstream
demonstrably needs it. Raw values are always preserved in `*_raw` columns.
Unknown category labels pass through untouched and are counted, never errored
-- a new label must never brick ingest (OQ-1.0 Hazards #1).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl
import yaml

CROSSWALK_VERSION = "1"
CROSSWALK_PATH = Path(__file__).parent / "resources" / "category_crosswalk_v1.yaml"

_CATEGORY_COLUMNS: tuple[str, ...] = (
    "diagnosis_category",
    "treatment_category",
)
_SUBCATEGORY_COLUMNS: tuple[str, ...] = (
    "diagnosis_subcategory",
    "treatment_subcategory",
)
_ALL_MAPPED_COLUMNS: tuple[str, ...] = _CATEGORY_COLUMNS + _SUBCATEGORY_COLUMNS


@dataclass(frozen=True)
class Crosswalk:
    """A loaded, invariant-checked `category_crosswalk_v1.yaml`."""

    version: int
    canonical_scheme: str
    diagnosis_canonical: frozenset[str]
    diagnosis_aliases: dict[str, str]
    treatment_canonical: frozenset[str]
    treatment_aliases: dict[str, str]
    # {"diagnosis": {label: {"to": ..., "why": ...}}, "treatment": {...}} -- best
    # guesses, never applied. Kept for the report and the lead's ruling.
    uncertain: dict[str, dict[str, dict[str, str]]]


@dataclass
class NormalizeReport:
    """What `apply()` did, for `ingest_report.json` and the EDA."""

    crosswalk_version: str
    mapped: dict[str, int]
    unknown_labels: dict[str, dict[str, int]]
    uncertain_seen: dict[str, dict[str, int]]


def load_crosswalk(path: Path | str | None = None) -> Crosswalk:
    """Load and invariant-check the crosswalk YAML.

    Raises `ValueError` if any label is both canonical and an alias key, or if
    an alias targets a label that isn't canonical.
    """
    path = Path(path) if path is not None else CROSSWALK_PATH
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    diagnosis, treatment = raw["diagnosis"], raw["treatment"]
    crosswalk = Crosswalk(
        version=raw["version"],
        canonical_scheme=raw["canonical_scheme"],
        diagnosis_canonical=frozenset(diagnosis["canonical"]),
        diagnosis_aliases=dict(diagnosis.get("aliases") or {}),
        treatment_canonical=frozenset(treatment["canonical"]),
        treatment_aliases=dict(treatment.get("aliases") or {}),
        uncertain={
            "diagnosis": dict(diagnosis.get("uncertain") or {}),
            "treatment": dict(treatment.get("uncertain") or {}),
        },
    )
    _validate_crosswalk(crosswalk)
    return crosswalk


def _validate_crosswalk(crosswalk: Crosswalk) -> None:
    axes = (
        ("diagnosis", crosswalk.diagnosis_canonical, crosswalk.diagnosis_aliases),
        ("treatment", crosswalk.treatment_canonical, crosswalk.treatment_aliases),
    )
    for axis, canonical, aliases in axes:
        overlap = canonical & aliases.keys()
        if overlap:
            raise ValueError(
                f"{axis}: label(s) both canonical and alias key: {sorted(overlap)}"
            )
        dangling = {target for target in aliases.values() if target not in canonical}
        if dangling:
            raise ValueError(f"{axis}: alias target(s) not canonical: {sorted(dangling)}")

        # An `uncertain` entry means "stays canonical-as-itself until ruled" -- so
        # its key must already be in `canonical`. A typo here would silently demote
        # a real label to "unknown" instead of leaving it alone.
        uncertain_keys = crosswalk.uncertain.get(axis, {}).keys()
        stray = {key for key in uncertain_keys if key not in canonical}
        if stray:
            raise ValueError(f"{axis}: uncertain key(s) not canonical: {sorted(stray)}")


def _mechanical_clean(expr: pl.Expr) -> pl.Expr:
    """Trim + collapse internal whitespace. No case change, no alias lookup --
    the mechanical-only treatment subcategories get (OQ-1.2 depth ruling)."""
    return expr.str.strip_chars().str.replace_all(r"\s+", " ")


def canonicalize_text(expr: pl.Expr, canonical: frozenset[str], aliases: dict[str, str]) -> pl.Expr:
    """Mechanically clean `expr`, then match case-insensitively against
    `canonical` and `aliases` keys, preserving the canonical spelling on a hit.

    An unrecognized label passes through mechanically cleaned but otherwise
    untouched -- it is never an error (OQ-1.0 Hazards #1).
    """
    cleaned = _mechanical_clean(expr)
    lowered = cleaned.str.to_lowercase()

    lower_to_canonical: dict[str, str] = {label.lower(): label for label in canonical}
    for key, target in aliases.items():
        lower_to_canonical[key.lower()] = target

    return lowered.replace_strict(lower_to_canonical, default=cleaned, return_dtype=pl.String)


def _known_lower(canonical: frozenset[str], aliases: dict[str, str]) -> set[str]:
    return {label.lower() for label in canonical} | {key.lower() for key in aliases}


def _counts_by_label(
    df: pl.DataFrame, col: str, *, lower_keys: set[str], keep: bool
) -> dict[str, int]:
    """Count rows in `col` whose lowercase form is (`keep`) or isn't (`not keep`)
    in `lower_keys`, keyed by the value actually present in `col`."""
    hit = pl.col(col).str.to_lowercase().is_in(list(lower_keys)) if lower_keys else pl.lit(False)
    subset = df.filter(hit if keep else ~hit)
    if subset.height == 0:
        return {}
    grouped = subset.group_by(col).agg(pl.len().alias("n"))
    return dict(zip(grouped[col].to_list(), grouped["n"].to_list(), strict=True))


def apply(
    df: pl.DataFrame, crosswalk: Crosswalk | None = None
) -> tuple[pl.DataFrame, NormalizeReport]:
    """Add `*_raw` columns, canonicalize the two category columns via the
    crosswalk, and mechanically clean the two subcategory columns.

    Rows are never dropped or reordered.
    """
    crosswalk = crosswalk or load_crosswalk()

    df = df.with_columns(
        *[pl.col(col).alias(f"{col}_raw") for col in _ALL_MAPPED_COLUMNS]
    )

    df = df.with_columns(
        canonicalize_text(
            pl.col("diagnosis_category"),
            crosswalk.diagnosis_canonical,
            crosswalk.diagnosis_aliases,
        ).alias("diagnosis_category"),
        canonicalize_text(
            pl.col("treatment_category"),
            crosswalk.treatment_canonical,
            crosswalk.treatment_aliases,
        ).alias("treatment_category"),
        _mechanical_clean(pl.col("diagnosis_subcategory")).alias("diagnosis_subcategory"),
        _mechanical_clean(pl.col("treatment_subcategory")).alias("treatment_subcategory"),
    )

    mapped = {
        col: int((df[col] != df[f"{col}_raw"]).fill_null(False).sum())
        for col in _ALL_MAPPED_COLUMNS
    }

    diag_known = _known_lower(crosswalk.diagnosis_canonical, crosswalk.diagnosis_aliases)
    treat_known = _known_lower(crosswalk.treatment_canonical, crosswalk.treatment_aliases)
    diag_uncertain = {k.lower() for k in crosswalk.uncertain["diagnosis"]}
    treat_uncertain = {k.lower() for k in crosswalk.uncertain["treatment"]}

    unknown_labels = {
        "diagnosis_category": _counts_by_label(
            df, "diagnosis_category", lower_keys=diag_known, keep=False
        ),
        "treatment_category": _counts_by_label(
            df, "treatment_category", lower_keys=treat_known, keep=False
        ),
    }
    uncertain_seen = {
        "diagnosis_category": _counts_by_label(
            df, "diagnosis_category", lower_keys=diag_uncertain, keep=True
        ),
        "treatment_category": _counts_by_label(
            df, "treatment_category", lower_keys=treat_uncertain, keep=True
        ),
    }

    report = NormalizeReport(
        crosswalk_version=CROSSWALK_VERSION,
        mapped=mapped,
        unknown_labels=unknown_labels,
        uncertain_seen=uncertain_seen,
    )
    return df, report
