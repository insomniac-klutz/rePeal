"""DuckDB warehouse for the Phase 1.5 walking skeleton (OQ-1.5.3).

Joins the Phase 1 ingest parquet (`cases`, the full 42,749-row corpus) with the
~100 LLM-extracted case cards (`case_cards`, `repeal.skeleton.cards.cards_frame`'s
shape) into one `slice` view keyed on `row_id` -- never `reference_id`, which has
39 duplicate pairs in the real corpus and would cross-join a naive join into
double-counted rows.

`precedents()` answers a display-only lookup over the FULL `cases` table, not the
card slice: category-match + recency, cheap because DuckDB reads the parquet
directly. The skeleton's logreg baseline takes no precedent input, so this is a
display surface only (PRD Sec.5 item 5 permits raw `findings` with citation on
human-in-the-loop surfaces) -- but the OQ-0.1 amendment's self-exclusion and
strictly-earlier-year discipline are applied anyway, on principle, so nobody
downstream inherits a leaky habit from the throwaway.

Environment note: `pyarrow` is not a project dependency and is not installed here.
DuckDB's polars bridge (`.pl()` / `.df()` / `.arrow()` / `.register()`) all route
through polars' `to_arrow()`, which requires it -- confirmed by hand, all four
raise `ModuleNotFoundError` in this environment. Every duckdb<->polars crossing in
this module goes around that bridge instead: `case_cards` loads via a scratch
parquet file (DuckDB's own reader, not `register`), and reads come back through
`_fetch_polars` (plain DB-API `fetchall()` + `description`, built into a polars
frame by hand). If `pyarrow` ever becomes a real dependency, none of this needs to
change -- it would just be free to simplify.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import duckdb
import polars as pl

DB_FILENAME = "skeleton.duckdb"

# Columns returned by `precedents` -- display surface only (PRD Sec.5 item 5).
_PRECEDENT_COLUMNS: tuple[str, ...] = (
    "row_id",
    "reference_id",
    "report_year",
    "case_type",
    "diagnosis_category",
    "treatment_category",
    "overturned",
    "findings",
)

# Fixed dtypes so an empty result (no earlier-year matches at all) still carries
# the right schema instead of polars' all-null-column `Null` dtype.
_PRECEDENT_SCHEMA: dict[str, Any] = {
    "row_id": pl.Int64,
    "reference_id": pl.String,
    "report_year": pl.Int32,
    "case_type": pl.String,
    "diagnosis_category": pl.String,
    "treatment_category": pl.String,
    "overturned": pl.Boolean,
    "findings": pl.String,
    "match_level": pl.String,
}

# Card-derived columns joined onto `cases` to form `slice`. `k.reference_id` is
# skipped (`c.*` already carries it) and so is `evidence_json` -- provenance, not
# a display field.
_CARD_VIEW_COLUMNS: tuple[str, ...] = (
    "denial_basis",
    "n_evidence",
    "evidence_kinds",
    "scrub_flag_count",
    "patient_context",
    "diagnosis_norm",
    "treatment_requested",
    "payer_rationale",
)


class CardRowIdMismatchError(ValueError):
    """A case card's `row_id` has no matching row in `cases`."""


def build(
    db_path: Path,
    parquet: Path,
    cards: Path | pl.DataFrame,
    *,
    check_hash: bool = True,
) -> duckdb.DuckDBPyConnection:
    """Build the skeleton DuckDB: `cases`, `case_cards`, and a `slice` view.

    `db_path` is deleted and recreated on every call -- re-runs are deterministic,
    never a merge onto a stale schema. `cards` is either a cards JSONL path (loaded
    and prompt-hash-checked via `repeal.skeleton.cards`) or an already-built cards
    frame (`cards_frame()`'s shape), so callers that already have the frame -- and
    tests -- don't need that module. Fails loud (`CardRowIdMismatchError`) if any
    card's `row_id` has no matching row in `cases`.
    """
    cards_frame = _resolve_cards_frame(cards, check_hash=check_hash)

    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(db_path))
    try:
        con.execute("CREATE TABLE cases AS SELECT * FROM read_parquet(?)", [str(parquet)])
        _load_cards_table(con, cards_frame)
        _check_card_row_ids_exist(con)
        card_columns_sql = ", ".join(f"k.{c}" for c in _CARD_VIEW_COLUMNS)
        con.execute(
            f"CREATE VIEW slice AS SELECT c.*, {card_columns_sql} "
            "FROM cases c JOIN case_cards k USING (row_id)"
        )
    except Exception:
        con.close()
        raise
    return con


def _resolve_cards_frame(cards: Path | pl.DataFrame, *, check_hash: bool) -> pl.DataFrame:
    if isinstance(cards, pl.DataFrame):
        return cards
    from repeal.skeleton.cards import cards_frame, load_cards  # lazy: optional dep

    return cards_frame(load_cards(cards, check_hash=check_hash))


