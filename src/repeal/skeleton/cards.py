"""Case-card schema, sampler, prompt, and JSONL I/O for the Phase 1.5 walking skeleton
(OQ-1.5.1, OQ-1.5.2, OQ-1.5.4).

A case card is an LLM paraphrase of a `findings` narrative, scrubbed of the reviewer's
verdict (PRD Sec.5 / OQ-0.1: raw `findings` is never a prediction input). Cards are
sampled -> extracted by three parallel workflows against the versioned prompt at
`PROMPT_PATH` -> merged (provenance stamped) -> loaded. `warehouse.build` reads the
merged JSONL through `load_cards` + `cards_frame`; `baseline.features` reads the frame.

CLI: `python -m repeal.skeleton.cards --sample|--merge|--validate`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from enum import StrEnum
from pathlib import Path

import polars as pl
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from repeal.config import get_settings

PROMPT_PATH: Path = Path(__file__).resolve().parent / "prompts" / "case_card_v0.md"
PROMPT_VERSION = "0"
WORKFLOW = "skeleton-extract-v0"
MODEL = "claude-sonnet-5"

# Never `overturned` / `determination_raw` -- the sample is what an extractor sees,
# and the label used only to stratify (OQ-0.1) never rides along.
SAMPLE_COLUMNS: tuple[str, ...] = (
    "row_id",
    "reference_id",
    "report_year",
    "case_type",
    "imr_type",
    "age_range",
    "patient_gender",
    "diagnosis_category",
    "treatment_category",
    "findings",
)

_PARQUET_FILENAME = "imr_cases.parquet"
_SAMPLE_FILENAME = "sample.jsonl"
_CARDS_FILENAME = "cards.jsonl"
_PART_GLOB = "cards_part_*.jsonl"


class DenialBasis(StrEnum):
    medical_necessity = "medical_necessity"
    experimental_investigational = "experimental_investigational"
    urgent = "urgent"


class EvidenceKind(StrEnum):
    guideline = "guideline"
    peer_reviewed_study = "peer_reviewed_study"
    fda_status = "fda_status"
    clinical_trial = "clinical_trial"
    expert_opinion = "expert_opinion"
    other = "other"


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: EvidenceKind
    text: str


class CaseCard(BaseModel):
    """One extracted, verdict-scrubbed case card. `extra="forbid"` so an extractor's
    typo or stray field fails loud at merge/load time instead of vanishing silently."""

    model_config = ConfigDict(extra="forbid")

    row_id: int
    reference_id: str
    patient_context: str
    diagnosis_norm: str
    treatment_requested: str
    denial_basis: DenialBasis
    payer_rationale: str
    evidence_cited: list[Evidence] = Field(default_factory=list)
    scrub_flags: list[str] = Field(default_factory=list)

    # Provenance: absent from raw extractor output, stamped by `merge_parts`.
    prompt_hash: str | None = None
    prompt_version: str | None = None
    model: str | None = None
    workflow: str | None = None
    extractor: str | None = None


_DENIAL_BASIS_SYNONYMS: dict[str, DenialBasis] = {
    "medical necessity": DenialBasis.medical_necessity,
    "medically necessary": DenialBasis.medical_necessity,
    "experimental investigational": DenialBasis.experimental_investigational,
    "experimental": DenialBasis.experimental_investigational,
    "investigational": DenialBasis.experimental_investigational,
    "e i": DenialBasis.experimental_investigational,
    "urgent": DenialBasis.urgent,
    "urgent care": DenialBasis.urgent,
}


def _normalize_key(value: str) -> str:
    """Lowercase, punctuation/underscores/whitespace collapsed to single spaces."""
    lowered = value.strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_denial_basis(value: str) -> DenialBasis:
    """Tolerant string -> `DenialBasis`: case/space/punctuation-insensitive, with
    synonyms ("medical necessity", "Experimental/Investigational", "E/I",
    "urgent care", ...). Raises `ValueError` on anything unrecognized.
    """
    key = _normalize_key(value)
    if key in _DENIAL_BASIS_SYNONYMS:
        return _DENIAL_BASIS_SYNONYMS[key]
    for member in DenialBasis:
        if key == _normalize_key(member.value):
            return member
    raise ValueError(f"unrecognized denial_basis value: {value!r}")


def prompt_hash(path: Path = PROMPT_PATH) -> str:
    """sha256 hex digest of the prompt file's raw bytes -- the contract's fingerprint.
    Every merged card stamps this; `load_cards` rejects a mismatch (a card extracted
    against a stale prompt version)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sample_row_ids(df: pl.DataFrame, n: int = 100, seed: int = 42) -> list[int]:
    """Deterministic stratified sample of `row_id`s for the skeleton extraction slice
    (OQ-1.5.4).

    Strata are `case_type` x `overturned` x era (era = `report_year` <= 2021 vs
    >= 2022, the ruled OQ-1.5 cutoff). Excludes `report_year` in (2001, 2026) and rows
    with `flag_findings_short`. Quota per stratum is `round(n * stratum_share)`,
    floored at 2, capped at the stratum's own size ("small strata taken whole").
    `overturned` stratifies only -- see `write_sample` for what actually gets written.
    Deterministic under `seed`; returns sorted row_ids.
    """
    eligible = df.filter(
        (~pl.col("report_year").is_in([2001, 2026])) & (~pl.col("flag_findings_short"))
    ).with_columns(
        pl.when(pl.col("report_year") <= 2021)
        .then(pl.lit("pre"))
        .otherwise(pl.lit("post"))
        .alias("_era")
    )
    total = eligible.height
    if total == 0:
        return []

    strata = (
        eligible.select("case_type", "overturned", "_era")
        .unique()
        .sort(["case_type", "overturned", "_era"])
    )

    selected: list[int] = []
    for i, stratum in enumerate(strata.iter_rows(named=True)):
        group = eligible.filter(
            (pl.col("case_type") == stratum["case_type"])
            & (pl.col("overturned") == stratum["overturned"])
            & (pl.col("_era") == stratum["_era"])
        )
        share = group.height / total
        quota = min(max(round(n * share), 2), group.height)
        ids = group.get_column("row_id").sample(n=quota, seed=seed + i, shuffle=True)
        selected.extend(ids.to_list())

    return sorted(selected)


