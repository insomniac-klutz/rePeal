"""Tests for the walking-skeleton static demo page (OQ-1.5.5): a single
self-contained, deterministic, HTML-escaped document."""

from __future__ import annotations

import polars as pl

from repeal.skeleton import page

FOOTER = (
    "Drafts for professional review — not legal or medical advice. "
    "Estimates reflect external-review-stage likelihood only."
)


def _case(**overrides: object) -> dict:
    base = {
        "reference_id": "MN26-00001",
        "report_year": 2022,
        "case_type": "Medical Necessity",
        "diagnosis_category": "Musculoskeletal",
        "treatment_category": "Surgery",
        "denial_basis": "medical_necessity",
        "patient_context": "A patient with chronic back pain.",
        "diagnosis_norm": "lumbar strain",
        "treatment_requested": "spinal fusion surgery",
        "payer_rationale": "not medically necessary per plan guidelines",
        "n_evidence": 2,
        "evidence_kinds": ["guideline", "peer_reviewed_study"],
    }
    base.update(overrides)
    return base


def _drivers() -> list[tuple[str, float]]:
    return [
        ("case_type=Urgent Care", 0.812),
        ("denial_basis=medical_necessity", -0.431),
        ("n_evidence", 0.220),
    ]


def _precedents() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "row_id": [10, 11],
            "reference_id": ["MN21-00010", "MN20-00011"],
            "report_year": [2021, 2020],
            "case_type": ["Medical Necessity", "Medical Necessity"],
            "diagnosis_category": ["Musculoskeletal", "Musculoskeletal"],
            "treatment_category": ["Surgery", "Surgery"],
            "overturned": [True, False],
            "findings": ["A" * 400, "short finding"],
            "match_level": ["exact", "exact"],
        }
    )


def _meta() -> dict:
    return {"sha": "deadbeef", "prompt_hash": "cafef00d", "n_train": 80, "n_test": 20, "auc": 0.61}


def _render() -> str:
    return page.render(_case(), 0.734, _drivers(), _precedents(), _meta())


class TestRender:
    def test_contains_footer_verbatim(self):
        assert FOOTER in _render()

    def test_escapes_script_tags(self):
        html = page.render(
            _case(reference_id="<script>alert(1)</script>"), 0.5, [], _precedents(), _meta()
        )
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_includes_every_precedent_reference_id(self):
        html = _render()
        for reference_id in _precedents().get_column("reference_id"):
            assert reference_id in html

    def test_is_byte_identical_across_two_renders(self):
        assert _render() == _render()

    def test_contains_probability_as_percentage(self):
        assert "73.4%" in _render()

    def test_contains_the_not_a_claim_banner(self):
        assert "NOT A CLAIM" in _render()

    def test_truncates_findings_excerpt_to_300_chars_plus_ellipsis(self):
        html = _render()
        assert ("A" * 300 + "…") in html
        assert ("A" * 301) not in html

    def test_empty_precedents_does_not_crash(self):
        empty = pl.DataFrame(schema=_precedents().schema)
        html = page.render(_case(), 0.5, _drivers(), empty, _meta())
        assert "NOT A CLAIM" in html


class TestWrite:
    def test_write_creates_parent_dirs_and_file(self, tmp_path):
        target = tmp_path / "nested" / "demo.html"
        page.write(target, "<html>hi</html>")
        assert target.read_text(encoding="utf-8") == "<html>hi</html>"
