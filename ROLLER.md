# ROLLER — rolling backlog

Append-only. Nothing lands here without a yes said out loud by the owner — no teammate
spawns work off this file on its own, items are pulled deliberately. IDs are `R-nn`,
sequential, never reused. Every item is one-for-one with an `OQ.md` ruling,
cross-referenced both ways: `OQ: <section> — "<first words of the title>"` here,
`ROLLER: R-nn` there. An item with no OQ behind it is work nobody ruled on; an OQ ruling
with code in it and no item here is work nobody will do. Tick an item when the change is
in the tree and green — `Landed:` names the commit by subject before it exists and by
hash after, blank is not honest. Gate is per session: a session's own open items stop
its commits (`grep -nE '^\s*- \[ \] \[s:<tag>\]' OQ.md ROLLER.md` must print nothing),
everyone else's are theirs. The queue is never empty, and that's fine.

---

- [x] [s:53ce5611] R-01 — Fold ADRs, build logs, the Phase 1 HLD and its OQ file into OQ.md and ROLLER.md; re-point PRD.md, TODO.md, README.md, docs/data-card.md and CLAUDE.md. OQ: Process — "Decision-tracking model". Landed: 1dd64c9 (`refactor : fold adrs oqs hld and logs into oq and roller ledgers`)
- [x] [s:53ce5611] R-02 — Terms follow-up: one control-page check on the CHHS portal to establish whether the OPA click-through modal is portal-wide boilerplate or specific to the DMHC IMR dataset (optionally an email to DMHC for a written read); record the finding and the ruled posture in `docs/data-card.md`'s terms section. OQ: Phase 1 — "Terms posture". Landed: 691241c (`update : data card terms posture from oq-1.1`)
- [x] [s:53ce5611] R-03 — PRD §12 taxonomy-drift row: refine "normalization map built in Phase 1 EDA; versioned" to a legacy→new crosswalk canonicalizing to the 2026 ICD-10-chapter vocabulary at category level, raw labels preserved. OQ: Phase 1 — "Category crosswalk". Landed: 5ef12a2 (`update : prd defaults from phase 1 rulings`)
- [x] [s:53ce5611] R-04 — PRD §4: note that "actively updated" upstream means v1 builds against one pinned, sha256-identified snapshot and refresh is an explicit, deliberate act, never automatic. OQ: Phase 1 — "Snapshot policy". Landed: 5ef12a2 (`update : prd defaults from phase 1 rulings`)
- [x] [s:53ce5611] R-05 — PRD §5 application note: the corpus carries three undocumented fields; `days_to_review`/`days_to_adopt` are post-decision and never prediction inputs, `imr_type` is filing-time and prediction-eligible (nuance in the model card). OQ: Phase 1 — "Leakage-protocol classification". Landed: 5ef12a2 (`update : prd defaults from phase 1 rulings`)
- [x] [s:53ce5611] R-06 — PRD §9 Phase 1: "EDA notebook exported to `docs/evals/eda.md`" → a tested EDA module (`profile.py`) rendering `docs/evals/eda.md` deterministically from the parquet; no notebook. OQ: Phase 1 — "EDA vehicle". Landed: 5ef12a2 (`update : prd defaults from phase 1 rulings`)
- [x] [s:53ce5611] R-07 — PRD §8 `tests/` comment: "fixtures with small synthetic/excerpt samples" → synthetic fixtures only, generated from the schema contract; no real rows committed. OQ: Phase 1 — "Fixtures". Landed: 5ef12a2 (`update : prd defaults from phase 1 rulings`)
- [x] [s:53ce5611] R-08 — PRD §9 Phase 5: replace "(working proposal: train ≤ 2021, test 2022+)" with the ruled, frozen cutoff — train ≤2021 / test 2022–2025, 2001 and 2026 excluded — citing OQ-1.5 and `docs/evals/eda.md`. OQ: Phase 1 — "Temporal cutoff". Landed: cf7b887 (`update : prd phase 5 cutoff year from oq-1.5`)
- [x] [s:53ce5611] R-09 — Crosswalk: move the nine ruled mappings from `uncertain` to `aliases` in `category_crosswalk_v1.yaml` with a design-trace header comment; update `tests/test_normalize.py`; re-run `make ingest` + `make eda`; update `docs/data-card.md` counts, add the crosswalk design trace and the OQ-1.13 revisit note. OQ: Phase 1 — "Crosswalk". Landed: 3fabd9e (`add : category crosswalk and quality flags`) + c89aeb8 (data card, `add : eda profile report and data card`)