def write_sample(parquet: Path, out: Path, n: int = 100, seed: int = 42) -> int:
    """Sample `row_id`s from `parquet` via `sample_row_ids`, write `SAMPLE_COLUMNS`-only
    JSONL to `out` (one object per line, sorted by `row_id`). Returns the row count.
    """
    df = pl.read_parquet(parquet)
    row_ids = sample_row_ids(df, n=n, seed=seed)
    sample = (
        df.filter(pl.col("row_id").is_in(row_ids)).select(list(SAMPLE_COLUMNS)).sort("row_id")
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for row in sample.iter_rows(named=True):
            fh.write(json.dumps(row) + "\n")
    return sample.height


def merge_parts(parts_dir: Path, out: Path, *, prompt_path: Path = PROMPT_PATH) -> int:
    """Merge `cards_part_*.jsonl` in `parts_dir` into one provenance-stamped `out`.

    Each line is validated as a `CaseCard` (sans provenance), then stamped with
    `prompt_hash`/`prompt_version`/`model`/`workflow`/`extractor` -- `extractor` is the
    part filename's suffix (`cards_part_a.jsonl` -> `"a"`). Fails loud, naming the
    row_id and the field, on an invalid card; fails loud, naming the row_id, on a
    duplicate. Output is sorted by `row_id`, one JSON object per line. Returns the
    merged row count.
    """
    parts = sorted(parts_dir.glob(_PART_GLOB))
    if not parts:
        raise ValueError(f"no {_PART_GLOB} files found in {parts_dir}")

    stamp = {
        "prompt_hash": prompt_hash(prompt_path),
        "prompt_version": PROMPT_VERSION,
        "model": MODEL,
        "workflow": WORKFLOW,
    }

    cards: dict[int, CaseCard] = {}
    for part in parts:
        extractor = part.stem.removeprefix("cards_part_")
        for lineno, line in enumerate(part.read_text(encoding="utf-8").splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{part.name}:{lineno}: invalid JSON: {exc}") from exc
            row_id = raw.get("row_id")
            try:
                card = CaseCard.model_validate(raw | stamp | {"extractor": extractor})
            except ValidationError as exc:
                raise ValueError(
                    f"{part.name}:{lineno}: invalid card for row_id={row_id!r}: {exc}"
                ) from exc
            if card.row_id in cards:
                raise ValueError(
                    f"duplicate row_id={card.row_id} in {part.name} "
                    "(already present from another part)"
                )
            cards[card.row_id] = card

    ordered = [cards[row_id] for row_id in sorted(cards)]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for card in ordered:
            fh.write(card.model_dump_json() + "\n")
    return len(ordered)


def load_cards(
    path: Path, *, check_hash: bool = True, prompt_path: Path = PROMPT_PATH
) -> list[CaseCard]:
    """Load a cards JSONL file, validating every line as a `CaseCard`.

    Raises `ValueError` on any invalid line, or (unless `check_hash=False`) on a card
    whose `prompt_hash` doesn't match `prompt_hash(prompt_path)` -- a card extracted
    against a stale prompt version.
    """
    expected = prompt_hash(prompt_path) if check_hash else None
    cards: list[CaseCard] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
            card = CaseCard.model_validate(raw)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ValueError(f"{path.name}:{lineno}: invalid card: {exc}") from exc
        if check_hash and card.prompt_hash != expected:
            raise ValueError(
                f"{path.name}:{lineno}: row_id={card.row_id} prompt_hash mismatch "
                f"(card={card.prompt_hash!r} expected={expected!r})"
            )
        cards.append(card)
    return cards


def cards_frame(cards: list[CaseCard]) -> pl.DataFrame:
    """One row per card: `row_id`, `reference_id`, `denial_basis` (str), `n_evidence`,
    `evidence_kinds` (list[str]), `scrub_flag_count`, `patient_context`,
    `diagnosis_norm`, `treatment_requested`, `payer_rationale`, `evidence_json` (str).
    """
    schema = {
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
    if not cards:
        return pl.DataFrame(schema=schema)

    rows = [
        {
            "row_id": card.row_id,
            "reference_id": card.reference_id,
            "denial_basis": card.denial_basis.value,
            "n_evidence": len(card.evidence_cited),
            "evidence_kinds": [e.kind.value for e in card.evidence_cited],
            "scrub_flag_count": len(card.scrub_flags),
            "patient_context": card.patient_context,
            "diagnosis_norm": card.diagnosis_norm,
            "treatment_requested": card.treatment_requested,
            "payer_rationale": card.payer_rationale,
            "evidence_json": json.dumps([e.model_dump(mode="json") for e in card.evidence_cited]),
        }
        for card in cards
    ]
    return pl.DataFrame(rows, schema=schema)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m repeal.skeleton.cards")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sample", action="store_true", help="sample row_ids -> sample.jsonl")
    group.add_argument(
        "--merge", action="store_true", help="merge cards_part_*.jsonl -> cards.jsonl"
    )
    group.add_argument("--validate", action="store_true", help="load + hash-check cards.jsonl")
    parser.add_argument("--n", type=int, default=100, help="sample size (--sample only)")
    parser.add_argument("--seed", type=int, default=42, help="sample seed (--sample only)")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns 0 on success, 1 with a readable message on failure."""
    args = _build_arg_parser().parse_args(argv)
    settings = get_settings()
    skeleton_dir = settings.interim_dir / "skeleton"

    if args.sample:
        parquet = settings.interim_dir / _PARQUET_FILENAME
        out = skeleton_dir / _SAMPLE_FILENAME
        try:
            count = write_sample(parquet, out, n=args.n, seed=args.seed)
        except Exception as exc:
            print(f"sample failed: {exc}", file=sys.stderr)
            return 1
        print(f"sample: {count} rows -> {out}")
        return 0

    if args.merge:
        out = skeleton_dir / _CARDS_FILENAME
        try:
            count = merge_parts(skeleton_dir, out)
        except Exception as exc:
            print(f"merge failed: {exc}", file=sys.stderr)
            return 1
        print(f"merge: {count} cards -> {out}")
        return 0

    path = skeleton_dir / _CARDS_FILENAME
    try:
        cards = load_cards(path)
    except Exception as exc:
        print(f"validate failed: {exc}", file=sys.stderr)
        return 1
    print(f"validate: {len(cards)} cards ok in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
