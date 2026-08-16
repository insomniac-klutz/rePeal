# rePeal
re: your denial

Appeals intelligence over the public California DMHC Independent Medical Review corpus — tens of thousands of real external-review decisions with outcomes. `repeal` turns that corpus into three things a denials analyst can use: **precedent retrieval** over comparable cases, a **calibrated overturn-likelihood** estimate for a denial worth escalating, and **grounded appeal-letter drafting** with every claim traceable to a cited source.

**Status: Phase 0 scaffold.**

## Quickstart

```bash
uv sync --group dev          # install deps (incl. dev group)
uv run pytest                # run the test suite
bash scripts/install-hooks.sh   # install the pre-commit hook (required after a fresh clone)
```

## Documents

- [PRD.md](PRD.md) — product requirements, execution phases, and definitions of done
- [TODO.md](TODO.md) — phase-by-phase task tracker
- [docs/adr/](docs/adr/) — architecture decision records (ADR-001 leakage protocol onward)

## Notes

Estimates reflect **external-review-stage likelihood only** — these cases already survived internal appeal. Drafts are for professional review, not legal or medical advice. See ADR-001 for the full leakage and selection-bias protocol.

Raw and modified DMHC data is **not redistributed** — see PRD §4. Code is Apache-2.0 ([LICENSE](LICENSE)).

*This README is a Phase 0 stub; the full version is written in Phase 8.*
