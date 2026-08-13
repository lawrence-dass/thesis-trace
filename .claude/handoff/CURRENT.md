# Handover — 2026-08-13 | Claude Opus 5

## Mode
Between epics. Epic 6 complete (7 of 7), its retrospective done, and the AD-1
post-epic fix is built and in review. **The next move is Lawrence's, not an agent's.**

## Focus
- **Task**: none in flight for an agent. The board is gated on a decision packet.
- **Branch**: `claude/epic-6-retro-and-handover-fix-2026-08-13`
- **Open PR**: **#69** — persist the reverse DCF (AD-1). CI green, mergeable,
  deliberately NOT merged: it is waiting on the Codex review handoff.

## ⚠️ Correction — Epic 7 is NOT unblocked
Two earlier handovers said "Nothing blocks Epic 7". **That was wrong**, and a session
acting on it would have planned an epic the roadmap forbids selecting. `epic_catalog`
records Epic 7 as `decomposition: deferred`, `deferred_under: D9`, with:

> `decompose_when`: The increment before it has produced its own decision packet
> (D10) and this epic is what that packet's single largest research failure selects.

Epics 8 and 9 are gated the same way. **D9 forbids choosing the next epic from list
order** — it must be selected by the largest research failure observed in a real
decision packet. Do not decompose any of them from the FR alone.

## The one thing blocking everything
`_bmad-output/decision-packets/` contains `TEMPLATE.md` and no packets.

A decision packet (D10) is **the same condition as D3.2** — "ThesisTrace informs at
least one real investment decision by user zero". From `foundational-decisions.md:189`:
*"D3.2 never closed, so Phase 1 has never met its own success definition and Epic 5
shipped on top of a half-met Phase 1."* One packet closes D3.2 **and** unblocks D9's
selection — they are not two pieces of work.

It requires a real hold/sell/pass/size judgment on real money, written *before*
opening the app. An agent cannot produce this, and a synthetic one would invert the
ordering D9 exists to protect. Note the falsifiability clause: a packet with **no**
blocking gap is still a valid finding — it would mean D9's roadmap is not
evidence-led and the epic list should be re-derived from scratch.

## Resume Point
Nothing to resume. If Lawrence has written a packet, read it and let its single
named research failure select the next epic. If not, the useful agent work is the
hygiene list below — none of it advances the roadmap.

## Uncommitted Files
None.

## What Happened This Session
- **PR #69 — persisted the reverse DCF (AD-1).** The read path was solving the whole
  DCF plus all 35 sensitivity cells on every page load. Now: two tables
  (`reverse_dcf_runs` + `reverse_dcf_cells`), migration `b43d7bd6fe33`,
  `backend/valuation/store.py`, a stage in `run_issuer`, and `repository.py:287`
  reading the stored row. Suite 313 → 323, CI green.
- **Epic 6 retrospective run** — 9 durable learnings appended to `project-context.md`.
- **PR #68 merged** (the previous session's handover) and its stale worktree removed.

## Decisions Made
- **Two tables, not one** (the scope sketch said one). Grid cells are their own table
  because a growth rate is a financial figure and AD-15 requires NUMERIC, and because
  "meaning parked in a blob" is this repo's most repeated failure. Mirrors
  `score_runs`/`score_results`.
- **Rate columns are `NUMERIC(18,10)`, not `NUMERIC(28,6)`.** The solver's tolerance
  is 1e-7, so a money-shaped column would round the answer coarser than the bisection
  that produced it.
- **The upsert also deletes other fiscal years** for the issuer/spec. The solver picks
  the year and a later run can pick an earlier one; the upsert alone would strand the
  stale newer row, and the read takes the latest stored year.

## Context Needed
- **DB tests need `TEST_DATABASE_URL` EXPORTED** — conftest reads `os.environ` only,
  not `.env`, so they skip silently (219 passed instead of 323).
- `test_health_db_503_when_unconfigured` fails locally and is NOT a regression: the
  gitignored root `.env` is read by pydantic below the env layer; CI has no `.env`.
- **The dev DB has been migrated and materialized by hand.** `reverse_dcf_runs` and
  `reverse_dcf_cells` exist and hold all 7 filers. If you check out `main` without
  PR #69, those tables sit unread — harmless, but that is why they are there.
- A company page now shows **no reverse DCF until the pipeline has run** for that
  issuer. Correct CQRS behaviour, asserted deliberately. Plan a post-deploy run.

## Open, none of it blocking
- `post_epic_work` is **empty** — PR #69 closed the last item.
- Track P: the overview N+1 (484 queries for OTEX). Now pinned by
  `test_overview_query_count.py`, so it cannot drift while it waits. Batching it is
  real work but optimizes a product nobody has used for a real decision yet.
- The market-price date backfill — inert until it runs.
- **There is no frontend test runner at all** — `devDependencies` has eslint and tsc
  but no test framework, and CI's frontend job is lint + build only.

## Next Action
**Lawrence: write the first decision packet** using
`_bmad-output/decision-packets/TEMPLATE.md`. One company, one real question, written
before opening the app. That closes D3.2 and selects the next epic.

Agent work available meanwhile, in rough value order: hand over the Codex review for
PR #69; add a frontend test runner; the market-price backfill; Track P batching.

## References
- `_bmad-output/planning-artifacts/foundational-decisions.md` — **D10** (what a packet
  is, lines 171+) and **D3.2**; D9's binding selection criterion
- `_bmad-output/decision-packets/TEMPLATE.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `epic_catalog`,
  `post_epic_work`, `story_6_5_open_deviations`
- `.claude/context/project-context.md` — Epic 6 learnings appended 2026-08-13

---
*Generated 2026-08-13 after the Epic 6 retrospective. PR #69 open and unmerged.*