def _load_cards_table(con: duckdb.DuckDBPyConnection, frame: pl.DataFrame) -> None:
    """Materialize `case_cards` from a polars frame via a scratch parquet file.

    Not `con.register` + CTAS: DuckDB's polars registration calls polars'
    `to_arrow()`, which needs `pyarrow` (see module docstring). `read_parquet` is
    DuckDB's own reader and needs neither -- and it round-trips `evidence_kinds:
    list[str]` to a native DuckDB LIST(VARCHAR), which reads back as polars
    `List(String)` (verified by hand), so the list stays a list end to end, no
    JSON-string detour needed for that column.
    """
    with tempfile.TemporaryDirectory() as scratch:
        scratch_path = Path(scratch) / "cards.parquet"
        frame.write_parquet(scratch_path)
        con.execute(
            "CREATE TABLE case_cards AS SELECT * FROM read_parquet(?)", [str(scratch_path)]
        )


def _check_card_row_ids_exist(con: duckdb.DuckDBPyConnection) -> None:
    missing = con.execute(
        "SELECT k.row_id FROM case_cards k LEFT JOIN cases c USING (row_id) "
        "WHERE c.row_id IS NULL ORDER BY k.row_id"
    ).fetchall()
    if missing:
        offending = [row[0] for row in missing]
        raise CardRowIdMismatchError(f"case card row_id(s) not found in cases: {offending}")


def slice_frame(con: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    """The joined `slice` view as polars, sorted by `row_id`."""
    return _fetch_polars(con.execute("SELECT * FROM slice ORDER BY row_id"))


def precedents(con: duckdb.DuckDBPyConnection, row_id: int, k: int = 5) -> pl.DataFrame:
    """Up to `k` precedent cases for `row_id`, queried over the FULL `cases` table
    (not the card slice) -- display-only (PRD Sec.5 item 5: raw `findings` allowed
    with citation on human-in-the-loop surfaces; this feeds no predictor).

    OQ-0.1 amendment discipline applied anyway: self-excluded, strictly earlier
    `report_year` only (never the query's own year or later), newest-first
    (`report_year DESC, row_id ASC`). Matches `diagnosis_category` +
    `treatment_category` + `case_type`; if fewer than `k` match on all three,
    falls back to `diagnosis_category` + `case_type` alone, and every row says
    which query answered it via `match_level` (`"full"` / `"diagnosis"`).
    """
    query = con.execute(
        "SELECT diagnosis_category, treatment_category, case_type, report_year "
        "FROM cases WHERE row_id = ?",
        [row_id],
    ).fetchone()
    if query is None:
        raise ValueError(f"row_id {row_id} not found in cases")
    diagnosis_category, treatment_category, case_type, report_year = query

    columns_sql = ", ".join(_PRECEDENT_COLUMNS)
    full_count = con.execute(
        "SELECT COUNT(*) FROM cases WHERE diagnosis_category = ? AND treatment_category = ? "
        "AND case_type = ? AND report_year < ? AND row_id != ?",
        [diagnosis_category, treatment_category, case_type, report_year, row_id],
    ).fetchone()[0]

    if full_count >= k:
        cursor = con.execute(
            f"SELECT {columns_sql}, 'full' AS match_level FROM cases "
            "WHERE diagnosis_category = ? AND treatment_category = ? AND case_type = ? "
            "AND report_year < ? AND row_id != ? "
            "ORDER BY report_year DESC, row_id ASC LIMIT ?",
            [diagnosis_category, treatment_category, case_type, report_year, row_id, k],
        )
    else:
        cursor = con.execute(
            f"SELECT {columns_sql}, "
            "CASE WHEN treatment_category = ? THEN 'full' ELSE 'diagnosis' END AS match_level "
            "FROM cases WHERE diagnosis_category = ? AND case_type = ? "
            "AND report_year < ? AND row_id != ? "
            "ORDER BY report_year DESC, row_id ASC LIMIT ?",
            [treatment_category, diagnosis_category, case_type, report_year, row_id, k],
        )
    return _fetch_polars(cursor, schema=_PRECEDENT_SCHEMA)


def _fetch_polars(
    cursor: duckdb.DuckDBPyConnection, *, schema: dict[str, Any] | None = None
) -> pl.DataFrame:
    """`fetchall()` -> polars, column-oriented. Not `.pl()` (see module docstring:
    duckdb's polars bridge needs `pyarrow`, which isn't installed here)."""
    columns = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    data = {c: [row[i] for row in rows] for i, c in enumerate(columns)}
    return pl.DataFrame(data, schema=schema)


def close(con: duckdb.DuckDBPyConnection) -> None:
    """Close the connection."""
    con.close()
