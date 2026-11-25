# Ops 7: A missed nightly run is noticed

Status: in-progress
Date: 2026-11-25
Scope: ordinary code story (CI configuration and a stdlib script; no figure changes)

## Why

`pipeline.yml` is scheduled for 10:00 UTC daily. Its scheduled trigger has never
fired: the only run in its history was the manual one of 2026-11-24, so AAPL, NVDA,
KO and MSFT (merged in #163 for "the next nightly") were not in production until a
hand-triggered run on 2026-11-25 at 13:37 UTC. Nothing reported the missing run. A
pipeline that FAILS exits non-zero and GitHub emails about it. A pipeline that never
STARTS produces no signal at all.

It matters beyond stale scores: per `pipeline.yml`'s own header, the nightly write is
what keeps the free Supabase project from auto-pausing after a week idle, the cause
of the 2026-11 outage.

GitHub documents that scheduled runs can be delayed or dropped under load, and most
often at the top of the hour, which is exactly where `0 10 * * *` sits.

## Acceptance criteria

1. A scheduled watchdog workflow fails when the newest SUCCESSFUL `pipeline.yml`
   run finished more than 26 hours ago, or when there is none. A failing scheduled
   run is GitHub's own email to Lawrence (the owner chose this channel 2026-11-25),
   with no new service and no new secret.
2. The decision is a pure function with tests on both sides of the boundary, a
   positive control (a fresh success passes), and the cases a naive check gets
   wrong: a newer FAILED or in-progress run must not count as fresh.
3. The watchdog runs twice a day, off the top of the hour, so a single dropped
   watchdog run does not silence it.
4. The nightly moves off the top of the hour (`23 10 * * *`), GitHub's documented
   high-load slot.
5. The failure message says what to do: run `pipeline.yml` by hand.

## Tasks

- [x] `scripts/pipeline_watchdog.py`: `check(runs, now, max_age_hours)` + CLI (AC 1, 2, 5)
- [x] `backend/tests/test_pipeline_watchdog.py` (AC 2). Mutation check: counting
      every run instead of only completed successes fails the failed-run and
      in-progress-run tests.
- [x] `.github/workflows/pipeline-watchdog.yml` (AC 1, 3)
- [x] `pipeline.yml` cron to `23 10 * * *` (AC 4)
- [x] Real run history: `OK ... 0.5h ago` (exit 0) now; `STALE ... 74.6h ago` (exit 1)
      with `--now` three days ahead
- [x] `make test` 725 passed; lint clean (including the new script)

## Detection time (measured, not assumed)

A missed scheduled run is caught the SAME afternoon: the last good run is
yesterday's ~10:30, so the 16:17 slot sees ~30h. The actual 2026-11-25 incident
would have been caught one slot later, at 04:17 on 11-26: its last success was a
manual run at 15:52 on 11-24, only 24.4h old at 16:17 on 11-25. The first draft
of the test assumed same-day detection for that case and failed, which is how this
was found; both shapes are now tested.
- [ ] PR; after merge, trigger the watchdog once by hand to prove it runs in Actions

## Known limit

The watchdog is itself a scheduled workflow, so GitHub could drop it too. Two slots a
day make a silent day unlikely rather than impossible. An external pinger would close
that gap at the cost of a new service. Not taken: recorded here, not built.
