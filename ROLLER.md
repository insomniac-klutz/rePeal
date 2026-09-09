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

- [x] [s:53ce5611] R-01 — Fold ADRs, build logs, the Phase 1 HLD and its OQ file into OQ.md and ROLLER.md; re-point PRD.md, TODO.md, README.md, docs/data-card.md and CLAUDE.md. OQ: Process — "Decision-tracking model". Landed: `refactor : fold adrs oqs hld and logs into oq and roller ledgers`
