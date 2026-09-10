"""Walking-skeleton overturn-likelihood baseline (OQ-1.5): temporal split, a
leakage-safe feature builder, and a one-hot + logistic-regression pipeline.

Throwaway by design (PRD Sec.9, OQ-1.5): wiring end-to-end matters, the numbers do
not -- `evaluate`'s `banner` says so on every call. `features` never touches a
post-decision column (`schema.POST_DECISION`, `schema.NARRATIVE`, `determination_raw`,
`schema.LABEL`); Phase 5 owns the real leakage test, this one just refuses to regress
before then.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import polars as pl
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder

from repeal.ingest import schema

CUTOFF_YEAR = 2021  # OQ-1.5, frozen: train report_year <= 2021, test > 2021
STRUCTURED: tuple[str, ...] = (
    "case_type",
    "imr_type",
    "age_range",
    "patient_gender",
    "diagnosis_category",
    "treatment_category",
)
CARD: tuple[str, ...] = ("denial_basis",)
BANNER = "NOT A CLAIM — 100-case walking skeleton"

_NULL_TOKEN = "<null>"
_CATEGORICAL: tuple[str, ...] = (*STRUCTURED, *CARD)
_FORBIDDEN: frozenset[str] = frozenset(
    {*schema.POST_DECISION, schema.NARRATIVE, "determination_raw", schema.LABEL}
)


@dataclass
class Split:
    """A temporal train/test partition of the cards-joined slice."""

    train: pl.DataFrame
    test: pl.DataFrame


def temporal_split(df: pl.DataFrame, cutoff: int = CUTOFF_YEAR) -> Split:
    """Train = `report_year <= cutoff`, test = `report_year > cutoff` (OQ-1.5).

    Raises `ValueError` naming whichever side ends up empty -- a silent 0-row split
    is a bug in the caller's sample, not a valid walking-skeleton run.
    """
    train = df.filter(pl.col("report_year") <= cutoff)
    test = df.filter(pl.col("report_year") > cutoff)
    if train.height == 0:
        raise ValueError(f"temporal_split: train side is empty (report_year <= {cutoff})")
    if test.height == 0:
        raise ValueError(f"temporal_split: test side is empty (report_year > {cutoff})")
    return Split(train=train, test=test)


def _kinds_lists(df: pl.DataFrame) -> list[list[str]]:
    """`evidence_kinds` normalized to `list[str]` per row, whether the column is a
    polars `List[str]` or a JSON-string; null/empty becomes `[]`."""
    raw = df.get_column("evidence_kinds").to_list()
    out: list[list[str]] = []
    for value in raw:
        if value is None:
            out.append([])
        elif isinstance(value, str):
            out.append(list(json.loads(value)) if value else [])
        else:
            out.append(list(value))
    return out


def _distinct_kinds(df: pl.DataFrame) -> list[str]:
    return sorted({kind for row in _kinds_lists(df) for kind in row})


def _evidence_kind_block(df: pl.DataFrame, kinds: Sequence[str]) -> np.ndarray:
    rows = _kinds_lists(df)
    if not kinds:
        return np.empty((len(rows), 0), dtype=np.float64)
    return np.array(
        [[1.0 if kind in row else 0.0 for kind in kinds] for row in rows], dtype=np.float64
    )


def features(
    df: pl.DataFrame, *, known_kinds: Sequence[str] | None = None
) -> tuple[np.ndarray, list[str]]:
    """Design matrix (object dtype: categoricals as str, numerics as float) + names.

    Columns are exactly `STRUCTURED + CARD` (nulls filled with `"<null>"`), then
    `n_evidence`, then one `ek_<kind>` 0/1 column per evidence kind -- `known_kinds`
    if given, else every kind seen in `df`. `Baseline` pins the vocabulary learned
    from `train` and passes it back in at predict time, so a kind that only shows up
    in `test` doesn't shift column alignment against the fitted model.

    Never selects a forbidden column (`findings`, `days_to_review`, `days_to_adopt`,
    `determination_raw`, `overturned`) -- asserted, not just avoided by convention.
    """
    kinds = list(known_kinds) if known_kinds is not None else _distinct_kinds(df)
    ek_names = [f"ek_{kind}" for kind in kinds]
    names = [*_CATEGORICAL, "n_evidence", *ek_names]
    leaked = _FORBIDDEN & set(names)
    if leaked:
        raise AssertionError(f"forbidden column(s) leaked into features: {sorted(leaked)}")

    cat_block = (
        df.select(list(_CATEGORICAL))
        .with_columns([pl.col(c).cast(pl.Utf8).fill_null(_NULL_TOKEN) for c in _CATEGORICAL])
        .to_numpy()
        .astype(object)
    )
    numeric_block = (
        df.select(pl.col("n_evidence").fill_null(0).cast(pl.Float64)).to_numpy().astype(object)
    )
    ek_block = _evidence_kind_block(df, kinds).astype(object)
    matrix = np.hstack([cat_block, numeric_block, ek_block])
    return matrix, names


class Baseline:
    """One-hot + logistic-regression pipeline over `STRUCTURED + CARD` features.

    `fit` pins the category levels (via the encoder) and the evidence-kind vocabulary
    (from `train`); `predict_proba` and `drivers` reuse both, so an unseen category or
    evidence kind at predict time is ignored, not a crash.
    """

    def __init__(self) -> None:
        self._pipeline: Pipeline | None = None
        self._feature_names: list[str] | None = None
        self._kinds: list[str] = []
        self.n_train_: int = 0

    def fit(self, train: pl.DataFrame) -> Baseline:
        self._kinds = _distinct_kinds(train)
        design, raw_names = features(train, known_kinds=self._kinds)
        y = train.get_column(schema.LABEL).to_numpy()

        n_categorical = len(_CATEGORICAL)
        cat_idx = list(range(n_categorical))
        num_idx = list(range(n_categorical, len(raw_names)))
        pre = ColumnTransformer(
            transformers=[
                (
                    "cat",
                    OneHotEncoder(
                        handle_unknown="ignore",
                        sparse_output=False,
                        feature_name_combiner=lambda feature, category: f"{feature}={category}",
                    ),
                    cat_idx,
                ),
                ("num", FunctionTransformer(lambda a: np.asarray(a, dtype=np.float64)), num_idx),
            ]
        )
        pipeline = Pipeline([("prep", pre), ("clf", LogisticRegression(max_iter=1000))])
        pipeline.fit(design, y)

        encoder: OneHotEncoder = pipeline.named_steps["prep"].named_transformers_["cat"]
        cat_names = [raw_names[i] for i in cat_idx]
        encoded_names = list(encoder.get_feature_names_out(cat_names))
        passthrough_names = [raw_names[i] for i in num_idx]

        self._pipeline = pipeline
        self._feature_names = [*encoded_names, *passthrough_names]
        self.n_train_ = train.height
        return self

    def predict_proba(self, df: pl.DataFrame) -> np.ndarray:
        if self._pipeline is None:
            raise RuntimeError("Baseline.predict_proba: call fit() first")
        design, _names = features(df, known_kinds=self._kinds)
        return self._pipeline.predict_proba(design)[:, 1]

    def drivers(self, k: int = 5) -> list[tuple[str, float]]:
        if self._pipeline is None or self._feature_names is None:
            raise RuntimeError("Baseline.drivers: call fit() first")
        coefs = self._pipeline.named_steps["clf"].coef_[0]
        pairs = list(zip(self._feature_names, (float(c) for c in coefs), strict=True))
        pairs.sort(key=lambda pair: abs(pair[1]), reverse=True)
        return pairs[:k]


def evaluate(model: Baseline, test: pl.DataFrame) -> dict:
    """AUC (`None` on a one-class test split -- `roc_auc_score` is undefined there),
    row counts, and the mandatory throwaway banner."""
    proba = model.predict_proba(test)
    y = test.get_column(schema.LABEL).to_numpy()
    auc = float(roc_auc_score(y, proba)) if len(set(y.tolist())) > 1 else None
    return {
        "auc": auc,
        "n_test": test.height,
        "n_train": model.n_train_,
        "banner": BANNER,
    }
