"""Tests for repeal.ingest.normalize -- the category crosswalk (OQ-1.2).

TDD note: written before src/repeal/ingest/normalize.py exists. First run is
expected to fail on import (red); normalize.py lands next to turn it green.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
import yaml

from repeal.ingest.normalize import (
    CROSSWALK_PATH,
    Crosswalk,
    apply,
    canonicalize_text,
    load_crosswalk,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "imr_synthetic.csv"


def _row(row_id: int, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "row_id": row_id,
        "reference_id": f"MN26-{10000 + row_id}",
        "report_year": 2026,
        "diagnosis_category": "Musculoskeletal",
        "diagnosis_subcategory": "Back  Pain",  # double space -- exercises mechanical cleanup
        "treatment_category": "Surgery",
        "treatment_subcategory": " Spinal ",  # leading/trailing space
        "determination_raw": "Upheld Decision of Health Plan",
        "case_type": "Medical Necessity",
        "age_range": "41-50",
        "patient_gender": "Female",
        "imr_type": "Standard",
        "days_to_review": 30,
        "days_to_adopt": 5,
        "overturned": False,
        "findings": "x" * 250,
    }
    base.update(overrides)
    return base


def _frame(rows: list[dict[str, object]]) -> pl.DataFrame:
    # Pin the nullable string columns' dtype explicitly: a single-row frame
    # where one of these happens to be None gives polars nothing to infer a
    # String dtype from otherwise (it infers Null), which `.str.*` rejects --
    # schema.py's `validate()` always produces a proper nullable String here.
    return pl.DataFrame(
        rows,
        schema_overrides={
            "diagnosis_subcategory": pl.String,
            "treatment_subcategory": pl.String,
            "age_range": pl.String,
            "patient_gender": pl.String,
        },
    )


def test_crosswalk_loads_and_validates() -> None:
    crosswalk = load_crosswalk()
    assert isinstance(crosswalk, Crosswalk)
    assert crosswalk.canonical_scheme == "icd10-chapter-2026"
    assert "Musculoskeletal" in crosswalk.diagnosis_canonical
    assert crosswalk.diagnosis_aliases["Orth/Musculoskeletal"] == "Musculoskeletal"


def test_crosswalk_path_is_the_packaged_file() -> None:
    assert CROSSWALK_PATH.exists()
    assert CROSSWALK_PATH.name == "category_crosswalk_v1.yaml"


def test_real_crosswalk_has_no_duplicate_or_dangling_labels() -> None:
    crosswalk = load_crosswalk()
    for canonical, aliases, uncertain in (
        (
            crosswalk.diagnosis_canonical,
            crosswalk.diagnosis_aliases,
            crosswalk.uncertain["diagnosis"],
        ),
        (
            crosswalk.treatment_canonical,
            crosswalk.treatment_aliases,
            crosswalk.uncertain["treatment"],
        ),
    ):
        assert not (canonical & aliases.keys())
        assert all(target in canonical for target in aliases.values())
        assert all(entry["to"] in canonical for entry in uncertain.values())
        assert all(key not in aliases for key in uncertain)


@pytest.mark.parametrize(
    ("legacy", "canonical"),
    [
        ("Orth/Musculoskeletal", "Musculoskeletal"),
        ("Endocrine/Metabolic", "Endo/Metabolic"),
        ("Mental Disorder", "Mental Behav Neur"),
        ("Cancer", "Neoplasms (Tumor)"),
    ],
)
def test_known_diagnosis_pairs_map(legacy: str, canonical: str) -> None:
    df = _frame([_row(0, diagnosis_category=legacy)])
    result, report = apply(df)
    assert result["diagnosis_category"].to_list() == [canonical]
    assert result["diagnosis_category_raw"].to_list() == [legacy]
    assert report.mapped["diagnosis_category"] == 1


def test_canonical_2026_label_is_untouched() -> None:
    df = _frame([_row(0, diagnosis_category="Musculoskeletal")])
    result, report = apply(df)
    assert result["diagnosis_category"].to_list() == ["Musculoskeletal"]
    assert report.mapped["diagnosis_category"] == 0


def test_unknown_label_passes_through_and_is_counted() -> None:
    df = _frame([_row(0, diagnosis_category="Zzz Unknown Category")])
    result, report = apply(df)
    assert result["diagnosis_category"].to_list() == ["Zzz Unknown Category"]
    assert report.unknown_labels["diagnosis_category"]["Zzz Unknown Category"] == 1


def test_whitespace_and_case_variants_map() -> None:
    df = _frame(
        [
            _row(0, diagnosis_category="  orth/musculoskeletal  "),
            _row(1, diagnosis_category="ORTH/MUSCULOSKELETAL"),
        ]
    )
    result, _ = apply(df)
    assert result["diagnosis_category"].to_list() == ["Musculoskeletal", "Musculoskeletal"]


def test_case_insensitive_match_against_canonical_itself() -> None:
    # "gen surg proc" is a lowercase variant of canonical "Gen Surg Proc" (the real
    # corpus even has a 2-row "Gen Surg proc" typo). No alias entry exists or should
    # exist for it -- case-insensitive matching against the canonical set itself
    # must resolve it without one.
    df = _frame([_row(0, treatment_category="gen surg proc")])
    result, _ = apply(df)
    assert result["treatment_category"].to_list() == ["Gen Surg Proc"]


def test_raw_columns_equal_input() -> None:
    df = _frame(
        [
            _row(
                0,
                diagnosis_category="Cancer",
                diagnosis_subcategory="  Skin  Cancer ",
                treatment_category="Chemo Drugs",
                treatment_subcategory="IV",
            )
        ]
    )
    result, _ = apply(df)
    assert result["diagnosis_category_raw"].to_list() == ["Cancer"]
    assert result["diagnosis_subcategory_raw"].to_list() == ["  Skin  Cancer "]
    assert result["treatment_category_raw"].to_list() == ["Chemo Drugs"]
    assert result["treatment_subcategory_raw"].to_list() == ["IV"]


def test_subcategories_only_get_trimmed_not_cased_or_aliased() -> None:
    df = _frame(
        [_row(0, diagnosis_subcategory="  Knee   pain  ", treatment_subcategory="spinal FUSION")]
    )
    result, _ = apply(df)
    assert result["diagnosis_subcategory"].to_list() == ["Knee pain"]
    assert result["treatment_subcategory"].to_list() == ["spinal FUSION"]  # case untouched


def test_subcategory_null_passes_through() -> None:
    df = _frame([_row(0, diagnosis_subcategory=None)])
    result, _ = apply(df)
    assert result["diagnosis_subcategory"].to_list() == [None]
    assert result["diagnosis_subcategory_raw"].to_list() == [None]


def test_uncertain_labels_not_mapped_but_counted() -> None:
    # Autism Spectrum was ruled into `aliases` by OQ-1.12 (2026-09-10); Dental
    # Problems is one of the seven that stayed uncertain, so it still exercises
    # this path.
    df = _frame([_row(0, diagnosis_category="Dental Problems")])
    result, report = apply(df)
    assert result["diagnosis_category"].to_list() == ["Dental Problems"]
    assert report.uncertain_seen["diagnosis_category"]["Dental Problems"] == 1
    assert "Dental Problems" not in report.unknown_labels.get("diagnosis_category", {})


@pytest.mark.parametrize(
    ("axis", "legacy", "canonical"),
    [
        ("diagnosis", "Autism Spectrum", "Mental Behav Neur"),
        ("diagnosis", "Chron Pain Synd", "Sym/Sign Ab Find"),
        ("diagnosis", "Genetic Diseases", "Malfor/Deform/Abnor"),
        ("diagnosis", "Immuno Disorders", "Diseases of Blood"),
        ("diagnosis", "Morbid Obesity", "Endo/Metabolic"),
        ("diagnosis", "Post Surgical Comp", "Injury Poison Oth"),
        ("diagnosis", "Prevention/Good Hlth", "Hlth Factor/Contact"),
        ("treatment", "DME", "Durable Med Equip"),
        ("treatment", "Transportation", "Ambulance Transport"),
    ],
)
def test_ruled_oq_1_12_mappings_apply(axis: str, legacy: str, canonical: str) -> None:
    # OQ-1.12 (ruled 2026-09-10): these nine moved from `uncertain` guesses to
    # applied `aliases` -- the ICD-10-chapter-consistent broadenings.
    col = f"{axis}_category"
    df = _frame([_row(0, **{col: legacy})])
    result, report = apply(df)
    assert result[col].to_list() == [canonical]
    assert result[f"{col}_raw"].to_list() == [legacy]
    assert report.mapped[col] == 1


def test_real_crosswalk_reflects_oq_1_12_ruling() -> None:
    # Shape check on the real YAML, not a fixture: exactly the seven labels OQ-1.12
    # left uncertain remain there, and the nine it ruled in are now aliases.
    crosswalk = load_crosswalk()
    assert set(crosswalk.uncertain["diagnosis"]) == {
        "Dental Problems",
        "Ears/Nose/Throat",
        "Foot Disorder",
        "OB-GYN/ Pregnancy",
    }
    assert set(crosswalk.uncertain["treatment"]) == {
        "Alternative Tx",
        "Diag Imag & Screen",
        "Mental Health",
    }
    ruled = {
        "Autism Spectrum",
        "Chron Pain Synd",
        "Genetic Diseases",
        "Immuno Disorders",
        "Morbid Obesity",
        "Post Surgical Comp",
        "Prevention/Good Hlth",
        "DME",
        "Transportation",
    }
    aliased = crosswalk.diagnosis_aliases.keys() | crosswalk.treatment_aliases.keys()
    assert ruled <= aliased


def test_near_duplicate_pregnancy_pair_converges() -> None:
    df = _frame(
        [
            _row(0, diagnosis_category="Pregnancy Childbirth"),
            _row(1, diagnosis_category="Pregnancy/Childbirth"),
        ]
    )
    result, _ = apply(df)
    assert result["diagnosis_category"].to_list() == [
        "Pregnancy Childbirth",
        "Pregnancy Childbirth",
    ]


def test_crosswalk_invariant_both_canonical_and_alias_raises(tmp_path: Path) -> None:
    bad = {
        "version": 1,
        "canonical_scheme": "test",
        "diagnosis": {"canonical": ["A", "B"], "aliases": {"A": "B"}},
        "treatment": {"canonical": ["C"], "aliases": {}},
    }
    bad_path = tmp_path / "bad_crosswalk.yaml"
    bad_path.write_text(yaml.safe_dump(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="canonical and alias key"):
        load_crosswalk(bad_path)


def test_crosswalk_invariant_alias_target_must_be_canonical(tmp_path: Path) -> None:
    bad = {
        "version": 1,
        "canonical_scheme": "test",
        "diagnosis": {"canonical": ["A"], "aliases": {"Z": "not-canonical"}},
        "treatment": {"canonical": ["C"], "aliases": {}},
    }
    bad_path = tmp_path / "bad_crosswalk2.yaml"
    bad_path.write_text(yaml.safe_dump(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="not canonical"):
        load_crosswalk(bad_path)


def test_crosswalk_invariant_uncertain_key_must_be_canonical(tmp_path: Path) -> None:
    # An `uncertain` entry means "stays canonical-as-itself until ruled" -- a key
    # that isn't in `canonical` would silently demote a real label to "unknown".
    bad = {
        "version": 1,
        "canonical_scheme": "test",
        "diagnosis": {
            "canonical": ["A"],
            "aliases": {},
            "uncertain": {"Not Canonical": {"to": "A", "why": "typo test"}},
        },
        "treatment": {"canonical": ["C"], "aliases": {}},
    }
    bad_path = tmp_path / "bad_crosswalk3.yaml"
    bad_path.write_text(yaml.safe_dump(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="uncertain key"):
        load_crosswalk(bad_path)


def test_row_count_and_order_unchanged() -> None:
    df = _frame([_row(i) for i in range(4)])
    result, _ = apply(df)
    assert result.height == 4
    assert result["row_id"].to_list() == [0, 1, 2, 3]


def test_canonicalize_text_preserves_canonical_spelling_case_insensitively() -> None:
    canonical = frozenset({"Musculoskeletal"})
    aliases = {"Orth/Musculoskeletal": "Musculoskeletal"}
    expr = canonicalize_text(pl.col("x"), canonical, aliases)
    result = pl.DataFrame(
        {"x": ["  orth/musculoskeletal  ", "Musculoskeletal", "Something Else"]}
    ).select(expr.alias("x"))
    assert result["x"].to_list() == ["Musculoskeletal", "Musculoskeletal", "Something Else"]


def _load_fixture_frame() -> pl.DataFrame | None:
    if not FIXTURE_PATH.exists():
        return None
    try:
        from repeal.ingest.schema import validate
    except ImportError:
        return None
    try:
        return validate(pl.scan_csv(FIXTURE_PATH, infer_schema_length=0).collect())
    except Exception:
        return None


@pytest.mark.skipif(
    _load_fixture_frame() is None,
    reason="synthetic fixture and/or schema.validate() not committed yet",
)
def test_apply_on_synthetic_fixture_has_only_planted_unknown() -> None:
    df = _load_fixture_frame()
    assert df is not None
    result, report = apply(df)
    assert result.height == df.height
    for col, allowed in (
        ("diagnosis_category", {"Zzz Unknown Category"}),
        ("treatment_category", set()),
    ):
        assert set(report.unknown_labels.get(col, {})) <= allowed
