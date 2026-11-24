# Ops 2: "What changed" pivots on the latest FILED filing

Status: review
Date: 2026-11-24
Scope: a figure rendered to a user, so the live-data definition of done applies

## Why

SHOP's live report said "Compared against Aug 15, 2026 (before filing
0001594805-17-000007)", presenting a 2017 10-K as the latest filing. The pivot was
the most recently STORED filing, and an Inline XBRL backfill had stored old
filings. In production, 7 of 9 filers were affected (CP 2013, ZTS 2015, SHOP 2017,
QSR 2021, CCJ 2022, SU 2022, BCE 2025). Recorded in
`engineering-findings.yaml: ops_2_latest_filing_pivot_followed_storage_time`.

## Acceptance criteria

1. The default pivot is the filer's most recently filed filing (`filing_date`),
   ties broken by storage time.
2. The pivot instant is still that filing's `created_at`.
3. A backfilled older filing stored after the latest one cannot become the pivot.
4. The "What changed" section and the provenance footer name the same latest filing.

## Tasks

- [x] `diff.engine.latest_filing_pivot`: order by `filing_date desc, created_at desc` (AC 1-3)
- [x] Regression test `test_a_backfilled_old_filing_does_not_become_the_latest`,
      confirmed to FAIL on the old ordering (AC 3)
- [x] Full backend suite: 680 passed; ruff clean
- [x] Live-data check: local API, all 9 filers pivot on their 2025-26 filing (AC 1, 4)
- [x] Rendered SHOP, ZTS, CP (no prior state) and OTEX (has changes)
- [x] Finding recorded; deferred follow-up recorded as
      `changes_since_pivot_include_backfill_rescoring` (open)

## Verification

| Filer | Pivot before | Pivot after | Rendered |
|---|---|---|---|
| SHOP | 0001594805-17-000007 (2017) | 0001594805-26-000011 | "No earlier record to compare against yet" |
| CP | 2013 filing | 0001193125-26-173665 | same |
| ZTS | 2015 filing | 0001555280-26-000011 | same |
| OTEX | 0001002638-26-000068 | unchanged | compares against its FY2026 10-K |

"No earlier record" is the truthful state for filers whose whole history was
loaded in one batch: no stored state predates their latest filing.

## Deferred (rule 3: ship the fix, defer the finding)

OTEX's change list includes FY2006-2009 rows caused by a same-day backfill, not by
the filing. Real stored changes, not this story's ACs; see
`changes_since_pivot_include_backfill_rescoring`.
