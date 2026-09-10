"""Single self-contained HTML demo page for the walking skeleton (OQ-1.5.5).

Hand-written, throwaway: the design zip doesn't exist yet (OQ-0.3), so this is
`render()` -> one string -> `write()` -> a file, plain inline CSS, no JS, no
external assets. Every dynamic value is HTML-escaped; nothing timestamps, so two
renders of the same inputs are byte-identical. The query case's own `findings` /
`determination_raw` / `overturned` never render here -- this is a "predict before
you know the answer" demo, not a leak of the answer key; precedents legitimately
show their outcome and a `findings` excerpt (OQ-1.5.3: display-only, citation-safe).
"""

from __future__ import annotations

import html as _html
from pathlib import Path

import polars as pl

from repeal.skeleton.baseline import BANNER

FOOTER = (
    "Drafts for professional review — not legal or medical advice. "
    "Estimates reflect external-review-stage likelihood only."
)

_EXCERPT_LEN = 300

_CASE_FIELDS: tuple[tuple[str, str], ...] = (
    ("reference_id", "Reference ID"),
    ("report_year", "Report year"),
    ("case_type", "Case type"),
    ("diagnosis_category", "Diagnosis category"),
    ("treatment_category", "Treatment category"),
    ("denial_basis", "Denial basis"),
    ("patient_context", "Patient context"),
    ("diagnosis_norm", "Diagnosis (normalized)"),
    ("treatment_requested", "Treatment requested"),
    ("payer_rationale", "Payer rationale"),
    ("n_evidence", "Evidence count"),
    ("evidence_kinds", "Evidence kinds"),
)

_PRECEDENT_COLUMNS: tuple[str, ...] = (
    "reference_id",
    "report_year",
    "case_type",
    "diagnosis_category",
    "treatment_category",
    "outcome",
    "excerpt",
)
_PRECEDENT_LABELS: dict[str, str] = {
    "reference_id": "Reference ID",
    "report_year": "Year",
    "case_type": "Type",
    "diagnosis_category": "Diagnosis",
    "treatment_category": "Treatment",
    "outcome": "Outcome",
    "excerpt": "Findings (excerpt)",
}

_CSS = (
    "body{font-family:system-ui,sans-serif;max-width:860px;margin:2rem auto;"
    "padding:0 1rem;color:#1a1a1a;background:#fff}"
    "table{border-collapse:collapse;width:100%;margin:0.5rem 0 1.5rem}"
    "th,td{border:1px solid #ccc;padding:0.35rem 0.6rem;text-align:left;font-size:0.92rem}"
    "td.num{text-align:right;font-variant-numeric:tabular-nums}"
    ".banner{background:#fff3cd;border:1px solid #ffe69c;padding:0.5rem 0.75rem;"
    "font-weight:600}"
    ".meta{color:#555;font-size:0.85rem}"
    ".empty{color:#555;font-style:italic}"
    "footer{margin-top:2rem;padding-top:1rem;border-top:1px solid #ccc;"
    "font-size:0.85rem;color:#555}"
)


def _esc(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return _html.escape(", ".join(str(v) for v in value))
    return _html.escape(str(value))


def _case_table(case: dict) -> str:
    rows = "".join(
        f"<tr><th>{_esc(label)}</th><td>{_esc(case.get(key))}</td></tr>"
        for key, label in _CASE_FIELDS
        if key in case
    )
    return f'<table class="case">{rows}</table>'


def _drivers_table(drivers: list[tuple[str, float]]) -> str:
    if not drivers:
        return '<p class="empty">No drivers.</p>'
    rows = "".join(
        f"<tr><td>{_esc(name)}</td><td class=\"num\">{weight:+.3f}</td></tr>"
        for name, weight in drivers
    )
    return (
        '<table class="drivers"><thead><tr><th>Feature</th><th>Weight</th></tr></thead>'
        f"<tbody>{rows}</tbody></table>"
    )


def _outcome(overturned: object) -> str:
    if overturned is None:
        return ""
    return "Overturned" if overturned else "Upheld"


def _excerpt(findings: object) -> str:
    text = "" if findings is None else str(findings)
    return text[:_EXCERPT_LEN] + "…" if len(text) > _EXCERPT_LEN else text


def _precedents_table(precedents: pl.DataFrame) -> str:
    if precedents.height == 0:
        return '<p class="empty">No precedents found.</p>'
    body_rows = []
    for row in precedents.iter_rows(named=True):
        cells = []
        for key in _PRECEDENT_COLUMNS:
            if key == "outcome":
                cells.append(f"<td>{_esc(_outcome(row.get('overturned')))}</td>")
            elif key == "excerpt":
                cells.append(f"<td>{_esc(_excerpt(row.get('findings')))}</td>")
            else:
                cells.append(f"<td>{_esc(row.get(key))}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    header = "".join(f"<th>{_esc(_PRECEDENT_LABELS[key])}</th>" for key in _PRECEDENT_COLUMNS)
    return (
        f'<table class="precedents"><thead><tr>{header}</tr></thead>'
        f"<tbody>{''.join(body_rows)}</tbody></table>"
    )


def _meta_line(meta: dict) -> str:
    parts = []
    if meta.get("sha"):
        parts.append(f"snapshot sha256: {_esc(meta['sha'])}")
    if meta.get("prompt_hash"):
        parts.append(f"prompt hash: {_esc(meta['prompt_hash'])}")
    if "n_train" in meta:
        parts.append(f"n_train={_esc(meta['n_train'])}")
    if "n_test" in meta:
        parts.append(f"n_test={_esc(meta['n_test'])}")
    auc = meta.get("auc")
    parts.append(f"AUC={auc:.3f}" if isinstance(auc, int | float) else "AUC=n/a (one-class test)")
    return " · ".join(parts)


def render(
    case: dict,
    proba: float,
    drivers: list[tuple[str, float]],
    precedents: pl.DataFrame,
    meta: dict,
) -> str:
    """Render one self-contained, deterministic HTML page: case, prediction, top
    drivers, precedents, the throwaway banner, and the mandatory disclaimer footer.
    Every dynamic string is HTML-escaped; no timestamps, so repeat calls with the
    same inputs produce byte-identical output.
    """
    reference_id = _esc(case.get("reference_id", "unknown case"))
    pct = f"{proba * 100:.1f}%"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>repeal — walking skeleton demo: {reference_id}</title>
<style>{_CSS}</style>
</head>
<body>
<p class="banner">{_esc(BANNER)}</p>
<h1>Case {reference_id}</h1>
{_case_table(case)}
<h2>External-review overturn likelihood: {pct}</h2>
<h3>Top drivers</h3>
{_drivers_table(drivers)}
<h3>Precedents</h3>
{_precedents_table(precedents)}
<p class="meta">{_meta_line(meta)}</p>
<footer>{_esc(FOOTER)}</footer>
</body>
</html>
"""


def write(path: Path, html: str) -> None:
    """Write `html` to `path`, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
