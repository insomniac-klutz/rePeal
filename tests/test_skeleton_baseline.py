"""Tests for the walking-skeleton logreg baseline (OQ-1.5): temporal split, the
feature builder's leakage guard, fit/predict/drivers, and the throwaway `evaluate`
summary. Every fixture is an inline frame -- no real corpus rows (CLAUDE.md)."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from repeal.ingest import schema
from repeal.skeleton.baseline import (
    CARD,
    CUTOFF_YEAR,
    STRUCTURED,
    Baseline,
    Split,
    evaluate,
    features,
    temporal_split,
)

FORBIDDEN_SUBSTRINGS = ("findings", "days_to", "overturned", "determination")


def _row(
    row_id: int,
    year: int,
    *,
    overturned: bool,
    case_type: str = "Medical Necessity",
    denial_basis: str = "medical_necessity",
    n_evidence: int = 2,
    evidence_kinds: list[str] | None = None,
) -> dict:
    return {
        "row_id": row_id,
        "reference_id": f"MN{year % 100:02d}-{row_id:05d}",
        "report_year": year,
        "diagnosis_category": "Musculoskeletal",
        "diagnosis_subcategory": "Back Pain",
        "treatment_category": "Surgery",
        "treatment_subcategory": "Spine",
        "case_type": case_type,
        "age_range": "31 to 40",
        "patient_gender": "Female",
        "imr_type": "Standard",
        "days_to_review": 10,
        "days_to_adopt": 20,
        "determination_raw": (
            "Overturned Decision of Health Plan"
            if overturned
            else "Upheld Decision of Health Plan"
        ),
        "overturned": overturned,
        "findings": "The reviewer found the treatment was appropriate.",
        "denial_basis": denial_basis,
        "n_evidence": n_evidence,
        "evidence_kinds": (
            evidence_kinds if evidence_kinds is not None else ["guideline", "peer_reviewed_study"]
        ),
        "scrub_flag_count": 0,
        "patient_context": "A patient with chronic back pain.",
        "diagnosis_norm": "lumbar strain",
        "treatment_requested": "spinal fusion surgery",
        "payer_rationale": "not medically necessary per plan guidelines",
    }


def _inline_frame(n: int = 20) -> pl.DataFrame:
    """`n` rows, years 2019-2021 (all `<= CUTOFF_YEAR`), alternating label."""
    rows = [_row(i, 2019 + (i % 3), overturned=(i % 2 == 0)) for i in range(n)]
    return pl.DataFrame(rows)


def _split_frame(n_train: int = 14, n_test: int = 6) -> pl.DataFrame:
    """A frame that survives `temporal_split`: train years <= cutoff, test years >
    cutoff, test carrying a never-seen-in-train `case_type` and evidence kind on its
    first row (the "unseen at predict time" seam)."""
    rows = [_row(i, 2019 + (i % 3), overturned=(i % 2 == 0)) for i in range(n_train)]
    for i in range(n_test):
        row_id = n_train + i
        rows.append(
            _row(
                row_id,
                2022 + (i % 2),
                overturned=(i % 2 == 0),
                case_type="Urgent Care" if i == 0 else "Medical Necessity",
                evidence_kinds=["fda_status_never_seen"] if i == 0 else None,
            )
        )
    return pl.DataFrame(rows)


class TestTemporalSplit:
    def test_train_is_le_cutoff_test_is_gt(self):
        split = temporal_split(_split_frame(), cutoff=CUTOFF_YEAR)
        assert isinstance(split, Split)
        assert split.train.get_column("report_year").max() <= CUTOFF_YEAR
        assert split.test.get_column("report_year").min() > CUTOFF_YEAR

    def test_default_cutoff_matches_module_constant(self):
        df = _split_frame()
        default_split = temporal_split(df)
        explicit_split = temporal_split(df, cutoff=CUTOFF_YEAR)
        assert default_split.train.height == explicit_split.train.height

    def test_empty_train_raises_naming_train(self):
        only_future = _inline_frame(n=5).with_columns(pl.lit(2025).alias("report_year"))
        with pytest.raises(ValueError, match="train"):
            temporal_split(only_future, cutoff=CUTOFF_YEAR)

    def test_empty_test_raises_naming_test(self):
        all_past = _inline_frame(n=5)  # every row report_year <= CUTOFF_YEAR
        with pytest.raises(ValueError, match="test"):
            temporal_split(all_past, cutoff=CUTOFF_YEAR)


class TestFeatures:
    def test_excludes_forbidden_columns(self):
        _matrix, names = features(_inline_frame())
        for name in names:
            lowered = name.lower()
            assert not any(bad in lowered for bad in FORBIDDEN_SUBSTRINGS), name
        forbidden = set(schema.POST_DECISION)
        forbidden |= {schema.NARRATIVE, "determination_raw", schema.LABEL}
        assert not (forbidden & set(names))

    def test_returns_ndarray_with_width_matching_names(self):
        df = _inline_frame()
        matrix, names = features(df)
        assert isinstance(matrix, np.ndarray)
        assert matrix.shape == (df.height, len(names))

    def test_names_cover_structured_and_card_columns(self):
        _matrix, names = features(_inline_frame())
        for column in (*STRUCTURED, *CARD, "n_evidence"):
            assert column in names

    def test_known_kinds_pins_evidence_vocabulary(self):
        df = _inline_frame()  # every row's evidence_kinds = ["guideline", "peer_reviewed_study"]
        _matrix, names_pinned = features(df, known_kinds=["guideline"])
        assert "ek_guideline" in names_pinned
        assert "ek_peer_reviewed_study" not in names_pinned


class TestBaseline:
    def test_fit_predict_returns_probabilities_in_unit_interval(self):
        df = _inline_frame(n=20)
        model = Baseline().fit(df)
        proba = model.predict_proba(df)
        assert proba.shape == (20,)
        assert np.all((proba >= 0.0) & (proba <= 1.0))

    def test_handles_unseen_category_and_evidence_kind_at_predict_time(self):
        split = temporal_split(_split_frame(), cutoff=CUTOFF_YEAR)
        model = Baseline().fit(split.train)
        proba = model.predict_proba(split.test)
        assert proba.shape == (split.test.height,)
        assert np.all((proba >= 0.0) & (proba <= 1.0))

    def test_drivers_returns_k_named_float_weights(self):
        model = Baseline().fit(_inline_frame())
        drivers = model.drivers(k=5)
        assert len(drivers) == 5
        for name, weight in drivers:
            assert isinstance(name, str)
            assert isinstance(weight, float)

    def test_drivers_sorted_by_absolute_weight_descending(self):
        model = Baseline().fit(_inline_frame())
        every_driver = model.drivers(k=1000)
        magnitudes = [abs(weight) for _name, weight in every_driver]
        assert magnitudes == sorted(magnitudes, reverse=True)

    def test_predict_before_fit_raises(self):
        with pytest.raises(RuntimeError):
            Baseline().predict_proba(_inline_frame())

    def test_drivers_before_fit_raises(self):
        with pytest.raises(RuntimeError):
            Baseline().drivers()


class TestEvaluate:
    def test_auc_is_none_on_one_class_test(self):
        train_rows = [_row(i, 2019 + (i % 3), overturned=(i % 2 == 0)) for i in range(14)]
        test_rows = [_row(100 + i, 2022, overturned=True) for i in range(4)]  # one class only
        split = temporal_split(pl.DataFrame(train_rows + test_rows), cutoff=CUTOFF_YEAR)
        model = Baseline().fit(split.train)
        result = evaluate(model, split.test)
        assert result["auc"] is None
        assert result["n_test"] == 4
        assert result["n_train"] == 14

    def test_auc_is_a_float_on_two_class_test(self):
        split = temporal_split(_split_frame(), cutoff=CUTOFF_YEAR)
        model = Baseline().fit(split.train)
        result = evaluate(model, split.test)
        assert isinstance(result["auc"], float)
        assert 0.0 <= result["auc"] <= 1.0

    def test_banner_present(self):
        split = temporal_split(_split_frame(), cutoff=CUTOFF_YEAR)
        model = Baseline().fit(split.train)
        result = evaluate(model, split.test)
        assert result["banner"] == "NOT A CLAIM — 100-case walking skeleton"
